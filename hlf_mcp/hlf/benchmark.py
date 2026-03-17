"""
HLF Benchmark — token compression analysis using tiktoken cl100k_base.

Measures HLF token efficiency vs natural language and verbose JSON equivalents.
"""

from __future__ import annotations

from typing import Any

try:
    import tiktoken

    _ENCODER = tiktoken.get_encoding("cl100k_base")

    def _count(text: str) -> int:
        return len(_ENCODER.encode(text))

except ImportError:
    # Fallback: rough word/token estimate
    def _count(text: str) -> int:  # type: ignore[misc]
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
            "compare_text_preview": compare_source[:100] + "..." if len(compare_source) > 100 else compare_source,
            "line_analysis": line_analysis,
        }

    def benchmark_suite(self) -> dict[str, Any]:
        """Run the full benchmark suite against all NLP templates."""
        from hlf_mcp.hlf.grammar import GLYPHS

        results = []
        total_hlf = 0
        total_nlp = 0

        for domain, nlp_text in _NLP_TEMPLATES.items():
            nlp_tokens = _count(nlp_text)
            # Use a representative HLF program for each domain
            hlf_source = _DOMAIN_HLF.get(domain, f"[HLF-v3]\nΔ {domain}\nΩ\n")
            hlf_tokens = _count(hlf_source)
            compression = round((1 - hlf_tokens / nlp_tokens) * 100, 1) if nlp_tokens > 0 else 0
            results.append({
                "domain": domain,
                "nlp_tokens": nlp_tokens,
                "hlf_tokens": hlf_tokens,
                "compression_pct": compression,
            })
            total_hlf += hlf_tokens
            total_nlp += nlp_tokens

        overall = round((1 - total_hlf / total_nlp) * 100, 1) if total_nlp > 0 else 0
        return {
            "results": results,
            "totals": {"hlf": total_hlf, "nlp": total_nlp, "compression_pct": overall},
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
                    raise ValueError(f"Missing benchmark template for domain={domain}, language={language}")
                source = language_to_hlf(text, language=language)
                analysis = self.analyze(source, compare_text=text)
                diagnostics = translation_diagnostics(text, language=language, source=source).to_dict()
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
                lang_totals["input_tokens"] = int(lang_totals["input_tokens"]) + int(analysis["nlp_tokens"])
                lang_totals["hlf_tokens"] = int(lang_totals["hlf_tokens"]) + int(analysis["hlf_tokens"])
                lang_totals["input_bytes"] = int(lang_totals["input_bytes"]) + input_bytes
                lang_totals["fallback_samples"] = int(lang_totals.get("fallback_samples", 0)) + int(diagnostics["fallback_used"])
                lang_totals["roundtrip_fidelity_total"] = float(lang_totals.get("roundtrip_fidelity_total", 0.0)) + float(diagnostics["roundtrip_fidelity_score"])

        for language, totals in per_language.items():
            input_tokens = int(totals["input_tokens"])
            hlf_tokens = int(totals["hlf_tokens"])
            sample_count = int(totals["samples"])
            totals["compression_pct"] = round((1 - hlf_tokens / input_tokens) * 100, 1) if input_tokens > 0 else 0.0
            totals["fallback_rate"] = round((int(totals.get("fallback_samples", 0)) / sample_count), 3) if sample_count > 0 else 0.0
            totals["roundtrip_fidelity_avg"] = round((float(totals.get("roundtrip_fidelity_total", 0.0)) / sample_count), 3) if sample_count > 0 else 0.0

        return {
            "rows": rows,
            "per_language": per_language,
            "domains": selected_domains,
            "languages": selected_languages,
            "tiktoken_model": "cl100k_base",
        }


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
        line = line.replace("⌘", "Command").replace("∇", "Source").replace("⩕", "Priority").replace("⊎", "Branch")
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
