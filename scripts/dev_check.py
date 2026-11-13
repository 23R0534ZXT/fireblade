"""Every gate a change must pass, behind one command.

    python -m scripts.dev_check              # version, lint, smoke, full suite
    python -m scripts.dev_check --quick      # version, lint, smoke (no suite)
    python -m scripts.dev_check --platform offscreen

The suite runs on the platform the application targets: on Windows the offscreen
Qt plugin has no font database, so pixel and layout tests fail for reasons that
have nothing to do with the change.
"""
import argparse
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# La suite et le smoke écrivent leurs fichiers de test sans préciser d'encodage :
# sous Windows le défaut est la page de code locale (cp1252), et les caractères
# accentués sortent dans un autre encodage que celui que le code lit. La CI est en
# UTF-8, donc le forcer ici fait tourner la porte locale dans les mêmes conditions.
UTF8_ENV = {"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}


def run(command, env=None):
    print("$ " + " ".join(command), flush=True)
    result = subprocess.run(command, cwd=ROOT, env=env)
    if result.returncode:
        raise SystemExit(f"ECHEC : {' '.join(command)} (code {result.returncode})")


def check_version():
    """The tag, the package and the build must never disagree."""
    version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    match = re.search(r'__version__\s*=\s*"([^"]+)"',
                      (ROOT / "src/fireblade/__init__.py").read_text(encoding="utf-8"))
    if match is None:
        raise SystemExit("ECHEC : __version__ absent de src/fireblade/__init__.py")
    declared = match.group(1)
    if version != declared:
        raise SystemExit(f"ECHEC : pyproject {version} != paquet {declared}")
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise SystemExit(f"ECHEC : version non X.Y.Z : {version}")
    print(f"version {version} : pyproject et paquet d'accord")


def check_lint():
    run([sys.executable, "-m", "ruff", "check", "src", "scripts", "tests"])


def check_smoke():
    """A real window, not just an import: the menus, panels and docks are built."""
    code = (
        "from PySide6.QtWidgets import QApplication\n"
        "app = QApplication([])\n"
        "from fireblade.ui.app import Window\n"
        "window = Window(require_case=False)\n"
        "assert window.windowTitle() == 'Fireblade', window.windowTitle()\n"
        "assert len(window.menuBar().actions()) >= 5\n"
        "window.close()\n"
        "print('fenêtre principale construite')\n"
    )
    run([sys.executable, "-c", code],
        env=dict(os.environ, QT_QPA_PLATFORM="offscreen", **UTF8_ENV))


def purge_stale_pytest_tmp():
    """Supprime un dossier temporaire pytest dont l'orthographe a dérivé.

    pytest nomme son dossier temporaire d'après le nom d'utilisateur en minuscules.
    Windows ne distingue pas la casse : si un dossier du même nom mais écrit autrement
    existe déjà (ancien compte, ancienne version), pytest le réutilise sans corriger son
    orthographe. Or resolve() renvoie la casse réelle du disque : les chemins ne
    correspondent plus aux chaînes attendues et des dizaines de tests échouent sur une
    majuscule, avec des messages qui n'ont aucun rapport avec la cause.
    """
    import getpass
    import re
    import shutil
    import tempfile

    user = re.sub(r"[^A-Za-z0-9_.-]", "_", getpass.getuser()).lower()
    expected = f"pytest-of-{user}"
    for path in Path(tempfile.gettempdir()).glob("pytest-of-*"):
        if path.is_dir() and path.name != expected:
            print(f"dossier temporaire pytest obsolète supprimé : {path.name}", flush=True)
            shutil.rmtree(path, ignore_errors=True)


def check_tests(platform):
    purge_stale_pytest_tmp()
    print(f"suite complète, plateforme Qt = {platform}", flush=True)
    run([sys.executable, "-m", "pytest", "-q"],
        env=dict(os.environ, QT_QPA_PLATFORM=platform, **UTF8_ENV))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Vérifications avant commit")
    parser.add_argument("--quick", action="store_true", help="sans la suite de tests")
    parser.add_argument("--platform", default="windows", help="QT_QPA_PLATFORM pour la suite")
    options = parser.parse_args(argv)
    check_version()
    check_lint()
    check_smoke()
    if not options.quick:
        check_tests(options.platform)
    print("\nTOUT EST VERT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
