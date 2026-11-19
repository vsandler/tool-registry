"""The app's own wording uses US spelling: "Personalize", not "Personalise" (DECISIONS.md #23).

Two places are exempt on purpose, because changing them changes what the AI sees:
- the AI's instructions (`SYSTEM_PROMPT` in registry/agent.py): a change would make the
  sample advice stale and the eval results no longer apply;
- the seeded tools in registry/seed.py: their content is fingerprinted by the sample advice.
The eval cases (evals/) and sample advice (registry/sample_advice.json) aren't checked here.
"""

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"
REGISTRY_DIR = ROOT / "registry"

# British spellings to keep out, by word family. An explicit list, not a general "-ise"
# rule, so words that are the same in US English (advise, otherwise, promise, exercise)
# never trip it.
BRITISH = re.compile(
    r"\b(?:"
    r"personalis\w*|summaris\w*|recognis\w*|organis\w*|prioritis\w*|customis\w*|"
    r"optimis\w*|minimis\w*|maximis\w*|authoris\w*|categoris\w*|standardis\w*|"
    r"finalis\w*|realis\w*|utilis\w*|apologis\w*|criticis\w*|emphasis(?:e|es|ed|ing)|"
    r"analys(?:e|es|ed|ing)|"
    r"catalogue\w*|colour\w*|behaviour\w*|favour\w*|honour\w*|labour\w*|neighbour\w*|"
    r"labell\w*|cancell(?:ed|ing)|travell\w*|modell\w*|"
    r"centre\w*|centred|judgement\w*|defence\w*|offence\w*|licence\w*|programme\w*|"
    r"grey\w*|whilst|amongst|enrol|enrolment|fulfil|fulfilment|learnt|spelt"
    r")\b",
    re.I,
)

# Assignments whose text the AI sees, so they keep their wording (see the docstring).
EXEMPT = {"agent.py": {"SYSTEM_PROMPT"},
          "seed.py": {"SAFE_TOOLS", "FAILING_TOOL", "DEMO_DRAFTS"}}


def _back_end_text(path: Path) -> list[str]:
    """Every piece of text in a back-end module (messages, labels, hints, docstrings),
    leaving out the exempt assignments."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    skip = EXEMPT.get(path.name, set())
    texts = []

    def walk(node):
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id in skip for t in node.targets):
            return
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            texts.append(node.value)
        for child in ast.iter_child_nodes(node):
            walk(child)

    walk(tree)
    return texts


@pytest.mark.parametrize("british", ["Personalise", "personalised", "Summarise", "colour",
                                     "catalogue", "labelled", "recognise", "centred", "grey",
                                     "judgement", "behaviour", "defence", "analyse"])
def test_the_list_catches_british_spellings(british):
    assert BRITISH.search(f"Please {british} it.")


@pytest.mark.parametrize("fine", ["Personalize", "personalized", "summarize", "color",
                                  "Catalog", "labeled", "recognize", "centered", "gray",
                                  "judgment", "behavior", "defense", "analyze", "advise",
                                  "otherwise", "promise", "exercise", "analysis", "emphasis",
                                  "precise", "rise"])
def test_the_list_leaves_us_and_shared_spellings_alone(fine):
    assert not BRITISH.search(f"Please {fine} it.")


def test_screens_use_us_spelling():
    """Every page, script and stylesheet, comments included."""
    for path in sorted(WEB_DIR.iterdir()):
        if path.suffix in (".html", ".js", ".css"):
            found = BRITISH.findall(path.read_text(encoding="utf-8"))
            assert not found, f"web/{path.name} says {found}: use US spelling"


@pytest.mark.parametrize("path", sorted(REGISTRY_DIR.glob("*.py")), ids=lambda p: p.name)
def test_back_end_messages_use_us_spelling(path):
    found = [w for text in _back_end_text(path) for w in BRITISH.findall(text)]
    assert not found, f"registry/{path.name} says {found}: use US spelling"


def test_the_exempt_text_is_still_there():
    """The exemptions name real assignments, so a rename can't quietly widen them."""
    for name, targets in EXEMPT.items():
        tree = ast.parse((REGISTRY_DIR / name).read_text(encoding="utf-8"))
        assigned = {t.id for node in ast.walk(tree) if isinstance(node, ast.Assign)
                    for t in node.targets if isinstance(t, ast.Name)}
        assert targets <= assigned, (name, targets - assigned)
