from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path

import pytest

import hlf_mcp.hlf.stdlib as stdlib_pkg
from hlf_mcp.hlf.stdlib import crypto_mod, io_mod, math_mod, net_mod, string_mod, system_mod


EXPECTED_STDLIB_MODULES = {
    "agent",
    "collections_mod",
    "crypto_mod",
    "io_mod",
    "math_mod",
    "net_mod",
    "string_mod",
    "system_mod",
}


def test_stdlib_module_inventory_matches_packaged_surface() -> None:
    discovered = {module.name for module in pkgutil.iter_modules(stdlib_pkg.__path__) if not module.name.startswith("__")}
    assert discovered == EXPECTED_STDLIB_MODULES


@pytest.mark.parametrize("module_name", sorted(EXPECTED_STDLIB_MODULES))
def test_stdlib_modules_are_importable(module_name: str) -> None:
    module = importlib.import_module(f"{stdlib_pkg.__name__}.{module_name}")
    assert module is not None


def test_math_and_string_modules_expose_expected_behavior() -> None:
    assert math_mod.MATH_ABS(-7) == 7
    assert math_mod.MATH_MAX(3, 9) == 9
    assert string_mod.STRING_UPPER("hello") == "HELLO"
    assert string_mod.STRING_JOIN(["a", "b"], ":") == "a:b"


def test_crypto_module_supports_hash_sign_and_encrypt_roundtrip() -> None:
    key = crypto_mod.KEY_GENERATE()
    digest = crypto_mod.HASH("hello")
    signature = crypto_mod.SIGN("hello", "shared-secret")
    ciphertext = crypto_mod.ENCRYPT("hello", key)

    assert len(key) == 64
    assert crypto_mod.HASH_VERIFY("hello", digest) is True
    assert crypto_mod.SIGN_VERIFY("hello", signature, "shared-secret") is True
    assert crypto_mod.DECRYPT(ciphertext, key) == "hello"


def test_io_module_rejects_paths_outside_acfs_roots(tmp_path: Path) -> None:
    with pytest.raises(PermissionError, match="ACFS confinement"):
        io_mod.FILE_WRITE(str(tmp_path / "blocked.txt"), "hello")


def test_io_path_helpers_are_available() -> None:
    joined = io_mod.PATH_JOIN("alpha", "beta", "file.txt")
    assert joined.endswith(str(Path("alpha") / "beta" / "file.txt"))
    assert io_mod.PATH_BASENAME(joined) == "file.txt"
    assert io_mod.PATH_DIRNAME(joined).endswith(str(Path("alpha") / "beta"))


def test_net_module_blocks_ssrf_targets_and_encodes_queries() -> None:
    with pytest.raises(PermissionError, match="blocked"):
        net_mod.HTTP_GET("http://169.254.169.254/latest/meta-data")

    query = net_mod.URL_ENCODE({"q": "hlf", "page": 1})
    decoded = net_mod.URL_DECODE(query)
    assert decoded == {"q": "hlf", "page": "1"}


def test_system_module_reports_basic_runtime_state() -> None:
    assert system_mod.SYS_OS()
    assert system_mod.SYS_ARCH()
    assert system_mod.SYS_CWD()
    assert system_mod.SYS_SETENV("HLF_TEST_ENV", "ok") is True
    assert system_mod.SYS_ENV("HLF_TEST_ENV") == "ok"
    assert isinstance(system_mod.SYS_TIME(), int)