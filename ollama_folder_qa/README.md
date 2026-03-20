# Ollama Folder Q&A Tool

This tool lets you batch-query your general use folder (and all subdirectories) using an Ollama LLM (local server at 11434, Devrtal larg 2 or devstrral 2 cloud model) to extract, classify, and cross-reference all constitutive HLF surfaces, mechanisms, and patterns.

## Usage

1. **Install requirements:**
   - Python 3.10+
   - `requests` library (`pip install requests`)
   - Ollama server running at `localhost:11434` with the desired model pulled (e.g., `ollama pull devrtal-larg-2`)

2. **Run the tool:**
   ```sh
   python ollama_folder_qa.py
   ```
   - This will recursively scan the parent folder, chunk files, and run the research questions in batch mode.
   - Results are saved to `ollama_qa_results.json` in the same directory.

3. **Enhancements:**
   - See `ENHANCEMENT_PLAN.md` for planned features: interactive mode, export formats, plugin system, etc.

## Research Questions (Batch Mode)
- What is the architectural/functional role of these files in HLF?
- Are any of these surfaces constitutive to HLF’s vision, governance, or agentic operation?
- What would be lost if this cluster were omitted or replaced?
- How do these files interact with other HLF pillars?
- Are there hidden dependencies or doctrine encoded here?

## Output
- Results are in JSON format, with file/question/answer triples for easy post-processing or reporting.

---

For more detail or to add custom probes, see the plugin system plan in `ENHANCEMENT_PLAN.md`.
