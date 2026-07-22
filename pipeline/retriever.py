"""Local keyword retriever over /data/corpus/ (reproducible, no live web)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import config


@dataclass
class CorpusDoc:
    doc_id: str
    title: str
    text: str


_TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


class LocalCorpusRetriever:
    """Simple TF-style keyword overlap retriever over local text files.

    Drop `.txt` files into CORPUS_DIR. Optional first-line metadata:
      # id: doc_01
      # title: Some Title
    Remaining lines are the document body.
    """

    def __init__(self, corpus_dir: Path | None = None, top_k: int | None = None):
        self.corpus_dir = corpus_dir or config.CORPUS_DIR
        self.top_k = top_k if top_k is not None else config.RETRIEVER_TOP_K
        self.docs: list[CorpusDoc] = []
        self._load()

    def _load(self) -> None:
        self.docs = []
        if not self.corpus_dir.exists():
            return
        for path in sorted(self.corpus_dir.glob("*.txt")):
            raw = path.read_text(encoding="utf-8")
            doc_id = path.stem
            title = path.stem.replace("_", " ").title()
            body_lines: list[str] = []
            for line in raw.splitlines():
                if line.startswith("# id:"):
                    doc_id = line.split(":", 1)[1].strip()
                elif line.startswith("# title:"):
                    title = line.split(":", 1)[1].strip()
                elif line.startswith("#"):
                    continue
                else:
                    body_lines.append(line)
            text = "\n".join(body_lines).strip()
            self.docs.append(CorpusDoc(doc_id=doc_id, title=title, text=text))

    def search(self, query: str, top_k: int | None = None) -> list[tuple[CorpusDoc, float]]:
        k = top_k if top_k is not None else self.top_k
        q_tokens = set(_tokenize(query))
        if not q_tokens or not self.docs:
            return []

        scored: list[tuple[CorpusDoc, float]] = []
        for doc in self.docs:
            d_tokens = _tokenize(f"{doc.title} {doc.text}")
            if not d_tokens:
                continue
            overlap = q_tokens & set(d_tokens)
            # Jaccard-like score with slight boost for title hits
            title_hits = len(q_tokens & set(_tokenize(doc.title)))
            score = (len(overlap) / len(q_tokens | set(d_tokens))) + 0.05 * title_hits
            if score > 0:
                scored.append((doc, float(score)))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:k]


# Module-level singleton — reloadable if corpus changes
_retriever: LocalCorpusRetriever | None = None


def get_retriever(reload: bool = False) -> LocalCorpusRetriever:
    global _retriever
    if _retriever is None or reload:
        _retriever = LocalCorpusRetriever()
    return _retriever
