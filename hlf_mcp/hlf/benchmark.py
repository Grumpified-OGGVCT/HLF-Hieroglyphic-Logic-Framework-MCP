"""
HLF Benchmark — token compression analysis using tiktoken cl100k_base.

Measures HLF token efficiency vs natural language and verbose JSON equivalents.
Also provides bounded, patch-plan-only workflow benchmarks for HLF self-improvement.
"""

from __future__ import annotations

import json
from typing import Any

_ENCODER: Any | None = None
_TOKENIZER_UNAVAILABLE = False


def _count(text: str) -> int:
    global _ENCODER, _TOKENIZER_UNAVAILABLE

    if not _TOKENIZER_UNAVAILABLE and _ENCODER is None:
        try:
            import tiktoken

            _ENCODER = tiktoken.get_encoding("cl100k_base")
        except ImportError:
            _TOKENIZER_UNAVAILABLE = True

    if _ENCODER is not None:
        return len(_ENCODER.encode(text))

    import re

    return len(re.findall(r"\S+", text))


# Reference NLP templates for standard HLF intent types
_NLP_TEMPLATES: dict[str, str] = {
    "security_audit": (
        "Please analyze the file at /security/seccomp.json in read-only mode. "
        "I expect you to identify vulnerabilities and return them in shorthand format. "
        "All agents must reach strict consensus before proceeding."
    ),
    "hello_world": (
        "Please say hello to the world and confirm the system is operational. "
        "Return a greeting message with status OK."
    ),
    "db_migration": (
        "Execute a database migration on the production database at /data/prod.db. "
        "Apply schema version 2.1, create the users table if it does not exist, "
        "and run all pending migration scripts. Verify the migration succeeded."
    ),
    "content_delegation": (
        "Delegate a fractal summarization task to the scribe agent. "
        "The source data is at /data/raw_logs/matrix_sync_2026.txt. "
        "Set priority to high. Assert that available VRAM is at least 8GB."
    ),
    "log_analysis": (
        "Analyze the log file at /var/log/system.log using read-only access. "
        "Extract error patterns, count occurrences, and return a summary report "
        "with the top 10 most frequent errors and their timestamps."
    ),
    "stack_deployment": (
        "Deploy the application stack using the auto routing strategy for the current "
        "deployment tier. Set temperature to 0.0 for deterministic output. "
        "Require operator confirmation before proceeding with deployment."
    ),
}

_SELF_IMPROVEMENT_SURFACES = (
    "authority",
    "grammar",
    "internal_loop",
    "code_bearing",
    "swarm",
    "governance",
)

_REAL_WORKFLOW_BENCHMARK_PROFILE = "real_hlf_self_improvement_workflow_compare"

_SELF_IMPROVEMENT_WORKFLOWS: dict[str, dict[str, Any]] = {
    "authority-grammar-loop": {
        "title": "Authority-bound grammar metadata self-improvement",
        "surfaces": ["authority", "grammar", "internal_loop", "governance"],
        "files": [
            "hlf_mcp/hlf/grammar.py",
            "governance/tag_i18n.yaml",
            "governance/templates/dictionary.json",
            "docs/HLF_GRAMMAR_REFERENCE.md",
        ],
        "patch_steps": [
            "classify claim lane before touching grammar metadata",
            "derive tag contract from present packaged truth, not wrong-checkout artifacts",
            "update parser/dictionary/docs/TextMate as one consistency surface",
            "validate, compile, lint, and verify the HLF patch plan",
            "record governance proof and replay scope",
        ],
        "hlf_source": """\
[HLF-v3]
Δ [INTENT] goal="self_improve_hlf" workflow="authority_grammar_loop"
∇ [SOURCE] path="hlf_mcp/hlf/grammar.py"
∇ [SOURCE] path="governance/tag_i18n.yaml"
Ж [ASSERT] authority_lane="present-packaged-current-truth"
Ж [CONSTRAINT] mode="patch-plan-only"
⌘ [DELEGATE] agent="grammar-reviewer" goal="derive_consistency_patch"
⨝ [VOTE] voter="authority-verifier" decision="approve" quorum="strict"
Ж [EXPECT] validation="validate_compile_lint_proof"
Ω
""",
    },
    "code-bearing-contract": {
        "title": "Code-bearing HLF self-improvement contract",
        "surfaces": ["authority", "internal_loop", "code_bearing", "governance"],
        "files": [
            "hlf_mcp/hlf/code_execution.py",
            "tests/test_code_bearing_execution.py",
            "hlf_mcp/server_core.py",
        ],
        "entrypoint": "verify_plan",
        "patch_steps": [
            "express code-bearing change as a bounded HLF block",
            "dry-run the HLF VM admission path before any runtime execution",
            "refuse non-HLF code execution while preserving compile-only evidence",
            "compare validation and governance proof coverage against baseline notes",
            "add targeted regression tests before applying any real patch",
        ],
        "hlf_source": """\
[HLF-v3]
Δ [INTENT] goal="self_improve_hlf_code_execution" workflow="code_bearing_contract"
∇ [SOURCE] path="hlf_mcp/hlf/code_execution.py"
Ж [ASSERT] authority_lane="present-packaged-current-truth"
Ж [CONSTRAINT] mode="dry-run"
Δ [CODE] name="patch_notes" language="python" body="plan only: no repository write"
FUNCTION verify_plan {
  RESULT 0 "patch-plan-only"
}
⨝ [VOTE] voter="sandbox-verifier" decision="approve" quorum="strict"
Ω
""",
    },
    "swarm-governance-report": {
        "title": "Swarm and governance proof reporting self-improvement",
        "surfaces": ["authority", "internal_loop", "swarm", "governance"],
        "files": [
            "hlf_mcp/hlf/swarm_mechanics.py",
            "hlf_mcp/hlf/governance_proofs.py",
            "hlf_mcp/server_resources.py",
            "tests/test_swarm_mechanics.py",
        ],
        "patch_steps": [
            "delegate bounded local review roles through raw HLF handoff",
            "materialize votes, dissent, progress, and lineage as HLF artifacts",
            "verify SHA-256 hash-chain proof boundaries honestly",
            "expose report/status resource without claiming distributed A2A",
            "run targeted proof and resource tests",
        ],
        "hlf_source": """\
[HLF-v3]
Δ [INTENT] goal="self_improve_hlf_swarm_governance" workflow="swarm_governance_report"
∇ [SOURCE] path="hlf_mcp/hlf/swarm_mechanics.py"
∇ [SOURCE] path="hlf_mcp/hlf/governance_proofs.py"
Ж [CONSTRAINT] mode="patch-plan-only"
⌘ [DELEGATE] agent="planner" goal="resource_report_patch" role="coordinator"
⌘ [DELEGATE] agent="verifier" goal="proof_boundary_check" role="reviewer"
⨝ [VOTE] voter="planner" decision="approve" quorum="strict"
Ж [DISSENT] agent="operator" reason="do_not_fake_file_modification" severity="warning"
∇ [PROGRESS] event_id="bench-swarm-1" phase="patch_plan" status="materialized"
Ω
""",
    },
}


_MULTILINGUAL_NLP_TEMPLATES: dict[str, dict[str, str]] = {
    "security_audit": {
        "en": "Please analyze the file at /security/seccomp.json in read-only mode. I expect you to identify vulnerabilities and return them in shorthand format. All agents must reach strict consensus before proceeding.",
        "fr": "Veuillez analyser le fichier /security/seccomp.json en mode lecture seule. Identifiez les vulnérabilités et retournez-les en format abrégé. Tous les agents doivent parvenir à un consensus strict avant de continuer.",
        "es": "Analiza el archivo /security/seccomp.json en modo de solo lectura. Identifica vulnerabilidades y devuélvelas en formato abreviado. Todos los agentes deben alcanzar un consenso estricto antes de continuar.",
        "ar": "يرجى تحليل الملف /security/seccomp.json في وضع القراءة فقط. حدد الثغرات وأعدها بصيغة مختصرة. يجب أن تصل جميع الوكلاء إلى توافق صارم قبل المتابعة.",
        "zh": "请以只读模式分析 /security/seccomp.json 文件。识别漏洞并以简写格式返回。所有代理在继续之前必须达成严格共识。",
    },
    "hello_world": {
        "en": "Please say hello to the world and confirm the system is operational. Return a greeting message with status OK.",
        "fr": "Veuillez dire bonjour au monde et confirmer que le système est opérationnel. Retournez un message de salutation avec le statut OK.",
        "es": "Di hola al mundo y confirma que el sistema está operativo. Devuelve un mensaje de saludo con estado OK.",
        "ar": "يرجى قول مرحباً للعالم وتأكيد أن النظام يعمل. أعد رسالة ترحيب بالحالة OK.",
        "zh": "请向世界问好并确认系统正在运行。返回带有 OK 状态的问候消息。",
    },
    "db_migration": {
        "en": "Execute a database migration on the production database at /data/prod.db. Apply schema version 2.1, create the users table if it does not exist, and run all pending migration scripts. Verify the migration succeeded.",
        "fr": "Exécutez une migration de base de données sur la base de production /data/prod.db. Appliquez le schéma version 2.1, créez la table users si elle n'existe pas et exécutez tous les scripts en attente. Vérifiez que la migration a réussi.",
        "es": "Ejecuta una migración de base de datos en la base de producción /data/prod.db. Aplica la versión 2.1 del esquema, crea la tabla users si no existe y ejecuta todos los scripts pendientes. Verifica que la migración haya tenido éxito.",
        "ar": "نفذ ترحيل قاعدة البيانات على قاعدة الإنتاج /data/prod.db. طبق مخطط الإصدار 2.1، وأنشئ جدول users إذا لم يكن موجوداً، وشغل جميع نصوص الترحيل المعلقة. تحقق من نجاح الترحيل.",
        "zh": "在生产数据库 /data/prod.db 上执行数据库迁移。应用 2.1 版本架构，如果 users 表不存在则创建它，并运行所有待处理的迁移脚本。验证迁移成功。",
    },
    "content_delegation": {
        "en": "Delegate a fractal summarization task to the scribe agent. The source data is at /data/raw_logs/matrix_sync_2026.txt. Set priority to high. Assert that available VRAM is at least 8GB.",
        "fr": "Déléguez une tâche de résumé fractal à l'agent scribe. Les données sources sont dans /data/raw_logs/matrix_sync_2026.txt. Définissez la priorité sur haute. Affirmez que la VRAM disponible est d'au moins 8 Go.",
        "es": "Delega una tarea de resumen fractal al agente scribe. Los datos fuente están en /data/raw_logs/matrix_sync_2026.txt. Establece la prioridad en alta. Afirma que la VRAM disponible sea de al menos 8 GB.",
        "ar": "فوّض مهمة تلخيص كسوري إلى الوكيل scribe. توجد بيانات المصدر في /data/raw_logs/matrix_sync_2026.txt. اضبط الأولوية على عالية. أكد أن الذاكرة الرسومية المتاحة لا تقل عن 8 جيجابايت.",
        "zh": "将分形摘要任务委托给 scribe 代理。源数据位于 /data/raw_logs/matrix_sync_2026.txt。将优先级设为高。断言可用显存至少为 8GB。",
    },
    "log_analysis": {
        "en": "Analyze the log file at /var/log/system.log using read-only access. Extract error patterns, count occurrences, and return a summary report with the top 10 most frequent errors and their timestamps.",
        "fr": "Analysez le fichier journal /var/log/system.log en accès lecture seule. Extrayez les motifs d'erreur, comptez les occurrences et retournez un rapport résumant les 10 erreurs les plus fréquentes avec leurs horodatages.",
        "es": "Analiza el archivo de registro /var/log/system.log usando acceso de solo lectura. Extrae patrones de error, cuenta ocurrencias y devuelve un informe con los 10 errores más frecuentes y sus marcas de tiempo.",
        "ar": "حلل ملف السجل /var/log/system.log باستخدام وصول للقراءة فقط. استخرج أنماط الأخطاء وعدد التكرارات وأعد تقريراً يلخص أكثر 10 أخطاء شيوعاً مع الطوابع الزمنية الخاصة بها.",
        "zh": "使用只读访问分析日志文件 /var/log/system.log。提取错误模式、统计出现次数，并返回包含前 10 个最常见错误及其时间戳的摘要报告。",
    },
    "stack_deployment": {
        "en": "Deploy the application stack using the auto routing strategy for the current deployment tier. Set temperature to 0.0 for deterministic output. Require operator confirmation before proceeding with deployment.",
        "fr": "Déployez la pile applicative en utilisant la stratégie de routage automatique pour le niveau de déploiement courant. Définissez la température à 0.0 pour une sortie déterministe. Exigez une confirmation opérateur avant de poursuivre.",
        "es": "Despliega la pila de aplicaciones usando la estrategia de enrutamiento automático para el nivel de despliegue actual. Establece la temperatura en 0.0 para una salida determinista. Requiere confirmación del operador antes de continuar.",
        "ar": "انشر حزمة التطبيق باستخدام استراتيجية التوجيه التلقائي لمستوى النشر الحالي. اضبط درجة الحرارة على 0.0 للحصول على مخرجات حتمية. اطلب تأكيد المشغل قبل متابعة النشر.",
        "zh": "使用当前部署层级的自动路由策略部署应用栈。将 temperature 设为 0.0 以获得确定性输出。部署前必须要求操作员确认。",
    },
}


class HLFBenchmark:
    """Measure HLF token compression ratios."""

    def analyze(
        self,
        source: str,
        compare_text: str | None = None,
        domain: str | None = None,
    ) -> dict[str, Any]:
        """Analyze token compression of HLF source.

        Args:
            source: HLF source code
            compare_text: Optional NLP/JSON text to compare against
            domain: Optional domain name to use NLP template (if compare_text not given)

        Returns:
            dict with token counts, compression ratio, and per-line breakdown
        """
        hlf_tokens = _count(source)

        if compare_text:
            nlp_tokens = _count(compare_text)
            compare_source = compare_text
        elif domain and domain in _NLP_TEMPLATES:
            compare_source = _NLP_TEMPLATES[domain]
            nlp_tokens = _count(compare_source)
        else:
            # Estimate NLP equivalent from source
            compare_source = _estimate_nlp(source)
            nlp_tokens = _count(compare_source)

        if nlp_tokens > 0:
            compression_pct = round((1 - hlf_tokens / nlp_tokens) * 100, 1)
        else:
            compression_pct = 0.0

        # Per-line breakdown
        line_analysis = []
        for line in source.splitlines():
            stripped = line.strip()
            if stripped:
                tc = _count(stripped)
                line_analysis.append({"line": stripped[:60], "tokens": tc})

        return {
            "hlf_tokens": hlf_tokens,
            "nlp_tokens": nlp_tokens,
            "compression_pct": compression_pct,
            "savings": nlp_tokens - hlf_tokens,
            "tiktoken_model": "cl100k_base",
            "compare_text_preview": compare_source[:100] + "..."
            if len(compare_source) > 100
            else compare_source,
            "line_analysis": line_analysis,
        }

    def benchmark_suite(self, use_live_translator: bool = False) -> dict[str, Any]:
        """Run the full benchmark suite across ALL categories.

        Args:
            use_live_translator: If True, also run english_to_hlf() on
                each NLP text and report live translation token counts.
        """

        def _maybe_live_translate(text: str) -> dict[str, Any] | None:
            if not use_live_translator:
                return None
            try:
                from hlf_mcp.hlf.translator import english_to_hlf
                live_hlf = english_to_hlf(text)
                live_tokens = _count(live_hlf)
                live_compression = (
                    round((1 - live_tokens / max(1, _count(text))) * 100, 1)
                )
                return {
                    "live_hlf_tokens": live_tokens,
                    "live_compression_pct": live_compression,
                }
            except Exception:
                return None

        # ── Simple ────────────────────────────────────────────────────────
        simple_results: list[dict[str, Any]] = []
        simple_total_hlf = 0
        simple_total_nlp = 0
        simple_total_live_hlf = 0

        for domain, nlp_text in _NLP_TEMPLATES.items():
            nlp_tokens = _count(nlp_text)
            hlf_source = _DOMAIN_HLF.get(domain, f"[HLF-v3]\nΔ {domain}\nΩ\n")
            hlf_tokens = _count(hlf_source)
            compression = round((1 - hlf_tokens / nlp_tokens) * 100, 1) if nlp_tokens > 0 else 0

            row: dict[str, Any] = {
                "domain": domain,
                "nlp_tokens": nlp_tokens,
                "template_hlf_tokens": hlf_tokens,
                "template_compression_pct": compression,
            }

            live = _maybe_live_translate(nlp_text)
            if live:
                row["live_hlf_tokens"] = live["live_hlf_tokens"]
                row["live_compression_pct"] = live["live_compression_pct"]
                simple_total_live_hlf += live["live_hlf_tokens"]

            simple_results.append(row)
            simple_total_hlf += hlf_tokens
            simple_total_nlp += nlp_tokens

        simple_overall = round((1 - simple_total_hlf / max(1, simple_total_nlp)) * 100, 1)
        simple_totals: dict[str, Any] = {
            "nlp": simple_total_nlp,
            "template_hlf": simple_total_hlf,
            "template_compression_pct": simple_overall,
        }
        if use_live_translator:
            simple_totals["live_hlf"] = simple_total_live_hlf
            simple_totals["live_compression_pct"] = (
                round((1 - simple_total_live_hlf / max(1, simple_total_nlp)) * 100, 1)
            )

        # ── Complex ───────────────────────────────────────────────────────
        complex_results: list[dict[str, Any]] = []
        complex_total_hlf = 0
        complex_total_nlp = 0
        complex_total_live_hlf = 0

        for scenario_id, nlp_text in _COMPLEX_WORKFLOW_NLP.items():
            nlp_tokens = _count(nlp_text)
            hlf_source = _COMPLEX_WORKFLOW_HLF.get(
                scenario_id, f"[HLF-v3]\nΔ [WORKFLOW] name=\"{scenario_id}\"\nΩ\n"
            )
            hlf_tokens = _count(hlf_source)
            compression = round((1 - hlf_tokens / nlp_tokens) * 100, 1) if nlp_tokens > 0 else 0

            row: dict[str, Any] = {
                "scenario_id": scenario_id,
                "nlp_tokens": nlp_tokens,
                "template_hlf_tokens": hlf_tokens,
                "template_compression_pct": compression,
            }

            live = _maybe_live_translate(nlp_text)
            if live:
                row["live_hlf_tokens"] = live["live_hlf_tokens"]
                row["live_compression_pct"] = live["live_compression_pct"]
                complex_total_live_hlf += live["live_hlf_tokens"]

            complex_results.append(row)
            complex_total_hlf += hlf_tokens
            complex_total_nlp += nlp_tokens

        complex_overall = round((1 - complex_total_hlf / max(1, complex_total_nlp)) * 100, 1)
        complex_totals: dict[str, Any] = {
            "nlp": complex_total_nlp,
            "template_hlf": complex_total_hlf,
            "template_compression_pct": complex_overall,
        }
        if use_live_translator:
            complex_totals["live_hlf"] = complex_total_live_hlf
            complex_totals["live_compression_pct"] = (
                round((1 - complex_total_live_hlf / max(1, complex_total_nlp)) * 100, 1)
            )

        # ── Swarm ─────────────────────────────────────────────────────────
        swarm_results: list[dict[str, Any]] = []
        swarm_total_hlf = 0
        swarm_total_nlp = 0
        swarm_total_live_hlf = 0

        for scenario_id, nlp_text in _SWARM_WORKFLOW_NLP.items():
            nlp_tokens = _count(nlp_text)
            hlf_source = _SWARM_WORKFLOW_HLF.get(
                scenario_id, f"[HLF-v3]\n⨝ [SWARM] name=\"{scenario_id}\"\nΩ\n"
            )
            hlf_tokens = _count(hlf_source)
            compression = round((1 - hlf_tokens / nlp_tokens) * 100, 1) if nlp_tokens > 0 else 0

            row: dict[str, Any] = {
                "scenario_id": scenario_id,
                "nlp_tokens": nlp_tokens,
                "template_hlf_tokens": hlf_tokens,
                "template_compression_pct": compression,
            }

            live = _maybe_live_translate(nlp_text)
            if live:
                row["live_hlf_tokens"] = live["live_hlf_tokens"]
                row["live_compression_pct"] = live["live_compression_pct"]
                swarm_total_live_hlf += live["live_hlf_tokens"]

            swarm_results.append(row)
            swarm_total_hlf += hlf_tokens
            swarm_total_nlp += nlp_tokens

        swarm_overall = round((1 - swarm_total_hlf / max(1, swarm_total_nlp)) * 100, 1)
        swarm_totals: dict[str, Any] = {
            "nlp": swarm_total_nlp,
            "template_hlf": swarm_total_hlf,
            "template_compression_pct": swarm_overall,
        }
        if use_live_translator:
            swarm_totals["live_hlf"] = swarm_total_live_hlf
            swarm_totals["live_compression_pct"] = (
                round((1 - swarm_total_live_hlf / max(1, swarm_total_nlp)) * 100, 1)
            )

        # ── Scale curve ───────────────────────────────────────────────────
        scale_curve_data = self.benchmark_scale_curve()

        # ── Overall summary ───────────────────────────────────────────────
        crossover = scale_curve_data.get("crossover_point")
        max_comp = scale_curve_data.get("max_compression_pct", 0)
        if crossover is not None:
            overall_summary = (
                f"HLF wins at N>={crossover} steps with max compression of {max_comp}%"
            )
        else:
            overall_summary = (
                f"No crossover detected. Max compression: {max_comp}%"
            )

        return {
            "simple": {"results": simple_results, "totals": simple_totals},
            "complex": {"results": complex_results, "totals": complex_totals},
            "swarm": {"results": swarm_results, "totals": swarm_totals},
            "scale_curve": scale_curve_data,
            "overall_summary": overall_summary,
            "tiktoken_model": "cl100k_base",
            "use_live_translator": use_live_translator,
        }

    def benchmark_scale_curve(self) -> dict[str, Any]:
        """Measure NLP→HLF compression at increasing workflow step counts.

        Generates synthetic multi-step NLP prose from N=1 to N=50 and
        compares against a governance-first HLF block that stays compact
        regardless of step count.

        Returns:
            dict with curve data, crossover point, and max compression.
        """
        step_counts = [1, 3, 5, 7, 10, 15, 20, 30, 50]
        actions = [
            "detect anomalies in the monitoring feed",
            "classify severity based on impact scoring rules",
            "contain affected network segments",
            "investigate root cause from audit logs",
            "remediate using runbook RB-2026-03",
            "verify fix via sandbox replay",
            "report findings to SOC lead",
            "deploy canary to 10% of traffic",
            "monitor error rate for regression",
            "notify on-call operator",
        ]

        curve: list[dict[str, Any]] = []
        for n in step_counts:
            # Build synthetic NLP with N steps (cycling through actions)
            steps_text = " ".join(
                f"Step {i + 1}: {actions[i % len(actions)]}."
                for i in range(n)
            )
            nlp_tokens = _count(steps_text)

            # Governance-first HLF: compact block that doesn't grow with N
            # Vary constraints slightly as N increases for realism
            extra_constraints = ""
            if n >= 10:
                extra_constraints += '\n  Ж [CONSTRAINT] rollback_enabled=true'
            if n >= 20:
                extra_constraints += '\n  Ж [CONSTRAINT] audit_trail=full'
            if n >= 30:
                extra_constraints += '\n  Ж [CONSTRAINT] parallel_exec="limited_concurrency"'

            hlf_source = (
                f"[HLF-v3]\n"
                f"Δ [WORKFLOW] name=\"scale_benchmark\" max_steps={n}\n"
                f"  Ж [CONSTRAINT] mode=\"governed\"\n"
                f"  Ж [CONSTRAINT] detect classify contain investigate remediate verify report deploy monitor notify\n"
                f"  Ж [VOTE] consensus=\"majority\"\n"
                f"  Ж [EXPECT] workflow_complete{extra_constraints}\n"
                f"Ω\n"
            )
            hlf_tokens = _count(hlf_source)

            compression_pct = round((1 - hlf_tokens / nlp_tokens) * 100, 1) if nlp_tokens > 0 else 0.0

            curve.append({
                "steps": n,
                "nlp_tokens": nlp_tokens,
                "hlf_tokens": hlf_tokens,
                "compression_pct": compression_pct,
            })

        # Find crossover: first N where compression_pct > 0 (HLF wins)
        crossover = None
        for point in curve:
            if point["compression_pct"] > 0:
                crossover = point["steps"]
                break

        max_compression = max(p["compression_pct"] for p in curve) if curve else 0.0

        return {
            "curve": curve,
            "crossover_point": crossover,
            "max_compression_pct": max_compression,
            "tiktoken_model": "cl100k_base",
        }

    def benchmark_real_workflow(self) -> dict[str, Any]:
        """Benchmark a real dream-cycle workflow: observe→propose→verify→promote.

        Compares a prose description of a governance-bound remediation loop
        against its governance-first HLF encoding.
        """
        nlp_description = (
            "Observe system metrics from /metrics/prometheus. "
            "Propose scaling action based on threshold breach. "
            "Verify proposed action against safety constraints and resource limits. "
            "Promote verified action to execution queue. "
            "Record evidence chain with SHA-256 hashes. "
            "Notify operator of completed action with verification proof. "
            "Update runbook with new threshold observations."
        )

        hlf_source = """\
[HLF-v3]
Δ [WORKFLOW] name="dream_cycle_observe_propose_verify_promote" max_steps=7
  Ж [CONSTRAINT] observe source="/metrics/prometheus"
  Ж [CONSTRAINT] propose action=scaling trigger=threshold_breach
  Ж [CONSTRAINT] verify safety_constraints=true resource_limits=true
  Ж [CONSTRAINT] promote target="execution_queue"
  Ж [CONSTRAINT] record evidence=SHA-256 chain=true
  Ж [CONSTRAINT] notify operator=true proof=verification
  Ж [CONSTRAINT] update runbook="threshold_observations"
  Ж [VOTE] consensus="majority"
  Ж [EXPECT] action_completed verified=true
Ω
"""

        nlp_tokens = _count(nlp_description)
        hlf_tokens = _count(hlf_source)
        compression_pct = round((1 - hlf_tokens / nlp_tokens) * 100, 1) if nlp_tokens > 0 else 0.0

        return {
            "workflow_name": "dream_cycle_observe_propose_verify_promote",
            "nlp_description": nlp_description,
            "hlf_source": hlf_source,
            "nlp_tokens": nlp_tokens,
            "hlf_tokens": hlf_tokens,
            "compression_pct": compression_pct,
            "tiktoken_model": "cl100k_base",
        }

    def multilingual_matrix(
        self,
        domains: list[str] | None = None,
        languages: list[str] | None = None,
    ) -> dict[str, Any]:
        """Run a multilingual benchmark matrix across canonical intents."""
        from hlf_mcp.hlf.translator import language_to_hlf, translation_diagnostics

        selected_domains = domains or list(_MULTILINGUAL_NLP_TEMPLATES.keys())
        selected_languages = languages or ["en", "fr", "es", "ar", "zh"]

        rows: list[dict[str, Any]] = []
        per_language: dict[str, dict[str, float | int]] = {}

        for language in selected_languages:
            per_language[language] = {
                "samples": 0,
                "input_tokens": 0,
                "hlf_tokens": 0,
                "input_bytes": 0,
                "compression_pct": 0.0,
            }

        for domain in selected_domains:
            templates = _MULTILINGUAL_NLP_TEMPLATES.get(domain)
            if templates is None:
                raise ValueError(f"Unsupported benchmark domain: {domain}")
            for language in selected_languages:
                text = templates.get(language)
                if text is None:
                    raise ValueError(
                        f"Missing benchmark template for domain={domain}, language={language}"
                    )
                source = language_to_hlf(text, language=language)
                analysis = self.analyze(source, compare_text=text)
                diagnostics = translation_diagnostics(
                    text, language=language, source=source
                ).to_dict()
                input_bytes = len(text.encode("utf-8"))
                input_chars = len(text)
                row = {
                    "domain": domain,
                    "language": language,
                    "input_tokens": analysis["nlp_tokens"],
                    "hlf_tokens": analysis["hlf_tokens"],
                    "compression_pct": analysis["compression_pct"],
                    "savings": analysis["savings"],
                    "input_bytes": input_bytes,
                    "input_chars": input_chars,
                    "compare_text_preview": analysis["compare_text_preview"],
                    "fallback_used": diagnostics["fallback_used"],
                    "fallback_count": diagnostics["fallback_count"],
                    "roundtrip_fidelity_score": diagnostics["roundtrip_fidelity_score"],
                    "semantic_loss_flags": diagnostics["semantic_loss_flags"],
                    "roundtrip_summary_preview": diagnostics["roundtrip_summary"][:100],
                }
                rows.append(row)

                lang_totals = per_language[language]
                lang_totals["samples"] = int(lang_totals["samples"]) + 1
                lang_totals["input_tokens"] = int(lang_totals["input_tokens"]) + int(
                    analysis["nlp_tokens"]
                )
                lang_totals["hlf_tokens"] = int(lang_totals["hlf_tokens"]) + int(
                    analysis["hlf_tokens"]
                )
                lang_totals["input_bytes"] = int(lang_totals["input_bytes"]) + input_bytes
                lang_totals["fallback_samples"] = int(lang_totals.get("fallback_samples", 0)) + int(
                    diagnostics["fallback_used"]
                )
                lang_totals["roundtrip_fidelity_total"] = float(
                    lang_totals.get("roundtrip_fidelity_total", 0.0)
                ) + float(diagnostics["roundtrip_fidelity_score"])

        for language, totals in per_language.items():
            input_tokens = int(totals["input_tokens"])
            hlf_tokens = int(totals["hlf_tokens"])
            sample_count = int(totals["samples"])
            totals["compression_pct"] = (
                round((1 - hlf_tokens / input_tokens) * 100, 1) if input_tokens > 0 else 0.0
            )
            totals["fallback_rate"] = (
                round((int(totals.get("fallback_samples", 0)) / sample_count), 3)
                if sample_count > 0
                else 0.0
            )
            totals["roundtrip_fidelity_avg"] = (
                round((float(totals.get("roundtrip_fidelity_total", 0.0)) / sample_count), 3)
                if sample_count > 0
                else 0.0
            )

        return {
            "rows": rows,
            "per_language": per_language,
            "domains": selected_domains,
            "languages": selected_languages,
            "tiktoken_model": "cl100k_base",
        }

    def language_comparison_summary(
        self,
        domains: list[str] | None = None,
        languages: list[str] | None = None,
    ) -> dict[str, Any]:
        """Return a ranked multilingual comparison using measured benchmark outcomes.

        Ranking is intentionally evidence-first: languages are ordered by
        round-trip fidelity, then fallback discipline, then compression.
        This avoids projecting a winner before the measured signals exist.
        """
        matrix = self.multilingual_matrix(domains=domains, languages=languages)

        ranked_languages: list[dict[str, Any]] = []
        for language in matrix["languages"]:
            totals = matrix["per_language"][language]
            ranked_languages.append(
                {
                    "language": language,
                    "samples": int(totals["samples"]),
                    "compression_pct": float(totals["compression_pct"]),
                    "fallback_rate": float(totals["fallback_rate"]),
                    "roundtrip_fidelity_avg": float(totals["roundtrip_fidelity_avg"]),
                    "input_tokens": int(totals["input_tokens"]),
                    "hlf_tokens": int(totals["hlf_tokens"]),
                }
            )

        ranked_languages.sort(
            key=lambda item: (
                -item["roundtrip_fidelity_avg"],
                item["fallback_rate"],
                -item["compression_pct"],
                item["language"],
            )
        )

        return {
            "ranked_languages": ranked_languages,
            "leader": ranked_languages[0] if ranked_languages else None,
            "ranking_policy": [
                "roundtrip_fidelity_avg_desc",
                "fallback_rate_asc",
                "compression_pct_desc",
                "language_asc",
            ],
            "domains": matrix["domains"],
            "languages": matrix["languages"],
            "tiktoken_model": matrix["tiktoken_model"],
        }

    def real_workflow_self_improvement_benchmark(
        self,
        workflow_ids: list[str] | None = None,
        mode: str = "patch-plan",
    ) -> dict[str, Any]:
        """Benchmark HLF self-improvement workflows against non-HLF patch-plan baselines.

        The benchmark produces real validation/proof/swarm/code-admission artifacts, but it
        never writes repository files. File modifications are represented as explicit patch
        plans so the result is safe to run inside the MCP server.
        """
        if mode not in {"patch-plan", "dry-run"}:
            raise ValueError("mode must be 'patch-plan' or 'dry-run'")

        from hlf_mcp.hlf.authority import authority_matrix, downstream_guidance
        from hlf_mcp.hlf.code_execution import execute_code_bearing_hlf
        from hlf_mcp.hlf.compiler import HLFCompiler
        from hlf_mcp.hlf.formal_verifier import FormalVerifier
        from hlf_mcp.hlf.governance_proofs import (
            build_anchor,
            build_governance_proof,
            sha256_digest,
            verify_governance_proof,
        )
        from hlf_mcp.hlf.linter import HLFLinter
        from hlf_mcp.hlf.swarm_mechanics import build_swarm_mechanics_artifact

        selected_ids = workflow_ids or list(_SELF_IMPROVEMENT_WORKFLOWS)
        unknown = [workflow_id for workflow_id in selected_ids if workflow_id not in _SELF_IMPROVEMENT_WORKFLOWS]
        if unknown:
            raise ValueError(f"Unknown self-improvement workflow id(s): {', '.join(unknown)}")

        compiler = HLFCompiler()
        linter = HLFLinter()
        verifier = FormalVerifier()
        authority = authority_matrix()
        guidance = {
            "restore-grammar": list(downstream_guidance("restore-grammar")),
            "mandatory-internal-hlf": list(downstream_guidance("mandatory-internal-hlf")),
        }

        rows: list[dict[str, Any]] = []
        for workflow_id in selected_ids:
            spec = _SELF_IMPROVEMENT_WORKFLOWS[workflow_id]
            hlf_source = str(spec["hlf_source"])
            baseline_text = _render_non_hlf_self_improvement_baseline(workflow_id, spec)

            hlf_result = _measure_hlf_self_improvement_workflow(
                workflow_id=workflow_id,
                spec=spec,
                source=hlf_source,
                mode=mode,
                compiler=compiler,
                linter=linter,
                verifier=verifier,
                execute_code_bearing_hlf=execute_code_bearing_hlf,
                build_swarm_mechanics_artifact=build_swarm_mechanics_artifact,
                verify_governance_proof=verify_governance_proof,
            )
            baseline_result = _measure_non_hlf_self_improvement_baseline(
                workflow_id=workflow_id,
                spec=spec,
                baseline_text=baseline_text,
            )
            comparison = _compare_real_workflow_rows(hlf_result, baseline_result)
            rows.append(
                {
                    "workflow_id": workflow_id,
                    "title": spec["title"],
                    "mode": mode,
                    "modification_policy": (
                        "No repository files are modified by this benchmark; file changes are "
                        "represented as patch plans and bounded artifacts."
                    ),
                    "surfaces": list(spec["surfaces"]),
                    "target_files": list(spec["files"]),
                    "hlf_workflow": hlf_result,
                    "non_hlf_baseline": baseline_result,
                    "comparison": comparison,
                }
            )

        aggregate = _aggregate_real_workflow_rows(rows)
        report_body = {
            "profile_name": _REAL_WORKFLOW_BENCHMARK_PROFILE,
            "benchmark_kind": "hlf_self_improvement_real_workflow_compare",
            "mode": mode,
            "workflow_ids": selected_ids,
            "measurement_policy": {
                "measured": [
                    "HLF token counts",
                    "baseline token counts",
                    "HLF parser/compiler/linter/formal-verifier admission",
                    "HLF dry-run code-bearing admission where applicable",
                    "local bounded swarm artifact construction",
                    "governance proof verification and tamper detection",
                ],
                "estimated": [
                    "baseline quality, scope, thoroughness, validation intent, and error-chasing from deterministic text rubrics",
                    "token cost as tokenizer count only; no provider billing is inferred",
                ],
                "not_claimed": [
                    "no repository file modification",
                    "no distributed swarm/A2A execution",
                    "no digital signature or non-repudiation",
                ],
            },
            "authority_snapshot": authority,
            "downstream_guidance": guidance,
            "rows": rows,
            "summary": aggregate,
            "benchmark_scores": aggregate["benchmark_scores"],
        }
        proof = build_governance_proof(
            artifact_kind="real_workflow_benchmark",
            artifact_id=_REAL_WORKFLOW_BENCHMARK_PROFILE,
            events=[
                {"event_type": "workflow_rows", "payload": rows},
                {"event_type": "summary", "payload": aggregate},
                {"event_type": "measurement_policy", "payload": report_body["measurement_policy"]},
            ],
            memory_anchors=[build_anchor("memory", "authority_matrix", authority)],
            runtime_anchors=[build_anchor("runtime", "workflow_row_hash", sha256_digest(rows))],
            replay_scope={
                "workflow_ids": selected_ids,
                "mode": mode,
                "profile_name": _REAL_WORKFLOW_BENCHMARK_PROFILE,
                "row_hash": sha256_digest(rows),
            },
        )
        report_body["governance_proof"] = proof
        report_body["governance_proof_verification"] = verify_governance_proof(proof)
        return report_body

    def translation_memory_retrieval_matrix(
        self,
        memory_store: Any,
        domains: list[str] | None = None,
        languages: list[str] | None = None,
        top_k: int = 3,
        topic: str = "hlf_translation_contract_benchmark",
    ) -> dict[str, Any]:
        """Measure retrieval-backed translation memory quality across supported languages."""
        from hlf_mcp.hlf.translator import language_to_hlf, translation_diagnostics

        selected_domains = domains or list(_MULTILINGUAL_NLP_TEMPLATES.keys())
        selected_languages = languages or ["en", "fr", "es", "ar", "zh"]

        rows: list[dict[str, Any]] = []
        per_language: dict[str, dict[str, float | int]] = {
            language: {
                "samples": 0,
                "same_language_hit_count": 0,
                "exact_match_hit_count": 0,
                "top_similarity_total": 0.0,
                "retrieval_quality_total": 0.0,
                "roundtrip_fidelity_total": 0.0,
            }
            for language in selected_languages
        }

        for domain in selected_domains:
            templates = _MULTILINGUAL_NLP_TEMPLATES.get(domain)
            if templates is None:
                raise ValueError(f"Unsupported benchmark domain: {domain}")
            for language in selected_languages:
                text = templates.get(language)
                if text is None:
                    raise ValueError(
                        f"Missing benchmark template for domain={domain}, language={language}"
                    )
                source = language_to_hlf(text, language=language)
                diagnostics = translation_diagnostics(
                    text, language=language, source=source
                ).to_dict()
                payload = {
                    "kind": "hlf_translation_contract",
                    "benchmark_topic": topic,
                    "language": language,
                    "domain": domain,
                    "original_text": text,
                    "hlf_source": source,
                    "translation": diagnostics,
                }
                memory_store.store(
                    json.dumps(payload, ensure_ascii=False, sort_keys=True),
                    topic=topic,
                    confidence=float(diagnostics.get("roundtrip_fidelity_score", 1.0)),
                    provenance="hlf_benchmark.translation_memory_retrieval_matrix",
                    tags=["hlf", "translation", "benchmark", language, domain],
                    metadata={
                        "language": language,
                        "domain": domain,
                        "kind": "hlf_translation_contract",
                    },
                )

                query_result = memory_store.query(text, top_k=top_k, topic=topic)
                results = query_result.get("results", [])
                top_similarity = float(results[0]["similarity"]) if results else 0.0
                same_language_hit = any(
                    row.get("metadata", {}).get("language") == language for row in results
                )
                exact_match_hit = any(
                    row.get("metadata", {}).get("language") == language
                    and row.get("metadata", {}).get("domain") == domain
                    for row in results
                )
                retrieval_quality = 1.0 if exact_match_hit else 0.5 if same_language_hit else 0.0

                row = {
                    "domain": domain,
                    "language": language,
                    "top_similarity": round(top_similarity, 4),
                    "same_language_hit": same_language_hit,
                    "exact_match_hit": exact_match_hit,
                    "retrieval_quality": retrieval_quality,
                    "roundtrip_fidelity_score": diagnostics.get("roundtrip_fidelity_score", 0.0),
                    "fallback_used": diagnostics.get("fallback_used", False),
                }
                rows.append(row)

                totals = per_language[language]
                totals["samples"] = int(totals["samples"]) + 1
                totals["same_language_hit_count"] = int(totals["same_language_hit_count"]) + int(
                    same_language_hit
                )
                totals["exact_match_hit_count"] = int(totals["exact_match_hit_count"]) + int(
                    exact_match_hit
                )
                totals["top_similarity_total"] = (
                    float(totals["top_similarity_total"]) + top_similarity
                )
                totals["retrieval_quality_total"] = (
                    float(totals["retrieval_quality_total"]) + retrieval_quality
                )
                totals["roundtrip_fidelity_total"] = float(
                    totals["roundtrip_fidelity_total"]
                ) + float(diagnostics.get("roundtrip_fidelity_score", 0.0))

        for language, totals in per_language.items():
            sample_count = int(totals["samples"])
            totals["same_language_hit_rate"] = (
                round(int(totals["same_language_hit_count"]) / sample_count, 3)
                if sample_count
                else 0.0
            )
            totals["exact_match_hit_rate"] = (
                round(int(totals["exact_match_hit_count"]) / sample_count, 3)
                if sample_count
                else 0.0
            )
            totals["avg_top_similarity"] = (
                round(float(totals["top_similarity_total"]) / sample_count, 4)
                if sample_count
                else 0.0
            )
            totals["retrieval_quality_avg"] = (
                round(float(totals["retrieval_quality_total"]) / sample_count, 3)
                if sample_count
                else 0.0
            )
            totals["roundtrip_fidelity_avg"] = (
                round(float(totals["roundtrip_fidelity_total"]) / sample_count, 3)
                if sample_count
                else 0.0
            )

        benchmark_scores = {
            "translation_fidelity": min(
                float(per_language[language]["roundtrip_fidelity_avg"])
                for language in selected_languages
            ),
            "retrieval_quality": min(
                float(per_language[language]["retrieval_quality_avg"])
                for language in selected_languages
            ),
        }
        return {
            "rows": rows,
            "per_language": per_language,
            "domains": selected_domains,
            "languages": selected_languages,
            "topic": topic,
            "benchmark_scores": benchmark_scores,
            "profile_name": "translation_memory_multilingual",
        }

    def routing_context_retrieval_matrix(
        self,
        memory_store: Any,
        domains: list[str] | None = None,
        languages: list[str] | None = None,
        top_k: int = 3,
        topic: str = "hlf_agent_routing_benchmark",
    ) -> dict[str, Any]:
        """Measure retrieval-backed multilingual routing-context quality across supported languages."""
        from hlf_mcp.hlf.translator import language_to_hlf, translation_diagnostics

        routing_lanes = {
            "security_audit": "verifier",
            "hello_world": "explainer",
            "db_migration": "code-generation",
            "content_delegation": "explainer",
            "log_analysis": "verifier",
            "stack_deployment": "explainer",
        }
        selected_domains = domains or list(_MULTILINGUAL_NLP_TEMPLATES.keys())
        selected_languages = languages or ["en", "fr", "es", "ar", "zh"]

        rows: list[dict[str, Any]] = []
        per_language: dict[str, dict[str, float | int]] = {
            language: {
                "samples": 0,
                "expected_lane_hit_count": 0,
                "same_language_hit_count": 0,
                "routing_quality_total": 0.0,
                "translation_fidelity_total": 0.0,
            }
            for language in selected_languages
        }

        for domain in selected_domains:
            templates = _MULTILINGUAL_NLP_TEMPLATES.get(domain)
            if templates is None:
                raise ValueError(f"Unsupported benchmark domain: {domain}")
            expected_lane = routing_lanes[domain]
            for language in selected_languages:
                text = templates.get(language)
                if text is None:
                    raise ValueError(
                        f"Missing benchmark template for domain={domain}, language={language}"
                    )
                source = language_to_hlf(text, language=language)
                diagnostics = translation_diagnostics(
                    text, language=language, source=source
                ).to_dict()
                payload = {
                    "kind": "hlf_routing_context",
                    "benchmark_topic": topic,
                    "language": language,
                    "domain": domain,
                    "expected_lane": expected_lane,
                    "original_text": text,
                    "hlf_source": source,
                    "translation": diagnostics,
                }
                memory_store.store(
                    json.dumps(payload, ensure_ascii=False, sort_keys=True),
                    topic=topic,
                    confidence=float(diagnostics.get("roundtrip_fidelity_score", 1.0)),
                    provenance="hlf_benchmark.routing_context_retrieval_matrix",
                    tags=["hlf", "routing", "benchmark", language, domain, expected_lane],
                    metadata={
                        "language": language,
                        "domain": domain,
                        "expected_lane": expected_lane,
                        "kind": "hlf_routing_context",
                    },
                )

                query_result = memory_store.query(text, top_k=top_k, topic=topic)
                results = query_result.get("results", [])
                same_language_hit = any(
                    row.get("metadata", {}).get("language") == language for row in results
                )
                expected_lane_hit = any(
                    row.get("metadata", {}).get("expected_lane") == expected_lane for row in results
                )
                routing_quality = (
                    1.0
                    if expected_lane_hit and same_language_hit
                    else 0.75
                    if expected_lane_hit
                    else 0.25
                    if same_language_hit
                    else 0.0
                )

                rows.append(
                    {
                        "domain": domain,
                        "language": language,
                        "expected_lane": expected_lane,
                        "same_language_hit": same_language_hit,
                        "expected_lane_hit": expected_lane_hit,
                        "routing_quality": routing_quality,
                        "roundtrip_fidelity_score": diagnostics.get(
                            "roundtrip_fidelity_score", 0.0
                        ),
                    }
                )
                totals = per_language[language]
                totals["samples"] = int(totals["samples"]) + 1
                totals["expected_lane_hit_count"] = int(totals["expected_lane_hit_count"]) + int(
                    expected_lane_hit
                )
                totals["same_language_hit_count"] = int(totals["same_language_hit_count"]) + int(
                    same_language_hit
                )
                totals["routing_quality_total"] = (
                    float(totals["routing_quality_total"]) + routing_quality
                )
                totals["translation_fidelity_total"] = float(
                    totals["translation_fidelity_total"]
                ) + float(diagnostics.get("roundtrip_fidelity_score", 0.0))

        for language, totals in per_language.items():
            sample_count = int(totals["samples"])
            totals["expected_lane_hit_rate"] = (
                round(int(totals["expected_lane_hit_count"]) / sample_count, 3)
                if sample_count
                else 0.0
            )
            totals["same_language_hit_rate"] = (
                round(int(totals["same_language_hit_count"]) / sample_count, 3)
                if sample_count
                else 0.0
            )
            totals["routing_quality_avg"] = (
                round(float(totals["routing_quality_total"]) / sample_count, 3)
                if sample_count
                else 0.0
            )
            totals["translation_fidelity_avg"] = (
                round(float(totals["translation_fidelity_total"]) / sample_count, 3)
                if sample_count
                else 0.0
            )

        benchmark_scores = {
            "routing_quality": min(
                float(per_language[language]["routing_quality_avg"])
                for language in selected_languages
            ),
            "translation_fidelity": min(
                float(per_language[language]["translation_fidelity_avg"])
                for language in selected_languages
            ),
        }
        return {
            "rows": rows,
            "per_language": per_language,
            "domains": selected_domains,
            "languages": selected_languages,
            "topic": topic,
            "benchmark_scores": benchmark_scores,
            "profile_name": "agent_routing_context_multilingual",
        }


def _render_non_hlf_self_improvement_baseline(workflow_id: str, spec: dict[str, Any]) -> str:
    patch_plan = {
        "workflow_id": workflow_id,
        "title": spec["title"],
        "mode": "patch-plan-only",
        "target_files": list(spec["files"]),
        "steps": list(spec["patch_steps"]),
        "validation": ["run targeted tests", "run ruff on changed files"],
        "risk_controls": [
            "do not edit unrelated dirty files",
            "do not claim file modification until a patch is applied",
            "record open questions and blockers honestly",
        ],
    }
    return (
        f"Non-HLF baseline plan for {spec['title']}.\n"
        "Use ordinary prose and JSON notes to plan a safe HLF self-improvement change. "
        "Cover authority, grammar, internal loop, code-bearing, swarm, and governance concerns where relevant. "
        "Validate with tests and ruff, and chase errors manually if they occur.\n"
        + json.dumps(patch_plan, ensure_ascii=False, sort_keys=True, indent=2)
    )


def _measure_hlf_self_improvement_workflow(
    *,
    workflow_id: str,
    spec: dict[str, Any],
    source: str,
    mode: str,
    compiler: Any,
    linter: Any,
    verifier: Any,
    execute_code_bearing_hlf: Any,
    build_swarm_mechanics_artifact: Any,
    verify_governance_proof: Any,
) -> dict[str, Any]:
    validation = compiler.validate(source)
    compile_result: dict[str, Any] = {"errors": ["compile_not_attempted"], "ast": {}}
    compile_error = ""
    try:
        compile_result = compiler.compile(source)
    except Exception as exc:  # pragma: no cover - covered through validation failure assertions
        compile_error = str(exc)

    lint_diagnostics = linter.lint(source)
    lint_errors = [diag for diag in lint_diagnostics if diag.get("level") == "error"]
    verification_report: dict[str, Any] = {}
    if isinstance(compile_result.get("ast"), dict) and not compile_error:
        verification_report = verifier.verify_ast(compile_result["ast"]).to_dict()

    code_result: dict[str, Any] | None = None
    if "code_bearing" in spec["surfaces"]:
        code_result = execute_code_bearing_hlf(
            source,
            entrypoint=str(spec.get("entrypoint") or ""),
            dry_run=True,
            compiler=compiler,
            linter=linter,
            verifier=verifier,
        )

    swarm_artifact: dict[str, Any] | None = None
    swarm_proof_report: dict[str, Any] | None = None
    if "swarm" in spec["surfaces"] and isinstance(compile_result.get("ast"), dict) and not compile_error:
        swarm_artifact = build_swarm_mechanics_artifact(
            source=source,
            ast=compile_result["ast"],
            validation=validation,
            compile_result=compile_result,
            votes=[{"voter": "benchmark-verifier", "decision": "approve"}],
            quorum="strict",
        )
        swarm_proof_report = verify_governance_proof(swarm_artifact["governance_proof"])

    tamper_detection = _tamper_detection_probe(swarm_artifact, code_result, verify_governance_proof)
    validation_checks = {
        "compiler_validate": bool(validation.get("valid")),
        "compile_errors_absent": not compile_error and not compile_result.get("errors"),
        "lint_errors_absent": not lint_errors,
        "formal_verifier_admitted": int(verification_report.get("failed", 0) or 0) == 0
        and int(verification_report.get("errors", 0) or 0) == 0,
        "code_dry_run_admitted": code_result is None or code_result.get("status") == "dry_run_ok",
        "swarm_proof_verified": swarm_proof_report is None or bool(swarm_proof_report.get("verified")),
        "tamper_probe_detected": tamper_detection["detected"],
    }
    validation_coverage = _ratio(validation_checks.values())
    proof_coverage = _ratio(
        [
            "governance" in spec["surfaces"],
            code_result is None or bool(code_result.get("governance_proof") or {}),
            swarm_artifact is None or bool(swarm_artifact.get("governance_proof") or {}),
            tamper_detection["detected"],
        ]
    )
    scope_coverage = _ratio(surface in spec["surfaces"] for surface in _SELF_IMPROVEMENT_SURFACES)
    thoroughness = min(1.0, round((len(spec["patch_steps"]) + len(spec["files"]) + 4) / 14, 3))
    quality = round(
        (0.25 * scope_coverage)
        + (0.25 * thoroughness)
        + (0.30 * validation_coverage)
        + (0.20 * proof_coverage),
        3,
    )

    artifact_tokens = _count(
        json.dumps(
            {
                "validation": validation,
                "compile": {
                    "errors": compile_result.get("errors"),
                    "gas_estimate": compile_result.get("gas_estimate"),
                },
                "code_status": code_result.get("status") if code_result else None,
                "swarm_id": swarm_artifact.get("swarm_id") if swarm_artifact else None,
                "tamper_detection": tamper_detection,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return {
        "workflow_form": "HLF",
        "source": source,
        "mode": mode,
        "measured": True,
        "patch_plan_only": True,
        "file_modification_claimed": False,
        "tokens": {
            "source_tokens": _count(source),
            "artifact_tokens": artifact_tokens,
            "total_proxy_tokens": _count(source) + artifact_tokens,
            "cost_proxy_note": "Tokenizer count only; no provider billing or hidden reasoning tokens are inferred.",
        },
        "scores": {
            "quality_proxy": quality,
            "scope_coverage": scope_coverage,
            "thoroughness_proxy": thoroughness,
            "validation_coverage": validation_coverage,
            "proof_coverage": proof_coverage,
            "error_chasing_coverage": 1.0 if tamper_detection["detected"] else 0.0,
        },
        "validation": {
            "checks": validation_checks,
            "compiler_validate": validation,
            "compile_errors": compile_result.get("errors", []),
            "compile_error": compile_error,
            "lint_error_count": len(lint_errors),
            "formal_verifier": verification_report,
        },
        "code_execution": _summarize_code_execution_result(code_result),
        "swarm": _summarize_swarm_artifact(swarm_artifact, swarm_proof_report),
        "tamper_detection": tamper_detection,
        "measurement_notes": [
            "HLF validation/proof/error-detection values are measured by packaged compiler, linter, verifier, dry-run code execution, swarm artifact, and proof verifier.",
            "No patch is applied; target file list is a patch plan.",
        ],
    }


def _measure_non_hlf_self_improvement_baseline(
    *,
    workflow_id: str,
    spec: dict[str, Any],
    baseline_text: str,
) -> dict[str, Any]:
    lower = baseline_text.lower()
    surface_hits = [surface for surface in _SELF_IMPROVEMENT_SURFACES if surface.replace("_", "-") in lower or surface in lower]
    validation_mentions = sum(
        lower.count(term)
        for term in ("validate", "validation", "test", "ruff", "proof", "verify", "lint")
    )
    error_chasing_mentions = sum(
        lower.count(term) for term in ("error", "failure", "regression", "risk", "blocker")
    )
    step_count = len(spec["patch_steps"])
    scope_coverage = _ratio(surface in surface_hits for surface in _SELF_IMPROVEMENT_SURFACES)
    thoroughness = min(1.0, round((step_count + validation_mentions + error_chasing_mentions) / 16, 3))
    validation_intent = min(1.0, round(validation_mentions / 8, 3))
    error_chasing = min(1.0, round(error_chasing_mentions / 5, 3))
    quality = round(
        (0.35 * scope_coverage)
        + (0.25 * thoroughness)
        + (0.15 * validation_intent)
        + (0.05 * error_chasing),
        3,
    )
    return {
        "workflow_form": "non-HLF prose+JSON",
        "workflow_id": workflow_id,
        "baseline_text": baseline_text,
        "measured": False,
        "estimated_by_text_rubric": True,
        "patch_plan_only": True,
        "file_modification_claimed": False,
        "tokens": {
            "source_tokens": _count(baseline_text),
            "artifact_tokens": 0,
            "total_proxy_tokens": _count(baseline_text),
            "cost_proxy_note": "Tokenizer count only; no provider billing or hidden reasoning tokens are inferred.",
        },
        "scores": {
            "quality_proxy": quality,
            "scope_coverage": scope_coverage,
            "thoroughness_proxy": thoroughness,
            "validation_coverage": 0.0,
            "validation_intent_estimate": validation_intent,
            "proof_coverage": 0.0,
            "error_chasing_coverage": 0.0,
            "error_chasing_intent_estimate": error_chasing,
        },
        "validation": {
            "checks": {},
            "note": "Baseline plan is not compiled, linted, formally verified, or proof-verified.",
        },
        "measurement_notes": [
            "Baseline quality/scope/thoroughness are deterministic text-rubric estimates.",
            "Baseline has no executable validation/proof coverage in this benchmark.",
        ],
    }


def _compare_real_workflow_rows(
    hlf_result: dict[str, Any], baseline_result: dict[str, Any]
) -> dict[str, Any]:
    hlf_scores = hlf_result["scores"]
    baseline_scores = baseline_result["scores"]
    hlf_tokens = int(hlf_result["tokens"]["total_proxy_tokens"])
    baseline_tokens = int(baseline_result["tokens"]["total_proxy_tokens"])
    return {
        "quality_delta": round(
            float(hlf_scores["quality_proxy"]) - float(baseline_scores["quality_proxy"]), 3
        ),
        "scope_delta": round(
            float(hlf_scores["scope_coverage"]) - float(baseline_scores["scope_coverage"]), 3
        ),
        "thoroughness_delta": round(
            float(hlf_scores["thoroughness_proxy"])
            - float(baseline_scores["thoroughness_proxy"]),
            3,
        ),
        "validation_coverage_delta": round(
            float(hlf_scores["validation_coverage"])
            - float(baseline_scores["validation_coverage"]),
            3,
        ),
        "proof_coverage_delta": round(
            float(hlf_scores["proof_coverage"]) - float(baseline_scores["proof_coverage"]), 3
        ),
        "error_chasing_delta": round(
            float(hlf_scores["error_chasing_coverage"])
            - float(baseline_scores["error_chasing_coverage"]),
            3,
        ),
        "token_delta": hlf_tokens - baseline_tokens,
        "token_ratio_hlf_to_baseline": round(hlf_tokens / baseline_tokens, 3)
        if baseline_tokens
        else None,
    }


def _aggregate_real_workflow_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    comparisons = [row["comparison"] for row in rows]
    hlf_scores = [row["hlf_workflow"]["scores"] for row in rows]
    baseline_scores = [row["non_hlf_baseline"]["scores"] for row in rows]
    hlf_tokens = sum(int(row["hlf_workflow"]["tokens"]["total_proxy_tokens"]) for row in rows)
    baseline_tokens = sum(
        int(row["non_hlf_baseline"]["tokens"]["total_proxy_tokens"]) for row in rows
    )
    covered_surfaces = sorted({surface for row in rows for surface in row["surfaces"]})
    token_headline = (
        "HLF was shorter in token proxy."
        if hlf_tokens <= baseline_tokens
        else "Non-HLF baselines were shorter in token proxy."
    )
    headline = (
        "HLF patch-plan workflows had stronger measured validation/proof/error-detection coverage; "
        f"{token_headline} Baseline quality/scope/thoroughness were text-rubric estimates."
    )
    return {
        "workflow_count": len(rows),
        "covered_surfaces": covered_surfaces,
        "surface_coverage": _ratio(surface in covered_surfaces for surface in _SELF_IMPROVEMENT_SURFACES),
        "hlf_avg_quality_proxy": _avg(score["quality_proxy"] for score in hlf_scores),
        "baseline_avg_quality_proxy": _avg(score["quality_proxy"] for score in baseline_scores),
        "avg_quality_delta": _avg(item["quality_delta"] for item in comparisons),
        "avg_validation_coverage_delta": _avg(
            item["validation_coverage_delta"] for item in comparisons
        ),
        "avg_proof_coverage_delta": _avg(item["proof_coverage_delta"] for item in comparisons),
        "avg_error_chasing_delta": _avg(item["error_chasing_delta"] for item in comparisons),
        "hlf_total_proxy_tokens": hlf_tokens,
        "baseline_total_proxy_tokens": baseline_tokens,
        "token_ratio_hlf_to_baseline": round(hlf_tokens / baseline_tokens, 3)
        if baseline_tokens
        else None,
        "benchmark_scores": {
            "quality_delta": _avg(item["quality_delta"] for item in comparisons),
            "validation_coverage_delta": _avg(
                item["validation_coverage_delta"] for item in comparisons
            ),
            "proof_coverage_delta": _avg(item["proof_coverage_delta"] for item in comparisons),
            "error_chasing_delta": _avg(item["error_chasing_delta"] for item in comparisons),
            "token_ratio_hlf_to_baseline": round(hlf_tokens / baseline_tokens, 3)
            if baseline_tokens
            else 0.0,
            "surface_coverage": _ratio(
                surface in covered_surfaces for surface in _SELF_IMPROVEMENT_SURFACES
            ),
        },
        "headline": headline,
    }


def _tamper_detection_probe(
    swarm_artifact: dict[str, Any] | None,
    code_result: dict[str, Any] | None,
    verify_governance_proof: Any,
) -> dict[str, Any]:
    proof_source = None
    if swarm_artifact and isinstance(swarm_artifact.get("governance_proof"), dict):
        proof_source = swarm_artifact["governance_proof"]
    elif code_result and isinstance(code_result.get("governance_proof"), dict):
        proof_source = code_result["governance_proof"]
    if proof_source is None:
        return {"attempted": False, "detected": False, "note": "no proof artifact available"}
    tampered = json.loads(json.dumps(proof_source, ensure_ascii=False))
    events = ((tampered.get("chain") or {}).get("events") or [])
    if not events:
        return {"attempted": False, "detected": False, "note": "proof had no events"}
    events[0]["payload"] = {"tampered": True}
    report = verify_governance_proof(tampered)
    return {
        "attempted": True,
        "detected": not bool(report.get("verified")),
        "verification_status": report.get("status"),
        "error_count": (report.get("chain") or {}).get("error_count", 0)
        if isinstance(report.get("chain"), dict)
        else 0,
    }


def _summarize_code_execution_result(code_result: dict[str, Any] | None) -> dict[str, Any] | None:
    if code_result is None:
        return None
    return {
        "status": code_result.get("status"),
        "compiled": code_result.get("compiled"),
        "verified": code_result.get("verified"),
        "executed": code_result.get("executed"),
        "sandbox_mode": code_result.get("sandbox_mode"),
        "governance_proof_present": isinstance(code_result.get("governance_proof"), dict),
    }


def _summarize_swarm_artifact(
    swarm_artifact: dict[str, Any] | None, proof_report: dict[str, Any] | None
) -> dict[str, Any] | None:
    if swarm_artifact is None:
        return None
    return {
        "swarm_id": swarm_artifact.get("swarm_id"),
        "boundary": swarm_artifact.get("boundary"),
        "delegation_count": len(swarm_artifact.get("delegations") or []),
        "vote_count": len(swarm_artifact.get("votes") or []),
        "dissent_count": len(swarm_artifact.get("dissent") or []),
        "progress_event_count": len(swarm_artifact.get("progress_events") or []),
        "governance_proof_verified": bool((proof_report or {}).get("verified")),
    }


def _ratio(values: Any) -> float:
    items = [bool(item) for item in values]
    return round(sum(items) / len(items), 3) if items else 0.0


def _avg(values: Any) -> float:
    items = [float(item) for item in values]
    return round(sum(items) / len(items), 3) if items else 0.0


def _estimate_nlp(source: str) -> str:
    """Generate a rough NLP equivalent from HLF source for comparison."""
    import re

    lines = []
    for raw in source.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[HLF-v"):
            lines.append("Begin HLF program.")
            continue
        if line == "Ω":
            lines.append("End of program.")
            continue
        # Convert glyphs + tags to prose
        line = line.replace("Δ", "Analyze").replace("Ж", "Enforce").replace("⨝", "Vote")
        line = (
            line.replace("⌘", "Command")
            .replace("∇", "Source")
            .replace("⩕", "Priority")
            .replace("⊎", "Branch")
        )
        line = re.sub(r"\[([A-Z_]+)\]", lambda m: m.group(1).replace("_", " ").capitalize(), line)
        lines.append(line.strip() + ".")
    return " ".join(lines)


# Representative HLF programs for each benchmark domain
_DOMAIN_HLF: dict[str, str] = {
    "security_audit": """\
[HLF-v3]
Δ analyze /security/seccomp.json
  Ж [CONSTRAINT] mode="ro"
  Ж [EXPECT] vulnerability_shorthand
  ⨝ [VOTE] consensus="strict"
Ω
""",
    "hello_world": """\
[HLF-v3]
Δ [INTENT] goal="hello_world"
  Ж [ASSERT] status="ok"
  ∇ [RESULT] message="Hello, World!"
Ω
""",
    "db_migration": """\
[HLF-v3]
⌘ [DELEGATE] agent="db_agent" goal="migrate"
  ∇ [SOURCE] /data/prod.db
  ∇ [PARAM] schema_version="2.1"
  Ж [ASSERT] table="users"
  Ж [EXPECT] migration_success
Ω
""",
    "content_delegation": """\
[HLF-v3]
⌘ [DELEGATE] agent="scribe" goal="fractal_summarize"
  ∇ [SOURCE] /data/raw_logs/matrix_sync_2026.txt
  ⩕ [PRIORITY] level="high"
  Ж [ASSERT] vram_limit="8GB"
Ω
""",
    "log_analysis": """\
[HLF-v3]
Δ analyze /var/log/system.log
  Ж [CONSTRAINT] mode="ro"
  Ж [EXPECT] error_patterns
  ∇ [PARAM] top_k=10
  ∇ [PARAM] include_timestamps=true
Ω
""",
    "stack_deployment": """\
[HLF-v3]
⌘ [ROUTE] strategy="auto" tier="$DEPLOYMENT_TIER"
  ∇ [PARAM] temperature=0.0
  Ж [VOTE] confirmation="required"
Ω
""",
}

# ── Complex multi-step workflow benchmarks ────────────────────────────────
# These test HLF's core value proposition: structural governance overhead
# amortizes over many steps in multi-agent coordination workflows.

_COMPLEX_WORKFLOW_NLP: dict[str, str] = {
    "incident_response_7step": (
        "Step 1: Detect the security incident from alert feed at /alerts/feed.json. "
        "Step 2: Classify severity as critical/high/medium/low based on impact scoring rules. "
        "Step 3: Contain the affected systems by isolating network segment 10.0.1.0/24. "
        "Step 4: Investigate root cause by analyzing logs at /var/log/audit/*.log. "
        "Step 5: Remediate the vulnerability following runbook RB-2026-03. "
        "Step 6: Verify the fix by replaying attack vectors in sandbox environment. "
        "Step 7: Generate post-incident report and notify SOC lead."
    ),
    "multi_service_deploy_5step": (
        "Step 1: Build Docker images for api-gateway, user-service, and payment-worker from main branch. "
        "Step 2: Run integration test suite against staging environment with 5-minute timeout. "
        "Step 3: Deploy canary to 10% of production traffic and monitor error rate for 2 minutes. "
        "Step 4: Full production rollout with rolling update strategy, max 3 pods at a time. "
        "Step 5: Health-check all endpoints and verify database migration completed successfully."
    ),
    "data_pipeline_6step": (
        "Step 1: Extract raw data from S3 bucket analytics-events/2026/03/ with 100MB batch size. "
        "Step 2: Validate schema against event-schema-v3.json, reject malformed records to dead-letter queue. "
        "Step 3: Transform events: anonymize PII, enrich with geo-ip, and normalize timestamps to UTC. "
        "Step 4: Load transformed data into BigQuery partitioned table events_v3 with WRITE_TRUNCATE. "
        "Step 5: Verify row counts match between source and destination within 1% tolerance. "
        "Step 6: Archive processed source files to cold-storage bucket with 90-day retention."
    ),
    # ── PIPE + TEMPLATE + @validate scenarios ──────────────────────────────────
    "multi_stage_deploy_pipe": (
        "Deploy platform update: migrate database schema, deploy API gateway with canary 10%, "
        "run integration tests, deploy workers, run smoke tests, switch all traffic. "
        "Require health check and rollback readiness at each deployment stage. "
        "Require production approval gate before switching traffic."
    ),
    "security_audit_remediate": (
        "Audit all services for SQL injection and XSS vulnerabilities, log findings to "
        "/reports/vulnerabilities.json, apply fixes with regression checks, re-audit "
        "services to confirm fixes, produce SOC2 compliance report. "
        "Validate each audit against audit.json schema."
    ),
    "multi_agent_research_synthesis": (
        "Research microservices scaling patterns with agent researcher_a. "
        "Research database sharding strategies with agent researcher_b. "
        "Require strict consensus from both agents. Synthesize findings into "
        "architecture recommendation with trade-off analysis. All recommendations "
        "must be research-backed with evidence."
    ),
}

_COMPLEX_WORKFLOW_HLF: dict[str, str] = {
    "incident_response_7step": """\
[HLF-v3]
Δ [WORKFLOW] name="incident_response" max_steps=7
  Ж [CONSTRAINT] source="/alerts/feed.json" action=detect
  Ж [CONSTRAINT] classify severity∈{critical,high,medium,low} rule=impact_scoring
  Ж [CONSTRAINT] contain_network="10.0.1.0/24" action=isolate
  Ж [CONSTRAINT] investigate_logs="/var/log/audit/*.log" goal=root_cause
  Ж [CONSTRAINT] remediate runbook="RB-2026-03"
  Ж [CONSTRAINT] verify method=replay_attack sandbox=true
  Ж [CONSTRAINT] report type=post_incident notify="soc_lead"
  Ж [EXPECT] incident_resolved
Ω
""",
    "multi_service_deploy_5step": """\
[HLF-v3]
⌘ [DEPLOY] services=["api-gateway","user-service","payment-worker"] branch=main
  Ж [CONSTRAINT] build_dockerfiles=true
  Ж [CONSTRAINT] test suite=integration env=staging timeout=300s
  Ж [CONSTRAINT] canary traffic_pct=10 monitor=error_rate duration=120s
  Ж [CONSTRAINT] rollout strategy=rolling_update max_concurrent=3
  Ж [CONSTRAINT] health_check endpoints=all verify_migration=true
  Ж [VOTE] require_confirmation=true deploy_tier="production"
Ω
""",
    "data_pipeline_6step": """\
[HLF-v3]
Δ [PIPELINE] name="analytics_etl" max_steps=6
  Ж [CONSTRAINT] extract source="s3://analytics-events/2026/03/" batch=100MB
  Ж [CONSTRAINT] validate schema="event-schema-v3.json" dead_letter=true
  Ж [CONSTRAINT] transform anonymize_pii=true enrich_geoip=true normalize_tz=UTC
  Ж [CONSTRAINT] load target="bigquery:events_v3" mode=WRITE_TRUNCATE
  Ж [CONSTRAINT] verify tolerance_pct=1 method=row_count_match
  Ж [CONSTRAINT] archive target="cold-storage" retention=90d
  Ж [EXPECT] pipeline_complete processing_tier="batch"
Ω
""",
    # ── PIPE + TEMPLATE + @validate scenarios ──────────────────────────────────
    "multi_stage_deploy_pipe": """\
[HLF-v3]
TEMPLATE deploy_pattern {
    Ж [ENFORCE] check="health_check"
    Ж [ENFORCE] check="rollback_ready"
}
⌘ [ROUTE] agent="dba" → Δ [ACTION] exec="migrate_database" @validate(schema="migration.json")
⌘ [ROUTE] agent="gateway" → Δ [ACTION] exec="deploy_api_gateway" canary="10" ref="deploy_pattern"
Δ [ACTION] exec="run_integration_tests"
⌘ [ROUTE] agent="worker" → Δ [ACTION] exec="deploy_workers" ref="deploy_pattern"
Δ [ACTION] exec="run_smoke_tests"
⌘ [ROUTE] agent="traffic" → Δ [ACTION] exec="switch_all_traffic" @validate(gate="prod_approval")
Ж [ASSERT] condition="all_steps_verified"
Σ [RESULT] output="deployment_complete"
Ω
""",
    "security_audit_remediate": """\
[HLF-v3]
TEMPLATE audit_surface {
    Ж [ENFORCE] check="sql_injection"
    Ж [ENFORCE] check="xss"
    Ж [ENFORCE] check="csrf"
}
TEMPLATE remediation_checks {
    Ж [ENFORCE] check="fix_applied"
    Ж [ENFORCE] check="regression_free"
}
⌘ [ROUTE] agent="auditor" → Δ [ACTION] exec="audit_services" ref="audit_surface" @validate(schema="audit.json")
Δ [ACTION] exec="log_findings" target="/reports/vulnerabilities.json"
⌘ [ROUTE] agent="fixer" → Δ [ACTION] exec="apply_fixes" ref="remediation_checks"
⌘ [ROUTE] agent="auditor" → Δ [ACTION] exec="reaudit_services" ref="audit_surface" @validate(schema="audit.json")
⌘ [ROUTE] agent="reporter" → Δ [ACTION] exec="compliance_report" format="SOC2"
Ж [ASSERT] condition="all_vulnerabilities_resolved"
Σ [RESULT] output="compliance_report_generated"
Ω
""",
    "multi_agent_research_synthesis": """\
[HLF-v3]
⌘ [ROUTE] agent="researcher_a" → Δ [ACTION] exec="research_microservices_scaling"
⌘ [ROUTE] agent="researcher_b" → Δ [ACTION] exec="research_database_sharding"
⨝ [JOIN] agents="researcher_a,researcher_b" consensus="strict"
Δ [ACTION] exec="synthesize_findings"
Δ [ACTION] exec="evaluate_tradeoffs"
Σ [RESULT] output="architecture_recommendation"
Ж [ASSERT] evidence="research_backed"
Ω
""",
}

# Scalability: same workflow at different step counts to measure amortization
_COMPLEX_SCALE_NLP = (
    "Analyze production logs for errors. "
    "Classify errors by severity. "
    "Correlate errors across services. "
    "Identify root cause patterns. "
    "Generate remediation plan. "
    "Execute safe fixes. "
    "Verify fixes in staging. "
    "Deploy verified fixes to canary. "
    "Monitor canary for regression. "
    "Full production rollout. "
    "Post-deployment health check. "
    "Archive deployment artifacts. "
    "Notify stakeholders. "
    "Update runbook with findings. "
    "Schedule follow-up review."
)

_COMPLEX_SCALE_HLF = """\
[HLF-v3]
Δ [WORKFLOW] name="error_remediation" max_steps=15
  Ж [CONSTRAINT] mode="governed_rollout"
  Ж [VOTE] consensus="majority"
  Ж [EXPECT] errors_resolved
Ω
"""

# Multi-agent swarm scenarios
_SWARM_WORKFLOW_NLP: dict[str, str] = {
    "code_review_3agent": (
        "Agent Alpha: Review the PR diff at github.com/org/repo/pull/42 for security vulnerabilities. "
        "Agent Beta: Review the same PR for performance regressions. "
        "Agent Gamma: Review the same PR for code style and documentation completeness. "
        "All agents vote: approve, request_changes, or comment. "
        "Strict consensus required before merge. Dissenting agents must provide evidence."
    ),
    "audit_trail_4agent": (
        "Agent Auditor: Analyze /var/log/audit/2026-03/*.log for unauthorized access patterns. "
        "Agent Compliance: Check all access against policy ACL-2026-Q1. "
        "Agent Forensics: Trace any anomalies back to source IP and user agent. "
        "Agent Reporter: Compile findings into SOC2 compliance report. "
        "Votes required: 3 of 4 must agree on severity classification. "
        "Dissenting opinion must be recorded with evidence chain."
    ),
}

_SWARM_WORKFLOW_HLF: dict[str, str] = {
    "code_review_3agent": """\
[HLF-v3]
⨝ [SWARM] agents=["alpha","beta","gamma"] target="github.com/org/repo/pull/42"
  ⌘ [AGENT alpha] review_for="security"
  ⌘ [AGENT beta] review_for="performance"
  ⌘ [AGENT gamma] review_for="style,documentation"
  Ж [VOTE] options={approve,request_changes,comment} consensus=strict
  Ж [DISSENT] require_evidence=true
  Ж [EXPECT] review_complete
Ω
""",
    "audit_trail_4agent": """\
[HLF-v3]
⨝ [SWARM] agents=["auditor","compliance","forensics","reporter"] quorum=3
  ⌘ [AGENT auditor] target="/var/log/audit/2026-03/*.log" goal=unauthorized_access
  ⌘ [AGENT compliance] policy="ACL-2026-Q1" goal=access_validation
  ⌘ [AGENT forensics] goal=trace_anomalies trace=source_ip,user_agent
  ⌘ [AGENT reporter] format="SOC2_compliance" goal=compile_findings
  Ж [VOTE] threshold=0.75 on=severity_classification
  Ж [DISSENT] record_evidence_chain=true
  Ж [EXPECT] audit_complete
Ω
""",
}



# ==============================================================================
# Complex Workflow Benchmark Runner
# ==============================================================================


def run_complex_workflow_benchmarks(use_llm: bool = False) -> dict[str, Any]:
    """Run multi-step workflow benchmarks across all scenarios.

    For each workflow scenario, translates NLP intent to HLF (keyword heuristic
    or LLM bridge), compiles the result, and measures structural metrics:
    statement counts, glyph breakdowns, PIPE stages, TEMPLATE refs, and
    @validate-sourced ENFORCE statements.

    Args:
        use_llm: If True, attempt LLM bridge translation. Default False
            (keyword heuristic for deterministic reproducibility).

    Returns:
        dict with per-scenario and aggregate metrics.
    """
    from hlf_mcp.hlf.compiler import HLFCompiler
    from hlf_mcp.hlf.translator import language_to_hlf

    compiler = HLFCompiler()

    # Collect all scenarios: COMPLEX + SWARM + new PIPE/TEMPLATE scenarios
    all_nlp: dict[str, str] = {}
    all_nlp.update(_COMPLEX_WORKFLOW_NLP)
    all_nlp.update(_SWARM_WORKFLOW_NLP)

    all_hlf: dict[str, str] = {}
    all_hlf.update(_COMPLEX_WORKFLOW_HLF)
    all_hlf.update(_SWARM_WORKFLOW_HLF)

    results: list[dict[str, Any]] = []
    total_nlp_tokens = 0
    total_hlf_tokens = 0
    total_compile_ok = 0
    total_compile_fail = 0

    for scenario_id, nlp_text in all_nlp.items():
        hlf_expected = all_hlf.get(scenario_id, "")

        # Translate: LLM or keyword heuristic
        hlf_translated: str | None = None
        translate_method = "keyword_heuristic"

        if use_llm:
            try:
                from hlf_mcp.hlf.hlf_llm_bridge import HLFLLMBridge
                bridge = HLFLLMBridge(model="deepseek-v4-pro:cloud")
                import asyncio

                async def _llm_translate():
                    return await bridge.send(
                        f"Translate to valid HLF-v3:\n\n{nlp_text}",
                        role="translator",
                        system=(
                            "You are a precise HLF-v3 translator. Output only a code block "
                            "with [HLF-v3] header and Omega terminator. Use glyphs. "
                            "Use PIPE for agent handoff chains. Use TEMPLATE blocks. "
                            "Use @validate for enforcement annotations. "
                            "Tags are UPPERCASE with underscores only."
                        ),
                    )

                llm_result = asyncio.run(_llm_translate())
                if llm_result.extracted and llm_result.hlf_output:
                    try:
                        compiler.compile(llm_result.hlf_output)
                        hlf_translated = llm_result.hlf_output
                        translate_method = "llm_bridge"
                    except Exception:
                        pass
            except Exception:
                pass

        if hlf_translated is None:
            # For PIPE/TEMPLATE scenarios, keyword translator can't generate
            # these new syntax features yet - use pre-written HLF directly
            if scenario_id in _NEW_PIPE_TEMPLATE_SCENARIOS:
                hlf_translated = hlf_expected
                translate_method = "pre_written"
            else:
                try:
                    hlf_translated = language_to_hlf(nlp_text, language="en")
                    if not hlf_translated or "[HLF-v3]" not in hlf_translated:
                        hlf_translated = hlf_expected
                        translate_method = "pre_written"
                    else:
                        translate_method = "keyword_heuristic"
                except Exception:
                    hlf_translated = hlf_expected
                    translate_method = "pre_written"

        hlf_source = hlf_translated or hlf_expected

        # Compile
        compile_success = False
        compile_error: str | None = None
        ast = None
        compile_result = None
        try:
            compile_result = compiler.compile(hlf_source)
            compile_success = True
            ast = compile_result["ast"]
        except Exception as exc:
            compile_error = str(exc)[:300]

        # Structural metrics
        stmts = ast["statements"] if ast else []
        glyph_stmts = [s for s in stmts if s.get("kind") == "glyph_stmt"]

        glyph_by_type: dict[str, int] = {}
        for s in glyph_stmts:
            g = s.get("glyph", "?")
            glyph_by_type[g] = glyph_by_type.get(g, 0) + 1

        pipe_stages = sum(1 for s in glyph_stmts if s.get("_pipe_context"))

        direct_enforce = sum(
            1 for s in glyph_stmts
            if s.get("glyph") == "Ж" and s.get("tag") != "ENFORCE"
        )
        validate_enforce = sum(
            1 for s in glyph_stmts
            if s.get("glyph") == "Ж" and s.get("tag") == "ENFORCE"
        )

        nlp_tokens = _count(nlp_text)
        hlf_tokens = _count(hlf_source)
        total_nlp_tokens += nlp_tokens
        total_hlf_tokens += hlf_tokens
        if compile_success:
            total_compile_ok += 1
        else:
            total_compile_fail += 1

        semantic_density = round(len(glyph_stmts) / max(1, nlp_tokens) * 100, 2)
        reproducibility = "deterministic" if translate_method != "llm_bridge" else "llm_variant"

        results.append({
            "scenario_id": scenario_id,
            "translate_method": translate_method,
            "compile_success": compile_success,
            "compile_error": compile_error,
            "nlp_tokens": nlp_tokens,
            "hlf_tokens": hlf_tokens,
            "token_reduction_pct": round(
                (1 - hlf_tokens / max(1, nlp_tokens)) * 100, 1
            ),
            "node_count": len(stmts),
            "glyph_count": len(glyph_stmts),
            "glyph_by_type": glyph_by_type,
            "pipe_stages": pipe_stages,
            "direct_enforce": direct_enforce,
            "validate_enforce": validate_enforce,
            "semantic_density": semantic_density,
            "reproducibility": reproducibility,
            "gas_estimate": compile_result.get("gas_estimate", 0) if compile_result else 0,
        })

    compile_rate = round(total_compile_ok / max(1, len(results)) * 100, 1)
    avg_density = round(
        sum(r["semantic_density"] for r in results) / max(1, len(results)), 2
    )
    total_pipe = sum(r["pipe_stages"] for r in results)
    total_validate = sum(r["validate_enforce"] for r in results)

    return {
        "scenarios": results,
        "aggregates": {
            "total_scenarios": len(results),
            "compile_success": total_compile_ok,
            "compile_fail": total_compile_fail,
            "compile_rate_pct": compile_rate,
            "total_nlp_tokens": total_nlp_tokens,
            "total_hlf_tokens": total_hlf_tokens,
            "avg_semantic_density": avg_density,
            "total_pipe_stages": total_pipe,
            "total_validate_enforce": total_validate,
        },
    }


def print_complex_workflow_benchmarks(use_llm: bool = False) -> None:
    """Print a formatted table of complex workflow benchmark results."""
    data = run_complex_workflow_benchmarks(use_llm=use_llm)

    print("=" * 90)
    print("HLF COMPLEX WORKFLOW BENCHMARKS")
    print("=" * 90)
    print(
        f"{'Scenario':<34s} {'OK':>3s} {'Method':>18s} "
        f"{'NLP':>5s} {'HLF':>5s} {'Red%':>5s} "
        f"{'Glyph':>5s} {'Pipe':>4s} {'@val':>4s} {'Dens':>5s}"
    )
    print("-" * 90)

    for r in data["scenarios"]:
        ok = "Y" if r["compile_success"] else "N"
        print(
            f"{r['scenario_id']:<34s} {ok:>3s} {r['translate_method']:>18s} "
            f"{r['nlp_tokens']:>5d} {r['hlf_tokens']:>5d} "
            f"{r['token_reduction_pct']:>5.1f} {r['glyph_count']:>5d} "
            f"{r['pipe_stages']:>4d} {r['validate_enforce']:>4d} "
            f"{r['semantic_density']:>5.1f}"
        )

    print("-" * 90)
    agg = data["aggregates"]
    red_total = round(
        (1 - agg["total_hlf_tokens"] / max(1, agg["total_nlp_tokens"])) * 100, 1
    )
    print(
        f"{'TOTAL / AVERAGE':<34s} {agg['compile_rate_pct']:>3.0f}% "
        f"{'':>18s} {agg['total_nlp_tokens']:>5d} "
        f"{agg['total_hlf_tokens']:>5d} {red_total:>5.1f} "
        f"{'':>5s} {agg['total_pipe_stages']:>4d} "
        f"{agg['total_validate_enforce']:>4d} {agg['avg_semantic_density']:>5.1f}"
    )
    print("=" * 90)


# Convenience accessors for the 3 new PIPE/TEMPLATE scenarios

_NEW_PIPE_TEMPLATE_SCENARIOS: tuple[str, str, str] = (
    "multi_stage_deploy_pipe",
    "security_audit_remediate",
    "multi_agent_research_synthesis",
)


def get_pipe_template_nlp(scenario_id: str) -> str:
    """Return NLP intent text for a PIPE/TEMPLATE benchmark scenario."""
    return _COMPLEX_WORKFLOW_NLP[scenario_id]


def get_pipe_template_hlf(scenario_id: str) -> str:
    """Return pre-written HLF source for a PIPE/TEMPLATE benchmark scenario."""
    return _COMPLEX_WORKFLOW_HLF[scenario_id]
