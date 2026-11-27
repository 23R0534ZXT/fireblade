"""The driver: one container per case, and nothing that outlives the case.

Docker is a fake binary here (``_fake_docker.py``): what this file checks is the
driver's own decisions — when a container is created, what it mounts, what the ceiling
does, what a destruction removes — and none of them needs a daemon.
"""

import json
import sys
from pathlib import Path

import pytest

from fireblade.core.investigations import InvestigationLibrary
from fireblade.web import agency

FAKE = Path(__file__).with_name("_fake_docker.py")


@pytest.fixture()
def driver(tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_DOCKER_STATE", str(tmp_path / "docker.json"))
    # No daemon to answer /health: the wait is the one part the fake cannot provide.
    monkeypatch.setattr(agency.CaseContainer, "wait_healthy", lambda self, timeout=25.0: None)
    return agency.Agency(
        tmp_path / "volumes",
        tmp_path / "certificates",
        docker=agency.Docker([sys.executable, str(FAKE)]),
        max_open=2,
    )


def calls(tmp_path) -> list:
    path = tmp_path / "docker.json"
    return json.loads(path.read_text(encoding="utf-8"))["calls"] if path.exists() else []


def test_a_case_gets_its_own_volume_with_the_desktop_layout(driver):
    identifier = driver.create("Driver case")["id"]
    volume = driver.volumes.folder(identifier)
    assert (volume / identifier / "case.json").is_file()
    assert (volume / "exports").is_dir() and (volume / "archives").is_dir()
    # The desktop reads the case back where it was written, nothing translated.
    assert InvestigationLibrary(volume).read(identifier)["name"] == "Driver case"
    # The staging folder that made the volume took the case's name and left nothing else.
    assert [item.name for item in driver.volumes.root.iterdir()] == [identifier]


def test_opening_a_case_creates_one_container_over_that_volume(driver, tmp_path):
    identifier = driver.create("One case")["id"]
    case = driver.open(identifier)
    assert case.name == f"fireblade-case-{identifier[:8]}"
    assert case.running()
    launched = [call for call in calls(tmp_path) if call[0] == "run"]
    assert len(launched) == 1
    arguments = launched[0]
    assert f"{driver.volumes.folder(identifier)}:/data/library" in arguments
    assert f"fireblade.case={identifier}" in arguments
    assert "fireblade.role=case" in arguments
    assert arguments[-1] == "/opt/fireblade/tools"
    assert "--root" in arguments and "/data/library" in arguments
    # Opening it again is not a second container.
    driver.open(identifier)
    assert len([call for call in calls(tmp_path) if call[0] == "run"]) == 1


def test_the_ceiling_stops_the_oldest_case_container(driver):
    first, second, third = (driver.create(name)["id"] for name in ("First", "Second", "Third"))
    driver.open(first)
    driver.open(second)
    driver.open(third)
    assert driver.container(third).running()
    assert driver.container(second).running()
    assert not driver.container(first).running(), "max_open is a ceiling on running containers"
    assert driver.container(first).exists(), "stopping is not destroying"


@pytest.mark.parametrize("method", ["dod3", "quick"])
def test_destroying_a_case_removes_its_container_volume_and_residue(driver, method):
    kept = driver.create("Kept case")["id"]
    gone = driver.create("Gone case")["id"]
    driver.open(kept)
    driver.open(gone)
    prefix = gone[:8]
    package = driver.volumes.folder(gone) / "exports" / f"{prefix}.fireblade"
    package.write_bytes(b"portable package")
    archive = driver.volumes.folder(gone) / "archives" / f"{prefix}.zip"
    archive.write_bytes(b"archive")

    result = driver.destroy(gone, {"confirmation": "Gone case", "method": method})

    assert not driver.container(gone).exists()
    assert not driver.volumes.folder(gone).exists()
    assert not package.exists() and not archive.exists()
    certificate = Path(result["certificate"])
    assert certificate.is_file() and certificate.parent == driver.certificates
    assert result["outside"] == 2
    assert result["deleted_files"] == result["files"]
    assert result["verified_files"] == (0 if method == "quick" else result["files"])
    # The other case is untouched, container included.
    assert driver.volumes.has(kept)
    assert driver.container(kept).running()


def test_a_wrong_confirmation_destroys_nothing(driver):
    identifier = driver.create("Careful")["id"]
    driver.open(identifier)
    with pytest.raises(ValueError):
        driver.destroy(identifier, {"confirmation": "careful"})
    assert driver.container(identifier).running()
    assert driver.volumes.has(identifier)


def test_reconcile_removes_a_container_whose_case_is_gone(driver):
    identifier = driver.create("Orphan")["id"]
    driver.open(identifier)
    driver.volumes.remove(identifier)
    assert driver.container(identifier).exists()
    assert driver.reconcile() == [identifier]
    assert not driver.container(identifier).exists()


def test_a_folder_that_is_not_a_case_is_reported_not_deleted(driver):
    stranger = driver.volumes.root / "notes-from-the-analyst"
    stranger.mkdir(parents=True)
    (stranger / "todo.txt").write_text("keep me", encoding="utf-8")
    catalogue = driver.cases()
    assert catalogue["cases"] == []
    assert any("notes-from-the-analyst" in item for item in catalogue["errors"])
    assert (stranger / "todo.txt").is_file()


def test_the_driver_page_lists_the_cases_and_their_prefix(driver):
    identifier = driver.create("Shown case")["id"]
    markup = agency.page(driver.cases(), version="0.7.9")
    assert "Shown case" in markup
    assert f"/case/{identifier}/" in markup
    assert f"/destroy/{identifier}" in markup
    assert "0.7.9" in markup
    # The page wears the client's own stylesheet: no second palette for the driver.
    assert 'href="/static/app.css"' in markup


def test_the_container_mounts_the_folder_as_the_daemon_sees_it(tmp_path, monkeypatch):
    """In a container the driver reads /data/volumes; docker needs the host's own path."""
    monkeypatch.setenv("FAKE_DOCKER_STATE", str(tmp_path / "docker.json"))
    monkeypatch.setattr(agency.CaseContainer, "wait_healthy", lambda self, timeout=25.0: None)
    driver = agency.Agency(
        tmp_path / "volumes",
        tmp_path / "certificates",
        docker=agency.Docker([sys.executable, str(FAKE)]),
        host_volumes="/srv/fireblade/volumes",
    )
    identifier = driver.create("Mounted case")["id"]
    driver.open(identifier)
    launched = next(call for call in calls(tmp_path) if call[0] == "run")
    expected = f"{Path('/srv/fireblade/volumes') / identifier}:/data/library"
    assert expected in launched, launched
    assert driver.volumes.folder(identifier).is_dir()


def test_a_new_volume_is_handed_to_the_case_containers_user(driver, monkeypatch):
    """The case image runs unprivileged: a volume owned by root would be unreadable."""
    seen = []
    monkeypatch.setattr(
        agency, "_chown_tree", lambda path, uid, gid: seen.append((Path(path).name, uid, gid))
    )
    identifier = driver.create("Owned case")["id"]
    assert seen == [(identifier, 10001, 10001)]


def test_the_client_erase_button_reaches_the_driver_through_the_prefix(driver, tmp_path):
    """The case cannot destroy its own container: the driver answers the prefixed call."""
    from fastapi.testclient import TestClient

    app = agency.create_app(tmp_path / "volumes", tmp_path / "certificates", agency=driver)
    identifier = driver.create("Prefixed case")["id"]
    driver.open(identifier)
    with TestClient(app) as client:
        response = client.post(
            f"/case/{identifier}/api/cases/{identifier}/destroy",
            json={"confirmation": "Prefixed case", "method": "dod3"},
        )
    assert response.status_code == 200, response.text
    body = response.json()
    assert Path(body["certificate"]).is_file()
    assert not driver.volumes.has(identifier)
    assert not driver.container(identifier).exists()


def test_the_driver_page_erases_a_case_through_its_form(driver, tmp_path):
    """The page posts a form, not JSON: both verbs have to reach the same destruction."""
    from fastapi.testclient import TestClient

    app = agency.create_app(tmp_path / "volumes", tmp_path / "certificates", agency=driver)
    identifier = driver.create("Form case")["id"]
    with TestClient(app) as client:
        response = client.post(
            f"/destroy/{identifier}",
            data={"confirmation": "Form case", "method": "dod3"},
            follow_redirects=False,
        )
    assert response.status_code == 303, response.text
    assert not driver.volumes.has(identifier)
    assert any(path.suffix == ".html" for path in driver.certificates.iterdir())


def test_an_upgrade_rebuilds_the_case_container_and_keeps_its_volume(driver, tmp_path):
    """The image moves; the case container must follow, the case itself must not move."""
    identifier = driver.create("Upgraded case")["id"]
    driver.open(identifier)
    before = driver.container(identifier).current_image_id()
    assert before, "the fake records the image it was built from"
    driver.image = "ghcr.io/23r0534zxt/kagarasu:0.9.0"
    driver.open(identifier)
    after = driver.container(identifier).current_image_id()
    assert after and after != before
    assert len([call for call in calls(tmp_path) if call[0] == "run"]) == 2
    assert driver.volumes.has(identifier)


def test_reconcile_drops_a_case_container_built_from_another_image(driver):
    """At start-up the stale containers go; a case nobody opens is still up to date."""
    identifier = driver.create("Stale case")["id"]
    driver.open(identifier)
    driver.image = "ghcr.io/23r0534zxt/kagarasu:0.9.0"
    assert driver.reconcile() == [identifier]
    assert not driver.container(identifier).exists()
    assert driver.volumes.has(identifier), "an upgrade never touches the case itself"
