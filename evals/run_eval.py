"""Run the AI pre-review agent over the labelled eval set and score it against BRIEF.md.

Usage (from the project root):
    .venv/Scripts/python.exe -m evals.run_eval            # 3 runs of every case
    .venv/Scripts/python.exe -m evals.run_eval --runs 1
    .venv/Scripts/python.exe -m evals.run_eval --model claude-sonnet-5-5   # this run only
    .venv/Scripts/python.exe -m evals.run_eval --case safe-01-meeting-summary   # just these
    .venv/Scripts/python.exe -m evals.run_eval --file evals/probe_practice.json  # another set

A case may list `must_not_mention` words. Any issue the AI lists that contains one
(ignoring case) is reported as an *unwanted issue*, separately from the score: the
verdict can be right while one of the issues is wrong.

Each run makes one real API call per submission, so it costs real money (about
$0.007 per run of 33 cases on Claude Haiku 5.5). The model can answer differently
each time, so by default every case runs 3 times and any case whose answer changes
between runs is reported. Results are saved to evals/results/<timestamp>.json.
Calls are also logged to logs/eval_calls.jsonl (tokens, cost, time; never the key).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from registry import agent

EVAL_DIR = Path(__file__).resolve().parent
SUBMISSIONS_PATH = EVAL_DIR / "submissions.json"
RESULTS_DIR = EVAL_DIR / "results"
LOG_PATH = agent.PROJECT_ROOT / "logs" / "eval_calls.jsonl"
DEFAULT_RUNS = 3

# Targets from BRIEF.md "Success Metrics". The safe target (at least 80% of safe
# cases passed) must be met in every run.
TARGETS = {
    "safe_pass_rate_min": 0.8,
    "max_cost_usd": 0.01,          # under 1 cent per review
    "max_response_seconds": 10.0,  # under 10 seconds per review
}


def load_submissions(path: Path = SUBMISSIONS_PATH) -> list[dict]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def select_cases(submissions: list[dict], ids: list[str] | None) -> list[dict]:
    """Just the cases named in `ids`, in the eval set's order. All of them if None."""
    if not ids:
        return submissions
    unknown = sorted(set(ids) - {s["id"] for s in submissions})
    if unknown:
        raise ValueError(f"No eval case with id: {', '.join(unknown)}")
    return [s for s in submissions if s["id"] in ids]


def unwanted_issues(case: dict) -> dict | None:
    """Issues mentioning any of the case's `must_not_mention` words, with the runs they
    appeared in. None if there are none (or the case lists no words)."""
    words = [w.lower() for w in case.get("must_not_mention", [])]
    if not words:
        return None
    found, in_runs = [], []
    for call in case["calls"]:
        bad = [i for i in call.get("issues", []) if any(w in i.lower() for w in words)]
        if bad:
            found += bad
            in_runs.append(call.get("run"))
    if not found:
        return None
    return {"id": case["id"], "words": case["must_not_mention"], "in_runs": in_runs,
            "issues": found}


def is_flagged(verdict: str) -> bool:
    """risky and needs_human both send the tool to a human with a flag."""
    return verdict != "safe"


def score(cases: list[dict]) -> dict:
    """Score cases, each {"id", "label", "verdicts": [...], "calls": [{cost_usd, response_seconds}]}.

    - A risky case counts as caught only if it was flagged in *every* run: one miss in
      real use is a miss. needs_human counts as flagged (a person checks it anyway).
    - A safe case counts as passed only if it was a clean "safe" in every run.
    - A case is *inconsistent* if its verdicts differ between runs.
    """
    risky = [c for c in cases if c["label"] == "risky"]
    safe = [c for c in cases if c["label"] == "safe"]
    runs = max((len(c["verdicts"]) for c in cases), default=0)
    calls = [call for c in cases for call in c["calls"]]
    costs = [call["cost_usd"] or 0.0 for call in calls]
    times = [call["response_seconds"] for call in calls]
    n = len(calls) or 1

    def flagged_runs(c):
        return sum(is_flagged(v) for v in c["verdicts"])

    per_run = []
    for i in range(runs):
        per_run.append({
            "run": i + 1,
            "risky_caught": sum(is_flagged(c["verdicts"][i]) for c in risky),
            "safe_passed": sum(not is_flagged(c["verdicts"][i]) for c in safe),
        })

    summary = {
        "runs": runs,
        "total_cases": len(cases),
        "total_calls": len(calls),
        "risky_total": len(risky),
        "risky_caught_every_run": sum(flagged_runs(c) == len(c["verdicts"]) for c in risky),
        "risky_missed": [{"id": c["id"], "missed_in_runs": len(c["verdicts"]) - flagged_runs(c)}
                         for c in risky if flagged_runs(c) < len(c["verdicts"])],
        "safe_total": len(safe),
        "safe_passed_every_run": sum(flagged_runs(c) == 0 for c in safe),
        "safe_flagged": [{"id": c["id"], "flagged_in_runs": flagged_runs(c)}
                         for c in safe if flagged_runs(c) > 0],
        "inconsistent": [{"id": c["id"], "label": c["label"], "verdicts": c["verdicts"]}
                         for c in cases if len(set(c["verdicts"])) > 1],
        "needs_human": [c["id"] for c in cases if "needs_human" in c["verdicts"]],
        # Reported apart from the score: right verdict, but a wrong issue listed.
        "unwanted_issues": [u for u in map(unwanted_issues, cases) if u],
        "per_run": per_run,
        "avg_cost_usd": sum(costs) / n,
        "max_cost_usd": max(costs, default=0.0),
        "total_cost_usd": sum(costs),
        "avg_response_seconds": sum(times) / n,
        "max_response_seconds": max(times, default=0.0),
    }
    min_safe_pass = min((r["safe_passed"] for r in per_run), default=0)
    summary["meets_targets"] = {
        "every_risky_caught_in_every_run": summary["risky_caught_every_run"] == len(risky),
        "safe_pass_rate_at_least_80pct_in_every_run":
            bool(safe) and min_safe_pass / len(safe) >= TARGETS["safe_pass_rate_min"],
        "every_review_under_1_cent": summary["max_cost_usd"] < TARGETS["max_cost_usd"],
        "every_review_under_10_seconds":
            summary["max_response_seconds"] < TARGETS["max_response_seconds"],
    }
    return summary


def run(submissions: list[dict], runs: int = DEFAULT_RUNS, client=None,
        config: dict | None = None, log_path: Path | None = LOG_PATH) -> list[dict]:
    """Review every submission `runs` times (all cases once, then again, and so on)."""
    config = config or agent.load_config()
    if client is None:
        client = agent.make_client()
    cases = {s["id"]: {"id": s["id"], "label": s["label"], "category": s["category"],
                       "verdicts": [], "calls": [],
                       **({"must_not_mention": s["must_not_mention"]}
                          if s.get("must_not_mention") else {})}
             for s in submissions}
    for i in range(runs):
        print(f"--- run {i + 1} of {runs}", flush=True)
        for sub in submissions:
            r = agent.review_tool(sub["tool"], client=client, config=config, log_path=log_path)
            case = cases[sub["id"]]
            case["verdicts"].append(r.verdict)
            case["calls"].append({
                "run": i + 1, "verdict": r.verdict, "issues": r.issues, "reason": r.reason,
                "input_tokens": r.input_tokens, "output_tokens": r.output_tokens,
                "cost_usd": r.cost_usd, "response_seconds": round(r.response_seconds, 3),
                "error": r.error,
            })
            right = is_flagged(r.verdict) == (sub["label"] == "risky")
            print(f"{'ok  ' if right else 'MISS'} {sub['id']:<46} label={sub['label']:<5} "
                  f"verdict={r.verdict:<11} {r.response_seconds:5.2f}s  ${r.cost_usd or 0:.6f}",
                  flush=True)
    return list(cases.values())


def eval_config(model: str | None = None) -> dict:
    """The settings for this eval run: config.json, with the model swapped for this
    run only if `model` is given. config.json itself is never changed."""
    config = dict(agent.load_config())
    if model:
        config["model"] = model
    return config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS)
    parser.add_argument("--model", help="Use this model for this run only (config.json "
                                        "is not changed), e.g. claude-sonnet-5-5")
    parser.add_argument("--file", type=Path, default=SUBMISSIONS_PATH,
                        help="Cases to run (default: the scored eval set, "
                             "evals/submissions.json)")
    parser.add_argument("--case", action="append", dest="cases", metavar="ID",
                        help="Run only this case (repeat for more). Default: every case.")
    args = parser.parse_args(argv)

    try:
        submissions = select_cases(load_submissions(args.file), args.cases)
    except ValueError as err:
        parser.error(str(err))
    config = eval_config(args.model)
    cases = run(submissions, runs=args.runs, config=config, log_path=LOG_PATH)
    summary = score(cases)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / f"{stamp}.json"
    out.write_text(json.dumps({"run_at": stamp, "model": config["model"],
                               "effort": config.get("effort"),
                               "file": str(args.file),
                               "selected_cases": args.cases or "all", "summary": summary,
                               "cases": cases}, indent=2), encoding="utf-8")

    s = summary
    print()
    print(f"Model: {config['model']} (effort {config.get('effort')}), {s['runs']} runs, "
          f"{s['total_cases']} cases, {s['total_calls']} calls")
    print(f"Risky caught in every run: {s['risky_caught_every_run']}/{s['risky_total']}  "
          f"missed: {s['risky_missed'] or 'none'}")
    print(f"Safe passed in every run:  {s['safe_passed_every_run']}/{s['safe_total']}  "
          f"flagged: {s['safe_flagged'] or 'none'}")
    print(f"Per run: {s['per_run']}")
    print(f"Inconsistent across runs: {s['inconsistent'] or 'none'}")
    print(f"Needs human (failed replies): {s['needs_human'] or 'none'}")
    print(f"Unwanted issues (reported apart from the score): {s['unwanted_issues'] or 'none'}")
    print(f"Cost per review: avg ${s['avg_cost_usd']:.6f}, max ${s['max_cost_usd']:.6f}, "
          f"total ${s['total_cost_usd']:.6f}")
    print(f"Response time: avg {s['avg_response_seconds']:.2f}s, "
          f"max {s['max_response_seconds']:.2f}s")
    print(f"Targets: {s['meets_targets']}")
    try:
        shown = out.relative_to(agent.PROJECT_ROOT)
    except ValueError:
        shown = out
    print(f"Saved: {shown}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
