"""SSRF protection for URL ingestion."""

import ipaddress
import socket
from urllib.parse import urlparse

from agent_memory.log import get_logger

logger = get_logger(__name__)

# Private/reserved IP ranges that should never be fetched
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),     # Link-local
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("::1/128"),             # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),            # IPv6 private
    ipaddress.ip_network("fe80::/10"),           # IPv6 link-local
]

# Cloud metadata endpoints
_BLOCKED_HOSTS = {
    "metadata.google.internal",
    "metadata.google.com",
}

_ALLOWED_SCHEMES = {"http", "https"}


class SSRFError(Exception):
    """Raised when a URL fails SSRF validation."""


def validate_url(url: str) -> str:
    """Validate a URL against SSRF risks.

    Args:
        url: The URL to validate.

    Returns:
        The validated URL (unchanged).

    Raises:
        SSRFError: If the URL targets a private/blocked resource.
    """
    parsed = urlparse(url)

    # Check scheme
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise SSRFError(f"Blocked scheme: {parsed.scheme}. Only HTTP(S) allowed.")

    # Check hostname
    hostname = parsed.hostname
    if not hostname:
        raise SSRFError("URL has no hostname.")

    # Check blocked hostnames
    if hostname.lower() in _BLOCKED_HOSTS:
        raise SSRFError(f"Blocked host: {hostname}")

    # Resolve hostname and check IP
    try:
        addr_infos = socket.getaddrinfo(hostname, parsed.port or 80)
    except socket.gaierror:
        raise SSRFError(f"Cannot resolve hostname: {hostname}")

    for _, _, _, _, sockaddr in addr_infos:
        ip_str = sockaddr[0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue

        for network in _BLOCKED_NETWORKS:
            if ip in network:
                raise SSRFError(
                    f"Blocked: {hostname} resolves to private IP {ip_str}"
                )

    logger.debug("URL passed SSRF validation", url=url)
    return url
