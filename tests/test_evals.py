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


# --- unwanted issues and --case (false "practice is null" flag, 2026-11-17) -------------

def case_with_issues(label, *issue_lists, words=None, id_="x"):
    """One scored case whose runs listed these issues."""
    c = {"id": id_, "label": label,
         "verdicts": ["risky" if issues else "safe" for issues in issue_lists],
         "calls": [{"run": i + 1, "cost_usd": 0.0001, "response_seconds": 1.0, "issues": issues}
                   for i, issues in enumerate(issue_lists)]}
    if words is not None:
        c["must_not_mention"] = words
    return c


def test_unwanted_issues_are_reported_with_their_runs():
    s = score([case_with_issues(
        "risky",
        ["Rationale is filler", "Practice field is null"],
        ["Rationale is filler"],
        ["The PRACTICE is missing"],
        words=["practice"], id_="weak")])
    assert s["unwanted_issues"] == [{
        "id": "weak", "words": ["practice"], "in_runs": [1, 3],
        "issues": ["Practice field is null", "The PRACTICE is missing"]}]


def test_unwanted_issues_do_not_change_the_score():
    """They're reported separately: the verdict is still right, so the score and the
    targets are unchanged."""
    clean = passing_set()
    with_unwanted = passing_set() + [case_with_issues(
        "risky", ["Practice is null"], ["Practice is null"], ["Practice is null"],
        words=["practice"], id_="weak")]
    s = score(with_unwanted)
    assert s["risky_caught_every_run"] == score(clean)["risky_caught_every_run"] + 1
    assert s["meets_targets"] == score(clean)["meets_targets"]
    assert len(s["unwanted_issues"]) == 1


def test_cases_without_forbidden_words_never_report_unwanted_issues():
    s = score([case_with_issues("risky", ["Practice field is null"], id_="no-words"),
               case_with_issues("risky", ["Rationale is filler"], words=["practice"], id_="ok")])
    assert s["unwanted_issues"] == []


def test_run_passes_forbidden_words_through(fake_ai):
    fake_ai.verdict = "risky"   # the fake lists "Fake issue for testing."
    subs = [dict(SUBMISSIONS[0], id="w", must_not_mention=["fake issue"])]
    cases = run(subs, runs=2, client=object(), config={"model": "claude-haiku-5-5"},
                log_path=None)
    assert cases[0]["must_not_mention"] == ["fake issue"]
    assert score(cases)["unwanted_issues"] == [{
        "id": "w", "words": ["fake issue"], "in_runs": [1, 2],
        "issues": ["Fake issue for testing.", "Fake issue for testing."]}]


def test_select_cases_keeps_the_eval_sets_order():
    from evals.run_eval import select_cases
    ids = [SUBMISSIONS[2]["id"], SUBMISSIONS[0]["id"]]
    assert [s["id"] for s in select_cases(SUBMISSIONS, ids)] == [
        SUBMISSIONS[0]["id"], SUBMISSIONS[2]["id"]]
    assert select_cases(SUBMISSIONS, None) == SUBMISSIONS


def test_select_cases_refuses_an_unknown_id():
    import pytest
    from evals.run_eval import select_cases
    with pytest.raises(ValueError, match="no-such-case"):
        select_cases(SUBMISSIONS, ["no-such-case"])


def test_case_option_runs_only_the_named_cases(fake_ai, monkeypatch, tmp_path):
    from evals import run_eval
    monkeypatch.setattr(run_eval, "RESULTS_DIR", tmp_path)
    monkeypatch.setattr(run_eval.agent, "make_client", lambda: object())
    monkeypatch.setattr(run_eval, "LOG_PATH", None)
    first, third = SUBMISSIONS[0]["id"], SUBMISSIONS[2]["id"]
    assert run_eval.main(["--runs", "1", "--case", first, "--case", third]) == 0
    assert len(fake_ai.calls) == 2
    saved = json.loads(next(tmp_path.glob("*.json")).read_text(encoding="utf-8"))
    assert [c["id"] for c in saved["cases"]] == [first, third]
    assert saved["selected_cases"] == [first, third]


def test_eval_set_has_the_firm_wide_no_practice_cases():
    """A firm-wide tool needs no practice: the AI shouldn't list a missing practice as
    an issue, whether the tool is otherwise safe or risky for another reason."""
    by_id = {s["id"]: s for s in SUBMISSIONS}
    safe = by_id["safe-17-firm-wide-no-practice"]
    risky = by_id["hard-risky-21-firm-wide-no-practice-weak-rationale"]
    assert safe["label"] == "safe" and risky["label"] == "risky"
    for s in (safe, risky):
        assert s["tool"]["visibility"] == "firm-wide" and s["tool"]["practice"] is None
        assert s["must_not_mention"] == ["practice"]


def test_forbidden_words_are_lists_of_text():
    for s in SUBMISSIONS:
        words = s.get("must_not_mention", [])
        assert isinstance(words, list) and all(isinstance(w, str) and w for w in words), s["id"]


def test_file_option_runs_cases_from_another_file(fake_ai, monkeypatch, tmp_path):
    """--file runs a separate set (for example a probe that copies one real tool) without
    adding it to the scored eval set."""
    from evals import run_eval
    probe = tmp_path / "probe.json"
    probe.write_text(json.dumps([dict(SUBMISSIONS[0], id="probe-1")]), encoding="utf-8")
    out_dir = tmp_path / "results"
    monkeypatch.setattr(run_eval, "RESULTS_DIR", out_dir)
    monkeypatch.setattr(run_eval.agent, "make_client", lambda: object())
    monkeypatch.setattr(run_eval, "LOG_PATH", None)
    assert run_eval.main(["--runs", "2", "--file", str(probe)]) == 0
    assert len(fake_ai.calls) == 2
    saved = json.loads(next(out_dir.glob("*.json")).read_text(encoding="utf-8"))
    assert [c["id"] for c in saved["cases"]] == ["probe-1"]
    # The probe is outside the project, so only its file name is saved, never a full
    # path from this computer.
    assert saved["file"] == "probe.json"


def test_saved_result_names_the_default_cases_file_relative_to_the_project(
        fake_ai, monkeypatch, tmp_path):
    """With no --file, the saved result says "evals/submissions.json", not a full path
    that would include someone's home folder."""
    from evals import run_eval
    monkeypatch.setattr(run_eval, "RESULTS_DIR", tmp_path)
    monkeypatch.setattr(run_eval.agent, "make_client", lambda: object())
    monkeypatch.setattr(run_eval, "LOG_PATH", None)
    assert run_eval.main(["--runs", "1", "--case", SUBMISSIONS[0]["id"]]) == 0
    saved = json.loads(next(tmp_path.glob("*.json")).read_text(encoding="utf-8"))
    assert saved["file"] == "evals/submissions.json"


def test_recorded_path_is_never_absolute(tmp_path):
    from pathlib import Path
    from evals.run_eval import EVAL_DIR, recorded_path
    inside = recorded_path(EVAL_DIR / "probe_practice.json")
    outside = recorded_path(tmp_path / "elsewhere" / "cases.json")
    assert inside == "evals/probe_practice.json"
    assert outside == "cases.json"
    for shown in (inside, outside):
        assert not Path(shown).is_absolute()
        assert str(Path.home()) not in shown and Path.home().name not in shown


def test_practice_probe_copies_the_real_tool():
    """evals/probe_practice.json: an exact copy of the tool whose real review wrongly
    listed "Practice field is null" (2026-11-17). Not part of the scored eval set."""
    from evals.run_eval import EVAL_DIR
    probe = load_submissions(EVAL_DIR / "probe_practice.json")
    assert [p["id"] for p in probe] == ["probe-real-tool-name-na"]
    tool = probe[0]["tool"]
    assert tool["name"] == "Name" and tool["rationale"] == "N/A"
    assert tool["visibility"] == "firm-wide" and tool["practice"] is None
    assert probe[0]["must_not_mention"] == ["practice"]
    assert set(agent.SUBMISSION_FIELDS) <= set(tool)
