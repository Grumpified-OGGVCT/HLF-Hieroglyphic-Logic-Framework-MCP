"""Quick test of hlf_do tool."""
from pathlib import Path
from hlf.mcp_resources import HLFResourceProvider
from hlf.mcp_tools import HLFToolProvider

rp = HLFResourceProvider(Path("."))
tp = HLFToolProvider(rp)


def t(label, intent, **kw):
    r = tp.call_tool("hlf_do", {"intent": intent, **kw})
    ok = r["success"]
    print(f"=== {label} === success={ok}")
    if ok:
        m = r.get("math", {})
        print(f"  audit: {r['audit'][:120]}")
        print(f"  conf={m.get('confidence')}  H_eng={m.get('entropy_english_bpc')}  H_hlf={m.get('entropy_hlf_bpc')}  compress={m.get('compression_ratio')}  gas={m.get('gas_estimate')}/{m.get('gas_budget')}")
        if "hlf_source" in r:
            for ln in r["hlf_source"].splitlines():
                print(f"    {ln}")
    else:
        print(f"  error: {r.get('error', r.get('validation_errors'))}")
    print()


t("T1 Audit", "audit /etc/config.json read-only and get a report", show_hlf=True)
t("T2 Write dry", "write a config file to /tmp/app.conf", dry_run=True, show_hlf=True)
t("T3 Deploy", "deploy the stack with consensus vote", show_hlf=True)
t("T4 Delegate", "delegate summarization to scribe agent high priority", show_hlf=True)
t("T5 Read top10", "read /var/log/system.log and report the top 10 errors", show_hlf=True)
t("T6 Delete", "delete /tmp/old_cache", show_hlf=True, tier="hearth")
t("T7 Empty", "")
