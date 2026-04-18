# icu-auto-diff-site

Project landing page for *"Enabling Granular Subgroup Level Model Evaluations by Generating Synthetic Medical Time Series"* (SynDAiTE @ ECML PKDD 2025, arXiv:[2510.19728](https://arxiv.org/abs/2510.19728)).

**Live site:** https://mahmoudibrahim98.github.io/icu-auto-diff-site/

**Paper code:** https://github.com/mahmoudibrahim98/icu-auto-diff

## Local preview

```bash
python3 -m http.server 58422 --bind 127.0.0.1
# Open http://localhost:58422/
```

## Data pipeline

The `data/*.json` files are derived products. To regenerate:

```bash
python3 scripts/extract_paper_numbers.py --pdf ../4_timediff/camera-ready.pdf --out data/results.json
python3 scripts/build_subgroups_json.py --csv-dir ../4_timediff/TimeDiff/intersectional_analysis_results --out data/subgroups.json
```
