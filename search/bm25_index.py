from rank_bm25 import BM25Okapi

class BM25AlarmIndex:
    """
    In-memory BM25 keyword index.
    Same mathematical algorithm as OpenSearch BM25.
    No server, no install beyond pip install rank_bm25.
    """
    def __init__(self):
        self.corpus: list = []       # tokenized text per document
        self.alarm_ids: list = []    # parallel list of alarm_id strings
        self.bm25 = None

    def build(self, alarm_records: list):
        """Build index from alarm records loaded from MongoDB."""
        self.corpus = []
        self.alarm_ids = []
        for r in alarm_records:
            # handle dict or Pydantic object
            is_dict = isinstance(r, dict)
            desc = r.get('description','') if is_dict else r.description
            cause = r.get('cause','') if is_dict else r.cause
            text = f"{desc} {cause}"
            self.corpus.append(text.lower().split())
            self.alarm_ids.append(r["alarm_id"] if is_dict else r.alarm_id)
        if self.corpus:
            self.bm25 = BM25Okapi(self.corpus)

    def search(self, query: str, top_k: int = 10) -> list:
        """Returns list of alarm_ids ranked by BM25 score."""
        if not self.bm25:
            return []
        scores = self.bm25.get_scores(query.lower().split())
        ranked = sorted(zip(self.alarm_ids, scores),
                        key=lambda x: x[1], reverse=True)
        return [aid for aid, score in ranked[:top_k] if score > 0]
