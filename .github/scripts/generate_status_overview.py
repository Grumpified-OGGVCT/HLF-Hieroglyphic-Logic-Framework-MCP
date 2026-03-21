from __future__ import annotations

import argparse
import html
import json
import os
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = REPO_ROOT / "docs"

DASHBOARD_GLOB = "HLF_INTERNAL_READINESS_DASHBOARD_*.md"
SCORECARD_GLOB = "HLF_PILLAR_READINESS_SCORECARD_*.md"
MERGE_READINESS_DOC = DOCS_DIR / "HLF_MERGE_READINESS_SUMMARY_2026-03-20.md"
CLAIMS_LEDGER_DOC = DOCS_DIR / "HLF_BRANCH_AWARE_CLAIMS_LEDGER_2026-03-20.md"

MARKDOWN_OUTPUT = DOCS_DIR / "HLF_STATUS_OVERVIEW.md"
HTML_OUTPUT = DOCS_DIR / "index.html"
MERGE_HTML_OUTPUT = DOCS_DIR / "merge-readiness.html"
CLAIMS_HTML_OUTPUT = DOCS_DIR / "claims-ledger.html"
CSS_PATH = "assets/status-site.css"
DOCS_BLOB_BASE = (
    "https://github.com/Grumpified-OGGVCT/HLF-Hieroglyphic-Logic-Framework-MCP/blob/main/docs"
)


def _docs_blob_href(filename: str) -> str:
    return f"{DOCS_BLOB_BASE}/{filename}"


def _docs_blob_href(filename: str) -> str:
    repo = str(os.getenv("GITHUB_REPOSITORY", "")).strip()
    normalized = filename.lstrip("/")
    if repo:
        override_ref = os.getenv("STATUS_DOCS_REF") or os.getenv("DOCS_REF")
        branch = str(
            override_ref or os.getenv("GITHUB_BASE_REF") or os.getenv("GITHUB_REF_NAME") or "main"
        ).strip()
        return f"https://github.com/{repo}/blob/{branch}/docs/{normalized}"
    return normalized


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _write_if_changed(path: Path, content: str) -> bool:
    current = path.read_text(encoding="utf-8") if path.exists() else None
    if current == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def _extract_date_key(path: Path) -> tuple[int, int, int]:
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})", path.name)
    if not match:
        return (0, 0, 0)
    return tuple(int(value) for value in match.groups())


def _load_latest_doc(docs_dir: Path, glob_pattern: str) -> Path:
    candidates = sorted(docs_dir.glob(glob_pattern), key=_extract_date_key)
    if not candidates:
        raise FileNotFoundError(f"no docs matched {glob_pattern}")
    return candidates[-1]


def _load_doc_history(docs_dir: Path, glob_pattern: str) -> list[Path]:
    return sorted(docs_dir.glob(glob_pattern), key=_extract_date_key)


def _doc_timestamp(path: Path) -> datetime:
    year, month, day = _extract_date_key(path)
    if year == 0:
        return datetime(1970, 1, 1, tzinfo=UTC)
    return datetime(year, month, day, tzinfo=UTC)


def _extract_section(text: str, heading: str) -> str:
    lines = text.splitlines()
    try:
        start = next(index for index, line in enumerate(lines) if line.strip() == heading)
    except StopIteration as exc:
        raise ValueError(f"missing heading: {heading}") from exc

    level = len(heading) - len(heading.lstrip("#"))
    collected: list[str] = []
    heading_pattern = re.compile(rf"^#{{1,{level}}}\s+")

    for line in lines[start + 1 :]:
        if heading_pattern.match(line):
            break
        collected.append(line)
    return "\n".join(collected).strip("\n")


def _extract_labeled_block(text: str, label: str) -> str:
    lines = text.splitlines()
    try:
        start = next(index for index, line in enumerate(lines) if line.strip() == label)
    except StopIteration as exc:
        raise ValueError(f"missing label: {label}") from exc

    collected: list[str] = []
    for line in lines[start + 1 :]:
        stripped = line.strip()
        if stripped.startswith("## ") or (
            stripped.endswith(":") and not stripped.startswith(("-", "1.", "2.", "3."))
        ):
            break
        collected.append(line)
    return "\n".join(collected).strip("\n")


def _extract_section_or_label(text: str, *, heading: str, label: str) -> str:
    try:
        return _extract_section(text, heading)
    except ValueError:
        return _extract_labeled_block(text, label)


def _parse_markdown_table(section: str) -> list[dict[str, str]]:
    rows = [line.strip() for line in section.splitlines() if line.strip().startswith("|")]
    if len(rows) < 3:
        return []
    headers = [cell.strip() for cell in rows[0].strip("|").split("|")]
    parsed: list[dict[str, str]] = []
    for line in rows[2:]:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != len(headers):
            continue
        parsed.append(dict(zip(headers, cells, strict=True)))
    return parsed


def _replace_inline_code(text: str) -> str:
    return re.sub(r"`([^`]+)`", lambda match: f"<code>{html.escape(match.group(1))}</code>", text)


def _inline_html(text: str) -> str:
    return _replace_inline_code(html.escape(text))


def _clean_value(value: str) -> str:
    return value.replace("`", "").strip()


def _format_percent(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.1f}%"


def _format_delta(value: float) -> str:
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.1f} pts"


def _normalize_relative(path: Path, base_path: Path = REPO_ROOT) -> str:
    return path.relative_to(base_path).as_posix()


def _tracked_repo_files(repo_root: Path) -> set[str] | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "ls-files"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return {line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()}


def _parse_dashboard(path: Path, repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    text = _read_text(path)

    top_level_rows = _parse_markdown_table(_extract_section(text, "## Top-Level Indices"))
    cluster_rows = _parse_markdown_table(_extract_section(text, "## Cluster View"))
    pillar_rows = _parse_markdown_table(_extract_section(text, "### Per-Pillar Readiness"))

    overall_row = next(row for row in top_level_rows if row["Index"] == "Overall repo readiness")
    strongest_cluster = max(
        cluster_rows,
        key=lambda row: float(_clean_value(row["Score"]).rstrip("%")),
    )
    weakest_cluster = min(
        cluster_rows,
        key=lambda row: float(_clean_value(row["Score"]).rstrip("%")),
    )

    return {
        "path": _normalize_relative(path, repo_root),
        "overall_readiness": float(_clean_value(overall_row["Score"]).rstrip("%")),
        "interpretation_band": _clean_value(overall_row["Reading"]),
        "clusters": [
            {
                "name": row["Cluster"],
                "score": float(_clean_value(row["Score"]).rstrip("%")),
                "reading": row["Reading"],
            }
            for row in cluster_rows
        ],
        "pillars": [
            {
                "name": row["Pillar"],
                "score": float(_clean_value(row["Score"]).rstrip("%")),
            }
            for row in pillar_rows
        ],
        "strongest_cluster": strongest_cluster["Cluster"],
        "weakest_cluster": weakest_cluster["Cluster"],
    }


def _parse_scorecard(path: Path, repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    text = _read_text(path)
    strongest_rows = _parse_markdown_table(_extract_section(text, "## Strongest Pillars"))
    weakest_rows = _parse_markdown_table(_extract_section(text, "## Weakest Pillars"))
    weighted_match = re.search(r"- `([0-9.]+%)`", _extract_section(text, "## Weighted Result"))
    if weighted_match is None:
        raise ValueError("missing weighted result")

    return {
        "path": _normalize_relative(path, repo_root),
        "weighted_result": float(weighted_match.group(1).rstrip("%")),
        "strongest": [
            {
                "pillar": row["Pillar"],
                "score": float(_clean_value(row["Score"]).rstrip("%")),
                "reading": row["Why it leads"],
            }
            for row in strongest_rows
        ],
        "weakest": [
            {
                "pillar": row["Pillar"],
                "score": float(_clean_value(row["Score"]).rstrip("%")),
                "reading": row["Why it lags"],
            }
            for row in weakest_rows
        ],
    }


def _load_artifact(path: Path, repo_root: Path = REPO_ROOT) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    payload["_artifact_path"] = _normalize_relative(path, repo_root)
    return payload


def _artifact_timestamp(artifact: dict[str, Any]) -> datetime:
    generated_at = artifact.get("generated_at") or "1970-01-01T00:00:00+00:00"
    return datetime.fromisoformat(str(generated_at).replace("Z", "+00:00"))


def _artifact_metric(artifact: dict[str, Any]) -> dict[str, Any]:
    review_metadata = (artifact.get("governed_review") or {}).get("review_metadata") or {}
    workflow_payload = artifact.get("workflow_payload") or {}
    percent_covered = review_metadata.get("percent_covered")
    if isinstance(percent_covered, (int, float)):
        return {
            "kind": "percent_covered",
            "value": float(percent_covered),
            "display": _format_percent(float(percent_covered)),
        }

    drift_detected = review_metadata.get("drift_detected")
    if isinstance(drift_detected, bool):
        return {
            "kind": "drift_detected",
            "value": drift_detected,
            "display": "drift detected" if drift_detected else "no measured drift",
        }

    doc_drift = workflow_payload.get("doc_drift") or {}
    if isinstance(doc_drift.get("drift_detected"), bool):
        drift_value = bool(doc_drift["drift_detected"])
        return {
            "kind": "drift_detected",
            "value": drift_value,
            "display": "drift detected" if drift_value else "no measured drift",
        }

    return {"kind": "summary_only", "value": None, "display": "summary-only"}


def _summarize_lane_reading(artifact: dict[str, Any]) -> str:
    governed_review = artifact.get("governed_review") or {}
    summary = governed_review.get("summary")
    if isinstance(summary, str) and summary.strip():
        return summary.strip()
    return "No governed review summary available."


def _build_lane_trend(latest: dict[str, Any], previous: dict[str, Any] | None) -> dict[str, str]:
    latest_metric = _artifact_metric(latest)
    latest_display = latest_metric["display"]
    if previous is None:
        return {
            "current": latest_display,
            "previous": "n/a",
            "movement": "baseline",
            "reading": "first committed replay for this lane",
        }

    previous_metric = _artifact_metric(previous)
    previous_display = previous_metric["display"]

    if latest_metric["kind"] == "percent_covered" and previous_metric["kind"] == "percent_covered":
        delta = float(latest_metric["value"]) - float(previous_metric["value"])
        movement = "flat" if abs(delta) < 0.05 else _format_delta(delta)
        if abs(delta) < 0.05:
            reading = "coverage is effectively flat versus the previous committed replay"
        elif delta > 0:
            reading = "coverage improved versus the previous committed replay"
        else:
            reading = "coverage regressed versus the previous committed replay"
        return {
            "current": latest_display,
            "previous": previous_display,
            "movement": movement,
            "reading": reading,
        }

    if latest_metric["kind"] == "percent_covered" and previous_metric["kind"] != "percent_covered":
        return {
            "current": latest_display,
            "previous": previous_display,
            "movement": "recovered",
            "reading": "latest replay restored a comparable coverage signal after an earlier incomplete result",
        }

    if latest_metric["kind"] == "drift_detected" and previous_metric["kind"] == "drift_detected":
        changed = latest_metric["value"] != previous_metric["value"]
        if changed:
            reading = "lane status changed between drift and no-drift across the last two replays"
            movement = "changed"
        else:
            reading = "lane remained stable across the last two committed replays"
            movement = "stable"
        return {
            "current": latest_display,
            "previous": previous_display,
            "movement": movement,
            "reading": reading,
        }

    return {
        "current": latest_display,
        "previous": previous_display,
        "movement": "qualitative",
        "reading": "lane exposes governed evidence, but not a directly comparable numeric series",
    }


def _collect_weekly_lanes(repo_root: Path) -> list[dict[str, Any]]:
    tracked_files = _tracked_repo_files(repo_root)
    artifacts_by_source: dict[str, list[dict[str, Any]]] = {}
    for path in sorted(
        (repo_root / "observability" / "local_validation").glob("**/weekly-*-artifact.json")
    ):
        artifact_path = _normalize_relative(path, repo_root)
        if tracked_files is not None and artifact_path not in tracked_files:
            continue
        artifact = _load_artifact(path, repo_root)
        if artifact is None:
            continue
        source = str(artifact.get("source") or path.stem)
        artifacts_by_source.setdefault(source, []).append(artifact)

    lanes: list[dict[str, Any]] = []
    for source, artifacts in sorted(artifacts_by_source.items()):
        ordered = sorted(artifacts, key=_artifact_timestamp)
        latest = ordered[-1]
        previous = ordered[-2] if len(ordered) > 1 else None
        governed_review = latest.get("governed_review") or {}
        lanes.append(
            {
                "source": source,
                "status": str(latest.get("artifact_status") or "unknown"),
                "summary": _summarize_lane_reading(latest),
                "owner_persona": str(governed_review.get("owner_persona") or "unknown"),
                "triage_lane": str(governed_review.get("recommended_triage_lane") or "unknown"),
                "artifact_path": str(latest.get("_artifact_path") or ""),
                "generated_at": str(latest.get("generated_at") or ""),
                "trend": _build_lane_trend(latest, previous),
            }
        )
    return lanes


def _collect_readiness_trend(docs_dir: Path) -> dict[str, str]:
    history_paths = _load_doc_history(docs_dir, DASHBOARD_GLOB)
    repo_root = docs_dir.parent
    current_path = history_paths[-1]
    current_data = _parse_dashboard(current_path, repo_root)
    if len(history_paths) == 1:
        return {
            "current": _format_percent(current_data["overall_readiness"]),
            "previous": "n/a",
            "movement": "baseline",
            "reading": "first committed readiness snapshot in the current docs set",
        }

    previous_data = _parse_dashboard(history_paths[-2], repo_root)
    delta = current_data["overall_readiness"] - previous_data["overall_readiness"]
    if abs(delta) < 0.05:
        movement = "flat"
        reading = "overall readiness is materially unchanged versus the prior committed snapshot"
    elif delta > 0:
        movement = _format_delta(delta)
        reading = "overall readiness improved versus the prior committed snapshot"
    else:
        movement = _format_delta(delta)
        reading = "overall readiness declined versus the prior committed snapshot"

    return {
        "current": _format_percent(current_data["overall_readiness"]),
        "previous": _format_percent(previous_data["overall_readiness"]),
        "movement": movement,
        "reading": reading,
    }


def _collect_generated_at(
    dashboard_path: Path,
    scorecard_path: Path,
    lanes: list[dict[str, Any]],
) -> str:
    timestamps = [_doc_timestamp(dashboard_path), _doc_timestamp(scorecard_path)]
    for lane in lanes:
        generated_at = lane.get("generated_at")
        if isinstance(generated_at, str) and generated_at:
            timestamps.append(datetime.fromisoformat(generated_at.replace("Z", "+00:00")))
    latest = max(timestamps)
    return latest.isoformat().replace("+00:00", "Z")


def collect_status_data(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    docs_dir = repo_root / "docs"
    dashboard_path = _load_latest_doc(docs_dir, DASHBOARD_GLOB)
    scorecard_path = _load_latest_doc(docs_dir, SCORECARD_GLOB)
    dashboard = _parse_dashboard(dashboard_path, repo_root)
    scorecard = _parse_scorecard(scorecard_path, repo_root)
    lanes = _collect_weekly_lanes(repo_root)

    strongest_pillar = scorecard["strongest"][0]
    weakest_pillar = scorecard["weakest"][0]

    return {
        "generated_at": _collect_generated_at(dashboard_path, scorecard_path, lanes),
        "dashboard": dashboard,
        "scorecard": scorecard,
        "lanes": lanes,
        "readiness_trend": _collect_readiness_trend(docs_dir),
        "strongest_pillar": strongest_pillar,
        "weakest_pillar": weakest_pillar,
        "source_materials": [
            "SSOT_HLF_MCP.md",
            dashboard["path"],
            scorecard["path"],
            "docs/HLF_READINESS_SCORING_MODEL.md",
            "docs/HLF_READINESS_REFRESH_PROCEDURE.md",
            "docs/HLF_MERGE_READINESS_SUMMARY_2026-03-20.md",
            "docs/HLF_BRANCH_AWARE_CLAIMS_LEDGER_2026-03-20.md",
        ],
    }


def render_status_overview_markdown(data: dict[str, Any]) -> str:
    dashboard = data["dashboard"]
    scorecard = data["scorecard"]
    lanes = data["lanes"]
    strongest_cluster = dashboard["strongest_cluster"].lower()
    weakest_cluster = dashboard["weakest_cluster"].lower()
    readiness_trend = data["readiness_trend"]

    cluster_rows = "\n".join(
        f"| {row['name']} | `{row['score']:.1f}%` | {row['reading']} |"
        for row in dashboard["clusters"]
    )
    strongest_rows = "\n".join(
        f"| Strongest | {row['pillar']} | `{row['score']:.1f}%` | {row['reading']} |"
        for row in scorecard["strongest"]
    )
    weakest_rows = "\n".join(
        f"| Weakest | {row['pillar']} | `{row['score']:.1f}%` | {row['reading']} |"
        for row in scorecard["weakest"]
    )
    pillar_rows = "\n".join(
        f"| {row['name']} | `{row['score']:.1f}%` |" for row in dashboard["pillars"]
    )
    weekly_rows = (
        "\n".join(
            f"| `{lane['source']}` | {lane['summary']} | `{lane['owner_persona']}` | `{lane['triage_lane']}` | `{lane['status']}` | `{lane['artifact_path']}` |"
            for lane in lanes
        )
        if lanes
        else "| `_No committed weekly artifacts were found in this checkout._` | - | - | - | `informational` | `local-only` |"
    )
    trend_rows = "\n".join(
        [
            f"| Overall readiness | `{readiness_trend['current']}` | `{readiness_trend['previous']}` | `{readiness_trend['movement']}` | {readiness_trend['reading']} |"
        ]
        + [
            f"| `{lane['source']}` | `{lane['trend']['current']}` | `{lane['trend']['previous']}` | `{lane['trend']['movement']}` | {lane['trend']['reading']} |"
            for lane in lanes
        ]
    )
    source_rows = "\n".join(f"- `{path}`" for path in data["source_materials"])

    lines = [
        "# HLF Status Overview",
        "",
        "This page is the published status surface for the repository.",
        "",
        "It is a generated presentation layer over the repo's current source materials, not a replacement for them.",
        "",
        "Reading rule:",
        "",
        "- use this page for a compact status view across the whole repo",
        "- use `SSOT_HLF_MCP.md` for current packaged truth",
        "- use the readiness dashboard and scorecard for the underlying internal scoring inputs",
        "- use weekly artifacts and governed reviews for operational evidence",
        "",
        "This page intentionally separates three bands that should not be flattened into one metric:",
        "",
        "1. current repo status",
        "2. weekly operational evidence",
        "3. bridge/readiness progress",
        "",
        "## Status Snapshot",
        "",
        "> Summary block",
        ">",
        f"> - overall internal readiness: `{dashboard['overall_readiness']:.1f}%`",
        f"> - interpretation band: `{dashboard['interpretation_band']}`",
        f"> - strongest cluster: {strongest_cluster}",
        f"> - main drag on total readiness: {weakest_cluster}",
        "> - claim-lane reading: current packaged truth is real and substantial, while broader HLF completion remains bridge work rather than finished product truth",
        "",
        "Short reading:",
        "",
        "HLF in this repo is already materially real as a packaged language, runtime, governance, and MCP product surface.",
        "It is not yet the full recovered HLF system.",
        "The right public reading is therefore:",
        "",
        "- current packaged truth is strong enough to inspect and use now",
        "- weekly governance evidence is real and operational",
        "- broader coordination, operator, and ecosystem completion is still in active bridge work",
        "",
        "## 1. Whole HLF Status",
        "",
        "This section answers one question:",
        "",
        "what is the repo as a whole, in honest claim-lane terms?",
        "",
        "### Current Reading",
        "",
        "| Status Signal | Current Reading |",
        "| --- | --- |",
        f"| Overall readiness | `{dashboard['overall_readiness']:.1f}%` |",
        f"| Interpretation band | `{dashboard['interpretation_band']}` |",
        "| Claim-lane label | current packaged truth plus bridge-qualified expansion |",
        "| One-sentence repo status | the repo already has a strong semantic and governance core, but the broader coordination-and-operator zone still suppresses total readiness |",
        "",
        "### Cluster Scores",
        "",
        "| Cluster | Score | Reading |",
        "| --- | ---: | --- |",
        cluster_rows,
        "",
        "### Claim-Lane Note",
        "",
        "This top-line score is an internal readiness indicator.",
        "",
        "It is not a claim that the whole HLF target is complete.",
        "",
        "Use it to understand repo posture, not to erase the distinction between:",
        "",
        "- what is implemented now",
        "- what is proved in weekly operation",
        "- what is still under bridge recovery",
        "",
        "### Current-Truth Anchor",
        "",
        "For the strict current-truth surface behind this section, read:",
        "",
        "- `SSOT_HLF_MCP.md`",
        "- `docs/HLF_MERGE_READINESS_SUMMARY_2026-03-20.md`",
        "- `docs/HLF_BRANCH_AWARE_CLAIMS_LEDGER_2026-03-20.md`",
        "",
        "## 2. Trend Snapshot",
        "",
        "This section answers one question:",
        "",
        "what is actually moving, and what is only a baseline so far?",
        "",
        "| Signal | Current | Previous | Movement | Reading |",
        "| --- | ---: | ---: | --- | --- |",
        trend_rows,
        "",
        "Trend reading rule:",
        "",
        "- use deltas where the repo exposes a directly comparable metric",
        "- use categorical movement where the lane reports state rather than percent",
        "- treat `baseline` rows as the current committed starting point, not as missing work",
        "",
        "## 3. Weekly Operational Results",
        "",
        "This section answers one question:",
        "",
        "what did the system actually do in its latest governed weekly lanes?",
        "",
        "These results are evidence summaries, not completion claims.",
        "",
        "### Latest Weekly Lanes",
        "",
        "| Lane | Latest Reading | Owner Persona | Triage Lane | Status | Artifact Path |",
        "| --- | --- | --- | --- | --- | --- |",
        weekly_rows,
        "",
        "_Note: Artifact paths under `observability/local_validation/...` are example/local-only locations used for governed runs and are not checked into this repository._",
        "",
        "### Why Weekly Results Are Separate",
        "",
        "Weekly evidence should not be collapsed into the top-level readiness percent.",
        "",
        "Different weekly lanes report different kinds of truth:",
        "",
        "- percentage-backed health readings",
        "- drift/no-drift findings",
        "- advisory vs verified outcomes",
        "- persona ownership and triage signals",
        "",
        "That variation is useful.",
        "Flattening it into one number would hide the difference between system health, documentation accuracy, and governed operator review.",
        "",
        "## 4. Build Percentages And Pillar Readiness",
        "",
        "This section answers one question:",
        "",
        "where is the repo strongest, and where is it still weakest?",
        "",
        "### Strongest And Weakest Areas",
        "",
        "| Type | Pillar | Score | Reading |",
        "| --- | --- | ---: | --- |",
        strongest_rows,
        weakest_rows,
        "",
        "### Per-Pillar Readiness",
        "",
        "| Pillar | Readiness |",
        "| --- | ---: |",
        pillar_rows,
        "",
        "### How To Read These Percentages",
        "",
        "These percentages are downstream of three things:",
        "",
        "- implementation saturation",
        "- proof saturation",
        "- operational integration",
        "",
        "They are meant to show where the repo is strong or weak in practice.",
        "",
        "They are not meant to imply that a single percentage can summarize the whole HLF story.",
        "",
        "## 5. What Moves The Score Next",
        "",
        "The next score-moving work is not in the already-strong language core.",
        "",
        "The highest-value remaining moves are:",
        "",
        "1. strengthen typed effect and capability contracts",
        "2. deepen formal verification and routing proof",
        "3. raise orchestration from partial lifecycle presence into stronger packaged coordination proof",
        "4. convert persona/operator doctrine into thicker workflow and runtime evidence",
        "5. keep memory governance and weekly evidence contracts converging without fragmenting the trust surface",
        "",
        "## 6. Source Materials Behind This Page",
        "",
        "This page is derived from these repo authorities:",
        "",
        source_rows,
        "",
        "## 7. Interpretation Boundary",
        "",
        "If you need the safest summary of this page, use this sentence:",
        "",
        "HLF in this repo already has a strong current packaged core and real weekly governed evidence, while broader coordination, operator, and ecosystem completion remains bridge-qualified rather than finished.",
        "",
        f"_Generated from repo sources on {data['generated_at']}._",
        "",
    ]
    return "\n".join(lines)


def _render_nav_links() -> str:
    links = [
        ("Status Overview", "index.html"),
        ("Merge Readiness", "merge-readiness.html"),
        ("Claims Ledger", "claims-ledger.html"),
        ("Vision", _docs_blob_href("HLF_VISION_PLAIN_LANGUAGE.md")),
        ("MCP Positioning", _docs_blob_href("HLF_MCP_POSITIONING.md")),
    ]
    return "\n".join(
        f'<a class="top-link" href="{html.escape(target)}">{html.escape(label)}</a>'
        for label, target in links
    )


def _lane_key(value: str) -> str:
    lowered = value.lower()
    if "current-true" in lowered or "current packaged truth" in lowered or "real now" in lowered:
        return "current"
    if "bridge" in lowered or "improved in branch" in lowered:
        return "bridge"
    if "still-open" in lowered or "open" in lowered or "missing" in lowered:
        return "open"
    if "safe to claim" in lowered or "publicly" in lowered:
        return "safe"
    if "risk" in lowered:
        return "risk"
    return "neutral"


def _verdict_key(value: str) -> str:
    lowered = value.lower()
    if "overstated" in lowered:
        return "overstated"
    if "valid" in lowered:
        return "valid"
    if "resolved" in lowered:
        return "resolved"
    if "open" in lowered:
        return "open"
    return "neutral"


def _score_tone(score: float) -> str:
    if score >= 70.0:
        return "strong"
    if score >= 50.0:
        return "bridge"
    return "open"


def _truncate_text(value: str, limit: int = 150) -> str:
    stripped = value.strip()
    if len(stripped) <= limit:
        return stripped
    return stripped[: limit - 1].rstrip() + "..."


def _first_nonempty(items: list[str], fallback: str) -> str:
    for item in items:
        if item.strip():
            return item.strip()
    return fallback


def _parse_percent_text(value: str) -> float | None:
    stripped = value.strip()
    if stripped.endswith("%"):
        try:
            return float(stripped.rstrip("%"))
        except ValueError:
            return None
    return None


def _render_chip(label: str, tone: str, *, subtle: bool = False) -> str:
    subtle_class = " chip-subtle" if subtle else ""
    return (
        f'<span class="verdict-chip verdict-{html.escape(tone)}{subtle_class}">'
        f"{html.escape(label)}"
        "</span>"
    )


def _render_lane_band(
    title: str, detail: str, lane: str, *, eyebrow: str, supporting: str | None = None
) -> str:
    supporting_html = f'<p class="metric-text">{_inline_html(supporting)}</p>' if supporting else ""
    safe_lane = html.escape(lane)
    safe_eyebrow = html.escape(eyebrow)
    safe_title = html.escape(title)
    safe_detail = _inline_html(detail)
    chip = _render_chip(title, lane, subtle=True)
    return f"""
        <article class="lane-band lane-{safe_lane}">
            <div class="lane-band-head">
                <div>
                    <div class="metric-label">{safe_eyebrow}</div>
                    <h3>{safe_title}</h3>
                </div>
                {chip}
            </div>
            <p class="lane-detail">{safe_detail}</p>
            {supporting_html}
        </article>
        """.strip()


def _render_cluster_card_grid(clusters: list[dict[str, Any]]) -> str:
    cards = []
    for cluster in clusters:
        tone = _score_tone(cluster["score"])
        cards.append(
            """
            <article class="metric-card metric-card-scored metric-{tone}">
              <div class="metric-label">{name}</div>
              <div class="metric-value">{score:.1f}%</div>
              <div class="readiness-strip" style="--score:{score:.1f}%">
                <div class="readiness-strip-fill"></div>
                <div class="readiness-strip-marker"></div>
              </div>
              <p class="metric-text">{reading}</p>
            </article>
            """.format(
                tone=html.escape(tone),
                name=html.escape(cluster["name"]),
                score=cluster["score"],
                reading=html.escape(cluster["reading"]),
            ).strip()
        )
    return "\n".join(cards)


def _render_readiness_strips(
    rows: list[dict[str, Any]], *, name_key: str, score_key: str, reading_key: str
) -> str:
    rendered = []
    for row in rows:
        score = float(row[score_key])
        tone = _score_tone(score)
        name = html.escape(str(row[name_key]))
        reading = html.escape(str(row[reading_key]))
        rendered.append(
            f"""
            <article class="strip-row strip-{tone}" style="--score:{score:.1f}%">
              <div class="strip-header">
                <div class="strip-title">{name}</div>
                <div class="strip-value">{score:.1f}%</div>
              </div>
              <div class="readiness-strip">
                <div class="readiness-strip-fill"></div>
                <div class="readiness-strip-marker"></div>
              </div>
              <div class="strip-reading">{reading}</div>
            </article>
            """.strip()
        )
    return "\n".join(rendered)


def _render_governance_flow() -> str:
    steps = [
        (
            "Observe",
            "Evidence enters the governed lane as recorded operator or workflow truth.",
            "current",
        ),
        (
            "Propose",
            "Bridge work becomes explicit rather than implied by attractive wording.",
            "bridge",
        ),
        (
            "Verify",
            "Tests, audits, and provenance decide whether the proposal is promotable.",
            "safe",
        ),
        (
            "Promote",
            "Only the surfaces that earn current-truth wording move into public-safe claims.",
            "open",
        ),
    ]
    cards = "\n".join(
        f"""
                <article class="flow-step flow-{html.escape(tone)}">
                    <div class="flow-index">{index}</div>
                    <div>
                        <h3>{html.escape(title)}</h3>
                        <p class="metric-text">{html.escape(detail)}</p>
                    </div>
                </article>
                """.strip()
        for index, (title, detail, tone) in enumerate(steps, start=1)
    )
    return f"""
        <section class="panel span-12 panel-narrative">
            <div class="panel-heading">
                <h2>Governance Trust Path</h2>
                <span class="panel-kicker">Clarify trust, do not beautify ambiguity</span>
            </div>
            <div class="flow-grid">
                {cards}
            </div>
        </section>
        """.strip()


def _render_trend_micrographics(data: dict[str, Any]) -> str:
    rows = [{"signal": "Overall readiness", **data["readiness_trend"]}]
    rows.extend({"signal": lane["source"], **lane["trend"]} for lane in data["lanes"])
    rendered = []
    for row in rows:
        current_percent = _parse_percent_text(str(row["current"]))
        previous_percent = _parse_percent_text(str(row["previous"]))
        movement = str(row["movement"])
        movement_tone = "stable"
        if movement.startswith("+"):
            movement_tone = "up"
        elif movement.startswith("-"):
            movement_tone = "down"
        elif movement in {"baseline", "qualitative", "recovered"}:
            movement_tone = "baseline"
        track = """
        <div class="trend-track trend-{tone}"{style_attr}>
          <div class="trend-fill"></div>
          {previous_marker}
        </div>
        """
        if current_percent is None:
            style_attr = ""
            previous_marker = ""
        else:
            style_attr = f' style="--current:{current_percent:.1f}%;--previous:{(previous_percent if previous_percent is not None else current_percent):.1f}%"'
            previous_marker = (
                '<div class="trend-prev-marker"></div>' if previous_percent is not None else ""
            )
        rendered.append(
            track.format(
                tone=html.escape(movement_tone),
                style_attr=style_attr,
                previous_marker=previous_marker,
            ).strip()
        )
        rendered[-1] = """
        <article class="trend-card">
          <div class="trend-head">
            <div>
              <div class="metric-label">Signal</div>
              <div class="strip-title">{signal}</div>
            </div>
            {chip}
          </div>
          {track}
          <div class="trend-values">
            <span>Current {current}</span>
            <span>Previous {previous}</span>
          </div>
          <p class="metric-text">{reading}</p>
        </article>
        """.format(
            signal=html.escape(str(row["signal"])),
            chip=_render_chip(movement, movement_tone, subtle=True),
            track=rendered[-1],
            current=html.escape(str(row["current"])),
            previous=html.escape(str(row["previous"])),
            reading=html.escape(str(row["reading"])),
        ).strip()
    return "\n".join(rendered)


def _render_cluster_cards(clusters: list[dict[str, Any]]) -> str:
    return _render_cluster_card_grid(clusters)


def _render_weekly_rows(lanes: list[dict[str, Any]]) -> str:
    if not lanes:
        return "\n".join(
            [
                "<tr>",
                "  <td colspan=\"6\">No committed weekly artifacts were found in this checkout. Local-only governed runs may still exist outside the repository.</td>",
                "</tr>",
            ]
        )
    return "\n".join(
        f"""
        <tr>
          <td><span class="code-pill">{html.escape(lane["source"])}</span></td>
          <td>{html.escape(lane["summary"])}</td>
          <td><span class="code-pill">{html.escape(lane["owner_persona"])}</span></td>
          <td><span class="code-pill">{html.escape(lane["triage_lane"])}</span></td>
          <td><span class="verdict-chip verdict-{html.escape(lane["status"].lower())}">{html.escape(lane["status"])}</span></td>
          <td><span class="code-pill">{html.escape(lane["artifact_path"])}</span></td>
        </tr>
        """.strip()
        for lane in lanes
    )


def _render_trend_rows(data: dict[str, Any]) -> str:
    rows = [
        {
            "signal": "Overall readiness",
            **data["readiness_trend"],
        }
    ]
    rows.extend({"signal": lane["source"], **lane["trend"]} for lane in data["lanes"])
    return "\n".join(
        """
        <tr>
          <td>{signal}</td>
          <td>{current}</td>
          <td>{previous}</td>
          <td>{movement}</td>
          <td>{reading}</td>
        </tr>
        """.format(
            signal=html.escape(str(row["signal"])),
            current=html.escape(str(row["current"])),
            previous=html.escape(str(row["previous"])),
            movement=html.escape(str(row["movement"])),
            reading=html.escape(str(row["reading"])),
        ).strip()
        for row in rows
    )


def _render_pillar_rows(rows: list[dict[str, Any]], row_type: str) -> str:
    return "\n".join(
        """
        <tr>
          <td>{row_type}</td>
          <td>{pillar}</td>
          <td>{score:.1f}%</td>
          <td>{reading}</td>
        </tr>
        """.format(
            row_type=html.escape(row_type),
            pillar=html.escape(row["pillar"]),
            score=row["score"],
            reading=html.escape(row["reading"]),
        ).strip()
        for row in rows
    )


def _render_governance_flow() -> str:
    steps = [
        (
            "Observe",
            "Evidence enters the governed lane as recorded operator or workflow truth.",
            "current",
        ),
        (
            "Propose",
            "Bridge work becomes explicit rather than implied by attractive wording.",
            "bridge",
        ),
        (
            "Verify",
            "Tests, audits, and provenance decide whether the proposal is promotable.",
            "safe",
        ),
        (
            "Promote",
            "Only the surfaces that earn current-truth wording move into public-safe claims.",
            "open",
        ),
    ]
    cards = "\n".join(
        f"""
                <article class="flow-step flow-{html.escape(tone)}">
                    <div class="flow-index">{index}</div>
                    <div>
                        <h3>{html.escape(title)}</h3>
                        <p class="metric-text">{html.escape(detail)}</p>
                    </div>
                </article>
                """.strip()
        for index, (title, detail, tone) in enumerate(steps, start=1)
    )
    return f"""
        <section class="panel span-12 panel-narrative">
            <div class="panel-heading">
                <h2>Governance Trust Path</h2>
                <span class="panel-kicker">Clarify trust, do not beautify ambiguity</span>
            </div>
            <div class="flow-grid">
                {cards}
            </div>
            <p class="section-note">This is a static doctrinal explainer, not a claim that every upstream governance path is fully restored in packaged form.</p>
        </section>
        """.strip()


def _render_decision_panel(title: str, kicker: str, panels: list[dict[str, str]]) -> str:
    cards = "\n".join(
        f"""
                <article class="decision-card decision-{html.escape(panel["tone"])}">
                    <div class="decision-head">
                        <div class="metric-label">{html.escape(panel["label"])}</div>
                        {_render_chip(panel["chip_label"], panel["tone"], subtle=True)}
                    </div>
                    <h3>{_inline_html(panel["value"])}</h3>
                    <p class="metric-text">{_inline_html(panel["detail"])}</p>
                </article>
                """.strip()
        for panel in panels
    )
    return f"""
        <section class="panel span-12 panel-decision">
            <div class="panel-heading">
                <h2>{html.escape(title)}</h2>
                <span class="panel-kicker">{html.escape(kicker)}</span>
            </div>
            <div class="decision-grid">
                {cards}
            </div>
        </section>
        """.strip()


def _render_per_pillar_rows(pillars: list[dict[str, Any]]) -> str:
    return "\n".join(
        """
        <tr>
          <td>{name}</td>
          <td>{score:.1f}%</td>
        </tr>
        """.format(name=html.escape(row["name"]), score=row["score"]).strip()
        for row in pillars
    )


def _render_source_provenance(
    *,
    source_href: str,
    source_label: str,
    generated_at: str,
    authority_text: str,
) -> str:
    return f"""
        <section class="panel span-12 provenance-panel panel-provenance">
            <div class="panel-heading">
                <h2>Source Provenance</h2>
                <span class="panel-kicker">Operator-facing generation trace</span>
            </div>
            <div class="provenance-box">
                <div class="provenance-meta">
                    <span class="code-pill">markdown source</span>
                    <a class="top-link provenance-link" href="{source_href}">{source_label}</a>
                    <span class="code-pill">watermark {generated_at}</span>
                </div>
                <p class="section-note provenance-note">{authority_text}</p>
            </div>
        </section>
        """.strip()


def _render_dynamic_table(rows: list[dict[str, str]]) -> str:
    if not rows:
        return ""
    headers = list(rows[0].keys())
    head = "\n".join(f"<th>{html.escape(header)}</th>" for header in headers)
    body = "\n".join(
        "<tr>{cells}</tr>".format(
            cells="".join(
                f"<td>{_replace_inline_code(html.escape(row.get(header, '')))}</td>"
                for header in headers
            )
        )
        for row in rows
    )
    return f"""
        <div class="table-wrap compact-table">
            <table>
                <thead>
                    <tr>{head}</tr>
                </thead>
                <tbody>
                    {body}
                </tbody>
            </table>
        </div>
        """.strip()


def render_status_index_html(data: dict[str, Any]) -> str:
    dashboard = data["dashboard"]
    scorecard = data["scorecard"]
    status_lane_cards = "\n".join(
        [
            _render_lane_band(
                "Current-True",
                "Packaged language, runtime, governance, and MCP surfaces are materially real now.",
                "current",
                eyebrow="Lane reading",
                supporting=f"Strongest pillar: {data['strongest_pillar']['pillar']} at {data['strongest_pillar']['score']:.1f}%.",
            ),
            _render_lane_band(
                "Bridge-True",
                "Coordination, operator, and recovery work is real but still requires explicit qualification before promotion.",
                "bridge",
                eyebrow="Lane reading",
                supporting="Weekly governed evidence and branch-ready recovery work belong here until they earn stricter packaged truth.",
            ),
            _render_lane_band(
                "Still-Open",
                "Lower-scoring pillars are still architecture obligations, not aesthetic gaps to hide with polish.",
                "open",
                eyebrow="Lane reading",
                supporting=f"Weakest pillar: {data['weakest_pillar']['pillar']} at {data['weakest_pillar']['score']:.1f}%.",
            ),
        ]
    )
    pillar_strips = _render_readiness_strips(
        dashboard["pillars"],
        name_key="name",
        score_key="score",
        reading_key="name",
    )
    provenance = _render_source_provenance(
        source_href=_docs_blob_href("HLF_STATUS_OVERVIEW.md"),
        source_label="HLF_STATUS_OVERVIEW.md",
        generated_at=data["generated_at"],
        authority_text="This page is rendered from the generated markdown status source, which is itself derived from the repo authorities listed inside that markdown file.",
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>HLF Status Surface</title>
  <meta name="description" content="Compact public-safe status surface for HLF current truth, weekly evidence, and bridge readiness.">
  <link rel="stylesheet" href="{CSS_PATH}">
</head>
<body class="page-status">
  <div class="site-shell">
    <header class="site-header">
      <div class="eyebrow">HLF Status Surface</div>
      <div class="header-row">
        <div>
          <h1>Current truth, weekly evidence, and bridge readiness without flattening the repo.</h1>
          <p class="lede">This front door is presentation-only. It summarizes the packaged system, the latest governed weekly lanes, and the internal readiness baseline while keeping vision, current truth, and bridge work distinct.</p>
        </div>
        <div class="hero-card hero-card-status">
          <div class="hero-label">Overall readiness</div>
          <div class="hero-value">{dashboard["overall_readiness"]:.1f}%</div>
          <div class="hero-meta">{html.escape(dashboard["interpretation_band"])}</div>
          <p class="hero-text">Strongest cluster: {
        html.escape(dashboard["strongest_cluster"].lower())
    }. Main drag: {html.escape(dashboard["weakest_cluster"].lower())}.</p>
        </div>
      </div>
      <nav class="top-nav">
        {_render_nav_links()}
      </nav>
    </header>

    <main class="content-grid">
            <section class="panel span-12 panel-band">
                <div class="panel-heading">
                    <h2>Lane Reading Bands</h2>
                    <span class="panel-kicker">Current truth, bridge truth, and still-open posture</span>
                </div>
                <div class="lane-band-grid">
                    {status_lane_cards}
                </div>
            </section>

    <section class="panel span-8 panel-proof">
        <div class="panel-heading">
          <h2>Whole HLF Status</h2>
          <span class="panel-kicker">Current repo posture</span>
        </div>
        <div class="metric-grid">
          {_render_cluster_cards(dashboard["clusters"])}
        </div>
        <p class="section-note">Top-line readiness is an internal indicator. It helps operators read repo posture, but it does not collapse current truth, weekly proof, and bridge recovery into one completion claim.</p>
      </section>

    <section class="panel span-4 panel-brief">
        <div class="panel-heading">
                    <h2>Trend Micrographics</h2>
          <span class="panel-kicker">Only where comparison is honest</span>
        </div>
                <div class="trend-grid">
                    {_render_trend_micrographics(data)}
        </div>
      </section>

    <section class="panel span-12 panel-ledger">
        <div class="panel-heading">
          <h2>Weekly Operational Results</h2>
          <span class="panel-kicker">Governed evidence lanes</span>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Lane</th>
                <th>Latest reading</th>
                <th>Owner</th>
                <th>Triage</th>
                <th>Status</th>
                <th>Artifact</th>
              </tr>
            </thead>
            <tbody>
              {_render_weekly_rows(data["lanes"])}
            </tbody>
          </table>
        </div>
        <p class="section-note">Weekly rows are evidence summaries. They show live governed workflow behavior, but they are not stand-ins for whole-repo completion.</p>
        <p class="section-note">Artifact paths under <code>observability/local_validation/...</code> are example/local-only governed-run locations and are not checked into this repository.</p>
      </section>

    <section class="panel span-6 panel-brief">
        <div class="panel-heading">
          <h2>Strongest and Weakest Pillars</h2>
          <span class="panel-kicker">Where the repo actually leads or lags</span>
        </div>
        <div class="table-wrap compact-table">
          <table>
            <thead>
              <tr>
                <th>Type</th>
                <th>Pillar</th>
                <th>Score</th>
                <th>Reading</th>
              </tr>
            </thead>
            <tbody>
              {_render_pillar_rows(scorecard["strongest"], "Strongest")}
              {_render_pillar_rows(scorecard["weakest"], "Weakest")}
            </tbody>
          </table>
        </div>
      </section>

    <section class="panel span-6 panel-proof">
        <div class="panel-heading">
          <h2>Per-Pillar Readiness</h2>
                    <span class="panel-kicker">Readiness strips instead of flat score-only rows</span>
        </div>
                <div class="strip-grid">
                    {pillar_strips}
        </div>
                <p class="section-note">These strips remain evidence-backed score renderings. They do not replace the underlying readiness tables in the markdown authority.</p>
      </section>

            {
        _render_decision_panel(
            "Reviewer Decision Panel",
            "What a PR reader should conclude from the generated status front door",
            [
                {
                    "label": "What is real now",
                    "chip_label": "current-true",
                    "tone": "current",
                    "value": "Packaged HLF core is inspectable and usable now.",
                    "detail": _truncate_text(
                        _first_nonempty(
                            [cluster["reading"] for cluster in dashboard["clusters"]],
                            "Current packaged truth is present.",
                        )
                    ),
                },
                {
                    "label": "What is improved in branch",
                    "chip_label": "bridge-true",
                    "tone": "bridge",
                    "value": "Weekly evidence and operator recovery lanes sharpen branch posture.",
                    "detail": _truncate_text(
                        _first_nonempty(
                            [lane["summary"] for lane in data["lanes"]],
                            "Governed weekly evidence remains part of the branch signal.",
                        )
                    ),
                },
                {
                    "label": "What is still missing",
                    "chip_label": "still-open",
                    "tone": "open",
                    "value": data["weakest_pillar"]["pillar"],
                    "detail": _truncate_text(data["weakest_pillar"]["reading"]),
                },
                {
                    "label": "What is safe to claim publicly",
                    "chip_label": "claim-lane",
                    "tone": "safe",
                    "value": "Strong core, real evidence, unfinished recovery.",
                    "detail": "Public wording should keep packaged truth, weekly proof, and broader architectural recovery distinct.",
                },
            ],
        )
    }

            {_render_governance_flow()}

    <section class="panel span-12 panel-narrative">
        <div class="panel-heading">
          <h2>What Moves The Score Next</h2>
          <span class="panel-kicker">Bridge work with leverage</span>
        </div>
        <ol class="compact-list">
          <li>Strengthen typed effect and capability contracts.</li>
          <li>Deepen formal verification and routing proof.</li>
          <li>Raise orchestration from partial lifecycle presence into stronger packaged coordination proof.</li>
          <li>Convert persona and operator doctrine into thicker workflow and runtime evidence.</li>
          <li>Keep memory governance and weekly evidence contracts converging without fragmenting the trust surface.</li>
        </ol>
      </section>

            {provenance}
    </main>

    <footer class="site-footer">
                        <p>Public-safe presentation layer only. For strict packaged truth, use the repository root SSOT alongside the linked docs.</p>
    </footer>
  </div>
</body>
</html>
"""


def _parse_merge_readiness(path: Path, repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    text = _read_text(path)
    status_line = next(
        (line for line in text.splitlines() if line.startswith("Status:")),
        "Status: unavailable",
    )

    purpose_lines = [
        line[2:].strip()
        for line in _extract_section_or_label(
            text, heading="## Purpose", label="Purpose:"
        ).splitlines()
        if line.strip().startswith("-")
    ]
    verified_lines = [
        line[2:].strip()
        for line in _extract_section_or_label(
            text,
            heading="## Verified branch facts",
            label="Verified branch facts:",
        ).splitlines()
        if line.strip().startswith("-")
    ]

    section_order = [
        "## Current-True In This Checkout",
        "## Bridge-True But Real In This Branch",
        "## Still-Open Architectural Gaps",
        "## Near-Term Merge Risks",
        "## Merge Reading",
        "## Recommended Merge Framing",
    ]

    sections: list[dict[str, Any]] = []
    for heading in section_order:
        raw_body = _extract_section(text, heading)
        bullets = [
            line[2:].strip() for line in raw_body.splitlines() if line.strip().startswith("-")
        ]
        paragraphs = [
            paragraph.strip()
            for paragraph in raw_body.split("\n\n")
            if paragraph.strip()
            and not all(
                line.strip().startswith("-") for line in paragraph.splitlines() if line.strip()
            )
        ]
        sections.append(
            {
                "title": heading.replace("## ", ""),
                "paragraphs": paragraphs,
                "bullets": bullets,
            }
        )

    return {
        "path": _normalize_relative(path, repo_root),
        "status": status_line.replace("Status:", "").strip(),
        "purpose": purpose_lines,
        "verified": verified_lines,
        "sections": sections,
    }


def _render_bullet_list(items: list[str], class_name: str = "compact-list") -> str:
    if not items:
        return ""
    rendered = "\n".join(f"<li>{_inline_html(item)}</li>" for item in items)
    return f'<ul class="{class_name}">\n{rendered}\n</ul>'


def _render_paragraphs(paragraphs: list[str]) -> str:
    return "\n".join(f"<p>{_inline_html(paragraph)}</p>" for paragraph in paragraphs)


def _section_lookup(sections: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {section["title"]: section for section in sections}


def _render_merge_lane_cards(merge_data: dict[str, Any]) -> str:
    section_map = _section_lookup(merge_data["sections"])
    configs = [
        ("Current-True In This Checkout", "current", "Current-True"),
        ("Bridge-True But Real In This Branch", "bridge", "Bridge-True"),
        ("Still-Open Architectural Gaps", "open", "Still-Open"),
    ]
    cards: list[str] = []
    for section_title, tone, eyebrow in configs:
        section = section_map.get(section_title, {"paragraphs": [], "bullets": []})
        detail = _truncate_text(
            _first_nonempty(
                section.get("bullets", []),
                _first_nonempty(section.get("paragraphs", []), "No summary available."),
            ),
            180,
        )
        supporting = _truncate_text(
            _first_nonempty(
                section.get("paragraphs", []),
                "Lane remains intentionally bounded by the markdown authority.",
            ),
            160,
        )
        cards.append(
            _render_lane_band(section_title, detail, tone, eyebrow=eyebrow, supporting=supporting)
        )
    return "\n".join(cards)


def _parse_claims_ledger(path: Path, repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    text = _read_text(path)
    status_line = next(
        (line for line in text.splitlines() if line.startswith("Status:")),
        "Status: unavailable",
    )

    purpose_lines = [
        line[2:].strip()
        for line in _extract_labeled_block(text, "Purpose:").splitlines()
        if line.strip().startswith("-")
    ]
    reading_rule_lines = [
        line[2:].strip()
        for line in _extract_labeled_block(text, "Reading rule:").splitlines()
        if line.strip().startswith("-")
    ]
    verified_lines = [
        line[2:].strip()
        for line in _extract_labeled_block(text, "Verified branch facts used here:").splitlines()
        if line.strip().startswith("-")
    ]

    sections: list[dict[str, Any]] = []
    for heading, title in [
        ("## 1. Overstated Public Gaps", "Overstated Public Gaps"),
        ("## 2. Valid Public Gaps", "Valid Public Gaps"),
        ("## 3. Branch-Resolved Gaps", "Branch-Resolved Gaps"),
        ("## 4. Still-Open Architectural Gaps", "Still-Open Architectural Gaps"),
    ]:
        body = _extract_section(text, heading)
        sections.append({"title": title, "rows": _parse_markdown_table(body)})

    bottom_line = _extract_section(text, "## Bottom Line")
    bottom_paragraphs = [
        paragraph.strip()
        for paragraph in bottom_line.split("\n\n")
        if paragraph.strip()
        and not all(line.strip().startswith("-") for line in paragraph.splitlines() if line.strip())
    ]
    bottom_bullets = [
        line[2:].strip() for line in bottom_line.splitlines() if line.strip().startswith("-")
    ]

    return {
        "path": _normalize_relative(path, repo_root),
        "status": status_line.replace("Status:", "").strip(),
        "purpose": purpose_lines,
        "reading_rule": reading_rule_lines,
        "verified": verified_lines,
        "sections": sections,
        "bottom_line": {"paragraphs": bottom_paragraphs, "bullets": bottom_bullets},
    }


def render_merge_readiness_html(data: dict[str, Any], merge_data: dict[str, Any]) -> str:
    verified_cards = "\n".join(
        f'<article class="metric-card"><p class="metric-text">{_inline_html(item)}</p></article>'
        for item in merge_data["verified"]
    )
    section_map = _section_lookup(merge_data["sections"])
    provenance = _render_source_provenance(
        source_href=_docs_blob_href("HLF_MERGE_READINESS_SUMMARY_2026-03-20.md"),
        source_label="HLF_MERGE_READINESS_SUMMARY_2026-03-20.md",
        generated_at=data["generated_at"],
        authority_text="This page is rendered directly from the branch-aware merge-readiness markdown authority and should be read with claim-lane discipline intact.",
    )
    section_blocks = "\n".join(
        """
        <section class="panel span-6 {panel_class}">
            <div class="panel-heading">
                <h2>{title}</h2>
                <span class="panel-kicker">Merge lane summary</span>
            </div>
            {paragraphs}
            {bullets}
        </section>
        """.format(
            panel_class=(
                "panel-band"
                if section["title"]
                in {
                    "Current-True In This Checkout",
                    "Bridge-True But Real In This Branch",
                    "Still-Open Architectural Gaps",
                }
                else "panel-narrative"
            ),
            title=html.escape(section["title"]),
            paragraphs=_render_paragraphs(section["paragraphs"]),
            bullets=_render_bullet_list(section["bullets"]),
        ).strip()
        for section in merge_data["sections"]
    )
    decision_panel = _render_decision_panel(
        "Reviewer Decision Panel",
        "Compact PR-reader framing derived from the merge-readiness authority",
        [
            {
                "label": "What is real now",
                "chip_label": "current-true",
                "tone": "current",
                "value": _truncate_text(
                    _first_nonempty(
                        section_map.get("Current-True In This Checkout", {}).get("bullets", []),
                        "Current packaged truth is present.",
                    ),
                    100,
                ),
                "detail": _truncate_text(
                    _first_nonempty(
                        section_map.get("Current-True In This Checkout", {}).get("paragraphs", []),
                        "Present-tense packaged truth should stay explicit.",
                    ),
                    170,
                ),
            },
            {
                "label": "What is improved in branch",
                "chip_label": "bridge-true",
                "tone": "bridge",
                "value": _truncate_text(
                    _first_nonempty(
                        section_map.get("Bridge-True But Real In This Branch", {}).get(
                            "bullets", []
                        ),
                        "Bridge work is real in the checkout.",
                    ),
                    100,
                ),
                "detail": _truncate_text(
                    _first_nonempty(
                        section_map.get("Bridge-True But Real In This Branch", {}).get(
                            "paragraphs", []
                        ),
                        "Keep branch improvements qualified rather than inflated.",
                    ),
                    170,
                ),
            },
            {
                "label": "What is still missing",
                "chip_label": "still-open",
                "tone": "open",
                "value": _truncate_text(
                    _first_nonempty(
                        section_map.get("Still-Open Architectural Gaps", {}).get("bullets", []),
                        "Open architecture gaps remain.",
                    ),
                    100,
                ),
                "detail": _truncate_text(
                    _first_nonempty(
                        section_map.get("Still-Open Architectural Gaps", {}).get("paragraphs", []),
                        "Open work remains part of the reading.",
                    ),
                    170,
                ),
            },
            {
                "label": "What is safe to claim publicly",
                "chip_label": "public-safe",
                "tone": "safe",
                "value": _truncate_text(
                    _first_nonempty(
                        section_map.get("Recommended Merge Framing", {}).get("bullets", []),
                        "Use lane-qualified merge framing.",
                    ),
                    100,
                ),
                "detail": _truncate_text(
                    _first_nonempty(
                        section_map.get("Merge Reading", {}).get("bullets", []),
                        "Public wording should stay branch-aware and bounded.",
                    ),
                    170,
                ),
            },
        ],
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>HLF Merge Readiness</title>
    <meta name="description" content="Branch-aware merge readiness summary for HLF with current truth, bridge truth, and open architectural gaps.">
    <link rel="stylesheet" href="{CSS_PATH}">
</head>
<body class="page-merge">
    <div class="site-shell">
        <header class="site-header">
            <div class="eyebrow">HLF Merge Readiness</div>
            <div class="header-row">
                <div>
                    <h1>Branch-aware merge framing with current truth, bridge truth, and explicit remaining gaps.</h1>
                    <p class="lede">This page is a generated HTML view over the merge-readiness markdown source. It keeps the same public-safe visual standard as the status front door while preserving claim-lane discipline.</p>
                </div>
                <div class="hero-card hero-card-merge">
                    <div class="hero-label">Status</div>
                    <div class="hero-value hero-value-text">{html.escape(merge_data["status"])}</div>
                    <div class="hero-meta">branch-aware summary</div>
                    <p class="hero-text">Use this page to read what the branch can claim now, what remains bridge-qualified, and what still blocks architectural completion.</p>
                </div>
            </div>
            <nav class="top-nav">
                {_render_nav_links()}
            </nav>
        </header>

        <main class="content-grid">
            <section class="panel span-4 panel-brief">
                <div class="panel-heading">
                    <h2>Purpose</h2>
                    <span class="panel-kicker">Why this summary exists</span>
                </div>
                {_render_bullet_list(merge_data["purpose"])}
            </section>

            <section class="panel span-8 panel-proof">
                <div class="panel-heading">
                    <h2>Verified Branch Facts</h2>
                    <span class="panel-kicker">High-confidence branch state</span>
                </div>
                <div class="metric-grid metric-grid-verified">
                    {verified_cards}
                </div>
            </section>

            <section class="panel span-12 panel-band">
                <div class="panel-heading">
                    <h2>Lane Reading Bands</h2>
                    <span class="panel-kicker">Merge framing by claim lane</span>
                </div>
                <div class="lane-band-grid">
                    {_render_merge_lane_cards(merge_data)}
                </div>
            </section>

            {decision_panel}

            {section_blocks}

            {provenance}
        </main>

        <footer class="site-footer">
            <p>Public-safe presentation layer only. Use the markdown authority for exact branch wording and review context.</p>
        </footer>
    </div>
</body>
</html>
"""


def render_claims_ledger_html(data: dict[str, Any], claims_data: dict[str, Any]) -> str:
    verified_cards = "\n".join(
        f'<article class="metric-card"><p class="metric-text">{_inline_html(item)}</p></article>'
        for item in claims_data["verified"]
    )
    verdict_overview = "\n".join(
        """
        <article class="metric-card verdict-overview-card">
          <div class="metric-label">{title}</div>
          <div class="metric-value">{count}</div>
          <div class="verdict-chip-row">{chip}</div>
          <p class="metric-text">{detail}</p>
        </article>
        """.format(
            title=html.escape(section["title"]),
            count=len(section["rows"]),
            chip=_render_chip(section["title"], _verdict_key(section["title"])),
            detail=html.escape(
                f"{len(section['rows'])} branch-aware classifications in this lane."
            ),
        ).strip()
        for section in claims_data["sections"]
    )
    section_blocks = "\n".join(
        """
        <section class="panel span-12 panel-ledger">
            <div class="panel-heading">
                <div class="panel-heading-with-chip">
                    <h2>{title}</h2>
                    {chip}
                </div>
                <span class="panel-kicker">Branch-aware review table</span>
            </div>
            <p class="section-note">{note}</p>
            {table}
        </section>
        """.format(
            title=html.escape(section["title"]),
            chip=_render_chip(section["title"], _verdict_key(section["title"])),
            note=html.escape(
                f"{len(section['rows'])} classified statements remain grounded in the markdown ledger authority."
            ),
            table=_render_dynamic_table(section["rows"]),
        ).strip()
        for section in claims_data["sections"]
    )
    decision_panel = _render_decision_panel(
        "Reviewer Decision Panel",
        "How a branch reviewer should read the claims ledger",
        [
            {
                "label": "What is real now",
                "chip_label": "resolved",
                "tone": "resolved",
                "value": _truncate_text(
                    _first_nonempty(
                        claims_data["verified"], "Verified branch facts remain the grounding layer."
                    ),
                    100,
                ),
                "detail": "Verified branch facts anchor the ledger before any gap language is promoted.",
            },
            {
                "label": "What is improved in branch",
                "chip_label": "resolved",
                "tone": "resolved",
                "value": "Branch-resolved gaps are no longer accurate for this checkout.",
                "detail": f"{len(next((section['rows'] for section in claims_data['sections'] if section['title'] == 'Branch-Resolved Gaps'), []))} rows currently sit in the resolved lane.",
            },
            {
                "label": "What is still missing",
                "chip_label": "open",
                "tone": "open",
                "value": "Still-open gaps remain constitutive architecture work.",
                "detail": f"{len(next((section['rows'] for section in claims_data['sections'] if section['title'] == 'Still-Open Architectural Gaps'), []))} rows remain explicitly open.",
            },
            {
                "label": "What is safe to claim publicly",
                "chip_label": "claim-lane",
                "tone": "safe",
                "value": "Resolve stale gap claims without declaring full completion.",
                "detail": _truncate_text(
                    _first_nonempty(
                        claims_data["reading_rule"],
                        "Use claim-lane discipline when reusing wording.",
                    ),
                    170,
                ),
            },
        ],
    )
    provenance = _render_source_provenance(
        source_href=_docs_blob_href("HLF_BRANCH_AWARE_CLAIMS_LEDGER_2026-03-20.md"),
        source_label="HLF_BRANCH_AWARE_CLAIMS_LEDGER_2026-03-20.md",
        generated_at=data["generated_at"],
        authority_text="This page is rendered from the branch-aware claims-ledger markdown authority. Promote wording from it only with the claim-lane rules it references.",
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>HLF Claims Ledger</title>
    <meta name="description" content="Branch-aware claims ledger for public review, separating stale public gaps, resolved branch surfaces, and real remaining architectural obligations.">
    <link rel="stylesheet" href="{CSS_PATH}">
</head>
<body class="page-claims">
    <div class="site-shell">
        <header class="site-header">
            <div class="eyebrow">HLF Claims Ledger</div>
            <div class="header-row">
                <div>
                    <h1>Branch-aware public review without promoting bridge work into false completion.</h1>
                    <p class="lede">This page turns the claims ledger into a compact operator-facing review surface so PR readers can distinguish stale public gaps, valid remaining gaps, and branch-resolved improvements without flattening the architectural story.</p>
                </div>
                <div class="hero-card hero-card-claims">
                    <div class="hero-label">Status</div>
                    <div class="hero-value hero-value-text">{html.escape(claims_data["status"])}</div>
                    <div class="hero-meta">branch-aware review aid</div>
                    <p class="hero-text">Use this page when evaluating whether public-main perceptions are stale, still valid, or only partially corrected by bridge-qualified branch work.</p>
                </div>
            </div>
            <nav class="top-nav">
                {_render_nav_links()}
            </nav>
        </header>

        <main class="content-grid">
            <section class="panel span-4 panel-brief">
                <div class="panel-heading">
                    <h2>Purpose</h2>
                    <span class="panel-kicker">Why the ledger exists</span>
                </div>
                {_render_bullet_list(claims_data["purpose"])}
            </section>

            <section class="panel span-4 panel-narrative">
                <div class="panel-heading">
                    <h2>Reading Rule</h2>
                    <span class="panel-kicker">Promotion discipline</span>
                </div>
                {_render_bullet_list(claims_data["reading_rule"])}
            </section>

            <section class="panel span-4 panel-proof">
                <div class="panel-heading">
                    <h2>Verified Branch Facts</h2>
                    <span class="panel-kicker">Grounding facts</span>
                </div>
                <div class="metric-grid metric-grid-single">
                    {verified_cards}
                </div>
            </section>

            <section class="panel span-12 panel-band">
                <div class="panel-heading">
                    <h2>Verdict System</h2>
                    <span class="panel-kicker">Overstated, valid, resolved, and open classifications</span>
                </div>
                <div class="verdict-chip-row verdict-chip-row-legend">
                    {_render_chip("Overstated", "overstated")}
                    {_render_chip("Valid", "valid")}
                    {_render_chip("Resolved", "resolved")}
                    {_render_chip("Open", "open")}
                </div>
                <div class="metric-grid verdict-overview-grid">
                    {verdict_overview}
                </div>
                <p class="section-note">These chips classify statement status. They do not erase the need to read the linked markdown authority before promoting wording.</p>
            </section>

            {decision_panel}

            {section_blocks}

            <section class="panel span-12 panel-narrative">
                <div class="panel-heading">
                    <h2>Bottom Line</h2>
                    <span class="panel-kicker">How reviewers should read the branch</span>
                </div>
                {_render_paragraphs(claims_data["bottom_line"]["paragraphs"])}
                {_render_bullet_list(claims_data["bottom_line"]["bullets"])}
            </section>

            {provenance}
        </main>

        <footer class="site-footer">
            <p>Public-safe presentation layer only. Use the markdown authority when quoting exact wording into PR or review materials.</p>
        </footer>
    </div>
</body>
</html>
"""


def write_status_surfaces(repo_root: Path = REPO_ROOT) -> dict[str, bool]:
    data = collect_status_data(repo_root)
    docs_dir = repo_root / "docs"
    merge_data = _parse_merge_readiness(
        docs_dir / "HLF_MERGE_READINESS_SUMMARY_2026-03-20.md", repo_root
    )
    claims_data = _parse_claims_ledger(
        docs_dir / "HLF_BRANCH_AWARE_CLAIMS_LEDGER_2026-03-20.md", repo_root
    )
    markdown_changed = _write_if_changed(
        docs_dir / MARKDOWN_OUTPUT.name, render_status_overview_markdown(data)
    )
    html_changed = _write_if_changed(docs_dir / HTML_OUTPUT.name, render_status_index_html(data))
    merge_html_changed = _write_if_changed(
        docs_dir / MERGE_HTML_OUTPUT.name, render_merge_readiness_html(data, merge_data)
    )
    claims_html_changed = _write_if_changed(
        docs_dir / CLAIMS_HTML_OUTPUT.name, render_claims_ledger_html(data, claims_data)
    )
    return {
        "markdown_changed": markdown_changed,
        "html_changed": html_changed,
        "merge_html_changed": merge_html_changed,
        "claims_html_changed": claims_html_changed,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate the HLF status overview surfaces.")
    parser.add_argument("--check", action="store_true", help="fail if generated outputs are stale")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.check:
        data = collect_status_data(REPO_ROOT)
        merge_data = _parse_merge_readiness(MERGE_READINESS_DOC, REPO_ROOT)
        claims_data = _parse_claims_ledger(CLAIMS_LEDGER_DOC, REPO_ROOT)
        expected_markdown = render_status_overview_markdown(data)
        expected_html = render_status_index_html(data)
        expected_merge_html = render_merge_readiness_html(data, merge_data)
        expected_claims_html = render_claims_ledger_html(data, claims_data)
        stale: list[str] = []
        if (
            not MARKDOWN_OUTPUT.exists()
            or MARKDOWN_OUTPUT.read_text(encoding="utf-8") != expected_markdown
        ):
            stale.append(_normalize_relative(MARKDOWN_OUTPUT))
        if not HTML_OUTPUT.exists() or HTML_OUTPUT.read_text(encoding="utf-8") != expected_html:
            stale.append(_normalize_relative(HTML_OUTPUT))
        if (
            not MERGE_HTML_OUTPUT.exists()
            or MERGE_HTML_OUTPUT.read_text(encoding="utf-8") != expected_merge_html
        ):
            stale.append(_normalize_relative(MERGE_HTML_OUTPUT))
        if (
            not CLAIMS_HTML_OUTPUT.exists()
            or CLAIMS_HTML_OUTPUT.read_text(encoding="utf-8") != expected_claims_html
        ):
            stale.append(_normalize_relative(CLAIMS_HTML_OUTPUT))
        if stale:
            print(json.dumps({"stale_outputs": stale}, indent=2))
            return 1
        print(json.dumps({"stale_outputs": []}, indent=2))
        return 0

    result = write_status_surfaces(REPO_ROOT)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
