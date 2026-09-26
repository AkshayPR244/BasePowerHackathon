import ast
from pathlib import Path

APP = Path(__file__).resolve().parents[2] / "app"


def _imports(pkg: str) -> set[str]:
    found = set()
    for f in (APP / pkg).rglob("*.py"):
        for node in ast.walk(ast.parse(f.read_text("utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.module:
                found.add(node.module)
            elif isinstance(node, ast.Import):
                found.update(a.name for a in node.names)
    return found


def test_validator_is_independent_of_planning():
    bad = {m for m in _imports("validate") if m.startswith(("app.planning", "app.baselines"))}
    assert not bad, f"validator must not import planning code: {bad}"


def test_contracts_import_nothing_from_lanes():
    lanes = ("app.data", "app.valuation", "app.validate", "app.planning", "app.api")
    bad = {m for m in _imports("contracts") if m.startswith(lanes)}
    assert not bad, bad
