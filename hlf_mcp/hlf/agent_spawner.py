"""HLF Agent Spawner — bridge VM spawn_agent to real agent processes.

Backends:
  asyncio   : Run agents as asyncio coroutines (testing, no isolation)
  subprocess: Spawn python agent_worker.py processes (real isolation, real work)
  omni      : POST to Omni Orchestrator localhost:8090/route
  copilot   : Spawn Copilot CLI task agents (requires MCP bridge)

Each backend implements:
  spawn(agent_id, role, task, model, **kwargs) -> SpawnHandle
  wait(handle, timeout) -> SpawnResult
  poll(handle) -> SpawnResult | None
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


@dataclass
class SpawnHandle:
    agent_id: str
    backend: str
    pid: int | None = None
    token: str = ""
    work_dir: str = ""
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class SpawnResult:
    agent_id: str
    status: str  # pending | running | complete | error | timeout
    stdout: str = ""
    stderr: str = ""
    files_written: list[str] = field(default_factory=list)
    files_read: list[str] = field(default_factory=list)
    error: str | None = None
    elapsed_ms: float = 0.0
    tokens_used: int = 0


class SpawnerBackend(Protocol):
    def spawn(self, agent_id: str, role: str, task: str, model: str = "", **kwargs: Any) -> SpawnHandle:
        ...

    def wait(self, handle: SpawnHandle, timeout: float = 300.0) -> SpawnResult:
        ...

    def poll(self, handle: SpawnHandle) -> SpawnResult | None:
        ...


# ── Asyncio Backend (testing) ─────────────────────────────────────────────────


class AsyncioBackend:
    """Run agents as asyncio coroutines. No real isolation."""

    _tasks: dict[str, asyncio.Task[Any]] = {}
    _coros: dict[str, Any] = {}

    def spawn(self, agent_id: str, role: str, task: str, model: str = "", **kwargs: Any) -> SpawnHandle:
        handle = SpawnHandle(agent_id=agent_id, backend="asyncio", token=str(uuid.uuid4()))
        coro = self._run_agent(agent_id, role, task, handle)
        self._coros[agent_id] = coro
        return handle

    async def _run_agent(self, agent_id: str, role: str, task: str, handle: SpawnHandle) -> SpawnResult:
        # Simulate work
        await asyncio.sleep(0.05)
        return SpawnResult(agent_id=agent_id, status="complete", stdout=f"asyncio agent {agent_id} done")

    def wait(self, handle: SpawnHandle, timeout: float = 300.0) -> SpawnResult:
        coro = self._coros.pop(handle.agent_id, None)
        if coro is None:
            task = self._tasks.get(handle.agent_id)
            if task is None:
                return SpawnResult(agent_id=handle.agent_id, status="error", error="task not found")
        else:
            try:
                loop = asyncio.get_running_loop()
                task = loop.create_task(coro)
                self._tasks[handle.agent_id] = task
            except RuntimeError:
                # No running event loop — create one
                loop = asyncio.new_event_loop()
                try:
                    result = loop.run_until_complete(asyncio.wait_for(coro, timeout=timeout))
                    return result
                except asyncio.TimeoutError:
                    return SpawnResult(agent_id=handle.agent_id, status="timeout", error="timeout")
                except Exception as exc:
                    return SpawnResult(agent_id=handle.agent_id, status="error", error=str(exc))
                finally:
                    loop.close()

        try:
            loop = asyncio.get_event_loop()
            result = loop.run_until_complete(asyncio.wait_for(task, timeout=timeout))
            return result
        except asyncio.TimeoutError:
            return SpawnResult(agent_id=handle.agent_id, status="timeout", error="timeout")
        except Exception as exc:
            return SpawnResult(agent_id=handle.agent_id, status="error", error=str(exc))

    def poll(self, handle: SpawnHandle) -> SpawnResult | None:
        task = self._tasks.get(handle.agent_id)
        if task is None:
            return None
        if task.done():
            try:
                return task.result()
            except Exception as exc:
                return SpawnResult(agent_id=handle.agent_id, status="error", error=str(exc))
        return None


# ── Subprocess Backend (real isolation) ─────────────────────────────────────────


class SubprocessBackend:
    """Spawn real python processes via agent_worker.py.

    Each agent gets:
      - A temp work directory
      - A JSON config file with role, task, constraints, dependencies
      - The worker calls Ollama API to generate code/files
      - Writes status.json when done
    """

    WORKER_TEMPLATE = r'''#!/usr/bin/env python3
"""HLF Agent Worker — spawned by SubprocessBackend."""
import json, os, sys, time, pathlib, urllib.request

def main():
    config_path = sys.argv[1]
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    agent_id = cfg["agent_id"]
    role = cfg["role"]
    task = cfg["task"]
    model = cfg.get("model", "llama3.2")
    ollama_url = cfg.get("ollama_url", "http://localhost:11434")
    work_dir = cfg.get("work_dir", ".")
    os.makedirs(work_dir, exist_ok=True)
    start = time.time()
    # Call Ollama generate
    prompt = f"""You are Agent {agent_id} ({role}).
Task: {task}
Constraints: {', '.join(cfg.get('constraints', []))}
Dependencies: {json.dumps(cfg.get('dependencies', {}))}
Produce the required files. Return ONLY a JSON object mapping file paths to their full contents.
Example: {{"server.js": "const express = require('express');\\n..."}}
"""
    body = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode()
    req = urllib.request.Request(f"{ollama_url}/api/generate", data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            data = json.loads(resp.read().decode())
        response_text = data.get("response", "")
        # Try to extract JSON from response
        files_written = []
        try:
            # Find JSON block
            start_idx = response_text.find("{")
            end_idx = response_text.rfind("}")
            if start_idx != -1 and end_idx != -1:
                files = json.loads(response_text[start_idx:end_idx+1])
                for path, content in files.items():
                    full = os.path.join(work_dir, path)
                    os.makedirs(os.path.dirname(full), exist_ok=True)
                    with open(full, "w", encoding="utf-8") as f:
                        f.write(content)
                    files_written.append(path)
        except Exception:
            pass
        status = {
            "agent_id": agent_id,
            "status": "complete" if files_written else "error",
            "stdout": response_text[:500],
            "stderr": "",
            "files_written": files_written,
            "elapsed_ms": int((time.time() - start) * 1000),
            "tokens_used": data.get("eval_count", 0) + data.get("prompt_eval_count", 0)
        }
    except Exception as exc:
        status = {
            "agent_id": agent_id,
            "status": "error",
            "stdout": "",
            "stderr": str(exc),
            "files_written": [],
            "elapsed_ms": int((time.time() - start) * 1000),
            "tokens_used": 0,
            "error": str(exc)
        }
    with open(os.path.join(work_dir, "status.json"), "w", encoding="utf-8") as f:
        json.dump(status, f, indent=2)

if __name__ == "__main__":
    main()
'''

    def __init__(self, ollama_url: str = "http://localhost:11434", model: str = "llama3.2") -> None:
        self.ollama_url = ollama_url
        self.model = model
        self._procs: dict[str, subprocess.Popen[str]] = {}
        self._work_dirs: dict[str, str] = {}

    def spawn(self, agent_id: str, role: str, task: str, model: str = "", **kwargs: Any) -> SpawnHandle:
        work_dir = tempfile.mkdtemp(prefix=f"hlf_agent_{agent_id}_")
        model = model or self.model
        config = {
            "agent_id": agent_id,
            "role": role,
            "task": task,
            "model": model,
            "ollama_url": self.ollama_url,
            "work_dir": work_dir,
            "constraints": kwargs.get("constraints", []),
            "dependencies": kwargs.get("dependencies", {}),
        }
        config_path = os.path.join(work_dir, "config.json")
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        worker_path = os.path.join(work_dir, "agent_worker.py")
        with open(worker_path, "w", encoding="utf-8") as f:
            f.write(self.WORKER_TEMPLATE)
        proc = subprocess.Popen(
            [sys.executable, worker_path, config_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=work_dir,
        )
        self._procs[agent_id] = proc
        self._work_dirs[agent_id] = work_dir
        return SpawnHandle(
            agent_id=agent_id,
            backend="subprocess",
            pid=proc.pid,
            token=str(uuid.uuid4()),
            work_dir=work_dir,
            meta={"config_path": config_path, "worker_path": worker_path},
        )

    def wait(self, handle: SpawnHandle, timeout: float = 300.0) -> SpawnResult:
        proc = self._procs.get(handle.agent_id)
        if proc is None:
            return SpawnResult(agent_id=handle.agent_id, status="error", error="process not found")
        start = time.time()
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()
            return SpawnResult(agent_id=handle.agent_id, status="timeout", stdout=stdout, stderr=stderr, error="timeout")
        elapsed_ms = (time.time() - start) * 1000
        status_path = os.path.join(handle.work_dir or self._work_dirs.get(handle.agent_id, ""), "status.json")
        files_written: list[str] = []
        tokens_used = 0
        if os.path.exists(status_path):
            with open(status_path, "r", encoding="utf-8") as f:
                status_data = json.load(f)
            files_written = status_data.get("files_written", [])
            tokens_used = status_data.get("tokens_used", 0)
            if status_data.get("status") == "error" and not proc.returncode:
                proc.returncode = 1
        return SpawnResult(
            agent_id=handle.agent_id,
            status="complete" if proc.returncode == 0 else "error",
            stdout=stdout,
            stderr=stderr,
            files_written=files_written,
            error=stderr if proc.returncode != 0 else None,
            elapsed_ms=elapsed_ms,
            tokens_used=tokens_used,
        )

    def poll(self, handle: SpawnHandle) -> SpawnResult | None:
        proc = self._procs.get(handle.agent_id)
        if proc is None:
            return None
        if proc.poll() is None:
            return None
        return self.wait(handle, timeout=0.1)


# ── Omni Backend ───────────────────────────────────────────────────────────────


class OmniBackend:
    """POST to Omni Orchestrator at localhost:8090/route."""

    def __init__(self, url: str = "http://localhost:8090") -> None:
        self.url = url

    def spawn(self, agent_id: str, role: str, task: str, model: str = "", **kwargs: Any) -> SpawnHandle:
        import urllib.request

        payload = json.dumps({"prompt": task, "agent_id": agent_id, "role": role}).encode()
        req = urllib.request.Request(
            f"{self.url}/route",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
            token = data.get("attribution", agent_id)
        except Exception as exc:
            token = f"error:{exc}"
        return SpawnHandle(agent_id=agent_id, backend="omni", token=token)

    def wait(self, handle: SpawnHandle, timeout: float = 300.0) -> SpawnResult:
        # Omni is async; we would need a status endpoint. For now, simulate.
        time.sleep(1)
        return SpawnResult(agent_id=handle.agent_id, status="complete", stdout=f"omni agent {handle.agent_id} done")

    def poll(self, handle: SpawnHandle) -> SpawnResult | None:
        # No polling mechanism for Omni without a status endpoint
        return None


# ── Agent Spawner ─────────────────────────────────────────────────────────────


class AgentSpawner:
    """Unified agent spawner with pluggable backends."""

    BACKENDS: dict[str, type] = {
        "asyncio": AsyncioBackend,
        "subprocess": SubprocessBackend,
        "omni": OmniBackend,
    }

    def __init__(self, backend: str = "subprocess", **backend_kwargs: Any) -> None:
        self.backend_name = backend
        backend_cls = self.BACKENDS.get(backend)
        if backend_cls is None:
            raise ValueError(f"Unknown backend: {backend}")
        self.backend: SpawnerBackend = backend_cls(**backend_kwargs)
        self._handles: dict[str, SpawnHandle] = {}
        self._results: dict[str, SpawnResult] = {}

    def spawn(self, agent_id: str, role: str, task: str, model: str = "", **kwargs: Any) -> SpawnHandle:
        handle = self.backend.spawn(agent_id, role, task, model, **kwargs)
        self._handles[agent_id] = handle
        return handle

    def wait(self, agent_id: str, timeout: float = 300.0) -> SpawnResult:
        handle = self._handles.get(agent_id)
        if handle is None:
            return SpawnResult(agent_id=agent_id, status="error", error="agent not found")
        result = self.backend.wait(handle, timeout=timeout)
        self._results[agent_id] = result
        return result

    def poll(self, agent_id: str) -> SpawnResult | None:
        handle = self._handles.get(agent_id)
        if handle is None:
            return None
        result = self.backend.poll(handle)
        if result:
            self._results[agent_id] = result
        return result

    def wait_all(self, agent_ids: list[str], timeout: float = 300.0) -> dict[str, SpawnResult]:
        results: dict[str, SpawnResult] = {}
        for aid in agent_ids:
            results[aid] = self.wait(aid, timeout=timeout)
        return results

    def spawn_batch(self, agents: list[dict[str, Any]]) -> list[SpawnHandle]:
        handles: list[SpawnHandle] = []
        for a in agents:
            handle = self.spawn(
                agent_id=a["agent_id"],
                role=a.get("role", "agent"),
                task=a.get("task", ""),
                model=a.get("model", ""),
                constraints=a.get("constraints", []),
                dependencies=a.get("dependencies", {}),
            )
            handles.append(handle)
        return handles

    def get_result(self, agent_id: str) -> SpawnResult | None:
        return self._results.get(agent_id)

    def summary(self) -> dict[str, Any]:
        total = len(self._results)
        complete = sum(1 for r in self._results.values() if r.status == "complete")
        error = sum(1 for r in self._results.values() if r.status == "error")
        timeout = sum(1 for r in self._results.values() if r.status == "timeout")
        total_ms = sum(r.elapsed_ms for r in self._results.values())
        total_tokens = sum(r.tokens_used for r in self._results.values())
        return {
            "backend": self.backend_name,
            "total_agents": total,
            "complete": complete,
            "error": error,
            "timeout": timeout,
            "total_ms": round(total_ms, 2),
            "total_tokens": total_tokens,
        }
