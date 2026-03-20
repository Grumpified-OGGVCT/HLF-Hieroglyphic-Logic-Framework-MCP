import os
import requests
import json
from typing import List, Dict, Any

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "devrtal-larg-2"  # or "devstrral-2-cloud" for cloud

RESEARCH_QUESTIONS = [
    "What is the architectural/functional role of these files in HLF?",
    "Are any of these surfaces constitutive to HLF’s vision, governance, or agentic operation?",
    "What would be lost if this cluster were omitted or replaced?",
    "How do these files interact with other HLF pillars?",
    "Are there hidden dependencies or doctrine encoded here?"
]


def scan_directory(root: str) -> List[str]:
    """Recursively collect all file paths under root."""
    file_paths = []
    for dirpath, _, filenames in os.walk(root):
        for f in filenames:
            file_paths.append(os.path.join(dirpath, f))
    return file_paths


def chunk_file(file_path: str, max_bytes: int = 4000) -> List[str]:
    """Chunk large files for context-limited LLM input."""
    chunks = []
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        while True:
            chunk = f.read(max_bytes)
            if not chunk:
                break
            chunks.append(chunk)
    return chunks


def ask_ollama(question: str, context: str) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": f"Context:\n{context}\n\nQuestion: {question}\nAnswer:",
        "stream": False
    }
    response = requests.post(OLLAMA_URL, json=payload)
    response.raise_for_status()
    return response.json().get("response", "")


def batch_qa_run(root: str, questions: List[str]) -> List[Dict[str, Any]]:
    results = []
    file_paths = scan_directory(root)
    for file_path in file_paths:
        # Only process text-like files for demo (skip binaries)
        try:
            chunks = chunk_file(file_path)
        except Exception:
            continue
        for chunk in chunks:
            for question in questions:
                answer = ask_ollama(question, chunk)
                results.append({
                    "file": file_path,
                    "question": question,
                    "answer": answer
                })
    return results


def export_results(results: List[Dict[str, Any]], out_path: str):
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)


def main():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    results = batch_qa_run(root, RESEARCH_QUESTIONS)
    export_results(results, os.path.join(os.path.dirname(__file__), 'ollama_qa_results.json'))
    print("Batch Q&A complete. Results saved to ollama_qa_results.json.")

if __name__ == "__main__":
    main()
