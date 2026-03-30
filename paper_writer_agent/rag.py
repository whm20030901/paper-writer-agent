from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass


TOKEN_RE = re.compile(r"[A-Za-z\u4e00-\u9fff0-9_]+")


@dataclass
class Chunk:
    doc_id: str
    chunk_id: int
    text: str


@dataclass
class RetrievalResult:
    chunk: Chunk
    score: float


class RAGEngine:
    """A tiny TF-IDF-like retrieval engine for demo purposes."""

    def __init__(self, chunk_size: int = 220):
        self.chunk_size = chunk_size
        self.chunks: list[Chunk] = []
        self.doc_freq: dict[str, int] = defaultdict(int)
        self.term_freq: list[Counter[str]] = []

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return [t.lower() for t in TOKEN_RE.findall(text)]

    def add_document(self, doc_id: str, content: str) -> None:
        words = content.split()
        for idx in range(0, len(words), self.chunk_size):
            chunk_words = words[idx : idx + self.chunk_size]
            chunk_text = " ".join(chunk_words)
            chunk = Chunk(doc_id=doc_id, chunk_id=len(self.chunks), text=chunk_text)
            self.chunks.append(chunk)

            tf = Counter(self._tokenize(chunk_text))
            self.term_freq.append(tf)
            for term in tf:
                self.doc_freq[term] += 1

    def retrieve(self, query: str, top_k: int = 3) -> list[RetrievalResult]:
        if not self.chunks:
            return []

        query_terms = self._tokenize(query)
        n_docs = len(self.chunks)
        scores: list[tuple[float, int]] = []

        for idx, tf in enumerate(self.term_freq):
            score = 0.0
            for term in query_terms:
                if term not in tf:
                    continue
                idf = math.log((n_docs + 1) / (self.doc_freq.get(term, 0) + 1)) + 1.0
                score += tf[term] * idf
            if score > 0:
                scores.append((score, idx))

        scores.sort(reverse=True, key=lambda x: x[0])
        return [RetrievalResult(chunk=self.chunks[i], score=s) for s, i in scores[:top_k]]
