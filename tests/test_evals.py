"""Checks on the eval set itself and on the scoring, without calling the real API."""

import json
from types import SimpleNamespace

from evals.run_eval import load_submissions, run, score
from registry import agent

SUBMISSIONS = load_submissions()


def test_eval_set_has_about_20_cases_half_risky_half_safe():
    labels = [s["label"] for s in SUBMISSIONS]
    assert 18 <= len(labels) <= 22
    assert labels.count("risky") == labels.count("safe")
    assert set(labels) == {"risky", "safe"}


def test_eval_ids_are_unique():
    ids = [s["id"] for s in SUBMISSIONS]
    assert len(ids) == len(set(ids))


def test_eval_set_covers_required_risk_types():
    categories = {s["category"] for s in SUBMISSIONS if s["label"] == "risky"}
    for required in ("client data", "promise about returns", "missing rationale",
                     "tries to trick the agent"):
        assert required in categories


def test_every_case_has_the_fields_the_agent_sends():
    for s in SUBMISSIONS:
        assert set(agent.SUBMISSION_FIELDS) <= set(s["tool"]), s["id"]


def test_eval_data_uses_only_made_up_contact_details():
    """Any email in the eval set must be on the reserved example.com domain."""
    for s in SUBMISSIONS:
        for email in agent_emails(json.dumps(s)):
            assert email.endswith("@example.com"), s["id"]


def agent_emails(text):
    from registry.checks import EMAIL_PATTERN
    return EMAIL_PATTERN.findall(text)


def row(label, verdict, cost=0.0001, secs=1.0, id_="x"):
    return {"id": id_, "label": label, "verdict": verdict, "cost_usd": cost, "response_seconds": secs}


def test_needs_human_counts_as_caught_for_risky_but_not_passed_for_safe():
    s = score([row("risky", "needs_human", id_="r"), row("safe", "needs_human", id_="s")])
    assert s["risky_caught"] == 1
    assert s["safe_passed"] == 0
    assert s["needs_human"] == ["r", "s"]


def test_score_checks_every_target():
    rows = [row("risky", "risky", id_=f"r{i}") for i in range(10)]
    rows += [row("safe", "safe", id_=f"s{i}") for i in range(8)]
    rows += [row("safe", "risky", id_="s8"), row("safe", "risky", id_="s9")]
    s = score(rows)
    assert all(s["meets_targets"].values())

    s = score(rows + [row("risky", "safe", id_="missed")])
    assert s["risky_missed"] == ["missed"]
    assert s["meets_targets"]["every_risky_caught"] is False

    s = score([row("risky", "risky", cost=0.02, secs=12.0)])
    assert s["meets_targets"]["every_review_under_1_cent"] is False
    assert s["meets_targets"]["every_review_under_10_seconds"] is False


def test_run_uses_the_agent_for_each_case_with_a_fake_client():
    class Fake:
        def __init__(self):
            self.messages = self

        def create(self, **kwargs):
            text = json.dumps({"verdict": "risky", "issues": ["x"], "reason": "y"})
            return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)],
                                   stop_reason="end_turn",
                                   usage=SimpleNamespace(input_tokens=10, output_tokens=5))

    rows = run(SUBMISSIONS[:3], client=Fake(), config={"model": "claude-haiku-5-5"}, log_path=None)
    assert [r["id"] for r in rows] == [s["id"] for s in SUBMISSIONS[:3]]
    assert all(r["verdict"] == "risky" for r in rows)
