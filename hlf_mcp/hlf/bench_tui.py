"""
hlf bench --tui  —  Self-improving swarm visualization dashboard.

Zero-dependency curses TUI for HLF benchmark monitoring:
  • Swarm execution summary (agents, tokens, time, quality)
  • Per-agent breakdown with status, tokens, output files
  • HLF vs NL side-by-side comparison (when two files provided)
  • Live watch mode (--watch polls for metrics updates)
  • Self-improving trend view (--self-improve <dir> or point at iteration dir)

The self-improving mode loads multiple iterations and visualizes:
  • Quality score trending with iteration-over-iteration deltas
  • Token efficiency trends
  • Agent completion growth
  • HKS exemplar accumulation

Usage:
  hlf-bench results/metrics.json
  hlf-bench results-hlf/metrics.json results-nl/metrics.json  # comparison
  hlf-bench --watch results/metrics.json                       # live mode
  hlf-bench --self-improve self-improve-results/               # trend mode
  hlf-bench self-improve-results/                              # auto-detect dir
"""
from __future__ import annotations

import argparse
import curses
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


# ── Data Models ────────────────────────────────────────────────────────────────

@dataclass
class AgentResult:
    agent_id: str
    status: str
    elapsed_ms: float
    tokens_used: int
    files_written: list[str]
    error: Optional[str]
    stdout: str = ""
    stderr: str = ""


@dataclass
class BenchmarkMetrics:
    path: str
    mode: str = ""
    model: str = ""
    source: str = ""
    total_agents: int = 0
    complete: int = 0
    errors: int = 0
    timeouts: int = 0
    total_ms: float = 0.0
    total_tokens: int = 0
    artifact_tokens: int = 0
    per_agent_task_tokens: int = 0
    coordination_tokens: int = 0
    code_generation_tokens: int = 0
    files_produced: int = 0
    quality_score: float = 0.0
    quality_grade: str = ""
    agent_results: list[AgentResult] = field(default_factory=list)

    @classmethod
    def from_file(cls, filepath: str) -> "BenchmarkMetrics":
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        agents = [
            AgentResult(
                agent_id=a.get("agent_id", a.get("agent_name", "?")),
                status=a.get("status", "unknown"),
                elapsed_ms=a.get("elapsed_ms", 0),
                tokens_used=a.get("tokens_used", 0),
                files_written=a.get("files_written", []),
                error=a.get("error"),
                stdout=a.get("stdout", ""),
                stderr=a.get("stderr", ""),
            )
            for a in data.get("agent_results", data.get("agents", []))
        ]

        # Try quality data from various key locations
        quality = data.get("quality", data.get("quality_score", {}))
        if isinstance(quality, dict):
            qs = quality.get("score", quality.get("overall", 0))
            qg = quality.get("grade", "")
        else:
            qs = float(quality) if quality else 0.0
            qg = ""

        return cls(
            path=filepath,
            mode=data.get("mode", ""),
            model=data.get("model", ""),
            source=os.path.basename(data.get("source", "")),
            total_agents=data.get("total_agents", len(agents)),
            complete=data.get("complete", sum(1 for a in agents if a.status == "complete")),
            errors=data.get("errors", sum(1 for a in agents if a.status == "error")),
            timeouts=data.get("timeouts", sum(1 for a in agents if a.status == "timeout")),
            total_ms=data.get("total_ms", 0),
            total_tokens=data.get("total_tokens", 0),
            artifact_tokens=data.get("artifact_tokens", 0),
            per_agent_task_tokens=data.get("per_agent_task_tokens", 0),
            coordination_tokens=data.get("coordination_tokens", 0),
            code_generation_tokens=data.get("code_generation_tokens", 0),
            files_produced=data.get("files_produced", 0),
            quality_score=qs,
            quality_grade=qg,
            agent_results=agents,
        )

    @property
    def elapsed_sec(self) -> float:
        return self.total_ms / 1000.0

    @property
    def success_rate(self) -> float:
        if self.total_agents == 0:
            return 0.0
        return self.complete / self.total_agents

    @property
    def summary_line(self) -> str:
        return (
            f"{self.mode.upper():4s}  {self.complete}/{self.total_agents} done  "
            f"{self.total_tokens:,} tokens  {self.elapsed_sec:.0f}s  "
            f"{self.files_produced} files"
        )


# ── Iteration Series (Self-Improving Mode) ─────────────────────────────────────

@dataclass
class IterationPoint:
    """A single iteration in a self-improving swarm run."""
    index: int
    path: str
    metrics: BenchmarkMetrics
    label: str = ""


@dataclass
class IterationSeries:
    """Multiple iterations loaded from a self-improving swarm output directory."""
    iterations: list[IterationPoint] = field(default_factory=list)

    @classmethod
    def from_directory(cls, dirpath: str) -> "IterationSeries":
        """Load all iterations from a directory. Expects iter-N/metrics.json or
        N/metrics.json, or any metric files prefixed by iteration number."""
        root = Path(dirpath)
        if not root.is_dir():
            return cls()

        iterations: list[IterationPoint] = []

        # Pattern 1: iter-1/metrics.json, iter-2/metrics.json, ...
        for child in sorted(root.iterdir(), key=lambda p: p.name):
            m = re.match(r'iter[-_]?(\d+)', child.name, re.IGNORECASE)
            if child.is_dir():
                metrics_file = child / "metrics.json"
                if metrics_file.exists():
                    idx = int(m.group(1)) if m else len(iterations) + 1
                    try:
                        bm = BenchmarkMetrics.from_file(str(metrics_file))
                        iterations.append(IterationPoint(
                            index=idx, path=str(metrics_file), metrics=bm,
                            label=child.name
                        ))
                    except (json.JSONDecodeError, FileNotFoundError):
                        pass
                # Also check numbered subdirs like v1, v2, ...
                elif not m:
                    m2 = re.match(r'v(\d+)', child.name, re.IGNORECASE)
                    if m2:
                        metrics_file = child / "metrics.json"
                        if metrics_file.exists():
                            idx = int(m2.group(1))
                            try:
                                bm = BenchmarkMetrics.from_file(str(metrics_file))
                                iterations.append(IterationPoint(
                                    index=idx, path=str(metrics_file), metrics=bm,
                                    label=child.name
                                ))
                            except (json.JSONDecodeError, FileNotFoundError):
                                pass

        # Pattern 2: Single directory with metrics-1.json, metrics-2.json, ...
        if not iterations:
            for child in sorted(root.iterdir(), key=lambda p: p.name):
                m = re.match(r'metrics[-_]?(\d+)\.json', child.name, re.IGNORECASE)
                if m and child.is_file():
                    idx = int(m.group(1))
                    try:
                        bm = BenchmarkMetrics.from_file(str(child))
                        iterations.append(IterationPoint(
                            index=idx, path=str(child), metrics=bm,
                            label=f"iter-{idx}"
                        ))
                    except (json.JSONDecodeError, FileNotFoundError):
                        pass

        # Sort by index
        iterations.sort(key=lambda ip: ip.index)
        return cls(iterations=iterations)

    @classmethod
    def from_files(cls, files: list[str]) -> "IterationSeries":
        """Load from explicit list of metrics files with numeric naming."""
        iterations: list[IterationPoint] = []
        for i, f in enumerate(files):
            try:
                bm = BenchmarkMetrics.from_file(f)
                # Try to extract index from filename
                m = re.search(r'(\d+)', Path(f).stem)
                idx = int(m.group(1)) if m else i + 1
                iterations.append(IterationPoint(
                    index=idx, path=f, metrics=bm,
                    label=Path(f).parent.name if Path(f).parent.name != '.' else Path(f).stem
                ))
            except (json.JSONDecodeError, FileNotFoundError):
                pass
        iterations.sort(key=lambda ip: ip.index)
        return cls(iterations=iterations)

    @property
    def quality_trend(self) -> list[float]:
        return [ip.metrics.quality_score for ip in self.iterations]

    @property
    def token_trend(self) -> list[int]:
        return [ip.metrics.total_tokens for ip in self.iterations]

    @property
    def completion_trend(self) -> list[float]:
        return [ip.metrics.success_rate for ip in self.iterations]

    @property
    def file_trend(self) -> list[int]:
        return [ip.metrics.files_produced for ip in self.iterations]

    @property
    def best_quality(self) -> float:
        return max(self.quality_trend) if self.quality_trend else 0.0

    @property
    def quality_delta(self) -> float:
        """Improvement from first to last iteration."""
        qt = self.quality_trend
        if len(qt) < 2:
            return 0.0
        return qt[-1] - qt[0]

    @property
    def token_delta_pct(self) -> float:
        """Token change from first to last iteration (negative = savings)."""
        tt = self.token_trend
        if len(tt) < 2 or tt[0] == 0:
            return 0.0
        return ((tt[-1] - tt[0]) / tt[0]) * 100


# ── Sparkline Utility ──────────────────────────────────────────────────────────

def sparkline(values: list[float], width: int, min_v: float | None = None,
              max_v: float | None = None) -> str:
    """Render a unicode sparkline for a series of values."""
    if not values or width <= 0:
        return " " * max(width, 0)

    mn = min_v if min_v is not None else min(values)
    mx = max_v if max_v is not None else max(values)
    rng = mx - mn
    if rng == 0:
        rng = 1

    blocks = "▁▂▃▄▅▆▇█"
    result: list[str] = []
    step = max(1, len(values) / width)

    for i in range(width):
        idx = min(int(i * step), len(values) - 1)
        # Take max of a small window for better visibility
        window_start = max(0, int(i * step) - 1)
        window_end = min(len(values), int((i + 1) * step) + 1)
        val = max(values[window_start:window_end]) if window_start < window_end else values[idx]
        block_idx = min(len(blocks) - 1, max(0, int((val - mn) / rng * (len(blocks) - 1))))
        result.append(blocks[block_idx])

    return "".join(result)


# ── TUI Application ────────────────────────────────────────────────────────────

class BenchTUI:
    """Curses-based benchmark dashboard."""

    def __init__(self, metrics: list[BenchmarkMetrics], watch: bool = False,
                 interval: float = 2.0, iterations: Optional[IterationSeries] = None):
        self.metrics = metrics  # 0 = HLF (or primary), 1 = NL (optional comparison)
        self.watch = watch
        self.interval = interval
        self.iterations = iterations  # self-improving mode data
        self.running = True
        self.scroll_offset = 0
        self.selected_idx = 0
        self.view_mode = "summary"  # "summary", "agents", "comparison", "tokens", "trends"
        self._highlight_iter = -1  # highlighted iteration in trend view

        # Screen sections
        self.stdscr: Optional[curses.window] = None
        self.header_win: Optional[curses.window] = None
        self.body_win: Optional[curses.window] = None
        self.footer_win: Optional[curses.window] = None
        self._max_y = 0
        self._max_x = 0

    # ── Curses lifecycle ──────────────────────────────────────────────────

    def run(self) -> None:
        curses.wrapper(self._run)

    def _run(self, stdscr: curses.window) -> None:
        self.stdscr = stdscr
        curses.curs_set(0)
        curses.use_default_colors()
        self._init_colors()
        stdscr.clear()
        stdscr.refresh()
        self._resize()

        while self.running:
            self._draw()
            self._handle_input()

            if self.watch:
                self._reload_metrics()
                time.sleep(self.interval)

    def _init_colors(self) -> None:
        if not curses.has_colors():
            return
        curses.init_pair(1, curses.COLOR_GREEN, -1)    # success
        curses.init_pair(2, curses.COLOR_RED, -1)      # error
        curses.init_pair(3, curses.COLOR_YELLOW, -1)   # warning / timeout
        curses.init_pair(4, curses.COLOR_CYAN, -1)     # header
        curses.init_pair(5, curses.COLOR_MAGENTA, -1)  # highlight
        curses.init_pair(6, curses.COLOR_WHITE, curses.COLOR_BLUE)  # selected
        curses.init_pair(7, curses.COLOR_BLACK, curses.COLOR_CYAN)  # title bar

    def _resize(self) -> None:
        self._max_y, self._max_x = self.stdscr.getmaxyx()
        self.header_win = curses.newwin(3, self._max_x, 0, 0)
        self.body_win = curses.newwin(self._max_y - 5, self._max_x, 3, 0)
        self.footer_win = curses.newwin(2, self._max_x, self._max_y - 2, 0)

    # ── Reload ────────────────────────────────────────────────────────────

    def _reload_metrics(self) -> None:
        for m in self.metrics:
            try:
                new = BenchmarkMetrics.from_file(m.path)
                # Update in place
                m.complete = new.complete
                m.errors = new.errors
                m.total_tokens = new.total_tokens
                m.total_ms = new.total_ms
                m.files_produced = new.files_produced
                m.agent_results = new.agent_results
            except (json.JSONDecodeError, FileNotFoundError):
                pass  # file being written — try next cycle

    # ── Input ─────────────────────────────────────────────────────────────

    def _handle_input(self) -> None:
        try:
            self.stdscr.nodelay(True)
            key = self.stdscr.getch()
        except Exception:
            return

        if key == -1:
            return
        elif key in (ord("q"), ord("Q"), 27):  # q or ESC
            self.running = False
        elif key == curses.KEY_RESIZE:
            self._resize()
        elif key in (ord("1"),):
            self.view_mode = "summary"
            self.scroll_offset = 0
        elif key in (ord("2"),):
            self.view_mode = "agents"
            self.scroll_offset = 0
        elif key in (ord("3"),):
            self.view_mode = "tokens"
            self.scroll_offset = 0
        elif key in (ord("4"),) and len(self.metrics) >= 2:
            self.view_mode = "comparison"
            self.scroll_offset = 0
        elif key in (ord("5"),) and self.iterations and self.iterations.iterations:
            self.view_mode = "trends"
            self.scroll_offset = 0
        elif key == ord("r"):
            self._reload_metrics()
        elif key == curses.KEY_UP:
            self.selected_idx = max(0, self.selected_idx - 1)
        elif key == curses.KEY_DOWN:
            self.selected_idx = min(self.selected_idx + 1, 99)
        elif key == curses.KEY_PPAGE:
            self.scroll_offset = max(0, self.scroll_offset - 10)
        elif key == curses.KEY_NPAGE:
            self.scroll_offset += 10

    # ── Drawing ───────────────────────────────────────────────────────────

    def _draw(self) -> None:
        if not self.stdscr:
            return
        self.stdscr.erase()
        self._draw_header()
        self._draw_body()
        self._draw_footer()
        self.stdscr.refresh()

    def _draw_header(self) -> None:
        win = self.header_win
        if not win:
            return
        win.erase()
        _, w = win.getmaxyx()

        title = " HLF BENCH TUI "
        if self.iterations and self.iterations.iterations:
            n = len(self.iterations.iterations)
            title = f" HLF SELF-IMPROVING SWARM — {n} iterations "

        win.bkgd(" ", curses.color_pair(7))
        win.addstr(0, (w - len(title)) // 2, title, curses.color_pair(7) | curses.A_BOLD)

        primary = self.metrics[0]
        line = (
            f" Mode: {primary.mode.upper()} | Model: {primary.model} | "
            f"Source: {primary.source[:40]} | "
            f"Agents: {primary.complete}/{primary.total_agents} | "
            f"Tokens: {primary.total_tokens:,} | Time: {primary.elapsed_sec:.0f}s"
        )
        win.addstr(1, 1, line[: w - 2], curses.color_pair(4))
        win.noutrefresh()

    def _draw_body(self) -> None:
        win = self.body_win
        if not win:
            return
        win.erase()
        h, w = win.getmaxyx()

        if self.view_mode == "comparison" and len(self.metrics) >= 2:
            self._draw_comparison(win, h, w)
        elif self.view_mode == "agents":
            self._draw_agents(win, h, w)
        elif self.view_mode == "tokens":
            self._draw_tokens(win, h, w)
        elif self.view_mode == "trends" and self.iterations and self.iterations.iterations:
            self._draw_trends(win, h, w)
        else:
            self._draw_summary(win, h, w)

        win.noutrefresh()

    def _draw_summary(self, win: curses.window, h: int, w: int) -> None:
        primary = self.metrics[0]
        y = 0

        # Quality gauge
        if primary.quality_score > 0:
            grade_color = (
                curses.color_pair(1) if primary.quality_score >= 0.9
                else curses.color_pair(3) if primary.quality_score >= 0.75
                else curses.color_pair(2)
            )
            bar_w = min(40, w - 20)
            filled = int(bar_w * min(primary.quality_score, 1.0))
            bar = "█" * filled + "░" * (bar_w - filled)
            win.addstr(y, 1, f" Quality: {primary.quality_score:.4f} ", grade_color | curses.A_BOLD)
            win.addstr(y, 22, f" [{bar}]", grade_color)
            if primary.quality_grade:
                win.addstr(y, 22 + bar_w + 3, f" {primary.quality_grade} ", grade_color | curses.A_BOLD)
            y += 2

        # Key metrics grid
        metrics_grid = [
            ("Agents", f"{primary.complete}/{primary.total_agents}", primary.complete == primary.total_agents),
            ("Errors", str(primary.errors), primary.errors == 0),
            ("Timeouts", str(primary.timeouts), primary.timeouts == 0),
            ("Wall Time", f"{primary.elapsed_sec:.1f}s", True),
            ("Total Tokens", f"{primary.total_tokens:,}", True),
            ("Files Produced", str(primary.files_produced), primary.files_produced > 0),
            ("Success Rate", f"{primary.success_rate:.0%}", primary.success_rate >= 0.9),
        ]

        col_w = (w - 4) // 2
        row_h = 1
        for i, (label, value, ok) in enumerate(metrics_grid):
            col = i % 2
            row = y + (i // 2)
            x = 2 + col * (col_w + 2)
            win.addstr(row, x, f" {label}: ", curses.A_BOLD)
            win.addstr(row, x + len(label) + 3, value, curses.color_pair(1) if ok else curses.color_pair(2))

        y += (len(metrics_grid) + 1) // 2 + 1

        # Agent status grid
        win.addstr(y, 1, "─" * (w - 2))
        y += 1
        win.addstr(y, 1, " Agents", curses.A_BOLD)

        agents = primary.agent_results
        if agents:
            y += 1
            header = f" {'Agent':<24s} {'Status':<10s} {'Tokens':>8s} {'Time':>8s}  Files"
            win.addstr(y, 1, header[: w - 2], curses.A_UNDERLINE)
            y += 1

            visible = h - y - 1
            for i, a in enumerate(agents):
                if i < self.scroll_offset:
                    continue
                if i >= self.scroll_offset + visible:
                    break

                status_color = (
                    curses.color_pair(1) if a.status == "complete"
                    else curses.color_pair(2) if a.status == "error"
                    else curses.color_pair(3)
                )
                elapsed = f"{a.elapsed_ms / 1000:.1f}s"
                files = ", ".join(a.files_written[:2])
                if len(a.files_written) > 2:
                    files += f", +{len(a.files_written) - 2}"
                line = f" {a.agent_id:<24s} {a.status:<10s} {a.tokens_used:>7,} {elapsed:>8s}  {files}"
                attr = curses.A_REVERSE if i == self.selected_idx else curses.A_NORMAL
                win.addstr(y + i - self.scroll_offset, 1, line[: w - 2], status_color | attr)
        else:
            y += 1
            win.addstr(y, 1, " (no agent data)", curses.color_pair(3))

        # Nav help at bottom of body
        nav_parts = ["1:Summary", "2:Agents", "3:Tokens"]
        if len(self.metrics) >= 2:
            nav_parts.append("4:Comparison")
        if self.iterations and self.iterations.iterations:
            nav_parts.append("5:Trends")
        nav = "  " + "  ".join(nav_parts) + "  ↑↓:Scroll  q:Quit  r:Reload"
        win.addstr(h - 1, 1, nav[: w - 2], curses.color_pair(4))

    def _draw_agents(self, win: curses.window, h: int, w: int) -> None:
        primary = self.metrics[0]
        agents = primary.agent_results
        y = 0

        win.addstr(y, 1, " Per-Agent Detail", curses.A_BOLD)
        y += 2

        visible = h - y - 2
        for i, a in enumerate(agents):
            if i < self.scroll_offset:
                continue
            if i - self.scroll_offset >= visible:
                break

            ry = y + (i - self.scroll_offset) * 5
            if ry + 4 >= h:
                break

            status_color = (
                curses.color_pair(1) if a.status == "complete"
                else curses.color_pair(2) if a.status == "error"
                else curses.color_pair(3)
            )
            attr = curses.A_REVERSE if i == self.selected_idx else curses.A_NORMAL

            win.addstr(ry, 1, f" ▸ {a.agent_id}  [{a.status}]", status_color | attr | curses.A_BOLD)
            win.addstr(ry + 1, 3, f"Tokens: {a.tokens_used:,}  |  Time: {a.elapsed_ms / 1000:.1f}s  |  Files: {len(a.files_written)}")

            if a.files_written:
                files_str = ", ".join(a.files_written[:5])
                if len(a.files_written) > 5:
                    files_str += f"  ... +{len(a.files_written) - 5}"
                win.addstr(ry + 2, 3, f"Output: {files_str}"[: w - 6], curses.color_pair(4))

            if a.error:
                win.addstr(ry + 3, 3, f"Error: {a.error}"[: w - 6], curses.color_pair(2))

            # progress bar for elapsed relative to total
            pct = min(a.elapsed_ms / max(primary.total_ms, 1), 1.0)
            bar_w = min(30, w - 10)
            filled = int(bar_w * pct)
            bar = "▓" * filled + "░" * (bar_w - filled)
            win.addstr(ry + 4, 3, f"  [{bar}] {pct:.0%}")

        nav = "1:Summary  2:Agents  3:Tokens  ↑↓:Select  PgUp/PgDn:Scroll  q:Quit"
        win.addstr(h - 1, 1, nav[: w - 2], curses.color_pair(4))

    def _draw_tokens(self, win: curses.window, h: int, w: int) -> None:
        primary = self.metrics[0]
        y = 0

        win.addstr(y, 1, " Token Breakdown", curses.A_BOLD)
        y += 2

        total = max(primary.total_tokens, 1)
        token_cats = [
            ("Coordination (swarm orchestration)", primary.coordination_tokens),
            ("Per-agent task prompts", primary.per_agent_task_tokens),
            ("Code generation (agent output)", primary.code_generation_tokens),
            ("Artifact tokens", primary.artifact_tokens),
        ]

        for label, count in token_cats:
            pct = count / total
            bar_w = min(50, w - 40)
            filled = int(bar_w * pct)
            bar = "█" * filled + "░" * (bar_w - filled)
            win.addstr(y, 1, f" {label:<38s} {count:>8,}  [{bar}] {pct:.0%}")
            y += 1

        y += 1
        win.addstr(y, 1, f" ─{'─' * (w - 4)}")
        y += 1
        win.addstr(y, 1, f" TOTAL: {primary.total_tokens:,} tokens", curses.A_BOLD)

        y += 2
        # Per-agent token ranking
        win.addstr(y, 1, " Token Usage by Agent", curses.A_BOLD)
        y += 1

        ranked = sorted(primary.agent_results, key=lambda a: a.tokens_used, reverse=True)
        for i, a in enumerate(ranked):
            if y + i >= h - 2:
                break
            pct = a.tokens_used / total
            bar_w = min(30, w - 40)
            filled = int(bar_w * pct)
            bar = "█" * filled + "░" * (bar_w - filled)
            status_mark = "✓" if a.status == "complete" else "✗"
            win.addstr(y + i, 1, f" {status_mark} {a.agent_id:<26s} {a.tokens_used:>7,}  [{bar}] {pct:.0%}")

        nav = "1:Summary  2:Agents  3:Tokens  q:Quit"
        win.addstr(h - 1, 1, nav[: w - 2], curses.color_pair(4))

    def _draw_comparison(self, win: curses.window, h: int, w: int) -> None:
        hlf, nl = self.metrics[0], self.metrics[1]
        y = 0

        win.addstr(y, 1, " HLF vs NL Comparison", curses.A_BOLD)
        y += 2

        # Column headers
        half_w = (w - 4) // 2
        win.addstr(y, 2, f" {'HLF':^{half_w - 2}s}", curses.color_pair(5) | curses.A_BOLD)
        win.addstr(y, 2 + half_w + 1, f" {'NL':^{half_w - 2}s}", curses.color_pair(4) | curses.A_BOLD)
        y += 1

        # Metrics comparison rows
        rows = [
            ("Agents Complete", f"{hlf.complete}/{hlf.total_agents}", f"{nl.complete}/{nl.total_agents}", hlf.success_rate >= nl.success_rate),
            ("Errors", str(hlf.errors), str(nl.errors), hlf.errors <= nl.errors),
            ("Wall Time", f"{hlf.elapsed_sec:.0f}s", f"{nl.elapsed_sec:.0f}s", True),
            ("Total Tokens", f"{hlf.total_tokens:,}", f"{nl.total_tokens:,}", True),
            ("Files Produced", str(hlf.files_produced), str(nl.files_produced), hlf.files_produced >= nl.files_produced),
            ("Quality", f"{hlf.quality_score:.4f} {hlf.quality_grade}", f"{nl.quality_score:.4f} {nl.quality_grade}", hlf.quality_score >= nl.quality_score),
        ]

        for label, hlf_v, nl_v, _advantage_hlf in rows:
            win.addstr(y, 1, f" {label:<20s}")
            win.addstr(y, 23, f" {hlf_v:<{half_w - 25}s}", curses.color_pair(1))
            win.addstr(y, 23 + half_w, f" {nl_v:<{half_w - 25}s}")
            y += 1

        y += 1
        win.addstr(y, 1, "─" * (w - 2))
        y += 1

        # Token efficiency comparison
        win.addstr(y, 1, " Token Efficiency", curses.A_BOLD)
        y += 1

        tok_h = hlf.total_tokens
        tok_n = nl.total_tokens
        if tok_n > 0:
            ratio = tok_h / tok_n
            if ratio < 1:
                win.addstr(y, 1, f" HLF uses {ratio:.1%} of NL token budget ({tok_h:,} vs {tok_n:,})", curses.color_pair(1))
            else:
                win.addstr(y, 1, f" HLF uses {ratio:.1%} of NL token budget ({tok_h:,} vs {tok_n:,})", curses.color_pair(2))

        y += 2
        # Per-agent comparison
        win.addstr(y, 1, " Agent Comparison", curses.A_BOLD)
        y += 1

        hlf_agents = {a.agent_id: a for a in hlf.agent_results}
        nl_agents = {a.agent_id: a for a in nl.agent_results}
        all_ids = sorted(set(list(hlf_agents) + list(nl_agents)))

        for agent_id in all_ids:
            if y >= h - 2:
                win.addstr(y, 1, f" ... +{len(all_ids) - (y - h + 2)} more agents", curses.color_pair(3))
                break
            ha = hlf_agents.get(agent_id)
            na = nl_agents.get(agent_id)
            h_status = "✓" if ha and ha.status == "complete" else ("✗" if ha else "—")
            n_status = "✓" if na and na.status == "complete" else ("✗" if na else "—")
            win.addstr(y, 1, f" {agent_id:<24s}  HLF:{h_status}  NL:{n_status}", curses.color_pair(1) if h_status == "✓" else curses.color_pair(2))
            y += 1

        nav = "1:Summary  2:Agents  3:Tokens  4:Comparison  q:Quit"
        win.addstr(h - 1, 1, nav[: w - 2], curses.color_pair(4))

    def _draw_trends(self, win: curses.window, h: int, w: int) -> None:
        """Self-improving swarm trend visualization across iterations."""
        if not self.iterations:
            return
        its = self.iterations.iterations
        if not its:
            return
        y = 0

        win.addstr(y, 1, " Self-Improving Swarm Trends", curses.color_pair(5) | curses.A_BOLD)
        y += 1

        # ── Quality Trend ──────────────────────────────────────────────────
        y += 1
        win.addstr(y, 1, " Quality Score", curses.A_BOLD)
        y += 1

        q_values = self.iterations.quality_trend
        spark_w = min(60, w - 25)
        spark = sparkline(q_values, spark_w)
        win.addstr(y, 3, spark, curses.color_pair(5))
        y += 1

        # Quality values with delta markers
        line_parts: list[str] = []
        prev_q = None
        for ip in its:
            q = ip.metrics.quality_score
            if prev_q is not None and q != prev_q:
                delta = "↑" if q > prev_q else "↓"
                color_code = "\x01" if q > prev_q else "\x02"  # placeholder for color
                line_parts.append(f"{ip.index}:{q:.2f}{delta}")
            else:
                line_parts.append(f"{ip.index}:{q:.2f} ")
            prev_q = q
        trend_line = "  ".join(line_parts)
        quality_color = (
            curses.color_pair(1) if self.iterations.quality_delta >= 0
            else curses.color_pair(2)
        )
        win.addstr(y, 1, f" {trend_line}"[: w - 2],
                   quality_color if self.iterations.quality_delta != 0 else curses.A_NORMAL)
        y += 1

        delta_q = self.iterations.quality_delta
        win.addstr(y, 1, f" Δ: {delta_q:+.4f}  |  Best: {self.iterations.best_quality:.4f}  |  "
                   f"{len(its)} iterations",
                   curses.color_pair(1) if delta_q >= 0 else curses.color_pair(2))
        y += 2

        # ── Token Trend ────────────────────────────────────────────────────
        win.addstr(y, 1, "─" * (w - 2))
        y += 1
        win.addstr(y, 1, " Token Efficiency", curses.A_BOLD)
        y += 1

        t_values = [float(t) for t in self.iterations.token_trend]
        t_spark = sparkline(t_values, spark_w)
        win.addstr(y, 3, t_spark, curses.color_pair(4))
        y += 1

        # Token values
        token_parts = []
        for ip in its:
            token_parts.append(f"{ip.index}:{ip.metrics.total_tokens:,}")
        win.addstr(y, 1, f" {'  '.join(token_parts)}"[: w - 2])
        y += 1

        t_delta = self.iterations.token_delta_pct
        tok_color = curses.color_pair(1) if t_delta <= 0 else curses.color_pair(2)
        tok_label = "savings" if t_delta <= 0 else "increase"
        win.addstr(y, 1, f" Δ: {t_delta:+.0f}% token {tok_label} across iterations", tok_color)
        y += 2

        # ── Agent Completion Trend ─────────────────────────────────────────
        win.addstr(y, 1, " Agent Completion", curses.A_BOLD)
        y += 1

        c_values = [c * 100 for c in self.iterations.completion_trend]
        c_spark = sparkline(c_values, spark_w, min_v=0, max_v=100)
        win.addstr(y, 3, c_spark, curses.color_pair(1))
        y += 1

        comp_parts = []
        for ip in its:
            m = ip.metrics
            comp_parts.append(f"{ip.index}:{m.complete}/{m.total_agents}")
        win.addstr(y, 1, f" {'  '.join(comp_parts)}"[: w - 2])
        y += 2

        # ── Files Produced Trend ───────────────────────────────────────────
        win.addstr(y, 1, " Files Produced", curses.A_BOLD)
        y += 1

        f_values = [float(f) for f in self.iterations.file_trend]
        f_spark = sparkline(f_values, spark_w)
        win.addstr(y, 3, f_spark, curses.color_pair(4))
        y += 1

        file_parts = []
        for ip in its:
            file_parts.append(f"{ip.index}:{ip.metrics.files_produced}")
        win.addstr(y, 1, f" {'  '.join(file_parts)}"[: w - 2])
        y += 2

        # ── Per-Iteration Summary Table ────────────────────────────────────
        if y + len(its) + 2 < h:
            win.addstr(y, 1, "─" * (w - 2))
            y += 1
            win.addstr(y, 1, " Iteration Detail", curses.A_BOLD)
            y += 1

            # Header
            header = f" {'Iter':<6s} {'Agents':<8s} {'Tokens':>10s} {'Wall':>8s} {'Files':>6s} {'Quality':>10s}  ΔQuality"
            win.addstr(y, 1, header[: w - 2], curses.A_UNDERLINE)
            y += 1

            prev_q_detail = None
            for ip in its:
                if y >= h - 2:
                    break
                m = ip.metrics
                q_str = f"{m.quality_score:.4f}"
                if prev_q_detail is not None:
                    dq = m.quality_score - prev_q_detail
                    delta_str = f" {dq:+.4f}"
                    dq_color = curses.color_pair(1) if dq >= 0 else curses.color_pair(2)
                else:
                    delta_str = "  —"
                    dq_color = curses.A_NORMAL
                prev_q_detail = m.quality_score

                status_color = (
                    curses.color_pair(1) if m.errors == 0
                    else curses.color_pair(2)
                )
                line = (f" {ip.label:<6s} {m.complete}/{m.total_agents:<5s} "
                        f"{m.total_tokens:>10,} {m.elapsed_sec:>7.0f}s "
                        f"{m.files_produced:>5}  {q_str:>10s}{delta_str}")
                win.addstr(y, 1, line[: w - 2], status_color)
                win.addstr(y, 1 + len(line) - len(delta_str) if len(line) < w else w - len(delta_str) - 1,
                           delta_str, dq_color)
                y += 1

            # Total row
            if y < h - 1:
                total_tokens = sum(ip.metrics.total_tokens for ip in its)
                total_files = sum(ip.metrics.files_produced for ip in its)
                total_time = sum(ip.metrics.total_ms for ip in its) / 1000
                win.addstr(y, 1, f" {'TOTAL':<6s} {'':<8s} {total_tokens:>10,} {total_time:>7.0f}s "
                           f"{total_files:>5}  {'':>10s}", curses.A_BOLD)
                y += 1

        # Nav
        nav_parts = ["1:Summary", "2:Agents", "3:Tokens", "5:Trends"]
        if len(self.metrics) >= 2:
            nav_parts.insert(3, "4:Comparison")
        nav = "  " + "  ".join(nav_parts) + "  PgUp/PgDn:Scroll  q:Quit"
        win.addstr(h - 1, 1, nav[: w - 2], curses.color_pair(4))

    def _draw_footer(self) -> None:
        win = self.footer_win
        if not win:
            return
        win.erase()
        _, w = win.getmaxyx()

        if self.iterations and self.iterations.iterations:
            it = self.iterations
            line = (f" {len(it.iterations)} iterations | "
                    f"Quality: {it.quality_trend[0]:.4f} → {it.quality_trend[-1]:.4f} "
                    f"(Δ{it.quality_delta:+.4f}) | "
                    f"Tokens: Δ{it.token_delta_pct:+.0f}%")
        elif len(self.metrics) >= 2:
            line = f" HLF: {self.metrics[0].summary_line}  │  NL: {self.metrics[1].summary_line}"
        else:
            line = f" {self.metrics[0].summary_line}"
        win.addstr(0, 1, line[: w - 2], curses.color_pair(4))

        watch_marker = " ⏳ LIVE" if self.watch else ""
        if self.iterations and self.iterations.iterations:
            watch_marker = " 🔄 SELF-IMPROVING"
        win.addstr(1, w - len(watch_marker) - 2, watch_marker, curses.color_pair(3) | curses.A_BOLD)
        win.noutrefresh()


# ── CLI Entry Point ────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="HLF Self-Improving Swarm TUI — visualize swarm execution and quality trends.",
        prog="hlf-bench",
    )
    parser.add_argument(
        "metrics", nargs="*", help="Path(s) to metrics.json file(s). Two files enable comparison mode."
    )
    parser.add_argument(
        "--watch", "-w", action="store_true",
        help="Live mode: poll metrics file(s) for updates every 2 seconds.",
    )
    parser.add_argument(
        "--interval", "-i", type=float, default=2.0,
        help="Poll interval in seconds for --watch mode (default: 2.0).",
    )
    parser.add_argument(
        "--self-improve", "-s", type=str, default=None,
        help="Self-improving mode: path to directory containing multiple iterations.",
    )
    args = parser.parse_args()

    # Load iterations if self-improving mode
    iterations: Optional[IterationSeries] = None

    if args.self_improve:
        if not os.path.isdir(args.self_improve):
            print(f"Error: not a directory: {args.self_improve}", file=sys.stderr)
            sys.exit(1)
        iterations = IterationSeries.from_directory(args.self_improve)
        if not iterations.iterations:
            print(f"Error: no iterations found in {args.self_improve}", file=sys.stderr)
            sys.exit(1)
        print(f"Loaded {len(iterations.iterations)} iterations from {args.self_improve}")
        # Use the last iteration as primary metrics for summary view
        last_iter = iterations.iterations[-1].metrics
        loaded = [last_iter]
        # If we have enough iterations, show the first one as comparison
        if len(iterations.iterations) >= 2:
            loaded.append(iterations.iterations[0].metrics)
    elif args.metrics:
        loaded: list[BenchmarkMetrics] = []
        # Auto-detect: if a single argument is a directory, enter self-improve mode
        if len(args.metrics) == 1 and os.path.isdir(args.metrics[0]):
            iterations = IterationSeries.from_directory(args.metrics[0])
            if iterations.iterations:
                print(f"Auto-detected directory with {len(iterations.iterations)} iterations")
                last_iter = iterations.iterations[-1].metrics
                loaded = [last_iter]
                if len(iterations.iterations) >= 2:
                    loaded.append(iterations.iterations[0].metrics)
            else:
                print(f"Error: no iterations found in {args.metrics[0]}", file=sys.stderr)
                sys.exit(1)
        else:
            for path in args.metrics:
                if not os.path.isfile(path):
                    print(f"Error: file not found: {path}", file=sys.stderr)
                    sys.exit(1)
                try:
                    loaded.append(BenchmarkMetrics.from_file(path))
                except json.JSONDecodeError as e:
                    print(f"Error: invalid JSON in {path}: {e}", file=sys.stderr)
                    sys.exit(1)

        if not loaded:
            print("Error: no valid metrics files provided.", file=sys.stderr)
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)

    app = BenchTUI(loaded, watch=args.watch, interval=args.interval, iterations=iterations)
    app.run()


if __name__ == "__main__":
    main()
