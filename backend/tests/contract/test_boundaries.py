import ast
from importlib.util import resolve_name
from pathlib import Path

APP = Path(__file__).resolve().parents[2] / "app"


def _module_imports(source: str, package: str) -> set[str]:
    found = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom):
            name = "." * node.level + (node.module or "")
            module = resolve_name(name, package) if node.level else name
            found.add(module)
            found.update(f"{module}.{a.name}" for a in node.names)
        elif isinstance(node, ast.Import):
            found.update(a.name for a in node.names)
    return found


def _imports(pkg: str) -> set[str]:
    found = set()
    for f in (APP / pkg).rglob("*.py"):
        package = "app." + ".".join(f.relative_to(APP).parts[:-1])
        found.update(_module_imports(f.read_text("utf-8"), package))
    return found


def test_validator_is_independent_of_planning():
    bad = {m for m in _imports("validate") if m.startswith(("app.planning", "app.baselines"))}
    assert not bad, f"validator must not import planning code: {bad}"


def test_contracts_import_nothing_from_lanes():
    lanes = (
        "app.data",
        "app.valuation",
        "app.validate",
        "app.planning",
        "app.api",
        "app.baselines",
        "app.compare",
    )
    bad = {m for m in _imports("contracts") if m.startswith(lanes)}
    assert not bad, bad


def test_relative_and_from_imports_cannot_bypass_boundaries():
    imports = _module_imports(
        "from .. import planning\nfrom app import baselines\nfrom ..planning.core import solve",
        "app.validate",
    )
    assert {"app.planning", "app.baselines", "app.planning.core"} <= imports
