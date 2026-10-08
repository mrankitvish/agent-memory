"""Local memory browser and API sharing the MCP engine."""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, StringConstraints
from starlette.middleware.trustedhost import TrustedHostMiddleware

from agent_memory.engine.rag_engine import RAGEngine
from agent_memory.memory_models import MemoryType
from agent_memory.models import SourceType

Namespace = Annotated[str, StringConstraints(
    pattern=r"^[A-Za-z0-9](?:[A-Za-z0-9_-]{0,58}[A-Za-z0-9])?$",
)]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100_000)]


class MemoryInput(BaseModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    content: Text
    namespace: Namespace = "default"
    memory_type: MemoryType = MemoryType.SEMANTIC
    tags: list[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]] = Field(default_factory=list, max_length=20)


def same_origin(request: Request):
    origin = request.headers.get("origin")
    if origin and origin != str(request.base_url).rstrip("/"):
        raise HTTPException(403, "Cross-origin access is not allowed.")
    if request.headers.get("sec-fetch-site") == "cross-site":
        raise HTTPException(403, "Cross-site access is not allowed.")
    if request.method in {"POST", "PUT", "DELETE"}:
        if request.headers.get("x-memory-client") != "local-ui":
            raise HTTPException(403, "Missing local client header.")


def create_app(engine: RAGEngine, with_mcp: bool = True) -> FastAPI:
    http_mcp = sse_mcp = None
    if with_mcp:
        from agent_memory.mcp.server import create_mcp_server
        mcp = create_mcp_server(engine)
        http_mcp = mcp.http_app(transport="streamable-http", path="/")
        sse_mcp = mcp.http_app(transport="sse")

    @asynccontextmanager
    async def lifespan(app):
        if http_mcp is not None and sse_mcp is not None:
            async with http_mcp.lifespan(app), sse_mcp.lifespan(app):
                yield
        else:
            yield

    app = FastAPI(title="Agent Memory", lifespan=lifespan)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]", "testserver"])
    api = APIRouter(prefix="/api", dependencies=[Depends(same_origin)])

    @api.get("/status")
    def status():
        with engine.lock:
            return {"status": "ready", "namespaces": engine.metadata_store.namespaces(),
                    "total": engine.metadata_store.browse(limit=0)["total"],
                    "embedding_dimensions": engine.embedder.dimension}

    @api.get("/memories")
    def memories(namespace: str | None = None, memory_type: MemoryType | None = None,
                 query: str = "", limit: int = Query(50, ge=1, le=200),
                 offset: int = Query(0, ge=0)):
        with engine.lock:
            return engine.metadata_store.browse(namespace, memory_type, query, limit, offset)

    @api.get("/search")
    def search(query: str = Query(min_length=1, max_length=2000),
               namespace: Namespace = "default", top_k: int = Query(20, ge=1, le=100),
               memory_type: MemoryType | None = None):
        with engine.lock:
            results = engine.search(query, namespace, top_k)
            seen, items = set(), []
            for match in results:
                doc = engine.get_document(match.document_id)
                if doc and doc.id not in seen and (not memory_type or doc.memory_type == memory_type):
                    seen.add(doc.id)
                    items.append({**doc.model_dump(mode="json"), "score": match.score})
            return {"items": items, "total": len(items)}

    @api.get("/graph")
    def graph(namespace: str | None = None, memory_type: MemoryType | None = None, query: str = ""):
        with engine.lock:
            result = engine.metadata_store.browse(namespace, memory_type, query, 300)
            documents = result["items"]
            nodes = [{"id": doc.id, "title": doc.title, "namespace": doc.namespace,
                      "memory_type": doc.memory_type, "tags": doc.tags} for doc in documents]
            links = []
            for index, source in enumerate(documents):
                for target in documents[index + 1:]:
                    shared = sorted(set(source.tags) & set(target.tags))
                    if shared and source.namespace == target.namespace:
                        links.append({"source": source.id, "target": target.id, "tags": shared})
            return {"nodes": nodes, "links": links[:3000], "total": result["total"],
                    "truncated": result["total"] > len(nodes) or len(links) > 3000,
                    "relationship": "shared_tags"}

    @api.get("/memories/{memory_id}")
    def detail(memory_id: str):
        with engine.lock:
            doc = engine.get_document(memory_id)
            if doc is None:
                raise HTTPException(404, "Memory not found.")
            result = doc.model_dump(mode="json")
            result["chunks"] = engine.metadata_store.get_chunks_by_document(memory_id)
            result["original_available"] = bool(doc.content)
            return result

    def save(payload: MemoryInput, memory_id: str | None = None):
        with engine.lock:
            if memory_id and engine.get_document(memory_id) is None:
                raise HTTPException(404, "Memory not found.")
            try:
                result = engine.ingest(
                    payload.content, SourceType.TEXT, payload.title, payload.namespace,
                    tags=list(dict.fromkeys(payload.tags)), memory_type=payload.memory_type,
                    memory_id=memory_id,
                )
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc
            return detail(result.document_id)

    @api.post("/memories", status_code=201)
    def create(payload: MemoryInput):
        return save(payload)

    @api.put("/memories/{memory_id}")
    def update(memory_id: str, payload: MemoryInput):
        return save(payload, memory_id)

    @api.delete("/memories/{memory_id}", status_code=204)
    def delete(memory_id: str):
        if not engine.delete_document(memory_id):
            raise HTTPException(404, "Memory not found.")

    app.include_router(api)
    ui_dir = Path(__file__).parent / "ui"

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(ui_dir / "index.html", headers={"Cache-Control": "no-store"})

    app.mount("/ui", StaticFiles(directory=ui_dir, check_dir=False), name="ui")
    if http_mcp is not None and sse_mcp is not None:
        @app.api_route("/mcp", methods=["GET", "POST", "DELETE"], include_in_schema=False)
        def redirect_mcp():
            return RedirectResponse("/mcp/", status_code=307)

        app.mount("/mcp", http_mcp)
        app.mount("/", sse_mcp)
    return app