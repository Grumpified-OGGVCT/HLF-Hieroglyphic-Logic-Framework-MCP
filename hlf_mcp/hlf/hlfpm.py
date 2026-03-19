"""
HLF Package Manager (hlfpm) — OCI-based module install, update, freeze, search.

Usage:
  uv run hlfpm install math@v1.0.0
  uv run hlfpm list
  uv run hlfpm freeze
  uv run hlfpm search collections
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from hlf_mcp.hlf.oci_client import OCIClient, OCIError, OCIModuleRef


class HlfPmError(Exception):
    pass


LOCKFILE_SCHEMA = {
    "version": "string",
    "packages": [{"name": "string", "ref": "string", "sha256": "string", "size": "integer"}],
}

DEFAULT_INSTALL_ROOT = Path("hlf") / "modules"
DEFAULT_LOCKFILE = Path("hlf.lock.json")


class HlfPackageManager:
    """HLF Package Manager."""

    def __init__(
        self,
        install_root: Path | None = None,
        lockfile: Path | None = None,
        oci_client: OCIClient | None = None,
    ):
        self.install_root = install_root or DEFAULT_INSTALL_ROOT
        self.lockfile_path = lockfile or DEFAULT_LOCKFILE
        self.oci_client = oci_client or OCIClient()
        self.install_root.mkdir(parents=True, exist_ok=True)

    def install(self, package_ref: str) -> dict[str, Any]:
        ref = OCIModuleRef.parse(package_ref)
        target_path = self.install_root / ref.module
        if target_path.exists():
            return {"status": "already_installed", "package": str(ref), "path": str(target_path)}
        try:
            module_path = self.oci_client.pull(ref)
        except OCIError:
            # Offline: create a stub module
            target_path.mkdir(parents=True, exist_ok=True)
            stub_meta = {"name": ref.module, "version": ref.tag, "ref": str(ref), "status": "stub"}
            (target_path / "module.json").write_text(json.dumps(stub_meta, indent=2))
            return {"status": "stub_installed", "package": str(ref), "path": str(target_path)}
        # Validate checksum
        expected = self.oci_client.get_checksum(ref)
        actual = self._compute_checksum(module_path)
        if expected and actual != expected:
            raise HlfPmError(
                f"Checksum mismatch for {package_ref}: expected={expected[:16]}... actual={actual[:16]}..."
            )
        shutil.copytree(str(module_path), str(target_path), dirs_exist_ok=True)
        return {
            "status": "installed",
            "package": str(ref),
            "path": str(target_path),
            "sha256": actual[:16] + "...",
        }

    def uninstall(self, package_name: str) -> dict[str, Any]:
        module_path = self.install_root / package_name
        if not module_path.exists():
            raise HlfPmError(f"Package not installed: {package_name}")
        shutil.rmtree(module_path)
        return {"status": "uninstalled", "package": package_name}

    def list_installed(self) -> list[dict[str, Any]]:
        packages = []
        if not self.install_root.exists():
            return packages
        for module_dir in sorted(self.install_root.iterdir()):
            if not module_dir.is_dir():
                continue
            meta_file = module_dir / "module.json"
            if meta_file.exists():
                try:
                    meta = json.loads(meta_file.read_text())
                    meta["path"] = str(module_dir)
                    packages.append(meta)
                    continue
                except Exception:
                    pass
            packages.append(
                {
                    "name": module_dir.name,
                    "path": str(module_dir),
                    "status": "unknown",
                    "sha256": self._compute_checksum(module_dir)[:16] + "...",
                }
            )
        return packages

    def search(self, query: str) -> list[dict[str, Any]]:
        tags = self.oci_client.list_tags(f"library/{query}")
        return [
            {"name": query, "ref": f"registry.hlf.io/library/{query}:{t}", "tag": t}
            for t in tags[:20]
        ]

    def freeze(self) -> dict[str, Any]:
        packages = []
        for pkg in self.list_installed():
            path = Path(pkg["path"])
            packages.append(
                {
                    "name": pkg["name"],
                    "ref": pkg.get("ref", f"registry.hlf.io/library/{pkg['name']}:unknown"),
                    "sha256": self._compute_checksum(path),
                    "size": sum(f.stat().st_size for f in path.rglob("*") if f.is_file()),
                }
            )
        lockfile = {"version": "1.0", "packages": packages}
        self.lockfile_path.write_text(json.dumps(lockfile, indent=2))
        return lockfile

    def update(self, package_name: str) -> dict[str, Any]:
        module_path = self.install_root / package_name
        if not module_path.exists():
            return self.install(package_name)
        shutil.rmtree(module_path)
        return self.install(package_name)

    def _compute_checksum(self, path: Path) -> str:
        h = hashlib.sha256()
        if path.is_file():
            h.update(path.read_bytes())
        elif path.is_dir():
            for f in sorted(path.rglob("*")):
                if f.is_file():
                    h.update(f.name.encode())
                    h.update(f.read_bytes())
        return h.hexdigest()


def main() -> None:
    """CLI: hlfpm <command> [args]"""
    import argparse

    parser = argparse.ArgumentParser(prog="hlfpm", description="HLF Package Manager")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("list")
    inst = sub.add_parser("install")
    inst.add_argument("package")
    uninst = sub.add_parser("uninstall")
    uninst.add_argument("package")
    srch = sub.add_parser("search")
    srch.add_argument("query")
    sub.add_parser("freeze")
    upd = sub.add_parser("update")
    upd.add_argument("package")
    args = parser.parse_args()
    pm = HlfPackageManager()

    if args.command == "list":
        pkgs = pm.list_installed()
        if pkgs:
            for package in pkgs:
                print(f"  {package['name']}  {package.get('status', '?')}")
        else:
            print("  (no packages installed)")
    elif args.command == "install":
        result = pm.install(args.package)
        print(f"  {result['status']}: {result['package']}")
    elif args.command == "uninstall":
        result = pm.uninstall(args.package)
        print(f"  {result['status']}: {result['package']}")
    elif args.command == "search":
        results = pm.search(args.query)
        for result in results:
            print(f"  {result['name']}:{result['tag']}")
    elif args.command == "freeze":
        lockfile = pm.freeze()
        print(f"  Lockfile written: {len(lockfile['packages'])} packages")
    elif args.command == "update":
        result = pm.update(args.package)
        print(f"  {result['status']}: {result['package']}")
    else:
        parser.print_help()
        sys.exit(1)
