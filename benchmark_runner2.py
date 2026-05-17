from hlf_mcp.hlf.benchmark import HLFBenchmark, _count

b = HLFBenchmark()

print('=== BENCHMARK: Real HLF vs NLP Templates ===')
print()
suite = b.benchmark_suite()
for r in suite['results']:
    d = r['domain']
    n = r['nlp_tokens']
    h = r['hlf_tokens']
    c = r['compression_pct']
    print(f'  {d:25s} NLP={n:4d}  HLF={h:4d}  compression={c:+5.1f}%')
tot = suite['totals']
print(f'  {"TOTAL":25s} NLP={tot["nlp"]:4d}  HLF={tot["hlf"]:4d}  compression={tot["compression_pct"]:+5.1f}%')
print()

# Also measure using real fixture files
from pathlib import Path
fixture_dir = Path('fixtures')
fixture_map = {
    'security_audit': 'security_audit.hlf',
    'hello_world': 'hello_world.hlf',
    'db_migration': 'db_migration.hlf',
    'content_delegation': 'delegation.hlf',
    'log_analysis': 'log_analysis.hlf',
    'stack_deployment': 'stack_deployment.hlf',
}
print('=== BENCHMARK: Real fixture files vs NLP Templates ===')
total_nlp = 0
total_hlf_fixture = 0
for domain, filename in fixture_map.items():
    fixture_path = fixture_dir / filename
    if fixture_path.exists():
        hlf_src = fixture_path.read_text(encoding='utf-8')
        hlf_toks = _count(hlf_src)
        nlp_text = suite['results'][0]  # placeholder, get nlp from suite
        nlp_toks = _count(_NLP_TEXT[domain]) if domain in _NLP_TEXT else 0
        total_hlf_fixture += hlf_toks
        total_nlp += nlp_toks
        comp = round((1 - hlf_toks/nlp_toks)*100, 1) if nlp_toks > 0 else 0
        print(f'  {domain:25s} NLP={nlp_toks:4d}  HLF_fixture={hlf_toks:4d}  compression={comp:+5.1f}%')

from hlf_mcp.hlf.benchmark import _NLP_TEMPLATES as _NLP_TEXT
total_nlp = 0
total_hlf_fixture = 0
for domain, filename in fixture_map.items():
    fixture_path = fixture_dir / filename
    if fixture_path.exists():
        hlf_src = fixture_path.read_text(encoding='utf-8')
        hlf_toks = _count(hlf_src)
        nlp_toks = _count(_NLP_TEXT[domain])
        total_hlf_fixture += hlf_toks
        total_nlp += nlp_toks
        comp = round((1 - hlf_toks/nlp_toks)*100, 1)
        print(f'  {domain:25s} NLP={nlp_toks:4d}  HLF_fixture={hlf_toks:4d}  compression={comp:+5.1f}%')
comp_total = round((1 - total_hlf_fixture/total_nlp)*100, 1)
print(f'  {"TOTAL":25s} NLP={total_nlp:4d}  HLF_fixture={total_hlf_fixture:4d}  compression={comp_total:+5.1f}%')
