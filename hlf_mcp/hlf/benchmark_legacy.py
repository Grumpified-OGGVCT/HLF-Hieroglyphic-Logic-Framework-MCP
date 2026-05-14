"""
HLF Benchmark ΓÇö token compression analysis using tiktoken cl100k_base.

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


# Reference NLP payloads matching measured README benchmarks.
# These are the full JSON instructions an agent receives — what HLF glyphs
# compress against.  Token counts measured with tiktoken cl100k_base.
_NLP_TEMPLATES: dict[str, str] = {
    "hello_world": (
        '{"task": "greet", "target": "world", "message": "Hello, World!", '
        '"agent_instructions": "Execute a simple greeting intent towards the '
        "world entity. Emit a friendly hello message. This is the canonical "
        'baseline test for HLF compilation.", '
        '"result_format": {"code": 0, "message": "greeting_sent"}}'
    ),
    "security_audit": (
        '{"task": "analyze", "target": "/security/seccomp.json", '
        '"mode": "read-only", "expected_output": "vulnerability_shorthand", '
        '"voting": {"consensus": "strict"}, '
        '"agent_instructions": "Scan the seccomp configuration file for any '
        "CVE vulnerabilities. Access is read-only. Return a compact shorthand "
        "summary of findings. All participating agents must agree on the result "
        'before it is finalized.", '
        '"result_format": {"code": 0, "message": "scan_complete"}}'
    ),
    "content_delegation": (
        '{"task": "delegate", "target_agent": "scribe", '
        '"goal": "fractal_summarize", "source": "/data/raw_research.txt", '
        '"priority": "high", "constraints": {"vram_limit": "8GB"}, '
        '"agent_instructions": "Delegate a fractal summarization task to the '
        "Scribe agent. Use the raw research file as input. This is high "
        "priority and should respect the 8GB VRAM allocation limit for the "
        'local model.", '
        '"result_format": {"code": 0, "message": "delegated"}}'
    ),
    "db_migration": (
        '{"task": "migrate", "database": "user_profiles", '
        '"target_version": "v2.3", "backup_first": true, '
        '"max_downtime": "30s", "dry_run": false, "priority": "high", '
        '"integrity_check": "sha256_hash_of_db_and_version", '
        '"agent_instructions": "Run the database migration for user_profiles '
        "to version v2.3. Create a backup before migrating. Maximum allowed "
        "downtime is 30 seconds. This is not a dry run. Compute a SHA-256 "
        'hash of the database name and version for integrity verification.", '
        '"result_format": {"code": 0, "message": "migration_complete"}}'
    ),
    "log_analysis": (
        '{"task": "summarize", "agent": "scribe", '
        '"source": "/logs/agent_activity_latest.log", '
        '"timespan": "24h", "max_tokens": 2048, '
        '"priority": "medium", "voting": {"consensus": "quorum"}, '
        '"agent_instructions": "Delegate log summarization to the Scribe '
        "agent. Analyze the latest agent activity log for the past 24 hours. "
        "Keep the summary within 2048 tokens. Use quorum consensus \u2014 a "
        'majority of agents must agree on the summary.", '
        '"result_format": {"code": 0, "message": "summary_ready"}}'
    ),
    "stack_deployment": (
        '{"task": "deploy", "stack": "sovereign-prod", "replicas": 3, '
        '"tier": "forge", "health_check": true, '
        '"rollback_on_fail": true, "priority": "urgent", '
        '"agent_instructions": "Deploy the sovereign-prod stack with 3 '
        "replicas on the Forge tier. Enable health checks and automatically "
        "roll back if deployment fails. This is an urgent priority "
        'deployment.", '
        '"result_format": {"code": 0, "message": "deploy_initiated"}}'
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
╬ö [INTENT] goal="self_improve_hlf" workflow="authority_grammar_loop"
Γêç [SOURCE] path="hlf_mcp/hlf/grammar.py"
Γêç [SOURCE] path="governance/tag_i18n.yaml"
╨û [ASSERT] authority_lane="present-packaged-current-truth"
╨û [CONSTRAINT] mode="patch-plan-only"
Γîÿ [DELEGATE] agent="grammar-reviewer" goal="derive_consistency_patch"
Γ¿¥ [VOTE] voter="authority-verifier" decision="approve" quorum="strict"
╨û [EXPECT] validation="validate_compile_lint_proof"
╬⌐
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
╬ö [INTENT] goal="self_improve_hlf_code_execution" workflow="code_bearing_contract"
Γêç [SOURCE] path="hlf_mcp/hlf/code_execution.py"
╨û [ASSERT] authority_lane="present-packaged-current-truth"
╨û [CONSTRAINT] mode="dry-run"
╬ö [CODE] name="patch_notes" language="python" body="plan only: no repository write"
FUNCTION verify_plan {
  RESULT 0 "patch-plan-only"
}
Γ¿¥ [VOTE] voter="sandbox-verifier" decision="approve" quorum="strict"
╬⌐
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
╬ö [INTENT] goal="self_improve_hlf_swarm_governance" workflow="swarm_governance_report"
Γêç [SOURCE] path="hlf_mcp/hlf/swarm_mechanics.py"
Γêç [SOURCE] path="hlf_mcp/hlf/governance_proofs.py"
╨û [CONSTRAINT] mode="patch-plan-only"
Γîÿ [DELEGATE] agent="planner" goal="resource_report_patch" role="coordinator"
Γîÿ [DELEGATE] agent="verifier" goal="proof_boundary_check" role="reviewer"
Γ¿¥ [VOTE] voter="planner" decision="approve" quorum="strict"
╨û [DISSENT] agent="operator" reason="do_not_fake_file_modification" severity="warning"
Γêç [PROGRESS] event_id="bench-swarm-1" phase="patch_plan" status="materialized"
╬⌐
""",
    },
}


_MULTILINGUAL_NLP_TEMPLATES: dict[str, dict[str, str]] = {
    "security_audit": {
        "en": "Please analyze the file at /security/seccomp.json in read-only mode. I expect you to identify vulnerabilities and return them in shorthand format. All agents must reach strict consensus before proceeding.",
        "fr": "Veuillez analyser le fichier /security/seccomp.json en mode lecture seule. Identifiez les vuln├⌐rabilit├⌐s et retournez-les en format abr├⌐g├⌐. Tous les agents doivent parvenir ├á un consensus strict avant de continuer.",
        "es": "Analiza el archivo /security/seccomp.json en modo de solo lectura. Identifica vulnerabilidades y devu├⌐lvelas en formato abreviado. Todos los agentes deben alcanzar un consenso estricto antes de continuar.",
        "ar": "┘è╪▒╪¼┘ë ╪¬╪¡┘ä┘è┘ä ╪º┘ä┘à┘ä┘ü /security/seccomp.json ┘ü┘è ┘ê╪╢╪╣ ╪º┘ä┘é╪▒╪º╪í╪⌐ ┘ü┘é╪╖. ╪¡╪»╪» ╪º┘ä╪½╪║╪▒╪º╪¬ ┘ê╪ú╪╣╪»┘ç╪º ╪¿╪╡┘è╪║╪⌐ ┘à╪«╪¬╪╡╪▒╪⌐. ┘è╪¼╪¿ ╪ú┘å ╪¬╪╡┘ä ╪¼┘à┘è╪╣ ╪º┘ä┘ê┘â┘ä╪º╪í ╪Ñ┘ä┘ë ╪¬┘ê╪º┘ü┘é ╪╡╪º╪▒┘à ┘é╪¿┘ä ╪º┘ä┘à╪¬╪º╪¿╪╣╪⌐.",
        "zh": "Φ»╖Σ╗ÑσÅ¬Φ»╗µ¿íσ╝Åσêåµ₧É /security/seccomp.json µûçΣ╗╢πÇéΦ»åσê½µ╝Åµ┤₧σ╣╢Σ╗Ñτ«ÇσåÖµá╝σ╝ÅΦ┐öσ¢₧πÇéµëÇµ£ëΣ╗úτÉåσ£¿τ╗ºτ╗¡Σ╣ïσëìσ┐àΘí╗Φ╛╛µêÉΣ╕Ñµá╝σà▒Φ»åπÇé",
    },
    "hello_world": {
        "en": "Please say hello to the world and confirm the system is operational. Return a greeting message with status OK.",
        "fr": "Veuillez dire bonjour au monde et confirmer que le syst├¿me est op├⌐rationnel. Retournez un message de salutation avec le statut OK.",
        "es": "Di hola al mundo y confirma que el sistema est├í operativo. Devuelve un mensaje de saludo con estado OK.",
        "ar": "┘è╪▒╪¼┘ë ┘é┘ê┘ä ┘à╪▒╪¡╪¿╪º┘ï ┘ä┘ä╪╣╪º┘ä┘à ┘ê╪¬╪ú┘â┘è╪» ╪ú┘å ╪º┘ä┘å╪╕╪º┘à ┘è╪╣┘à┘ä. ╪ú╪╣╪» ╪▒╪│╪º┘ä╪⌐ ╪¬╪▒╪¡┘è╪¿ ╪¿╪º┘ä╪¡╪º┘ä╪⌐ OK.",
        "zh": "Φ»╖σÉæΣ╕ûτòîΘù«σÑ╜σ╣╢τí«Φ«ñτ│╗τ╗ƒµ¡úσ£¿Φ┐ÉΦíîπÇéΦ┐öσ¢₧σ╕ªµ£ë OK τè╢µÇüτÜäΘù«σÇÖµ╢êµü»πÇé",
    },
    "db_migration": {
        "en": "Execute a database migration on the production database at /data/prod.db. Apply schema version 2.1, create the users table if it does not exist, and run all pending migration scripts. Verify the migration succeeded.",
        "fr": "Ex├⌐cutez une migration de base de donn├⌐es sur la base de production /data/prod.db. Appliquez le sch├⌐ma version 2.1, cr├⌐ez la table users si elle n'existe pas et ex├⌐cutez tous les scripts en attente. V├⌐rifiez que la migration a r├⌐ussi.",
        "es": "Ejecuta una migraci├│n de base de datos en la base de producci├│n /data/prod.db. Aplica la versi├│n 2.1 del esquema, crea la tabla users si no existe y ejecuta todos los scripts pendientes. Verifica que la migraci├│n haya tenido ├⌐xito.",
        "ar": "┘å┘ü╪░ ╪¬╪▒╪¡┘è┘ä ┘é╪º╪╣╪»╪⌐ ╪º┘ä╪¿┘è╪º┘å╪º╪¬ ╪╣┘ä┘ë ┘é╪º╪╣╪»╪⌐ ╪º┘ä╪Ñ┘å╪¬╪º╪¼ /data/prod.db. ╪╖╪¿┘é ┘à╪«╪╖╪╖ ╪º┘ä╪Ñ╪╡╪»╪º╪▒ 2.1╪î ┘ê╪ú┘å╪┤╪ª ╪¼╪»┘ê┘ä users ╪Ñ╪░╪º ┘ä┘à ┘è┘â┘å ┘à┘ê╪¼┘ê╪»╪º┘ï╪î ┘ê╪┤╪║┘ä ╪¼┘à┘è╪╣ ┘å╪╡┘ê╪╡ ╪º┘ä╪¬╪▒╪¡┘è┘ä ╪º┘ä┘à╪╣┘ä┘é╪⌐. ╪¬╪¡┘é┘é ┘à┘å ┘å╪¼╪º╪¡ ╪º┘ä╪¬╪▒╪¡┘è┘ä.",
        "zh": "σ£¿τöƒΣ║ºµò░µì«σ║ô /data/prod.db Σ╕èµëºΦíîµò░µì«σ║ôΦ┐üτº╗πÇéσ║öτö¿ 2.1 τëêµ£¼µ₧╢µ₧ä∩╝îσªéµ₧£ users Φí¿Σ╕ìσ¡ÿσ£¿σêÖσê¢σ╗║σ«â∩╝îσ╣╢Φ┐ÉΦíîµëÇµ£ëσ╛àσñäτÉåτÜäΦ┐üτº╗ΦäÜµ£¼πÇéΘ¬îΦ»üΦ┐üτº╗µêÉσèƒπÇé",
    },
    "content_delegation": {
        "en": "Delegate a fractal summarization task to the scribe agent. The source data is at /data/raw_logs/matrix_sync_2026.txt. Set priority to high. Assert that available VRAM is at least 8GB.",
        "fr": "D├⌐l├⌐guez une t├óche de r├⌐sum├⌐ fractal ├á l'agent scribe. Les donn├⌐es sources sont dans /data/raw_logs/matrix_sync_2026.txt. D├⌐finissez la priorit├⌐ sur haute. Affirmez que la VRAM disponible est d'au moins 8 Go.",
        "es": "Delega una tarea de resumen fractal al agente scribe. Los datos fuente est├ín en /data/raw_logs/matrix_sync_2026.txt. Establece la prioridad en alta. Afirma que la VRAM disponible sea de al menos 8 GB.",
        "ar": "┘ü┘ê┘æ╪╢ ┘à┘ç┘à╪⌐ ╪¬┘ä╪«┘è╪╡ ┘â╪│┘ê╪▒┘è ╪Ñ┘ä┘ë ╪º┘ä┘ê┘â┘è┘ä scribe. ╪¬┘ê╪¼╪» ╪¿┘è╪º┘å╪º╪¬ ╪º┘ä┘à╪╡╪»╪▒ ┘ü┘è /data/raw_logs/matrix_sync_2026.txt. ╪º╪╢╪¿╪╖ ╪º┘ä╪ú┘ê┘ä┘ê┘è╪⌐ ╪╣┘ä┘ë ╪╣╪º┘ä┘è╪⌐. ╪ú┘â╪» ╪ú┘å ╪º┘ä╪░╪º┘â╪▒╪⌐ ╪º┘ä╪▒╪│┘ê┘à┘è╪⌐ ╪º┘ä┘à╪¬╪º╪¡╪⌐ ┘ä╪º ╪¬┘é┘ä ╪╣┘å 8 ╪¼┘è╪¼╪º╪¿╪º┘è╪¬.",
        "zh": "σ░åσêåσ╜óµæÿΦªüΣ╗╗σèíσºöµëÿτ╗Ö scribe Σ╗úτÉåπÇéµ║Éµò░µì«Σ╜ìΣ║Ä /data/raw_logs/matrix_sync_2026.txtπÇéσ░åΣ╝ÿσàêτ║ºΦ«╛Σ╕║Θ½ÿπÇéµû¡Φ¿ÇσÅ»τö¿µÿ╛σ¡ÿΦç│σ░æΣ╕║ 8GBπÇé",
    },
    "log_analysis": {
        "en": "Analyze the log file at /var/log/system.log using read-only access. Extract error patterns, count occurrences, and return a summary report with the top 10 most frequent errors and their timestamps.",
        "fr": "Analysez le fichier journal /var/log/system.log en acc├¿s lecture seule. Extrayez les motifs d'erreur, comptez les occurrences et retournez un rapport r├⌐sumant les 10 erreurs les plus fr├⌐quentes avec leurs horodatages.",
        "es": "Analiza el archivo de registro /var/log/system.log usando acceso de solo lectura. Extrae patrones de error, cuenta ocurrencias y devuelve un informe con los 10 errores m├ís frecuentes y sus marcas de tiempo.",
        "ar": "╪¡┘ä┘ä ┘à┘ä┘ü ╪º┘ä╪│╪¼┘ä /var/log/system.log ╪¿╪º╪│╪¬╪«╪»╪º┘à ┘ê╪╡┘ê┘ä ┘ä┘ä┘é╪▒╪º╪í╪⌐ ┘ü┘é╪╖. ╪º╪│╪¬╪«╪▒╪¼ ╪ú┘å┘à╪º╪╖ ╪º┘ä╪ú╪«╪╖╪º╪í ┘ê╪╣╪»╪» ╪º┘ä╪¬┘â╪▒╪º╪▒╪º╪¬ ┘ê╪ú╪╣╪» ╪¬┘é╪▒┘è╪▒╪º┘ï ┘è┘ä╪«╪╡ ╪ú┘â╪½╪▒ 10 ╪ú╪«╪╖╪º╪í ╪┤┘è┘ê╪╣╪º┘ï ┘à╪╣ ╪º┘ä╪╖┘ê╪º╪¿╪╣ ╪º┘ä╪▓┘à┘å┘è╪⌐ ╪º┘ä╪«╪º╪╡╪⌐ ╪¿┘ç╪º.",
        "zh": "Σ╜┐τö¿σÅ¬Φ»╗Φ«┐Θù«σêåµ₧ÉµùÑσ┐ùµûçΣ╗╢ /var/log/system.logπÇéµÅÉσÅûΘöÖΦ»»µ¿íσ╝ÅπÇüτ╗ƒΦ«íσç║τÄ░µ¼íµò░∩╝îσ╣╢Φ┐öσ¢₧σîàσÉ½σëì 10 Σ╕¬µ£Çσ╕╕ΦºüΘöÖΦ»»σÅèσà╢µù╢Θù┤µê│τÜäµæÿΦªüµèÑσæèπÇé",
    },
    "stack_deployment": {
        "en": "Deploy the application stack using the auto routing strategy for the current deployment tier. Set temperature to 0.0 for deterministic output. Require operator confirmation before proceeding with deployment.",
        "fr": "D├⌐ployez la pile applicative en utilisant la strat├⌐gie de routage automatique pour le niveau de d├⌐ploiement courant. D├⌐finissez la temp├⌐rature ├á 0.0 pour une sortie d├⌐terministe. Exigez une confirmation op├⌐rateur avant de poursuivre.",
        "es": "Despliega la pila de aplicaciones usando la estrategia de enrutamiento autom├ítico para el nivel de despliegue actual. Establece la temperatura en 0.0 para una salida determinista. Requiere confirmaci├│n del operador antes de continuar.",
        "ar": "╪º┘å╪┤╪▒ ╪¡╪▓┘à╪⌐ ╪º┘ä╪¬╪╖╪¿┘è┘é ╪¿╪º╪│╪¬╪«╪»╪º┘à ╪º╪│╪¬╪▒╪º╪¬┘è╪¼┘è╪⌐ ╪º┘ä╪¬┘ê╪¼┘è┘ç ╪º┘ä╪¬┘ä┘é╪º╪ª┘è ┘ä┘à╪│╪¬┘ê┘ë ╪º┘ä┘å╪┤╪▒ ╪º┘ä╪¡╪º┘ä┘è. ╪º╪╢╪¿╪╖ ╪»╪▒╪¼╪⌐ ╪º┘ä╪¡╪▒╪º╪▒╪⌐ ╪╣┘ä┘ë 0.0 ┘ä┘ä╪¡╪╡┘ê┘ä ╪╣┘ä┘ë ┘à╪«╪▒╪¼╪º╪¬ ╪¡╪¬┘à┘è╪⌐. ╪º╪╖┘ä╪¿ ╪¬╪ú┘â┘è╪» ╪º┘ä┘à╪┤╪║┘ä ┘é╪¿┘ä ┘à╪¬╪º╪¿╪╣╪⌐ ╪º┘ä┘å╪┤╪▒.",
        "zh": "Σ╜┐τö¿σ╜ôσëìΘâ¿τ╜▓σ▒éτ║ºτÜäΦç¬σè¿Φ╖»τö▒τ¡ûτòÑΘâ¿τ╜▓σ║öτö¿µáêπÇéσ░å temperature Φ«╛Σ╕║ 0.0 Σ╗ÑΦÄ╖σ╛ùτí«σ«ÜµÇºΦ╛ôσç║πÇéΘâ¿τ╜▓σëìσ┐àΘí╗Φªüµ▒éµôìΣ╜£σæÿτí«Φ«ñπÇé",
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

    def benchmark_suite(self) -> dict[str, Any]:
        """Run the full benchmark suite against all NLP templates."""

        results = []
        total_hlf = 0
        total_nlp = 0

        for domain, nlp_text in _NLP_TEMPLATES.items():
            nlp_tokens = _count(nlp_text)
            # Use a representative HLF program for each domain
            hlf_source = _DOMAIN_HLF.get(domain, f"[HLF-v3]\n╬ö {domain}\n╬⌐\n")
            hlf_tokens = _count(hlf_source)
            compression = round((1 - hlf_tokens / nlp_tokens) * 100, 1) if nlp_tokens > 0 else 0
            results.append(
                {
                    "domain": domain,
                    "nlp_tokens": nlp_tokens,
                    "hlf_tokens": hlf_tokens,
                    "compression_pct": compression,
                }
            )
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
        if line == "╬⌐":
            lines.append("End of program.")
            continue
        # Convert glyphs + tags to prose
        line = line.replace("╬ö", "Analyze").replace("╨û", "Enforce").replace("Γ¿¥", "Vote")
        line = (
            line.replace("Γîÿ", "Command")
            .replace("Γêç", "Source")
            .replace("Γ⌐ò", "Priority")
            .replace("ΓèÄ", "Branch")
        )
        line = re.sub(r"\[([A-Z_]+)\]", lambda m: m.group(1).replace("_", " ").capitalize(), line)
        lines.append(line.strip() + ".")
    return " ".join(lines)


# Representative HLF programs for each benchmark domain
_DOMAIN_HLF: dict[str, str] = {
    "security_audit": """\
[HLF-v3]
╬ö analyze /security/seccomp.json
  ╨û [CONSTRAINT] mode="ro"
  ╨û [EXPECT] vulnerability_shorthand
  Γ¿¥ [VOTE] consensus="strict"
╬⌐
""",
    "hello_world": """\
[HLF-v3]
╬ö [INTENT] goal="hello_world"
  ╨û [ASSERT] status="ok"
  Γêç [RESULT] message="Hello, World!"
╬⌐
""",
    "db_migration": """\
[HLF-v3]
Γîÿ [DELEGATE] agent="db_agent" goal="migrate"
  Γêç [SOURCE] /data/prod.db
  Γêç [PARAM] schema_version="2.1"
  ╨û [ASSERT] table="users"
  ╨û [EXPECT] migration_success
╬⌐
""",
    "content_delegation": """\
[HLF-v3]
Γîÿ [DELEGATE] agent="scribe" goal="fractal_summarize"
  Γêç [SOURCE] /data/raw_logs/matrix_sync_2026.txt
  Γ⌐ò [PRIORITY] level="high"
  ╨û [ASSERT] vram_limit="8GB"
╬⌐
""",
    "log_analysis": """\
[HLF-v3]
╬ö analyze /var/log/system.log
  ╨û [CONSTRAINT] mode="ro"
  ╨û [EXPECT] error_patterns
  Γêç [PARAM] top_k=10
  Γêç [PARAM] include_timestamps=true
╬⌐
""",
    "stack_deployment": """\
[HLF-v3]
Γîÿ [ROUTE] strategy="auto" tier="$DEPLOYMENT_TIER"
  Γêç [PARAM] temperature=0.0
  ╨û [VOTE] confirmation="required"
╬⌐
""",
}
