# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  HLF — Weekly Agentic Triage Intent File                                    ║
# ║                                                                              ║
# ║  This file defines intent-driven agentic automation for HLF's GitHub repo.  ║
# ║  It is consumed by GitHub's Agentic Workflows (preview feature) and         ║
# ║  by the weekly-triage.yml workflow which interprets these intents.           ║
# ║                                                                              ║
# ║  Philosophy: AI is the tool, people are the priority. This automation       ║
# ║  serves human contributors — it never silences, closes, or hides issues     ║
# ║  without a clear, documented rationale and a human-readable explanation.    ║
# ║                                                                              ║
# ║  Reference: https://github.blog/ai-and-ml/automate-repository-tasks-with-  ║
# ║             github-agentic-workflows                                         ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

name: "Weekly Agentic Triage — HLF Repository"

description: |
  AI-assisted weekly triage for the HLF MCP server repository.
  Runs every Monday at 10:00 UTC.
  Uses Ollama Cloud (nemotron-3-super primary, qwen3.5:cloud fallback) to
  analyse issue/PR content and propose labels, consolidations, and doc updates.

  ALL AI decisions are proposals only — humans approve or reject every change.
  No issue is closed automatically. The bot comments explaining its reasoning.

schedule:
  - cron: "0 10 * * 1"   # Every Monday 10:00 AM UTC

permissions:
  issues: write
  pull_requests: write
  contents: read

# ── Intents ─────────────────────────────────────────────────────────────────

intents:

  # Intent 1: Label open issues
  # Reads all open issues, classifies them, and applies labels.
  # Labels it knows: bug, enhancement, question, stale, security, ethos,
  # grammar, bytecode, vm, rag, instinct, server, docker, docs, model-drift
  - name: "Label Open Issues"
    description: |
      Review all open issues. For each:
        1. Read the title and body (first 500 chars).
        2. Classify using the HLF label taxonomy below.
        3. Apply up to 3 labels. Explain reasoning in a comment.
        4. If the issue is more than 90 days old with no activity, add 'stale'
           and leave a comment saying: "This issue has been open for 90+ days
           without activity. Labelled stale — a human maintainer will decide
           whether to close or continue."
        5. NEVER close issues automatically.

      HLF label taxonomy:
        bug           — something is broken
        enhancement   — new feature or improvement request
        question      — asking how something works
        stale         — no activity in 90+ days
        security      — relates to ALIGN rules, crypto, zero-trust, gas metering
        ethos         — relates to people-first ethos or Ethical Governor
        grammar       — HLF language grammar or compiler issues
        bytecode      — opcode spec, VM, gas table issues
        vm            — runtime execution, builtins, host dispatch
        rag           — memory store, RAG, Merkle chain, cosine dedup
        instinct      — SDD lifecycle, CoVE gate, phase transitions
        server        — FastMCP server, transports, tools/resources
        docker        — Dockerfile, compose, health check
        docs          — README, QA findings, handoff docs, roadmap
        model-drift   — semantic drift in AI model understanding of HLF spec

    ai_model:
      primary: "nemotron-3-super"
      fallback: "qwen3.5:cloud"
      capabilities:
        - structured_outputs   # JSON schema for label classification
        - thinking             # Use reasoning traces for confidence

    actions:
      - type: list_issues
        filters:
          state: open
          per_page: 50
      - type: analyze_issue_content
        max_chars_per_issue: 500
        use_structured_output: true
        output_schema:
          type: object
          properties:
            labels:
              type: array
              items: {type: string}
              description: "Up to 3 labels from the HLF taxonomy"
            is_stale:
              type: boolean
              description: "True if 90+ days old with no activity"
            reasoning:
              type: string
              description: "1-2 sentence justification for the labels"
          required: [labels, is_stale, reasoning]
      - type: apply_labels
        source: ai_analysis.labels
        comment_template: |
          🤖 **Agentic Triage (Monday auto-label)**
          Applied labels: {labels}
          **Reasoning:** {reasoning}
          *This is an AI suggestion. A human maintainer reviews all labels.*
      - type: add_stale_comment
        condition: ai_analysis.is_stale == true
        message: |
          This issue has been open for 90+ days without recent activity.
          Added the `stale` label — a human maintainer will decide whether
          to close, continue, or escalate this issue.

  # Intent 2: Identify duplicate/related issues and propose consolidation
  - name: "Propose Issue Consolidation"
    description: |
      Look for pairs of open issues that are semantically similar (same root
      cause or same feature area). For each identified pair:
        1. Comment on BOTH issues pointing to each other.
        2. Propose (but don't execute) that a maintainer consolidate them.
        3. Use web search to verify if there's an existing upstream reference
           for the bug/feature in question.

    ai_model:
      primary: "nemotron-3-super"
      fallback: "qwen3.5:cloud"
      capabilities:
        - web_search       # check for upstream references
        - thinking         # reason about issue similarity

    actions:
      - type: list_issues
        filters:
          state: open
      - type: compute_similarity_pairs
        threshold: 0.85   # cosine similarity threshold
        max_pairs: 5
      - type: comment_pair
        template: |
          🔗 **Possible Duplicate Detected (Agentic Triage)**
          This issue may be related to #{other_issue_number}: *{other_issue_title}*

          **Similarity score:** {score:.0%}
          **Suggested action:** A maintainer may want to consolidate these two issues.

          *This suggestion was made by automated triage. No action is taken automatically.*

  # Intent 3: Propose PRs to update stale documentation
  - name: "Propose Stale Documentation Updates"
    description: |
      Identify documentation files under docs/ and README.md that:
        a) Have not been modified in 180+ days, OR
        b) Contain TODO markers that have not been addressed.
      For each such file:
        1. Open a DRAFT pull request titled "docs: update {filename} (stale)"
           with a placeholder body listing the specific sections that need review.
        2. Assign the 'docs' label.
        3. Do NOT make the PR ready for review — keep it DRAFT so humans decide.

    ai_model:
      primary: "qwen3.5:cloud"    # multimodal + structured output = ideal for docs
      fallback: "nemotron-3-super"
      capabilities:
        - structured_outputs

    actions:
      - type: scan_repository
        filters:
          paths: ["docs/", "README.md"]
          file_types: [".md", ".rst", ".txt"]
      - type: check_file_staleness
        threshold_days: 180
      - type: scan_for_todo_markers
        patterns: ["TODO", "FIXME", "TBD", "PLACEHOLDER", "NOT IMPLEMENTED"]
      - type: create_draft_pull_request
        condition: stale OR has_todo_markers
        title_template: "docs: update {filename} (stale/todo)"
        body_template: |
          ## Documentation Update Needed

          **File:** `{filepath}`
          **Last modified:** {last_modified}
          **Days since update:** {days_stale}

          ### Reasons flagged:
          {reasons_list}

          ### TODO markers found:
          {todo_list}

          ---
          *This is an automatically generated DRAFT PR. A human maintainer must*
          *review, update the content, and mark it ready for review before merge.*
        labels: ["docs"]
        draft: true

  # Intent 4: Weekly phase roadmap check
  - name: "Weekly Phase Roadmap Progress Check"
    description: |
      Read README.md to extract the current roadmap phase status.
      Check if any Phase 2 items (sqlite-vec, fractal summarisation, hot/warm/cold
      tiering, LSP, REPL) have associated open PRs or issues.
      Post a weekly summary comment on the most-recent open 'enhancement' issue,
      or create a new 'HLF Weekly Roadmap Update' issue if none exists.
      Use web search to check if any relevant upstream libraries (sqlite-vec, etc.)
      have released new versions that enable Phase 2 work.

    ai_model:
      primary: "nemotron-3-super"
      fallback: "qwen3.5:cloud"
      capabilities:
        - web_search          # check for upstream library releases
        - thinking            # reason about phase readiness
        - structured_outputs  # produce parseable status table

    actions:
      - type: read_file
        path: README.md
        section_pattern: "Phase [0-9]"
      - type: list_issues
        filters:
          state: open
          labels: ["enhancement"]
      - type: web_search
        queries:
          - "sqlite-vec latest release"
          - "WASM MCP server 2025"
        max_results: 3
      - type: create_or_update_issue
        title: "📊 HLF Weekly Roadmap Update — {week}"
        labels: ["docs", "enhancement"]
        body_template: |
          ## HLF Roadmap Status — {week}

          ### Phase 1 ✅ Complete (this PR)
          ### Phase 2 🔨 In Progress

          {phase2_status_table}

          ### Upstream Dependencies (auto-checked)
          {upstream_library_updates}

          ---
          *Generated by weekly agentic triage. Update manually as work progresses.*

# ── Logging and notifications ────────────────────────────────────────────────
logging:
  level: info
  include_reasoning_traces: true   # Log AI thinking traces for audit

notifications:
  on_failure:
    create_issue: true
    label: "agentic-triage-failure"
  on_success:
    post_summary_to_discussion: false  # Set true once Discussions is enabled

# ── Safety constraints (ethos compliance) ───────────────────────────────────
safety:
  # Hard rules — the agent must NEVER violate these
  never_close_issues_automatically: true
  never_merge_pull_requests_automatically: true
  never_delete_files: true
  never_modify_governance_files: true   # governance/ is read-only for the agent
  never_modify_ethics_files: true       # hlf_mcp/hlf/ethics/ is read-only

  # All AI-generated comments must be clearly labelled as such
  require_ai_attribution_in_comments: true
  ai_attribution_prefix: "🤖 **Agentic Triage**"

  # Rate limits to prevent runaway automation
  max_issues_labelled_per_run: 20
  max_prs_created_per_run: 3
  max_comments_posted_per_run: 10
