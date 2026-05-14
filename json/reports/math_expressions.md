### ✅ math_expressions

**File:** `math_expressions.hlf` | **Lines:** 112 | **Nodes:** 44 | **Bytecode:** 3132B | **Time:** 12.2ms

<details open><summary><b>Surface 1: Glyph Source</b></summary>

```hlf
# HLF v3 — Governing Algorithm Fixture
# Exercises the specific formulas and algorithms that HLF uses internally:
#   Gas budget verification, salience scoring, compression ratio,
#   similarity thresholds, entropy drift policy, Merkle chain linkage.
# Each ASSIGN and IF maps to a real HLF governing computation.
[HLF-v3]

# ── Gas Budget Verification ──────────────────────────────────────────────────
# Real formula: total_gas = sum(op_gas) per statement, checked against tier max.
# Capsule tier budgets: hearth=100, forge=500, sovereign=1000.
# Host function gas: hash_sha256=2, merkle_chain=3, cosine_similarity=2,
#   formal_verify=10, memory_store=5, memory_recall=5, summarize=8, embed_text=5.
ASSIGN hash_gas = 2
ASSIGN merkle_gas = 3
ASSIGN similarity_gas = 2
ASSIGN verify_gas = 10
ASSIGN audit_pipeline_gas = hash_gas + merkle_gas + similarity_gas + verify_gas
ASSIGN hearth_max = 100
ASSIGN forge_max = 500
IF audit_pipeline_gas <= hearth_max {
  Δ [INTENT] goal="gas_budget_hearth_ok"
}
IF audit_pipeline_gas <= forge_max {
  Δ [INTENT] goal="gas_budget_forge_ok"
}

# ── Salience Scoring ─────────────────────────────────────────────────────────
# Real formula from rag/memory.py _compute_salience_score():
#   score = confidence*0.25 + groundedness*0.25 + citation_coverage*0.2
#         + freshness*0.15 + provenance*0.15 + semantic_bonus + promotion_bonus
# Archive threshold: score < 0.45 → eligible for long-term archival.
ASSIGN confidence = 8
ASSIGN groundedness = 9
ASSIGN citation_coverage = 7
ASSIGN freshness = 10
ASSIGN provenance = 10
ASSIGN weighted_score = confidence * 25 + groundedness * 25 + citation_coverage * 20 + freshness * 15 + provenance * 15
ASSIGN archive_threshold = 450
IF weighted_score >= archive_threshold {
  Δ [INTENT] goal="salience_above_archive_threshold"
}

# ── Token Compression Ratio ──────────────────────────────────────────────────
# Real formula from hlf/benchmark.py:
#   compression_pct = hlf_tokens * 100 / nlp_tokens
# HLF claims 12-30% compression over equivalent NLP (tiktoken cl100k_base).
ASSIGN hlf_tokens = 42
ASSIGN nlp_tokens = 58
ASSIGN compression_pct = hlf_tokens * 100 / nlp_tokens
ASSIGN target_ceiling = 88
IF compression_pct <= target_ceiling {
  Δ [INTENT] goal="compression_ratio_within_target"
}

# ── Similarity Gate Thresholds ───────────────────────────────────────────────
# Real thresholds:
#   Dedup gate:    cosine > 0.98 → block duplicate storage
#   Entropy anchor: cosine >= 0.95 → no drift
#   InsAIts round-trip: cosine >= 0.95 → semantic fidelity preserved
# Scaled to integer percentages for expression system.
ASSIGN similarity_score = 96
ASSIGN dedup_threshold = 98
ASSIGN drift_threshold = 95
IF similarity_score >= drift_threshold {
  Δ [INTENT] goal="entropy_anchor_no_drift"
}
IF similarity_score < dedup_threshold {
  Δ [INTENT] goal="dedup_gate_allows_storage"
}

# ── Entropy Drift Policy ─────────────────────────────────────────────────────
# Real policy from hlf/entropy_anchor.py:
#   default_threshold = 50 (0.5 scaled)
#   high_risk_threshold = 65 (0.65 scaled)
#   drift_detected = similarity < threshold → escalate
ASSIGN observed_similarity = 48
ASSIGN default_threshold = 50
ASSIGN high_risk_threshold = 65
IF observed_similarity < default_threshold {
  Δ [INTENT] goal="drift_detected_escalate"
}
IF observed_similarity < high_risk_threshold {
  Δ [INTENT] goal="drift_high_risk_halt_branch"
}

# ── Governance Retrieval Thresholds ──────────────────────────────────────────
# Real thresholds from rag/memory.py retrieval purpose policies:
#   translation_memory: min_rank_score = 12 (0.12 scaled to 100)
#   routing_evidence:   min_rank_score = 35 (0.35 scaled)
#   verifier_evidence:  min_rank_score = 30 (0.30 scaled)
ASSIGN query_rank = 28
ASSIGN translation_min = 12
ASSIGN routing_min = 35
ASSIGN verifier_min = 30
IF query_rank >= translation_min AND query_rank < routing_min {
  Δ [INTENT] goal="qualifies_translation_not_routing"
}

# ── Capsule Gas Boundary Check ───────────────────────────────────────────────
# Validates that a proposed operation chain fits within the capsule tier.
# memory_store=5, memory_recall=5, embed_text=5, cosine_similarity=2 = 17 total
ASSIGN mem_store = 5
ASSIGN mem_recall = 5
ASSIGN embed = 5
ASSIGN cosine = 2
ASSIGN rag_pipeline_gas = mem_store + mem_recall + embed + cosine
IF rag_pipeline_gas <= hearth_max {
  Δ [INTENT] goal="rag_pipeline_fits_hearth"
}

∇ [RESULT] message="governing_algorithms_validated"
Ω
```

</details>

<details><summary><b>Surface 2: Formatted Canonical</b></summary>

```hlf
[HLF-v3]
ASSIGN hash_gas = 2
ASSIGN merkle_gas = 3
ASSIGN similarity_gas = 2
ASSIGN verify_gas = 10
ASSIGN audit_pipeline_gas = hash_gas + merkle_gas + similarity_gas + verify_gas
ASSIGN hearth_max = 100
ASSIGN forge_max = 500
IF audit_pipeline_gas <= hearth_max {
Δ [INTENT] goal="gas_budget_hearth_ok"
}
IF audit_pipeline_gas <= forge_max {
Δ [INTENT] goal="gas_budget_forge_ok"
}
ASSIGN confidence = 8
ASSIGN groundedness = 9
ASSIGN citation_coverage = 7
ASSIGN freshness = 10
ASSIGN provenance = 10
ASSIGN weighted_score = confidence * 25 + groundedness * 25 + citation_coverage * 20 + freshness * 15 + provenance * 15
ASSIGN archive_threshold = 450
IF weighted_score >= archive_threshold {
Δ [INTENT] goal="salience_above_archive_threshold"
}
ASSIGN hlf_tokens = 42
ASSIGN nlp_tokens = 58
ASSIGN compression_pct = hlf_tokens * 100 / nlp_tokens
ASSIGN target_ceiling = 88
IF compression_pct <= target_ceiling {
Δ [INTENT] goal="compression_ratio_within_target"
}
ASSIGN similarity_score = 96
ASSIGN dedup_threshold = 98
ASSIGN drift_threshold = 95
IF similarity_score >= drift_threshold {
Δ [INTENT] goal="entropy_anchor_no_drift"
}
IF similarity_score < dedup_threshold {
Δ [INTENT] goal="dedup_gate_allows_storage"
}
ASSIGN observed_similarity = 48
ASSIGN default_threshold = 50
ASSIGN high_risk_threshold = 65
IF observed_similarity < default_threshold {
Δ [INTENT] goal="drift_detected_escalate"
}
IF observed_similarity < high_risk_threshold {
Δ [INTENT] goal="drift_high_risk_halt_branch"
}
ASSIGN query_rank = 28
ASSIGN translation_min = 12
ASSIGN routing_min = 35
ASSIGN verifier_min = 30
IF query_rank >= translation_min AND query_rank < routing_min {
Δ [INTENT] goal="qualifies_translation_not_routing"
}
ASSIGN mem_store = 5
ASSIGN mem_recall = 5
ASSIGN embed = 5
ASSIGN cosine = 2
ASSIGN rag_pipeline_gas = mem_store + mem_recall + embed + cosine
IF rag_pipeline_gas <= hearth_max {
Δ [INTENT] goal="rag_pipeline_fits_hearth"
}
  ∇ [RESULT] message="governing_algorithms_validated"
Ω
```

</details>

<details><summary><b>Surface 3: AST (JSON)</b></summary>

```json
{
  "kind": "program",
  "version": "3",
  "statements": [
    {
      "kind": "assign_stmt",
      "name": "hash_gas",
      "expr": {
        "kind": "value",
        "type": "int",
        "value": 2
      },
      "human_readable": "assign (mutable) hash_gas = 2"
    },
    {
      "kind": "assign_stmt",
      "name": "merkle_gas",
      "expr": {
        "kind": "value",
        "type": "int",
        "value": 3
      },
      "human_readable": "assign (mutable) merkle_gas = 3"
    },
    {
      "kind": "assign_stmt",
      "name": "similarity_gas",
      "expr": {
        "kind": "value",
        "type": "int",
        "value": 2
      },
      "human_readable": "assign (mutable) similarity_gas = 2"
    },
    {
      "kind": "assign_stmt",
      "name": "verify_gas",
      "expr": {
        "kind": "value",
        "type": "int",
        "value": 10
      },
      "human_readable": "assign (mutable) verify_gas = 10"
    },
    {
      "kind": "assign_stmt",
      "name": "audit_pipeline_gas",
      "expr": {
        "kind": "binop",
        "op": "+",
        "left": {
          "kind": "binop",
          "op": "+",
          "left": {
            "kind": "binop",
            "op": "+",
            "left": {
              "kind": "value",
              "type": "ident",
              "value": "hash_gas"
            },
            "right": {
              "kind": "value",
              "type": "ident",
              "value": "merkle_gas"
            }
          },
     
... (truncated) ...
 [
        {
          "kind": "kv_arg",
          "name": "message",
          "value": {
            "kind": "value",
            "type": "string",
            "value": "governing_algorithms_validated"
          }
        }
      ],
      "human_readable": "source [RESULT]: message=governing_algorithms_validated"
    }
  ],
  "node_count": 44,
  "human_readable": "HLF v3 program with 44 statement(s)",
  "sha256": "a02da4282df62087f505d0087e1f24d8cefd9db9d889b41a2c38fb765caa97fe",
  "env": {}
}
```

</details>

<details><summary><b>Surface 4: Bytecode (hex)</b></summary>

```
9020aa0b2c17da320c2375ac8e05bcadab8c5be4afe47bd8917bd84e922003d3484c42000400370200008da906df0000950000000102000000000000000308000000686173685f676173010300000000000000030a0000006d65726b6c655f676173010200000000000000030e00000073696d696c61726974795f676173010a00000000000000030a0000007665726966795f6761730308000000686173685f676173030a0000006d65726b6c655f676173030e00000073696d696c61726974795f676173030a0000007665726966795f676173031200000061756469745f706970656c696e655f676173016400000000000000030a0000006865617274685f6d617801f4010000000000000309000000666f7267655f6d6178031200000061756469745f706970656c696e655f676173030a0000006865617274685f6d6178030b000000ce94205b494e54454e545d03140000006761735f6275646765745f6865617274685f6f6b0304000000676f616c03140000006761735f6275646765745f6865617274685f6f6b031200000061756469745f706970656c696e655f6761730309000000666f7267655f6d6178030b000000ce94205b494e54454e545d03130000006761735f6275646765745f666f7267655f6f6b0304000000676f616c03130000006761735f6275646765745f666f7267655f6f6b010800000000000000030a000000636f6e666964656e6365010900000000000000030c00000067726f756e6465646e65737301070000000000000003110000006369746174696f6e5f636f766572616765010a00000000000000030900000066726573686e657373010a00000000000000030a00000070726f76656e616e6365030a000000636f6e666964656e6365011900000000000000030c00000067726f756e6465646e65737301190000000000000003110000006369746174696f6e5f636f766572616765011400000000000000030900000066726573686e657373010f00000000000000030a00000070726f76656e616e6365010f00000000000000030e00000077656967687465645f73636f726501c2010000000000000311000000617263686976655f7468726573686f6c64030e00000077656967687465645f73636f72650311000000617263686976655f7468726573686f6c64030b000000ce94205b494e54454e545d032000000073616c69656e63655f61626f76655f617263686976655f7468726573686f6c640304000000676f616c032000000073616c69656e63655f61626f76655f617263686976655f7468726573686f6c64012a00000000000000030a000000686c665f746f6b656e73013a00000000000000030a0000006e6c705f746f6b656e73030a000000686c665f746f6b656e73016400000000000000030a0000006e6c705f746f6b656e73030f000000636f6d7072657373696f6e5f706374015800000000000000030e0000007461726765745f6365696c696e67030f000000636f6d7072657373696f6e5f706374030e0000007461726765745f6365696c696e67030b000000ce94205b494e54454e545d031f000000636f6d7072657373696f6e5f726174696f5f77697468696e5f7461726765740304000000676f616c031f000000636f6d7072657373696f6e5f726174696f5f77697468696e5f746172676574016000000000000000031000000073696d696c61726974795f73636f7265016200000000000000030f00000064656475705f7468726573686f6c64015f00000000000000030f00000064726966745f7468726573686f6c64031000000073696d696c61726974795f73636f7265030f00000064726966745f7468726573686f6c64030b000000ce94205b494e54454e545d0317000000656e74726f70795f616e63686f725f6e6f5f64726966740304000000676f616c0317000000656e74726f70795f616e63686f725f6e6f5f6472696674031000000073696d696c61726974795f73636f7265030f00000064656475705f7468726573686f6c64030b000000ce94205b494e54454e545d031900000064656475705f676174655f616c6c6f77735f73746f726167650304000000676f616c031900000064656475705f676174655f616c6c6f77735f73746f7261676501300000000000000003130000006f627365727665645f73696d696c6172697479013200000000000000031100000064656661756c745f7468726573686f6c640141000000000000000313000000686967685f7269736b5f7468726573686f6c6403130000006f627365727665645f73696d696c6172697479031100000064656661756c745f7468726573686f6c64030b000000ce94205b494e54454e545d031700000064726966745f64657465637465645f657363616c6174650304000000676f616c031700000064726966745f64657465637465645f657363616c61746503130000006f627365727665645f73696d696c61726974790313000000686967685f7269736b5f7468726573686f6c64030b000000ce94205b494e54454e545d031b00000064726966745f686967685f7269736b5f68616c745f6272616e63680304000000676f616c031b00000064726966745f686967685f7269736b5f68616c745f6272616e6368011c00000000000000030a00000071756572795f72616e6b010c00000000000000030f0000007472616e736c6174696f6e5f6d696e012300000000000000030b000000726f7574696e675f6d696e011e00000000000000030c00000076657269666965725f6d696e030a00000071756572795f72616e6b030f0000007472616e736c6174696f6e5f6d696e030a00000071756572795f72616e6b030b000000726f7574696e675f6d696e030b000000ce94205b494e54454e545d03210000007175616c69666965735f7472616e736c6174696f6e5f6e6f745f726f7574696e670304000000676f616c03210000007175616c69666965735f7472616e736c6174696f6e5f6e6f745f726f7574696e6701050000000000000003090000006d656d5f73746f7265010500000000000000030a0000006d656d5f726563616c6c0105000000000000000305000000656d6265640102000000000000000306000000636f73696e6503090000006d656d5f73746f7265030a0000006d656d5f726563616c6c0305000000656d6265640306000000636f73696e6503100000007261675f706970656c696e655f67617303100000007261675f706970656c696e655f676173030a0000006865617274685f6d6178030b000000ce94205b494e54454e545d03180000007261675f706970656c696e655f666974735f6865617274680304000000676f616c03180000007261675f706970656c696e655f666974735f686561727468030c000000e28887205b524553554c545d031e000000676f7665726e696e675f616c676f726974686d735f76616c69646174656403070000006d657373616765031e000000676f7665726e696e675f616c676f726974686d735f76616c696461746564010000020100010200020300010400020500010600020700030800030900100000030a00100000030b00100000020c00010d00020e00010f00021000031100031200230000415400011400021500011600511304031700031800230000416c00011a00021b00011c00511904011d00021e00011f00022000012100022200012300022400012500022600032700012800120000032900012a00120000100000032b00012c00120000100000032d00012e00120000100000032f0001300012000010000002310001320002330003340003350025000041e400013700023800013900513604013a00023b00013c00023d00033e00013f00120000034000130000024100014200024300034400034500230000412001014700024800014900514604014a00024b00014c00024d00014e00024f00035000035100250000414a01015300025400015500515204035600035700220000416201015900025a00015b00515804015c00025d00015e00025f00016000026100036200036300220000418c0101650002660001670051640403680003690022000041a401016b00026c00016d00516a04016e00026f0001700002710001720002730001740002750003760003770025000003780003790022000030000041e001017b00027c00017d00517a04017e00027f00018000028100018200028300018400028500038600038700100000038800100000038900100000028a00038b00038c00230000412802018e00028f00019000518d04019200029300019400019100ff0000
```

</details>

<details><summary><b>Surface 5: Assembly</b></summary>

```asm
  0000  PUSH_CONST         #0  ; 2
  0003  STORE              #1  ; 'hash_gas'
  0006  PUSH_CONST         #2  ; 3
  0009  STORE              #3  ; 'merkle_gas'
  000C  PUSH_CONST         #4  ; 2
  000F  STORE              #5  ; 'similarity_gas'
  0012  PUSH_CONST         #6  ; 10
  0015  STORE              #7  ; 'verify_gas'
  0018  LOAD               #8  ; 'hash_gas'
  001B  LOAD               #9  ; 'merkle_gas'
  001E  ADD
  0021  LOAD               #10  ; 'similarity_gas'
  0024  ADD
  0027  LOAD               #11  ; 'verify_gas'
  002A  ADD
  002D  STORE              #12  ; 'audit_pipeline_gas'
  0030  PUSH_CONST         #13  ; 100
  0033  STORE              #14  ; 'hearth_max'
  0036  PUSH_CONST         #15  ; 500
  0039  STORE              #16  ; 'forge_max'
  003C  LOAD               #17  ; 'audit_pipeline_gas'
  003F  LOAD               #18  ; 'hearth_max'
  0042  CMP_LE
  0045  JZ                 #84  ; 'goal'
  0048  PUSH_CONST         #20  ; 'gas_budget_hearth_ok'
  004B  STORE              #21  ; 'goal'
  004E  PUSH_CONST         #22  ; 'gas_budget_hearth_ok'
  0051  CALL_HOST          #19 (args=1)  ; 'Δ [INTENT]'
  0054  LOAD               #23  ; 'audit_pipeline_gas'
  0057  LOAD               #24  ; 'forge_max'
  005A  CMP_LE
  005D  JZ                 #108  ; 'goal'
  0060  PUSH_CONST         #26  ; 'gas_budget_forge_ok'
  0063  STORE              #27  ; 'goal'
  0066  PUSH_CONST         #28  ; 'gas_budget_forge_ok'
  0069  CALL_HOST          #25 (args=1)  ; 'Δ [INTENT]'
  006C  PUSH_CONST         #29  ; 8
  006F  STORE              #30  ; 'confidence'
  0072  PUSH_CONST         #31  ; 9
  0075  STORE              #32  ; 'groundedness'
  0078  PUSH_CONST         #33  ; 7
  007B  STORE              #34  ; 'citation_coverage'
  007E  PUSH_CONST         #35  ; 10
  0081  STORE              #36  ; 'freshness'
  0084  PUSH_CONST         #37  ; 10
  0087  STORE              #38  ; 'provenance'
  008A  LOAD               #39  ; 'confidence'
  008D  PUSH_CONST         #40  ; 25
  0090  MUL
  0093  LOAD               #41  ; 'groundedness'
  0096  PUSH_CONST         #42  ; 25
  0099  MUL
  009C  ADD
  009F  LOAD               #43  ; 'citation_coverage'
  00A2  PUSH_CONST         #44  ; 20
  00A5  MUL
  00A8  ADD
  00AB  LOAD               #45  ; 'freshness'
  00AE  PUSH_CONST         #46  ; 15
  00B1  MUL
  00B4  ADD
  00B7  LOAD               #47  ; 'provenance'
  00BA  PUSH_CONST         #48  ; 15
  00BD  MUL
  00C0  ADD
  00C3  STORE              #49  ; 'weighted_score'
  00C6  PUSH_CONST         #50  ; 450
  00C9  STORE              #51  ; 'archive_threshold'
  00CC  LOAD               #52  ; 'weighted_score'
  00CF  LOAD               #53  ; 'archive_threshold'
  00D2  CMP_GE
  00D5  JZ                 #228  ; None
  00D8  PUSH_CONST         #55  ; 'salience_above_archive_threshold'
  00DB  STORE              #56  ; 'goal'
  00DE  PUSH_CONST         #57  ; 'salience_above_archive_threshold'
  00E1  CALL_HOST          #54 (args=1)  ; 'Δ [INTENT]'
  00E4  PUSH_CONST         #58  ; 42
  00E7  STORE              #59  ; 'hlf_tokens'
  00EA  PUSH_CONST         #60  ; 58
  00ED  STORE              #61  ; 'nlp_tokens'
  00F0  LOAD               #62  ; 'hlf_tokens'
  00F3  PUSH_CONST         #63  ; 100
  00F6  MUL
  00F9  LOAD               #64  ; 'nlp_tokens'
  00FC  DIV
  00FF  STORE              #65  ; 'compression_pct'
  0102  PUSH_CONST         #66  ; 88
  0105  STORE              #67  ; 'target_ceiling'
  0108  LOAD               #68  ; 'compression_pct'
  010B  LOAD               #69  ; 'target_ceiling'
  010E  CMP_LE
  0111  JZ                 #288  ; None
  0114  PUSH_CONST         #71  ; 'compression_ratio_within_target'
  0117  STORE              #72  ; 'goal'
  011A  PUSH_CONST         #73  ; 'compression_ratio_within_target'
  011D  CALL_HOST          #70 (args=1)  ; 'Δ [INTENT]'
  0120  PUSH_CONST         #74  ; 96
  0123  STORE              #75  ; 'similarity_score'
  0126  PUSH_CONST         #76  ; 98
  0129  STORE              #77  ; 'dedup_threshold'
  012C  PUSH_CONST         #78  ; 95
  012F  STORE              #79  ; 'drift_threshold'
  0132  LOAD               #80  ; 'similarity_score'
  0135  LOAD               #81  ; 'drift_threshold'
  0138  CMP_GE
  013B  JZ                 #330  ; None
  013E  PUSH_CONST         #83  ; 'entropy_anchor_no_drift'
  0141  STORE              #84  ; 'goal'
  0144  PUSH_CONST         #85  ; 'entropy_anchor_no_drift'
  0147  CALL_HOST          #82 (args=1)  ; 'Δ [INTENT]'
  014A  LOAD               #86  ; 'similarity_score'
  014D  LOAD               #87  ; 'dedup_threshold'
  0150  CMP_LT
  0153  JZ                 #354  ; None
  0156  PUSH_CONST         #89  ; 'dedup_gate_allows_storage'
  0159  STORE              #90  ; 'goal'
  015C  PUSH_CONST         #91  ; 'dedup_gate_allows_storage'
  015F  CALL_HOST          #88 (args=1)  ; 'Δ [INTENT]'
  0162  PUSH_CONST         #92  ; 48
  0165  STORE              #93  ; 'observed_similarity'
  0168  PUSH_CONST         #94  ; 50
  016B  STORE              #95  ; 'default_threshold'
  016E  PUSH_CONST         #96  ; 65
  0171  STORE              #97  ; 'high_risk_threshold'
  0174  LOAD               #98  ; 'observed_similarity'
  0177  LOAD               #99  ; 'default_threshold'
  017A  CMP_LT
  017D  JZ                 #396  ; None
  0180  PUSH_CONST         #101  ; 'drift_detected_escalate'
  0183  STORE              #102  ; 'goal'
  0186  PUSH_CONST         #103  ; 'drift_detected_escalate'
  0189  CALL_HOST          #100 (args=1)  ; 'Δ [INTENT]'
  018C  LOAD               #104  ; 'observed_similarity'
  018F  LOAD               #105  ; 'high_risk_threshold'
  0192  CMP_LT
  0195  JZ                 #420  ; None
  0198  PUSH_CONST         #107  ; 'drift_high_risk_halt_branch'
  019B  STORE              #108  ; 'goal'
  019E  PUSH_CONST         #109  ; 'drift_high_risk_halt_branch'
  01A1  CALL_HOST          #106 (args=1)  ; 'Δ [INTENT]'
  01A4  PUSH_CONST         #110  ; 28
  01A7  STORE              #111  ; 'query_rank'
  01AA  PUSH_CONST         #112  ; 12
  01AD  STORE              #113  ; 'translation_min'
  01B0  PUSH_CONST         #114  ; 35
  01B3  STORE              #115  ; 'routing_min'
  01B6  PUSH_CONST         #116  ; 30
  01B9  STORE              #117  ; 'verifier_min'
  01BC  LOAD               #118  ; 'query_rank'
  01BF  LOAD               #119  ; 'translation_min'
  01C2  CMP_GE
  01C5  LOAD               #120  ; 'query_rank'
  01C8  LOAD               #121  ; 'routing_min'
  01CB  CMP_LT
  01CE  AND
  01D1  JZ                 #480  ; None
  01D4  PUSH_CONST         #123  ; 'qualifies_translation_not_routing'
  01D7  STORE              #124  ; 'goal'
  01DA  PUSH_CONST         #125  ; 'qualifies_translation_not_routing'
  01DD  CALL_HOST          #122 (args=1)  ; 'Δ [INTENT]'
  01E0  PUSH_CONST         #126  ; 5
  01E3  STORE              #127  ; 'mem_store'
  01E6  PUSH_CONST         #128  ; 5
  01E9  STORE              #129  ; 'mem_recall'
  01EC  PUSH_CONST         #130  ; 5
  01EF  STORE              #131  ; 'embed'
  01F2  PUSH_CONST         #132  ; 2
  01F5  STORE              #133  ; 'cosine'
  01F8  LOAD               #134  ; 'mem_store'
  01FB  LOAD               #135  ; 'mem_recall'
  01FE  ADD
  0201  LOAD               #136  ; 'embed'
  0204  ADD
  0207  LOAD               #137  ; 'cosine'
  020A  ADD
  020D  STORE              #138  ; 'rag_pipeline_gas'
  0210  LOAD               #139  ; 'rag_pipeline_gas'
  0213  LOAD               #140  ; 'hearth_max'
  0216  CMP_LE
  0219  JZ                 #552  ; None
  021C  PUSH_CONST         #142  ; 'rag_pipeline_fits_hearth'
  021F  STORE              #143  ; 'goal'
  0222  PUSH_CONST         #144  ; 'rag_pipeline_fits_hearth'
  0225  CALL_HOST          #141 (args=1)  ; 'Δ [INTENT]'
  0228  PUSH_CONST         #146  ; 'governing_algorithms_validated'
  022B  STORE              #147  ; 'message'
  022E  PUSH_CONST         #148  ; 'governing_algorithms_validated'
  0231  PUSH_CONST         #145  ; '∇ [RESULT]'
  0234  HALT
```

</details>

<details><summary><b>Surface 6: English Translation</b></summary>

> HLF v3 program with 44 statement(s): assign (mutable) hash_gas = 2; assign (mutable) merkle_gas = 3; assign (mutable) similarity_gas = 2; assign (mutable) verify_gas = 10; assign (mutable) audit_pipeline_gas = hash_gas + merkle_gas + similarity_gas + verify_gas; assign (mutable) hearth_max = 100; assign (mutable) forge_max = 500; if audit_pipeline_gas <= hearth_max then block; if audit_pipeline_gas <= forge_max then block; assign (mutable) confidence = 8; assign (mutable) groundedness = 9; assign (mutable) citation_coverage = 7; assign (mutable) freshness = 10; assign (mutable) provenance = 10; assign (mutable) weighted_score = confidence * 25 + groundedness * 25 + citation_coverage * 20 + freshness * 15 + provenance * 15; assign (mutable) archive_threshold = 450; if weighted_score >= archive_threshold then block; assign (mutable) hlf_tokens = 42; assign (mutable) nlp_tokens = 58; assign (mutable) compression_pct = hlf_tokens * 100 / nlp_tokens; assign (mutable) target_ceiling = 88; if compression_pct <= target_ceiling then block; assign (mutable) similarity_score = 96; assign (mutable) dedup_threshold = 98; assign (mutable) drift_threshold = 95; if similarity_score >= drift_threshold then block; if similarity_score < dedup_threshold then block; assign (mutable) observed_similarity = 48; assign (mutable) default_threshold = 50; assign (mutable) high_risk_threshold = 65; if observed_similarity < default_threshold then block; if observed_similarity < high_risk_threshold then block; assign (mutable) query_rank = 28; assign (mutable) translation_min = 12; assign (mutable) routing_min = 35; assign (mutable) verifier_min = 30; if query_rank >= translation_min AND query_rank < routing_min then block; assign (mutable) mem_store = 5; assign (mutable) mem_recall = 5; assign (mutable) embed = 5; assign (mutable) cosine = 2; assign (mutable) rag_pipeline_gas = mem_store + mem_recall + embed + cosine; if rag_pipeline_gas <= hearth_max then block; source [RESULT]: message=governing_algorithms_validated.

</details>

---
