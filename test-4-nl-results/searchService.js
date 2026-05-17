class SearchService {
  constructor() {
    this.documents = new Map(); // id -> text content
    this.index = new Map(); // token (lowercase) -> Set of document ids
  }

  /**
   * Index a document
   * @param {string} id - unique document identifier
   * @param {string} content - text content
   */
  indexDocument(id, content) {
    // Remove old document if exists
    if (this.documents.has(id)) {
      this._removeFromIndex(id);
    }

    this.documents.set(id, content);

    // Tokenize: simple split on non-alphanumeric, lowercase
    const tokens = content.toLowerCase().split(/[^a-z0-9]+/).filter(Boolean);
    for (const token of tokens) {
      if (!this.index.has(token)) {
        this.index.set(token, new Set());
      }
      this.index.get(token).add(id);
    }
  }

  /**
   * Search documents
   * @param {string} query - search query
   * @returns {Array<{id: string, content: string, score: number}>} sorted by relevance
   */
  search(query) {
    const queryTokens = query.toLowerCase().split(/[^a-z0-9]+/).filter(Boolean);
    if (queryTokens.length === 0) return [];

    const matchedIds = new Set();
    const idScores = new Map();

    for (const token of queryTokens) {
      const docIds = this.index.get(token);
      if (!docIds) continue;
      for (const id of docIds) {
        matchedIds.add(id);
        idScores.set(id, (idScores.get(id) || 0) + 1);
      }
    }

    // Build results sorted by score descending
    const results = [];
    for (const id of matchedIds) {
      results.push({
        id,
        content: this.documents.get(id),
        score: idScores.get(id)
      });
    }
    results.sort((a, b) => b.score - a.score);
    return results;
  }

  /**
   * Delete a document from the index
   * @param {string} id
   * @returns {boolean} true if found and deleted
   */
  deleteDocument(id) {
    if (!this.documents.has(id)) return false;
    this._removeFromIndex(id);
    this.documents.delete(id);
    return true;
  }

  /**
   * Internal helper: remove all tokens of a document from the index
   * @param {string} id
   */
  _removeFromIndex(id) {
    const content = this.documents.get(id);
    if (!content) return;
    const tokens = content.toLowerCase().split(/[^a-z0-9]+/).filter(Boolean);
    for (const token of tokens) {
      const set = this.index.get(token);
      if (set) {
        set.delete(id);
        if (set.size === 0) this.index.delete(token);
      }
    }
  }

  /**
   * Get count of indexed documents
   */
  get documentCount() {
    return this.documents.size;
  }
}

module.exports = SearchService;