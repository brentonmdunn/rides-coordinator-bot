"""Enforce the import boundary between shared/ and bot packages.

Pure AST walk, no runtime imports of the packages under test — this must stay
cheap and dependency-free so it can run before anything else does.
"""

import ast
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]

# PR 1 replaces this with `bot_package_names()` from `shared.core.bots`.
BOT_PACKAGES = {"ridebot"}


def _collect_top_level_imports(source: str) -> set[tuple[str, int]]:
    """Return (top_level_module, lineno) for every absolute import in source."""
    tree = ast.parse(source)
    found: set[tuple[str, int]] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top_level = alias.name.split(".")[0]
                found.add((top_level, node.lineno))
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                # Relative import (e.g. `from . import foo`) — ignore.
                continue
            if node.module is None:
                continue
            top_level = node.module.split(".")[0]
            found.add((top_level, node.lineno))

    return found


def find_violations(package_dir: Path, forbidden: set[str]) -> list[str]:
    """
    Find imports of forbidden top-level packages under package_dir.

    Args:
        package_dir: Root directory of the package to scan.
        forbidden: Set of top-level module names that must not be imported.

    Returns:
        A list of "path:lineno imports X" strings, one per violation.
    """
    violations: list[str] = []

    for path in sorted(package_dir.rglob("*.py")):
        source = path.read_text()
        for top_level, lineno in sorted(_collect_top_level_imports(source)):
            if top_level in forbidden:
                violations.append(f"{path}:{lineno} imports {top_level}")

    return violations


# ---------------------------------------------------------------------------
# Real-tree assertions
# ---------------------------------------------------------------------------


def test_shared_does_not_import_bot_packages():
    shared_dir = BACKEND_ROOT / "shared"
    violations = find_violations(shared_dir, BOT_PACKAGES)
    assert violations == []


def test_bot_packages_do_not_import_each_other_or_api():
    for package_name in BOT_PACKAGES:
        package_dir = BACKEND_ROOT / package_name
        other_bot_packages = BOT_PACKAGES - {package_name}
        forbidden = other_bot_packages | {"api"}
        violations = find_violations(package_dir, forbidden)
        assert violations == [], f"{package_name} boundary violations: {violations}"


# ---------------------------------------------------------------------------
# Unit tests for find_violations itself, against a synthetic package
# ---------------------------------------------------------------------------


def test_find_violations_detects_top_level_import(tmp_path: Path):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "mod.py").write_text("import forbidden\n")

    violations = find_violations(pkg, {"forbidden"})

    assert len(violations) == 1
    assert "mod.py:1 imports forbidden" in violations[0]


def test_find_violations_detects_nested_import(tmp_path: Path):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "mod.py").write_text("def foo():\n    import forbidden\n    return forbidden\n")

    violations = find_violations(pkg, {"forbidden"})

    assert len(violations) == 1
    assert "mod.py:2 imports forbidden" in violations[0]


def test_find_violations_detects_from_import(tmp_path: Path):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "mod.py").write_text("from forbidden.submodule import thing\n")

    violations = find_violations(pkg, {"forbidden"})

    assert len(violations) == 1
    assert "mod.py:1 imports forbidden" in violations[0]


def test_find_violations_ignores_relative_imports(tmp_path: Path):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text("from . import sibling\nfrom .. import other\n")

    violations = find_violations(pkg, {"pkg", "sibling", "other"})

    assert violations == []


def test_find_violations_ignores_strings(tmp_path: Path):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "mod.py").write_text('target = "forbidden.submodule.thing"\n')

    violations = find_violations(pkg, {"forbidden"})

    assert violations == []


def test_find_violations_allows_non_forbidden_imports(tmp_path: Path):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "mod.py").write_text("import allowed\nfrom allowed.submodule import thing\n")

    violations = find_violations(pkg, {"forbidden"})

    assert violations == []
