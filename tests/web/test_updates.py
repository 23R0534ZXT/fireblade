"""The update check: it compares versions, it caches, and it never says "up to date"
when it could not ask."""

from fireblade.web import updates


def test_a_later_version_wins():
    assert updates.version_tuple("0.9.0") > updates.version_tuple("0.8.1")
    assert updates.version_tuple("0.10.0") > updates.version_tuple("0.9.9")
    assert updates.version_tuple("v0.8.1") == updates.version_tuple("0.8.1")
    assert updates.version_tuple("") == (0,)
    assert updates.version_tuple("nightly") == (0,)


def test_the_release_payload_is_reduced_to_what_a_banner_needs():
    release = updates.parse(
        {
            "tag_name": "v0.9.0",
            "html_url": "https://example/rel",
            "name": "Fireblade 0.9.0 — x",
            "published_at": "2026-12-01T00:00:00Z",
        }
    )
    assert release["version"] == "0.9.0"
    assert release["url"] == "https://example/rel"
    assert release["name"].startswith("Fireblade 0.9.0")


def test_the_answer_is_cached_and_a_failure_keeps_the_last_good_one():
    calls = []

    def fetch():
        calls.append("ok")
        return {"tag_name": "v0.9.0"}

    clock = [1000.0]
    checker = updates.Checker("0.8.1", "case", fetch=fetch, now=lambda: clock[0])
    first = checker.info()
    assert first["available"] is True and len(calls) == 1
    checker.info()
    assert len(calls) == 1, "the registry is not asked twice in six hours"

    clock[0] += updates.TTL + 1

    def broken():
        calls.append("ko")
        raise ValueError("no network")

    checker.fetch = broken
    answer = checker.info()
    assert answer["available"] is True, "a failed check keeps the last good answer"
    assert answer["error"] == "no network", "and says why, so nobody reads it as up to date"


def test_same_version_is_not_an_update():
    checker = updates.Checker("0.9.0", "host", fetch=lambda: {"tag_name": "v0.9.0"})
    assert checker.info()["available"] is False


def test_the_command_names_the_editions_own_image():
    driver = updates.command("driver", "0.9.0")
    assert driver[0] == "docker pull ghcr.io/23r0534zxt/fireblade-driver:0.9.0"
    assert any("fireblade:0.9.0" in line for line in driver)
    case = updates.command("case", "0.9.0")
    assert case == ["docker pull ghcr.io/23r0534zxt/fireblade:0.9.0"]
    assert "driver" in updates.guidance("case")


def test_the_host_update_is_one_line_a_shell_can_run():
    host = updates.command("host", "0.8.8")
    assert len(host) == 1
    line = host[0]
    image = "ghcr.io/23r0534zxt/fireblade:0.8.8"
    assert line.startswith(f"docker pull {image} && docker rm -f fireblade && docker run -d ")
    assert f"{image} && echo" in line and "-p 127.0.0.1:8080:8080" in line
    assert "README" in updates.guidance("host")


def test_the_check_can_be_switched_off_and_then_asks_nobody(monkeypatch):
    monkeypatch.setenv("FIREBLADE_UPDATE_CHECK", "off")
    asked = []
    checker = updates.Checker(
        "0.8.1", "host", fetch=lambda: asked.append(1) or {"tag_name": "v9.0.0"}
    )
    answer = checker.info()
    assert answer["disabled"] is True and answer["available"] is False and answer["command"] == []
    assert asked == [], "no request leaves the machine"
