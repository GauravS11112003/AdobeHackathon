"""Offline evaluation harness (dev only; the Dockerfile does not copy eval/).

- crello_convert.py  download a slice of the Crello dataset and convert it to schema v0.9
- metrics.py         per-case metrics shared by run_eval and the tests
- run_eval.py        run the engine over designs x preset catalogue, resumable, CSV + summary
- report.py          contact sheet of the worst cases + docs/EVAL_V1.md
"""
