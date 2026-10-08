"""Single-process ownership of local persistent stores."""

from contextlib import ExitStack, contextmanager
from pathlib import Path


@contextmanager
def store_lock(metadata_path: Path, chroma_path: Path):
    paths = sorted({metadata_path.resolve().with_suffix(".lock"),
                    chroma_path.resolve().parent / (chroma_path.name + ".lock")})
    with ExitStack() as stack:
        for path in paths:
            path.parent.mkdir(parents=True, exist_ok=True)
            handle = stack.enter_context(path.open("a+b"))
            handle.seek(0, 2)
            if handle.tell() == 0:
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            try:
                import sys
                if sys.platform == "win32":
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise RuntimeError(f"Another Agent Memory process is using this store: {path}") from exc
        yield