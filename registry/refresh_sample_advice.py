"""Refresh the sample AI advice for the seeded demo tools, using the real AI.

Run by hand only (it is never run automatically):
    .venv/Scripts/python -m registry.refresh_sample_advice

It makes one real AI call per seeded tool (3 calls, well under 1 cent), then rewrites
registry/sample_advice.json with the new advice, the current model, the current
instructions fingerprint and a fingerprint of each seeded tool's content. If any call fails (needs_human), nothing is written and the
old file is kept.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from registry import agent, sample_advice
from registry.tools import now


def refresh(path: Path = sample_advice.SAMPLE_ADVICE_PATH, client=None) -> bool:
    """Review each seeded tool with the real AI and save the advice. True if saved."""
    config = agent.load_config()
    if client is None:
        client = agent.make_client()
    advice, failures = {}, []
    for tool in sample_advice.seeded_tools():
        r = agent.review_tool(tool, client=client, config=config)
        print(f"{tool['name']}: {r.verdict}  ({r.response_seconds:.2f}s, ${r.cost_usd or 0:.6f})")
        if r.verdict == "needs_human":
            failures.append(f"{tool['name']}: {r.error}")
        advice[tool["name"]] = {"tool_fingerprint": sample_advice.tool_fingerprint(tool),
                                "verdict": r.verdict, "issues": r.issues, "reason": r.reason}

    if failures:
        print("\nNot saved: the AI didn't give a usable answer for:")
        for f in failures:
            print(f"  - {f}")
        print("The old sample advice was kept. Check .env has an API key, then try again.")
        return False

    old = sample_advice.load(path) if Path(path).exists() else {}
    data = {
        "about": old.get("about", "Pre-written AI advice for the seeded demo tools."),
        "model": config["model"],
        "instructions_fingerprint": agent.instructions_fingerprint(),
        "recorded_at": now(),
        "advice": advice,
    }
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nSaved {Path(path).name}. Read the new advice, run the tests, then commit it.")
    return True


if __name__ == "__main__":
    sys.exit(0 if refresh() else 1)
