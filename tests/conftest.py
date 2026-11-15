import pytest

from registry import agent
from registry.db import connect
from registry.personas import seed_personas


@pytest.fixture
def conn():
    """A fresh in-memory database with the five personas, for each test."""
    c = connect(":memory:")
    seed_personas(c)
    yield c
    c.close()


class FakeAI:
    """Stands in for the real AI pre-review in every test, so no test calls the API.

    Set `.verdict` to "risky", "safe" or "needs_human", or `.error` to make it raise.
    `.calls` records the tools it was asked to review.
    """

    def __init__(self):
        self.verdict = "safe"
        self.error = None
        self.calls = []

    def __call__(self, tool, **kwargs):
        self.calls.append(tool)
        if self.error:
            raise self.error
        issues = [] if self.verdict == "safe" else ["Fake issue for testing."]
        return agent.ReviewResult(verdict=self.verdict, issues=issues,
                                  reason="Fake AI review.", model="fake-model")


@pytest.fixture(autouse=True)
def fake_ai(monkeypatch):
    fake = FakeAI()
    monkeypatch.setattr(agent, "review_tool", fake)
    return fake
