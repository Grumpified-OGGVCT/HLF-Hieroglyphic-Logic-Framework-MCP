# Ollama Folder Q&A Tool

This tool batch-queries a folder tree with an Ollama-served model to extract, classify, and cross-reference constitutive HLF surfaces, mechanisms, and patterns.

## Usage

1. **Install requirements:**
   - Python 3.12+
   - `requests` library (`pip install requests`)
   - Ollama server running at `localhost:11434` with the desired model pulled
   - Default local model: `devstral:24b` (`ollama pull devstral:24b`)

2. **Optional environment overrides:**
   - `OLLAMA_URL` to point at a different Ollama endpoint
   - `OLLAMA_MODEL` to select a different installed model

3. **Run the tool:**
   ```sh
   python ollama_folder_qa.py
   ```
   - This will recursively scan the parent folder, chunk files, and run the research questions in batch mode.
   - Results are saved to `ollama_qa_results.json` in the same directory.

4. **Enhancements:**
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
