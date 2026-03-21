# Ollama Folder Q&A Tool: Design and Enhancement Plan

## Core Features
- **Recursive Directory Scan**: Traverse all subdirectories, build a manifest of files for context selection.
- **Ollama Q&A Integration**: Connect to Ollama server (default `localhost:11434`) and use an environment-selected model, defaulting to `devstral:24b`, for context-rich Q&A.
- **Context Selection**: Intelligently select relevant files/chunks for each question.
- **Answer Synthesis**: Aggregate, deduplicate, and reference file paths in answers.

## Enhancement Suggestions

### 1. Batch Mode
- Scripted Q&A runs for all research questions.
- Output: Full HLF surface map (Markdown, CSV, or JSON).
- Use: One-command audit of all constitutive surfaces.

### 2. Interactive Mode
- CLI or Web UI for user-driven Q&A.
- "Drill down" on any answer for more detail or clarification.
- Contextual follow-up: User can select a file/cluster to ask deeper questions.

### 3. Export/Report
- Export results in Markdown, CSV, or JSON.
- Easy integration into planning docs, audits, or recovery ledgers.
- Option to include rationale, dependencies, and recovery priority in output.

### 4. Plugin System
- Allow custom question templates (YAML/JSON or Python plugin).
- Support domain-specific probes (e.g., governance, verification, orchestration).
- Enable future extension for new research domains or audit types.

---

## Next Steps
- Scaffold the tool in `ollama_folder_qa/` with modular design for enhancements.
- Implement batch mode and export first for immediate research value.
- Add interactive and plugin systems iteratively.
