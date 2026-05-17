import asyncio
from hlf_mcp.hlf.hlf_llm_bridge import HLFLLMBridge
from hlf_mcp.hlf.compiler import HLFCompiler

bridge = HLFLLMBridge(model="deepseek-v4-pro:cloud")
compiler = HLFCompiler()

intents = [
    ("log_audit_simple", "Log all authentication attempts and flag suspicious activity in the audit trail"),
    ("deploy_simple", "Deploy the service to production"),
    ("content_delegation", "Generate the weekly content calendar and distribute to social channels"),
    ("incident_response_7step", "When an incident is reported: 1) Acknowledge receipt, 2) Assess severity, 3) Escalate to on-call, 4) Create tracking ticket, 5) Notify stakeholders, 6) Begin root cause analysis, 7) Update status page"),
    ("multi_service_deploy_5step", "Deploy the platform update: 1) Run database migrations, 2) Deploy API gateway, 3) Deploy worker services, 4) Run smoke tests, 5) Switch traffic"),
    ("data_pipeline_6step", "Run the daily ETL: 1) Extract from source DBs, 2) Validate schema, 3) Transform and normalize, 4) Load into warehouse, 5) Run data quality checks, 6) Generate reports"),
    ("code_review_3agent", "Review this code: Assign a security reviewer, a performance reviewer, and a style reviewer. Aggregate their findings and request changes"),
    ("audit_trail_4agent", "Run compliance audit: Deploy audit collector to all environments, aggregate logs, cross-reference with policy, flag violations"),
]

system = (
    "You are a precise HLF-v3 translator. Convert natural-language intents into valid HLF source code.\n"
    "CRITICAL GRAMMAR RULES:\n"
    "- Start with [HLF-v3] on its own line\n"
    "- End with Ω (Unicode Omega) on its own line\n"
    "- Use glyph statements: Δ (Delta=action), Ж (Zhe=assert/constrain), Σ (Sigma=result/summary), ⌘ (Command=delegate/route)\n"
    "- Each glyph has optional tag in [BRACKETS] and key=\"value\" arguments\n"
    "- Tags MUST NOT contain hyphens (-). Use underscores (_) or CamelCase instead. BAD: [AUDIT-TRAIL], GOOD: [AUDIT_TRAIL]\n"
    "- Indent continuation lines under a glyph with 2 spaces\n"
    "- DO NOT use MODULE, FUNCTION, or GOAL keywords — use glyphs instead\n"
    "- Decompose complex intents into MULTIPLE glyph statements (one per action/step)\n"
    "- Output ONLY a code block: ```hlf ... ```\n\n"
    "VALID EXAMPLE:\n"
    "```hlf\n"
    "[HLF-v3]\n"
    "Δ [INTENT] goal=\"deploy auth service to staging\"\n"
    "  Ж [CHECK] condition=\"deployment successful\"\n"
    "  Σ [RESULT] output=\"service deployed and tested\"\n"
    "Ω\n"
    "```\n\n"
    "Another valid example (multi-step):\n"
    "```hlf\n"
    "[HLF-v3]\n"
    "⌘ [GOAL] objective=\"run data pipeline\"\n"
    "Δ [EXTRACT] source=\"source DBs\"\n"
    "Δ [VALIDATE] schema=\"check schema\"\n"
    "Δ [TRANSFORM] operation=\"normalize data\"\n"
    "Δ [LOAD] target=\"warehouse\"\n"
    "Σ [REPORT] output=\"quality report generated\"\n"
    "Ω\n"
    "```"
)

async def test():
    for name, text in intents:
        prompt = f"Translate this intent into HLF-v3. Decompose into GOAL, ACTION, ASSERT, RESULT glyphs.\n\nINTENT:\n{text}"
        result = await bridge.send(prompt, role="translator", system=system)
        try:
            compiler.compile(result.hlf_output)
            print(f"  OK  {name}: extracted={result.extracted}, len={len(result.hlf_output)}")
        except Exception as e:
            print(f"  FAIL {name}: {str(e)[:120]}")

asyncio.run(test())
