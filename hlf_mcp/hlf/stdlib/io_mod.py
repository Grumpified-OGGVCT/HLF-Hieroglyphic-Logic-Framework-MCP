"""HLF stdlib: io module — file I/O with ACFS path validation."""

from pathlib import Path

_ALLOWED_ROOTS = [
    Path.home() / ".hlf" / "workspace",
    Path("/tmp/hlf"),
    Path("hlf"),
]


def _validate_path(p: str) -> Path:
    path = Path(p).resolve()
    for root in _ALLOWED_ROOTS:
        try:
            path.relative_to(root.resolve())
            return path
        except ValueError:
            continue
    raise PermissionError(f"ACFS confinement: path denied: {p}")


def FILE_READ(path: str) -> str:
    p = _validate_path(path)
    return p.read_text(encoding="utf-8")


def FILE_WRITE(path: str, data: str) -> bool:
    p = _validate_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(data, encoding="utf-8")
    return True


def FILE_EXISTS(path: str) -> bool:
    try:
        p = _validate_path(path)
        return p.exists()
    except PermissionError:
        return False


def FILE_DELETE(path: str) -> bool:
    p = _validate_path(path)
    p.unlink(missing_ok=True)
    return True


def DIR_LIST(path: str) -> list[str]:
    p = _validate_path(path)
    return [str(f) for f in p.iterdir()] if p.is_dir() else []


def DIR_CREATE(path: str) -> bool:
    p = _validate_path(path)
    p.mkdir(parents=True, exist_ok=True)
    return True


def PATH_JOIN(*parts: str) -> str:
    return str(Path(*parts))


def PATH_BASENAME(path: str) -> str:
    return Path(path).name


def PATH_DIRNAME(path: str) -> str:
    return str(Path(path).parent)
