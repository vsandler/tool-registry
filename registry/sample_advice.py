"""Fixed, pre-written AI advice for the seeded demo tools (DECISIONS.md #9).

The seed data uses this instead of calling the AI, so starting the app is free,
needs no API key and always shows the same advice. Real submissions still call the AI.

The file records which model and which agent instructions produced the advice, and a
fingerprint of each seeded tool's content. tests/test_sample_advice.py fails when any
of these no longer matches, so the advice can't quietly go out of date. It's only ever refreshed by hand:
    .venv/Scripts/python -m registry.refresh_sample_advice
"""

from __future__ import annotations

import json
from pathlib import Path

from registry import agent

SAMPLE_ADVICE_PATH = Path(__file__).resolve().parent / "sample_advice.json"
REFRESH_COMMAND = ".venv/Scripts/python -m registry.refresh_sample_advice"


def load(path: Path = SAMPLE_ADVICE_PATH) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def result_for(tool_name: str, data: dict | None = None) -> agent.ReviewResult:
    """The stored advice for one seeded tool, as a ReviewResult (no API call)."""
    data = data or load()
    try:
        advice = data["advice"][tool_name]
    except KeyError:
        raise KeyError(
            f"No sample advice for seeded tool {tool_name!r}. Run: {REFRESH_COMMAND}"
        ) from None
    return agent.ReviewResult(verdict=advice["verdict"], issues=list(advice["issues"]),
                              reason=advice["reason"], model=data["model"])


def seeded_tools() -> list[dict]:
    """The seeded sample submissions exactly as a real submit would send them to the AI."""
    from registry.db import connect
    from registry.personas import seed_personas
    from registry.seed import FAILING_TOOL, SAFE_TOOLS
    from registry.tools import create_tool, get_tool

    conn = connect(":memory:")
    seed_personas(conn)
    tools = []
    for spec in SAFE_TOOLS + [FAILING_TOOL]:
        tools.append(get_tool(conn, create_tool(conn, owner_id="u-builder", **spec)))
    conn.close()
    return tools


def tool_fingerprint(tool: dict) -> str:
    """A fingerprint (SHA-256 hash) of exactly the parts of a tool the AI reads.
    Any change to the name, description, template, variables, rationale, visibility
    or practice gives a different fingerprint."""
    import hashlib

    content = {key: tool.get(key) for key in agent.SUBMISSION_FIELDS}
    return hashlib.sha256(json.dumps(content, sort_keys=True).encode("utf-8")).hexdigest()


def staleness_problems(data: dict | None = None, config: dict | None = None,
                       tools: list[dict] | None = None) -> list[str]:
    """Plain-language explanations of anything out of date. Empty list = up to date."""
    data = data or load()
    config = config or agent.load_config()
    tools = seeded_tools() if tools is None else tools
    problems = []
    if data.get("model") != config["model"]:
        problems.append(
            f"The model changed. The sample advice was written by {data.get('model')!r}, "
            f"but config.json now says {config['model']!r}."
        )
    if data.get("instructions_fingerprint") != agent.instructions_fingerprint():
        problems.append(
            "The agent's instructions changed. The sample advice was written using an "
            "earlier version of the instructions (SYSTEM_PROMPT or RESPONSE_SCHEMA in "
            "registry/agent.py), so a real AI review might now give different advice."
        )
    advice = data.get("advice", {})
    names = [t["name"] for t in tools]
    for tool in tools:
        stored = advice.get(tool["name"])
        if stored is None:
            problems.append(
                f"A seeded tool has no sample advice: {tool['name']!r} (new, or renamed) "
                "in registry/seed.py."
            )
        elif stored.get("tool_fingerprint") != tool_fingerprint(tool):
            problems.append(
                f"A seeded tool changed: {tool['name']!r} in registry/seed.py is different "
                "from the version the sample advice was written for."
            )
    for name in advice:
        if name not in names:
            problems.append(
                f"Sample advice exists for {name!r}, which is no longer a seeded tool "
                "(removed, or renamed) in registry/seed.py."
            )
    return problems


def explain(problems: list[str]) -> str:
    """A step-by-step message for a failing staleness test."""
    lines = ["", "The sample AI advice for the demo data is out of date.", "",
             "What changed:"]
    lines += [f"  - {p}" for p in problems]
    lines += [
        "",
        "Why it matters: the three seeded demo tools show pre-written AI advice instead",
        "of calling the AI. If the model, the instructions or a seeded tool changes,",
        "that advice may no longer be what the real AI would say.",
        "",
        "How to fix it:",
        "  1. Check the change to config.json, registry/agent.py or registry/seed.py",
        "     was intended.",
        "  2. Make sure .env holds an API key (don't paste it anywhere else).",
        f"  3. Run: {REFRESH_COMMAND}",
        "     This makes 3 real AI calls (well under 1 cent) and rewrites",
        "     registry/sample_advice.json with fresh advice, the current model and",
        "     fresh fingerprints of the instructions and of each seeded tool.",
        "  4. Read the new advice in registry/sample_advice.json, re-run the tests,",
        "     and commit the updated file.",
    ]
    return "\n".join(lines)
