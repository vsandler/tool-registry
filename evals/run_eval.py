"""Run the AI pre-review agent over the labelled eval set and score it against BRIEF.md.

Usage (from the project root):
    .venv/Scripts/python.exe -m evals.run_eval

Each run makes one real API call per submission (about 20), so it costs real money
(roughly a few hundredths of a cent in total on Claude Haiku 5.5). Results are saved
to evals/results/<timestamp>.json and a summary is printed. Calls are also logged
to logs/eval_calls.jsonl (tokens, cost, time; never the key).
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from registry import agent

EVAL_DIR = Path(__file__).resolve().parent
SUBMISSIONS_PATH = EVAL_DIR / "submissions.json"
RESULTS_DIR = EVAL_DIR / "results"
LOG_PATH = agent.PROJECT_ROOT / "logs" / "eval_calls.jsonl"

# Targets from BRIEF.md "Success Metrics".
TARGETS = {
    "risky_caught_all": True,      # every risky submission flagged
    "safe_passed_min": 8,          # at least 8 of 10 safe submissions passed
    "max_cost_usd": 0.01,          # under 1 cent per review
    "max_response_seconds": 10.0,  # under 10 seconds per review
}


def load_submissions(path: Path = SUBMISSIONS_PATH) -> list[dict]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def score(cases: list[dict]) -> dict:
    """Score a list of {"id", "label", "verdict", "cost_usd", "response_seconds"} rows.

    A risky case is *caught* if the agent flagged it in any way (risky, or
    needs_human because the reply failed). A safe case *passes* only on a clean "safe".
    """
    risky = [c for c in cases if c["label"] == "risky"]
    safe = [c for c in cases if c["label"] == "safe"]
    caught = [c for c in risky if c["verdict"] != "safe"]
    passed = [c for c in safe if c["verdict"] == "safe"]
    costs = [c["cost_usd"] or 0.0 for c in cases]
    times = [c["response_seconds"] for c in cases]
    n = len(cases) or 1

    summary = {
        "total": len(cases),
        "risky_total": len(risky),
        "risky_caught": len(caught),
        "risky_missed": [c["id"] for c in risky if c["verdict"] == "safe"],
        "safe_total": len(safe),
        "safe_passed": len(passed),
        "safe_flagged": [c["id"] for c in safe if c["verdict"] != "safe"],
        "needs_human": [c["id"] for c in cases if c["verdict"] == "needs_human"],
        "avg_cost_usd": sum(costs) / n,
        "max_cost_usd": max(costs, default=0.0),
        "total_cost_usd": sum(costs),
        "avg_response_seconds": sum(times) / n,
        "max_response_seconds": max(times, default=0.0),
    }
    summary["meets_targets"] = {
        "every_risky_caught": len(caught) == len(risky),
        "safe_passed_at_least_8": len(passed) >= TARGETS["safe_passed_min"],
        "every_review_under_1_cent": summary["max_cost_usd"] < TARGETS["max_cost_usd"],
        "every_review_under_10_seconds":
            summary["max_response_seconds"] < TARGETS["max_response_seconds"],
    }
    return summary


def run(submissions: list[dict], client=None, config: dict | None = None,
        log_path: Path | None = LOG_PATH) -> list[dict]:
    config = config or agent.load_config()
    if client is None:
        client = agent.make_client()
    rows = []
    for sub in submissions:
        result = agent.review_tool(sub["tool"], client=client, config=config, log_path=log_path)
        rows.append({
            "id": sub["id"],
            "label": sub["label"],
            "category": sub["category"],
            "verdict": result.verdict,
            "correct": (result.verdict == "safe") == (sub["label"] == "safe"),
            "issues": result.issues,
            "reason": result.reason,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "cost_usd": result.cost_usd,
            "response_seconds": round(result.response_seconds, 3),
            "error": result.error,
        })
        mark = "ok  " if rows[-1]["correct"] else "MISS"
        print(f"{mark} {sub['id']:<42} label={sub['label']:<5} verdict={result.verdict:<11} "
              f"{result.response_seconds:5.2f}s  ${result.cost_usd or 0:.6f}", flush=True)
    return rows


def main() -> int:
    config = agent.load_config()
    rows = run(load_submissions(), config=config)
    summary = score(rows)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / f"{stamp}.json"
    out.write_text(json.dumps({"run_at": stamp, "model": config["model"],
                               "effort": config.get("effort"), "summary": summary,
                               "cases": rows}, indent=2), encoding="utf-8")

    print()
    print(f"Model: {config['model']} (effort {config.get('effort')})")
    print(f"Risky caught: {summary['risky_caught']}/{summary['risky_total']}  "
          f"missed: {summary['risky_missed'] or 'none'}")
    print(f"Safe passed:  {summary['safe_passed']}/{summary['safe_total']}  "
          f"flagged: {summary['safe_flagged'] or 'none'}")
    print(f"Needs human (failed replies): {summary['needs_human'] or 'none'}")
    print(f"Cost per review: avg ${summary['avg_cost_usd']:.6f}, max ${summary['max_cost_usd']:.6f}, "
          f"total ${summary['total_cost_usd']:.6f}")
    print(f"Response time: avg {summary['avg_response_seconds']:.2f}s, "
          f"max {summary['max_response_seconds']:.2f}s")
    print(f"Targets: {summary['meets_targets']}")
    print(f"Saved: {out.relative_to(agent.PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
