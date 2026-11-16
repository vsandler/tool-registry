"""Checks on the eval set itself and on the scoring, without calling the real API."""

import json

from evals.run_eval import load_submissions, run, score
from registry import agent

SUBMISSIONS = load_submissions()


def test_eval_set_is_about_half_risky_half_safe():
    """At least 18 cases, with the risky and safe counts within 2 of each other."""
    labels = [s["label"] for s in SUBMISSIONS]
    assert 18 <= len(labels) <= 40
    assert abs(labels.count("risky") - labels.count("safe")) <= 2
    assert set(labels) == {"risky", "safe"}


def test_eval_ids_are_unique():
    ids = [s["id"] for s in SUBMISSIONS]
    assert len(ids) == len(set(ids))


def test_eval_set_covers_required_risk_types():
    categories = {s["category"] for s in SUBMISSIONS if s["label"] == "risky"}
    for required in ("client data", "promise about returns", "meaningless rationale",
                     "tries to trick the agent"):
        assert required in categories


def test_ai_eval_set_has_no_missing_or_short_rationales(conn):
    """Missing or empty rationales belong to the rule-based check (tests/test_checks.py).
    Every AI eval case must have a rationale the rule-based check lets through, so the
    AI is only judging rationales that are present."""
    from registry.checks import check_has_rationale
    for s in SUBMISSIONS:
        assert check_has_rationale(s["tool"], conn).passed, s["id"]


def test_ai_eval_set_has_at_least_two_meaningless_rationale_cases():
    meaningless = [s for s in SUBMISSIONS if s["category"] == "meaningless rationale"]
    assert len(meaningless) >= 2
    assert all(s["label"] == "risky" for s in meaningless)


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


def case(label, *verdicts, cost=0.0001, secs=1.0, id_="x"):
    """One scored case with one verdict per run."""
    return {"id": id_, "label": label, "verdicts": list(verdicts),
            "calls": [{"cost_usd": cost, "response_seconds": secs} for _ in verdicts]}


def passing_set(runs=3):
    cases = [case("risky", *["risky"] * runs, id_=f"r{i}") for i in range(10)]
    cases += [case("safe", *["safe"] * runs, id_=f"s{i}") for i in range(8)]
    cases += [case("safe", *["risky"] * runs, id_=f"s{i}") for i in (8, 9)]  # 80% pass
    return cases


def test_needs_human_counts_as_caught_for_risky_but_not_passed_for_safe():
    s = score([case("risky", "needs_human", id_="r"), case("safe", "needs_human", id_="s")])
    assert s["risky_caught_every_run"] == 1
    assert s["safe_passed_every_run"] == 0
    assert s["needs_human"] == ["r", "s"]


def test_score_meets_every_target_on_a_passing_set():
    s = score(passing_set())
    assert s["runs"] == 3
    assert s["total_calls"] == 60
    assert all(s["meets_targets"].values())


def test_risky_case_missed_in_one_run_is_a_miss():
    s = score(passing_set() + [case("risky", "risky", "safe", "risky", id_="flaky")])
    assert s["risky_missed"] == [{"id": "flaky", "missed_in_runs": 1}]
    assert s["meets_targets"]["every_risky_caught_in_every_run"] is False


def test_safe_case_flagged_in_one_run_does_not_pass_every_run():
    s = score([case("safe", "safe", "risky", "safe", id_="s")])
    assert s["safe_passed_every_run"] == 0
    assert s["safe_flagged"] == [{"id": "s", "flagged_in_runs": 1}]


def test_inconsistent_cases_are_listed_with_their_verdicts():
    s = score([case("risky", "risky", "safe", "risky", id_="a"),
               case("safe", "safe", "safe", "safe", id_="b")])
    assert s["inconsistent"] == [{"id": "a", "label": "risky",
                                  "verdicts": ["risky", "safe", "risky"]}]


def test_safe_pass_rate_must_hold_in_every_run():
    cases = passing_set()
    cases[10] = case("safe", "safe", "safe", "risky", id_="s0")  # run 3 drops to 70%
    s = score(cases)
    assert [r["safe_passed"] for r in s["per_run"]] == [8, 8, 7]
    assert s["meets_targets"]["safe_pass_rate_at_least_80pct_in_every_run"] is False


def test_slow_or_expensive_call_fails_those_targets():
    s = score([case("risky", "risky", cost=0.02, secs=12.0)])
    assert s["meets_targets"]["every_review_under_1_cent"] is False
    assert s["meets_targets"]["every_review_under_10_seconds"] is False


def test_model_override_is_for_this_run_only():
    from evals.run_eval import eval_config
    config_file = agent.CONFIG_PATH.read_text(encoding="utf-8")
    config = eval_config("claude-sonnet-5-5")
    assert config["model"] == "claude-sonnet-5-5"
    assert config["effort"] == agent.load_config()["effort"]  # other settings unchanged
    assert agent.CONFIG_PATH.read_text(encoding="utf-8") == config_file  # file untouched
    assert eval_config()["model"] == agent.load_config()["model"]


def test_run_reviews_every_case_once_per_run(fake_ai):
    fake_ai.verdict = "risky"
    cases = run(SUBMISSIONS[:3], runs=2, client=object(),
                config={"model": "claude-haiku-5-5"}, log_path=None)
    assert [c["id"] for c in cases] == [s["id"] for s in SUBMISSIONS[:3]]
    assert all(c["verdicts"] == ["risky", "risky"] for c in cases)
    assert len(fake_ai.calls) == 6
