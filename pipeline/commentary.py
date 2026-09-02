"""
AI-generated board commentary, grounded in two sources and only two sources.

This is the part of the brief we could get badly wrong: "AI-powered insights,
commentary or financial analysis where appropriate." The wrong implementation
sends the raw PDFs back to an LLM and asks it to comment on Senus's
performance - which reintroduces exactly the failure mode the rest of this
project exists to prevent, an LLM doing financial reasoning with no way to
check its arithmetic.

Instead the model is given only:

  1. The COMPUTED metrics from pipeline/metrics.py - numbers Python already
     calculated and verified, with their formulas and flags. The model is
     never asked to compute anything, only to narrate what is already true.
  2. Excerpts from the timestamped transcript of management's own half-year
     results presentation - what Brendan Allen and Stephen Coen said about
     these numbers, in their own words.

The system prompt requires every numeric claim to trace to a metric id from
source (1), and every quote or characterisation of intent to be attributed to
management from source (2) and flagged as their view, not verified fact. A
structured `metrics_cited` field on the output makes that traceable rather
than just asserted - the UI can render each citation as a link back into the
same provenance panel every other figure in this report uses.

Run:  python -m pipeline.commentary
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import anthropic

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "web" / "public" / "board-report.json"
TRANSCRIPT = ROOT / "data" / "source" / "transcript.txt"
MODEL = "claude-opus-5"
MAX_TOKENS = 4096  # first run truncated mid-JSON at 1024; commentary + citations need more room

AUDIENCES = {
    "management": "Operational control - where cash is going and whether cost discipline is holding.",
    "board": "Fiduciary view - solvency, runway and whether the Senus 2030 plan remains credible.",
    "equity": "Growth and the path to profitability, measured against the 50% CAGR target.",
    "credit": "Ability to service and repay debt - liquidity, coverage and headroom.",
}

SYSTEM_PROMPT = """You write board commentary for Senus PLC from two sources only, \
and you must not use anything outside them.

SOURCE 1 - COMPUTED METRICS (JSON): figures already calculated and verified by \
deterministic Python code. Treat every value here as ground truth. You may cite \
any of these figures. You may NEVER state a number, percentage, or period-over-\
period comparison that is not present in this JSON - if a comparison would be \
useful but is not in the data, say what is missing rather than estimating it.

SOURCE 2 - MANAGEMENT TRANSCRIPT: a timestamped transcript of Brendan Allen \
(Managing Director) and Stephen Coen (General Manager) presenting Senus's half \
year results. This is management's characterisation of the business, not \
verified fact. When you draw on it, attribute it explicitly ("management told \
investors...", "Brendan Allen described...") - never present a management claim \
as an established fact of your own.

Rules:
1. Every number in your commentary must trace to a metric id in the JSON. List \
every metric id you used in `metrics_cited`.
2. Every claim about intent, plans, or explanation ("delayed by a wet winter", \
"transformational acquisition") that comes from the transcript must be \
attributed to management, not stated as your own analysis.
3. If the data does not support a claim a reader might expect (for example, no \
monthly figures exist), say so rather than inferring one.
4. Write for the named audience's actual decision, not a generic summary. A \
credit provider reads runway and coverage; an equity investor reads growth \
against the Senus 2030 target.
5. Three to five sentences. No bullet points, no headings, no restating the \
audience name.
6. Do not hedge with "it appears" or "seems to" for figures that are simply \
stated as fact in the metrics JSON. Do hedge appropriately for anything from \
the transcript, since it is management's own framing."""


def _load_metrics_for_audience(report: dict, audience: str) -> list[dict]:
    """The subset of metrics this audience's sections actually cover."""
    section_metric_ids = {
        m for s in report["sections"] if audience in s["audiences"] for m in s["metrics"]
    }
    return [
        {k: v for k, v in m.items() if k not in ("inputs",)}
        for m in report["metrics"]
        if m["id"] in section_metric_ids
    ]


def _transcript_excerpt(max_chars: int = 6000) -> str:
    if not TRANSCRIPT.exists():
        return ""
    text = TRANSCRIPT.read_text(encoding="utf-8")
    return text[:max_chars]


def generate_commentary(report: dict, audience: str, client: anthropic.Anthropic) -> dict:
    metrics = _load_metrics_for_audience(report, audience)
    transcript = _transcript_excerpt()

    user_content = f"""Audience: {audience} ({AUDIENCES[audience]})

COMPUTED METRICS (JSON):
{json.dumps(metrics, indent=2)}

MANAGEMENT TRANSCRIPT (excerpt, half-year results presentation):
{transcript}

Write the commentary for this audience now."""

    from pydantic import BaseModel, Field

    class CommentaryOutput(BaseModel):
        commentary: str = Field(description="3-5 sentences, no headings.")
        metrics_cited: list[str] = Field(description="Every metric id referenced.")
        management_attributions: list[str] = Field(
            default_factory=list,
            description="Short phrases drawn from the transcript, each one "
                        "explicitly attributed to management in the commentary.",
        )

    response = client.messages.parse(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
        output_format=CommentaryOutput,
    )
    out = response.parsed_output

    # Verify the model's own citation claim before trusting it: every cited id
    # must actually exist in the metrics we gave it. A model that cites a metric
    # id it invented is a grounding failure, and it must be caught here, not in
    # the UI.
    valid_ids = {m["id"] for m in metrics}
    invalid = [m for m in out.metrics_cited if m not in valid_ids]
    if invalid:
        print(f"    WARNING: {audience} cited unknown metric ids: {invalid}")

    return {
        "audience": audience,
        "commentary": out.commentary,
        "metrics_cited": [m for m in out.metrics_cited if m in valid_ids],
        "management_attributions": out.management_attributions,
        "model": MODEL,
        "grounding": {
            "metrics_available": len(metrics),
            "transcript_chars": len(transcript),
        },
    }


def main() -> int:
    if not REPORT.exists():
        raise SystemExit(f"no board report at {REPORT} - run pipeline.build first")

    report = json.loads(REPORT.read_text(encoding="utf-8"))
    client = anthropic.Anthropic()

    print("\nGenerating grounded AI commentary\n")
    commentary = {}
    for audience in AUDIENCES:
        result = generate_commentary(report, audience, client)
        commentary[audience] = result
        print(f"  {audience:<12} {len(result['metrics_cited'])} metrics cited, "
              f"{len(result['commentary'])} chars")

    report["commentary"] = commentary
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\n  wrote commentary for {len(commentary)} audiences into {REPORT.name}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
