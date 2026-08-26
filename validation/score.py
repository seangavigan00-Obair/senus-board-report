"""
Score a pipeline extraction against the hand-verified golden set.

Three numbers matter, and they are different questions:

  PRECISION  of the facts the pipeline produced that the golden set also covers,
             how many have the right value? This is "when it speaks, is it right?"
  RECALL     of the facts a human verified, how many did the pipeline find?
             This is "does it miss things?"
  UNVERIFIED facts the pipeline produced that the golden set says nothing about.
             Not errors - the golden set is a sample, not the whole corpus - but
             they are unaudited, and the count belongs in the README.

A fact is correct when the period and metric match and the value agrees within
one euro. The tolerance exists because the published statements themselves round
to the euro in places (defect D03).

Run:  python validation/score.py data/extracted/facts.json
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline.select import collapse

GOLDEN = Path(__file__).parent / "golden_set.json"
TOLERANCE = 1.0


def load_golden() -> tuple[dict, dict]:
    data = json.loads(GOLDEN.read_text(encoding="utf-8"))
    truth = {(f["period"], f["metric"]): f for f in data["facts"]}
    return data, truth


def load_extracted(path: Path) -> dict:
    """
    Collapse to one fact per (period, metric) using source precedence.

    A primary financial statement outranks a rounded narrative restatement of
    the same figure - see pipeline/select.py for why this is not a tie-break
    but a data-modelling rule.
    """
    rows = json.loads(path.read_text(encoding="utf-8"))
    flat = [
        {**row["fact"],
         "_document": row["provenance"]["document"],
         "_page": row["provenance"]["page"],
         "_path": row["provenance"]["extraction_path"]}
        for row in rows
    ]

    winners, superseded = collapse(
        flat,
        period=lambda r: r["period"],
        metric=lambda r: r["metric"],
        statement=lambda r: r["statement"],
        approximate=lambda r: r.get("is_approximate", False),
        document=lambda r: r["_document"],
        value=lambda r: r["value"],
    )

    conflicts = [s for s in superseded if s["_conflict"]]
    if conflicts:
        print(f"  {len(conflicts)} same-tier conflicts (two statements disagree):")
        for c in conflicts[:5]:
            print(f"    {c['period']} {c['metric']}: {c['value']:,.0f} in "
                  f"{c['_document'][:38]} p{c['_page']} vs {c['_superseded_by']:,.0f} kept")
    print(f"  {len(flat)} facts -> {len(winners)} after precedence "
          f"({len(superseded)} superseded, of which {len(conflicts)} genuine conflicts)")
    return winners


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2

    extracted_path = Path(sys.argv[1])
    if not extracted_path.exists():
        print(f"no extraction at {extracted_path}")
        return 2

    data, truth = load_golden()
    got = load_extracted(extracted_path)

    # Scope recall to what this run actually looked at. A run over two pages of
    # one document must not be scored against facts that live in a document it
    # never opened - that would report a miss where there was no attempt.
    # A golden fact is in scope only if the run read the document AND the page
    # that fact was verified from.
    attempted_periods = {p for p, _ in got}
    attempted_pages = {(v["_document"], v["_page"]) for v in got.values()}
    attempted_docs = {doc for doc, _ in attempted_pages}

    in_scope = {
        k: v for k, v in truth.items()
        if k[0] in attempted_periods
        and v["source"] in attempted_docs
        and (v["source"], v["page"]) in attempted_pages
    }
    out_of_scope = len(truth) - len(in_scope)

    correct, wrong, missed = [], [], []
    for key, expected in in_scope.items():
        actual = got.get(key)
        if actual is None:
            missed.append((key, expected))
        elif abs(actual["value"] - expected["value"]) <= TOLERANCE:
            correct.append((key, expected, actual))
        else:
            wrong.append((key, expected, actual))

    unverified = [k for k in got if k not in truth]

    print(f"\nExtraction scored against golden set")
    print(f"  source      {extracted_path}")
    print(f"  pages read  {len(attempted_pages)} across {len(attempted_docs)} document(s)")
    print(f"  periods     {', '.join(sorted(attempted_periods))}")
    print(f"  golden set  {len(in_scope)} verified facts on those pages "
          f"({out_of_scope} elsewhere in the corpus, not attempted)\n")

    if wrong:
        print("  WRONG VALUES")
        for (period, metric), expected, actual in wrong:
            print(f"    {period:<7} {metric:<28} expected {expected['value']:>13,.0f}  "
                  f"got {actual['value']:>13,.0f}  ({actual['_document'][:34]} p{actual['_page']})")
        print()

    if missed:
        print("  NOT FOUND")
        for (period, metric), expected in missed:
            print(f"    {period:<7} {metric:<28} expected {expected['value']:>13,.0f}  "
                  f"(golden source: {expected['source'][:38]} p{expected['page']})")
        print()

    scored = len(correct) + len(wrong)
    precision = len(correct) / scored if scored else 0.0
    recall = len(correct) / len(in_scope) if in_scope else 0.0

    by_path: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for _, _, actual in correct:
        by_path[actual["_path"]][0] += 1
    for _, _, actual in wrong:
        by_path[actual["_path"]][1] += 1

    print(f"  precision   {precision:6.1%}   ({len(correct)} of {scored} matched facts correct)")
    print(f"  recall      {recall:6.1%}   ({len(correct)} of {len(in_scope)} verified facts found)")
    for path, (ok, bad) in sorted(by_path.items()):
        total = ok + bad
        print(f"    via {path:<12} {ok}/{total} correct")
    print(f"  unverified  {len(unverified):>4}   facts extracted that the golden "
          f"set does not cover")
    print()

    return 0 if not wrong else 1


if __name__ == "__main__":
    sys.exit(main())
