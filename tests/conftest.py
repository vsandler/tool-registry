import pytest

from registry.db import connect
from registry.personas import seed_personas


@pytest.fixture
def conn():
    """A fresh in-memory database with the five personas, for each test."""
    c = connect(":memory:")
    seed_personas(c)
    yield c
    c.close()
