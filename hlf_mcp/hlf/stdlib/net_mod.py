"""HLF stdlib: net module — HTTP helpers."""
import urllib.parse, urllib.request

def HTTP_GET(url: str) -> str:
    with urllib.request.urlopen(url, timeout=30) as r:  # noqa: S310
        return r.read().decode("utf-8")

def HTTP_POST(url: str, body: str) -> str:
    data = body.encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310
        return r.read().decode("utf-8")

def HTTP_PUT(url: str, body: str) -> str:
    data = body.encode("utf-8")
    req = urllib.request.Request(url, data=data, method="PUT")
    with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310
        return r.read().decode("utf-8")

def HTTP_DELETE(url: str) -> str:
    req = urllib.request.Request(url, method="DELETE")
    with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310
        return r.read().decode("utf-8")

def URL_ENCODE(params: dict) -> str:
    return urllib.parse.urlencode(params)

def URL_DECODE(query: str) -> dict:
    return dict(urllib.parse.parse_qsl(query))
