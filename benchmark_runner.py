from hlf_mcp.hlf.benchmark import HLFBenchmark
import json

b = HLFBenchmark()

print('=== BENCHMARK SUITE (6 domains) ===')
suite = b.benchmark_suite()
for r in suite['results']:
    d = r['domain']
    n = r['nlp_tokens']
    h = r['hlf_tokens']
    c = r['compression_pct']
    print(f'  {d:25s} NLP={n:4d}  HLF={h:4d}  comp={c:5.1f}%')
tot = suite['totals']
print(f'  {"TOTAL":25s} NLP={tot["nlp"]:4d}  HLF={tot["hlf"]:4d}  comp={tot["compression_pct"]:5.1f}%')
print()

print('=== MULTILINGUAL MATRIX ===')
mm = b.multilingual_matrix()
for r in mm['rows']:
    d = r['domain']
    l = r['language']
    i = r['input_tokens']
    h = r['hlf_tokens']
    c = r['compression_pct']
    f = r['fidelity']
    print(f'  {d:25s} {l:4s}  in={i:4d}  hlf={h:4d}  comp={c:.1f}%  fid={f}')
print()
for lang, stats in mm['per_language'].items():
    print(f'  {lang}: {stats["samples"]} samples, avg comp={stats["compression_pct"]:.1f}%')
