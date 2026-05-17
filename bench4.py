from hlf_mcp.hlf.benchmark import HLFBenchmark
import json

b = HLFBenchmark()
mm = b.multilingual_matrix()

print('=== MULTILINGUAL MATRIX (5 languages x 5 domains) ===')
print()

# Show available keys in first row
first = mm['rows'][0]
print('Row keys:', list(first.keys()))
print()

for r in mm['rows']:
    d = r['domain']
    l = r['language']
    i = r['input_tokens']
    h = r['hlf_tokens']
    c = r['compression_pct']
    fs = r.get('fidelity_score', r.get('fidelity', 'N/A'))
    fu = r.get('fallback_used', 'N/A')
    print(f'{d:25s} {l:4s}  in={i:4d}  hlf={h:4d}  comp={c:+6.1f}%  fidelity={fs}  fallback={fu}')

print()
print('=== PER-LANGUAGE SUMMARY ===')
for lang, stats in mm['per_language'].items():
    s = stats['samples']
    c = stats['compression_pct']
    print(f'  {lang}: {s} samples, avg compression={c:+6.1f}%')
print()
print('=== PER-DOMAIN SUMMARY ===')
for domain, stats in mm['per_domain'].items():
    s = stats['samples']
    c = stats['compression_pct']
    print(f'  {domain:25s}: {s} samples, avg compression={c:+6.1f}%')
