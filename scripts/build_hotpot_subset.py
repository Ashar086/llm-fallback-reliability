"""
Build a 40-question HotpotQA distractor-dev subset + local corpus.

Access method: Hugging Face `datasets` library
  load_dataset("hotpot_qa", "distractor", split="validation")

Filtering (documented for the paper's dataset section):
  - Prefer short gold answers: 1–6 whitespace tokens, length <= 60 chars
  - Exclude answers that are only yes/no (ambiguous multi-valid often)
  - Require >= 2 supporting titles resolvable in context
  - Prefer `type == "bridge"` (true multi-hop) over comparison when available
  - Deterministic selection: sort by id, take first 40 that pass filters
  - Corpus = all supporting paragraphs for the 40 Qs
    + ~20 distractor paragraphs sampled from non-supporting contexts
      of those same questions (reproducible seed=42)
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from datasets import load_dataset

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
CORPUS_DIR = DATA_DIR / "corpus"
QUESTIONS_PATH = DATA_DIR / "questions.json"
META_PATH = DATA_DIR / "dataset_meta.json"

N_QUESTIONS = 40
N_DISTRACTORS = 20
SEED = 42


def _slug(title: str, max_len: int = 48) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", title.strip()).strip("_").lower()
    return (s or "doc")[:max_len]


def _answer_ok(answer: str) -> bool:
    a = answer.strip()
    if not a or len(a) > 60:
        return False
    tokens = a.split()
    if len(tokens) < 1 or len(tokens) > 6:
        return False
    if a.lower() in {"yes", "no", "true", "false"}:
        return False
    # Prefer answers with some alphanumeric content
    if not re.search(r"[A-Za-z0-9]", a):
        return False
    return True


def _context_map(context) -> dict[str, str]:
    """Hotpot context: titles + sentences lists → title -> paragraph text."""
    titles = context["title"]
    sentences = context["sentences"]
    out: dict[str, str] = {}
    for title, sents in zip(titles, sentences):
        out[title] = " ".join(sents).strip()
    return out


def _supporting_titles(supporting_facts) -> list[str]:
    titles = supporting_facts["title"]
    # unique, preserve order
    seen: set[str] = set()
    ordered: list[str] = []
    for t in titles:
        if t not in seen:
            seen.add(t)
            ordered.append(t)
    return ordered


def main() -> None:
    print("Loading HotpotQA distractor validation via Hugging Face datasets...")
    ds = load_dataset("hotpot_qa", "distractor", split="validation")
    print(f"  loaded {len(ds)} examples")

    candidates = []
    for ex in ds:
        ans = ex["answer"]
        if not _answer_ok(ans):
            continue
        if ex.get("type") not in {"bridge", "comparison"}:
            continue
        cmap = _context_map(ex["context"])
        supp_titles = _supporting_titles(ex["supporting_facts"])
        if len(supp_titles) < 2:
            continue
        if any(t not in cmap or not cmap[t] for t in supp_titles):
            continue
        # Prefer bridge; keep comparison as secondary pool
        candidates.append(ex)

    # Sort for determinism: bridge first, then by id
    candidates.sort(key=lambda e: (0 if e["type"] == "bridge" else 1, e["id"]))
    selected = candidates[:N_QUESTIONS]
    if len(selected) < N_QUESTIONS:
        raise SystemExit(f"Only found {len(selected)} candidates; need {N_QUESTIONS}")

    # Rebuild corpus directory
    if CORPUS_DIR.exists():
        shutil.rmtree(CORPUS_DIR)
    CORPUS_DIR.mkdir(parents=True)

    questions = []
    title_to_doc_id: dict[str, str] = {}
    doc_counter = 0
    written_docs: set[str] = set()

    def ensure_doc(title: str, text: str) -> str:
        nonlocal doc_counter
        if title in title_to_doc_id:
            return title_to_doc_id[title]
        doc_counter += 1
        doc_id = f"doc_{doc_counter:03d}_{_slug(title)}"
        title_to_doc_id[title] = doc_id
        path = CORPUS_DIR / f"{doc_id}.txt"
        path.write_text(
            f"# id: {doc_id}\n# title: {title}\n{text}\n",
            encoding="utf-8",
        )
        written_docs.add(doc_id)
        return doc_id

    # Supporting docs for all questions
    for ex in selected:
        cmap = _context_map(ex["context"])
        supp_titles = _supporting_titles(ex["supporting_facts"])
        supporting_doc_ids = []
        supporting_docs = []
        for t in supp_titles:
            doc_id = ensure_doc(t, cmap[t])
            supporting_doc_ids.append(doc_id)
            supporting_docs.append({"doc_id": doc_id, "title": t, "text": cmap[t]})

        # supporting facts as Hotpot provides (title + sentence index)
        sf = [
            {"title": t, "sent_id": int(sid)}
            for t, sid in zip(
                ex["supporting_facts"]["title"],
                ex["supporting_facts"]["sent_id"],
            )
        ]

        questions.append(
            {
                "id": ex["id"],
                "question": ex["question"],
                "gold_answer": ex["answer"],
                "supporting_doc_ids": supporting_doc_ids,
                "supporting_facts": sf,
                "supporting_docs": supporting_docs,
                "hotpot_type": ex["type"],
                "hotpot_level": ex.get("level"),
            }
        )

    # Distractors: non-supporting paragraphs from selected questions
    distractor_pool: list[tuple[str, str]] = []
    for ex in selected:
        cmap = _context_map(ex["context"])
        supp = set(_supporting_titles(ex["supporting_facts"]))
        for title, text in cmap.items():
            if title in supp or title in title_to_doc_id:
                continue
            if not text.strip():
                continue
            distractor_pool.append((title, text))

    # Deterministic sample
    distractor_pool.sort(key=lambda x: x[0])
    # Simple reproducible subsample without numpy
    step = max(1, len(distractor_pool) // N_DISTRACTORS)
    sampled = distractor_pool[::step][:N_DISTRACTORS]
    # If short, take from start
    if len(sampled) < N_DISTRACTORS:
        sampled = distractor_pool[:N_DISTRACTORS]

    distractor_ids = []
    for title, text in sampled:
        if title in title_to_doc_id:
            continue
        doc_id = ensure_doc(title, text)
        distractor_ids.append(doc_id)

    QUESTIONS_PATH.write_text(
        json.dumps(questions, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    meta = {
        "source": "hotpot_qa",
        "config": "distractor",
        "split": "validation",
        "access": "Hugging Face datasets: load_dataset('hotpot_qa', 'distractor', split='validation')",
        "n_questions": len(questions),
        "n_corpus_docs": len(written_docs),
        "n_supporting_docs": len(written_docs) - len(distractor_ids),
        "n_distractor_docs": len(distractor_ids),
        "filters": {
            "gold_answer_max_chars": 60,
            "gold_answer_max_tokens": 6,
            "exclude_yes_no": True,
            "min_supporting_titles": 2,
            "prefer_type": "bridge",
            "selection": "sort by (bridge-first, id), take first 40",
            "distractor_seed_note": f"sorted titles, stride subsample, target={N_DISTRACTORS}",
        },
        "question_ids": [q["id"] for q in questions],
        "distractor_doc_ids": distractor_ids,
    }
    META_PATH.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    # Update data README
    (DATA_DIR / "README.md").write_text(
        "# Dataset\n\n"
        "Built by `scripts/build_hotpot_subset.py` from HotpotQA distractor validation "
        "via Hugging Face `datasets`.\n\n"
        f"- Questions: `{QUESTIONS_PATH.name}` ({len(questions)} items)\n"
        f"- Corpus: `corpus/` ({len(written_docs)} docs = supporting + distractors)\n"
        f"- Metadata: `{META_PATH.name}`\n\n"
        "See `dataset_meta.json` for filtering logic suitable for the paper's dataset section.\n",
        encoding="utf-8",
    )

    print(f"Wrote {len(questions)} questions -> {QUESTIONS_PATH}")
    print(
        f"Wrote {len(written_docs)} corpus docs "
        f"({len(written_docs) - len(distractor_ids)} supporting + "
        f"{len(distractor_ids)} distractors) -> {CORPUS_DIR}"
    )
    print(f"Meta -> {META_PATH}")
    print("Sample gold answers:", [q["gold_answer"] for q in questions[:5]])


if __name__ == "__main__":
    main()
