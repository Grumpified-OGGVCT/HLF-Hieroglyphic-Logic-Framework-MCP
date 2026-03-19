"""HLF stdlib: net module — HTTP helpers."""

import ipaddress
import urllib.parse
import urllib.request

# ── SSRF protection ───────────────────────────────────────────────────────────
_BLOCKED_SCHEMES = frozenset({"file", "ftp", "gopher", "data", "ldap", "ldaps"})
_BLOCKED_HOSTS = frozenset(
    {
        "169.254.169.254",  # AWS / GCP / Azure IMDS
        "metadata.google.internal",
        "metadata.google",
        "fd00:ec2::254",  # AWS IPv6 IMDS
    }
)


def _validate_url(url: str) -> None:
    """Raise PermissionError if the URL targets a blocked scheme or address.

    Blocks:
    - Non-HTTP(S) schemes (file://, ftp://, gopher://, …)
    - Cloud instance metadata endpoints
    - RFC-1918 private ranges, loopback, and link-local addresses
    """
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception as exc:
        raise PermissionError(f"SSRF guard: malformed URL: {url!r}") from exc

    scheme = (parsed.scheme or "").lower()
    if scheme not in ("http", "https"):
        raise PermissionError(f"SSRF guard: scheme '{scheme}' is not allowed")

    host = (parsed.hostname or "").lower().strip("[]")
    if not host:
        raise PermissionError("SSRF guard: URL has no host")

    if host in _BLOCKED_HOSTS:
        raise PermissionError(f"SSRF guard: host '{host}' is blocked (IMDS/metadata)")

    # Resolve bare IP addresses — skip DNS names (not resolved at this layer)
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        return  # hostname — allow (DNS not checked here)

    if addr.is_loopback:
        raise PermissionError(f"SSRF guard: loopback address blocked: {host}")
    if addr.is_private:
        raise PermissionError(f"SSRF guard: private address blocked: {host}")
    if addr.is_link_local:
        raise PermissionError(f"SSRF guard: link-local address blocked: {host}")
    if addr.is_multicast:
        raise PermissionError(f"SSRF guard: multicast address blocked: {host}")


def HTTP_GET(url: str) -> str:
    _validate_url(url)
    with urllib.request.urlopen(url, timeout=30) as r:  # noqa: S310
        return r.read().decode("utf-8")


def HTTP_POST(url: str, body: str) -> str:
    _validate_url(url)
    data = body.encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310
        return r.read().decode("utf-8")


def HTTP_PUT(url: str, body: str) -> str:
    _validate_url(url)
    data = body.encode("utf-8")
    req = urllib.request.Request(url, data=data, method="PUT")
    with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310
        return r.read().decode("utf-8")


def HTTP_DELETE(url: str) -> str:
    _validate_url(url)
    req = urllib.request.Request(url, method="DELETE")
    with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310
        return r.read().decode("utf-8")


def URL_ENCODE(params: dict) -> str:
    return urllib.parse.urlencode(params)


def URL_DECODE(query: str) -> dict:
    return dict(urllib.parse.parse_qsl(query))
