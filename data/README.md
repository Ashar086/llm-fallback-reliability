# Dataset

Built by `scripts/build_hotpot_subset.py` from **HotpotQA** distractor
validation via Hugging Face `datasets`.

## Source and license

- **Upstream:** [HotpotQA](https://hotpotqa.github.io/)
  (Yang et al., EMNLP 2018)
- **License:** [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)
- Redistributed text under this folder inherits that license; please cite HotpotQA
  when using the subset.

## Contents

- `questions.json` — HotpotQA multi-hop questions used by the pipeline
- `corpus/` — supporting + distractor documents for local retrieval
- `dataset_meta.json` — filtering / construction metadata

See `dataset_meta.json` for filtering logic suitable for the paper's dataset
section. The camera-ready main experiment uses **150** Hotpot questions
(three trials); see `results/question_outcomes.csv`.
