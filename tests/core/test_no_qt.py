"""fireblade.core must import without Qt: the container has no display and no Qt.

The desktop keeps its window; the container runs the same core. A Qt import at
module level in core/ breaks that promise silently on a machine where PySide6 is
installed, and loudly in the image. This test makes the rule executable.
"""

import ast
import pathlib
import subprocess
import sys
import textwrap

ROOT = pathlib.Path(__file__).resolve().parents[2]
CORE = ROOT / "src" / "fireblade" / "core"


def _forbidden(name: str) -> bool:
    return name == "PySide6" or name.startswith("PySide6.") or name.startswith("fireblade.ui")


class _ModuleLevelImports(ast.NodeVisitor):
    """Imports that really run when the module is imported — function bodies excluded."""

    def __init__(self):
        self.found = []

    def visit_FunctionDef(self, node):
        return

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Lambda(self, node):
        return

    def visit_Import(self, node):
        for alias in node.names:
            if _forbidden(alias.name):
                self.found.append((node.lineno, alias.name))

    def visit_ImportFrom(self, node):
        if node.module and _forbidden(node.module):
            self.found.append((node.lineno, node.module))


def test_core_never_imports_qt_at_module_level():
    offenders = []
    for path in sorted(CORE.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        visitor = _ModuleLevelImports()
        visitor.visit(tree)
        for line, name in visitor.found:
            offenders.append(f"{path.relative_to(ROOT)}:{line}: {name}")
    assert not offenders, "Qt import at module level in fireblade.core:\n" + "\n".join(offenders)


def test_core_package_imports_with_qt_blocked(tmp_path):
    """Import every core module in a process where PySide6 cannot be imported."""
    script = textwrap.dedent(
        """
        import importlib
        import pkgutil
        import sys

        class NoQt:
            def find_spec(self, name, path=None, target=None):
                if name == 'PySide6' or name.startswith('PySide6.'):
                    raise ImportError('Qt is not available in this environment')
                return None

        sys.meta_path.insert(0, NoQt())
        import fireblade.core as core
        loaded = []
        for module in pkgutil.walk_packages(core.__path__, 'fireblade.core.'):
            importlib.import_module(module.name)
            loaded.append(module.name)
        print(len(loaded))
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(ROOT / "src"), "PATH": ""},
    )
    assert result.returncode == 0, result.stderr
    assert int(result.stdout.strip() or 0) > 50
