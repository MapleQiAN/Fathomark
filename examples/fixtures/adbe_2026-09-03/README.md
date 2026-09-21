# ADBE recorded public fixture

This directory is the smallest complete offline fixture for the Fathomark
golden path. It contains a fixed scope, two short evidence excerpts, eleven
factor proposals, the expected deterministic snapshot, and recorded agent
responses. It is not a current Adobe rating, forecast, recommendation or trade
instruction.

The evidence metadata points to public SEC EDGAR filing URLs:

- [Adobe Q2 FY2026 results](https://www.sec.gov/Archives/edgar/data/796343/000079634326000109/adbeex991q226.htm)
- [Adobe FY2026 Q2 Form 10-Q](https://www.sec.gov/Archives/edgar/data/796343/000079634326000112/adbe-20260529.htm)

The checked-in excerpts are short, historical fixture text intended for
reproducibility. CI never calls SEC or an LLM. Rebuild the agent cassette with
`uv run python scripts/build_cassette.py` only when the fixture contract and
expected snapshot are intentionally reviewed together.
