"""The investigation loop: the standard pass, then what the model asks for, then the answer."""

import json
import types

from fireblade.core import assistant as assistant_module
from fireblade.core.assistant_chat import Chat, answer_prompt, language_of, plan_prompt
from fireblade.core.assistant_history import History
from fireblade.core.case_tools import CaseTools

FINDINGS = (
    "- Suspicious Service Path, high, on FBVM, at 2026-11-17 10:02:52\n"
    "- AppX Located in Uncommon Directory, medium, on FBVM, at 2026-11-17 10:02:47\n"
    "- RDP Logon, informational, on FBVM, at 2026-11-17 10:02:44"
)


def _plan(tool="done", **kwargs):
    payload = dict(
        tool=tool,
        reason="",
        text="",
        host="",
        event_id="",
        artifact="",
        column="",
        time="",
        minutes=0,
        limit=0,
    )
    payload.update(kwargs)
    return json.dumps(payload)


def _ready(monkeypatch):
    monkeypatch.setattr(
        assistant_module.Assistant,
        "status",
        lambda self: types.SimpleNamespace(
            can_answer=True,
            enabled=True,
            state="ready",
            detail="ready",
            model="Qwen3-4B-Instruct-2507",
        ),
    )
    monkeypatch.setattr(
        assistant_module,
        "shared_server",
        lambda root, assistant=None: types.SimpleNamespace(port=1, stop=lambda: None),
    )


def _script(monkeypatch, answers):
    prompts = []

    def fake_ask(port, prompt, max_tokens=480, timeout=600, schema=None):
        prompts.append(prompt)
        if not answers:
            raise AssertionError("the model was asked more times than the test scripted")
        return dict(text=answers.pop(0), seconds=0.5, finish="stop")

    monkeypatch.setattr(assistant_module, "ask", fake_ask)
    return prompts


class Tools(CaseTools):
    """A case with three detections, and a record of what was asked of it."""

    def __init__(self):
        super().__init__(
            lambda sql, params: [],
            findings=lambda: [
                dict(
                    level="high",
                    title="Suspicious Service Path",
                    host="FBVM",
                    count=1,
                    start="2026-11-17 10:02:52",
                ),
                dict(
                    level="medium",
                    title="AppX Located in Uncommon Directory",
                    host="FBVM",
                    count=1,
                    start="2026-11-17 10:02:47",
                ),
                dict(
                    level="informational",
                    title="RDP Logon",
                    host="FBVM",
                    count=1,
                    start="2026-11-17 10:02:44",
                ),
            ],
        )
        self.asked = []

    def call(self, name, arguments):
        self.asked.append(name)
        if name == "overview":
            return "Case brief.", 1
        if name == "findings":
            return FINDINGS, 3
        if name == "around":
            return "[1] 10:02:52 FBVM 7045 updsvc C:\\Windows\\System32\\svchost.exe", 1
        if name == "sequence":
            return "in order: 10:02:44 logon, 10:02:47 appx, 10:02:52 service", 3
        if name == "entity":
            return "one row about " + arguments.get("text", ""), 1
        return "Nothing matches in this case.", 0


def test_the_standard_pass_reads_the_case_the_same_way_every_time(monkeypatch, tmp_path):
    _ready(monkeypatch)
    _script(monkeypatch, [_plan(), "Suspicious Service Path, high, 10:02:52 sur FBVM."])
    tools = Tools()

    turn = Chat(tmp_path, tools).ask("Que s est-il passe ?")

    assert [step.tool for step in turn.steps] == ["overview", "findings", "around", "sequence"]
    assert turn.steps[2].arguments["host"] == "FBVM"
    assert turn.steps[2].arguments["time"] == "2026-11-17 10:02:52"
    assert "Suspicious Service Path" in turn.text


def test_the_model_may_ask_for_one_more_lookup_after_it_has_seen_the_case(monkeypatch, tmp_path):
    _ready(monkeypatch)
    _script(
        monkeypatch,
        [
            _plan("entity", text="updsvc", reason="the service name appears once"),
            _plan("done"),
            "Suspicious Service Path, high : le service updsvc pointe vers un chemin systeme.",
        ],
    )
    tools = Tools()

    turn = Chat(tmp_path, tools).ask("Que fait updsvc ?")

    assert "entity" in [step.tool for step in turn.steps]
    assert tools.asked.count("entity") == 1
    assert turn.steps[[step.tool for step in turn.steps].index("entity")].reason.startswith(
        "the service name"
    )


def test_two_extra_lookups_is_the_ceiling(monkeypatch, tmp_path):
    _ready(monkeypatch)
    _script(
        monkeypatch,
        [
            _plan("entity", text="updsvc"),
            _plan("entity", text="FBVM"),
            _plan("entity", text="never asked"),
            "Suspicious Service Path, high, sur FBVM.",
        ],
    )
    tools = Tools()

    turn = Chat(tmp_path, tools).ask("Que s est-il passe ?")

    assert [step.tool for step in turn.steps].count("entity") == 2


def test_a_lookup_that_finds_nothing_stops_the_digging(monkeypatch, tmp_path):
    class Nothing(Tools):
        def call(self, name, arguments):
            if name == "entity":
                self.asked.append(name)
                return "Nothing matches in this case.", 0
            return super().call(name, arguments)

    _ready(monkeypatch)
    _script(monkeypatch, [_plan("entity", text="inconnu"), "Suspicious Service Path, high."])
    tools = Nothing()

    turn = Chat(tmp_path, tools).ask("Que s est-il passe ?")

    assert [step.tool for step in turn.steps][-1] == "entity"
    assert turn.text


def test_a_case_without_detections_is_still_answered(monkeypatch, tmp_path):
    class Empty(Tools):
        def call(self, name, arguments):
            if name == "findings":
                return "No detection matches.", 0
            return super().call(name, arguments)

    _ready(monkeypatch)
    _script(monkeypatch, [_plan(), "La case contient quinze lignes."])
    turn = Chat(tmp_path, Empty()).ask("Combien de lignes ?")

    assert [step.tool for step in turn.steps] == ["overview", "findings"]
    assert turn.text


def test_the_answer_is_written_in_the_language_of_the_question(monkeypatch, tmp_path):
    _ready(monkeypatch)
    _script(
        monkeypatch,
        [
            _plan(),
            "Nothing happened on this host at all, everything is calm and fine here.",
            "Suspicious Service Path, haut, sur FBVM a 10:02:52 : rien de calme.",
        ],
    )

    turn = Chat(tmp_path, Tools()).ask("Que s est-il passe sur cet hote ?")

    assert turn.text.startswith("Suspicious Service Path")


def test_an_answer_that_names_no_detection_is_asked_again(monkeypatch, tmp_path):
    _ready(monkeypatch)
    _script(
        monkeypatch,
        [
            _plan(),
            "Il y a des detections sur cet hote mais rien de grave.",
            "Suspicious Service Path, high, sur FBVM a 10:02:52.",
        ],
    )

    turn = Chat(tmp_path, Tools()).ask("Que s est-il passe sur cet hote ?")

    assert "Suspicious Service Path" in turn.text


def test_the_turn_is_written_into_the_case_history(monkeypatch, tmp_path):
    case = tmp_path / "case.duckdb"
    case.write_bytes(b"")
    _ready(monkeypatch)
    _script(
        monkeypatch,
        [
            _plan(),
            "Suspicious Service Path, high, sur FBVM a 10:02:52.",
            "Suspicious Service Path, high, sur FBVM a 10:02:52, encore.",
        ],
    )
    history = History(case)
    chat = Chat(tmp_path, Tools(), history=history)

    chat.ask("Que s est-il passe ?")

    saved = history.conversations()
    assert len(saved) == 1
    assert saved[0].question_count() == 1
    assert saved[0].messages[0].role == "user"
    assert "Suspicious Service Path" in saved[0].messages[1].text
    assert saved[0].messages[1].steps[0]["tool"] == "overview"


def test_a_second_chat_continues_the_conversation_that_is_on_disk(monkeypatch, tmp_path):
    case = tmp_path / "case.duckdb"
    case.write_bytes(b"")
    _ready(monkeypatch)
    _script(
        monkeypatch,
        [
            _plan(),
            "Suspicious Service Path, high, sur FBVM.",
            "Suspicious Service Path, high, sur FBVM, encore.",
        ],
    )
    history = History(case)
    Chat(tmp_path, Tools(), history=history).ask("Premiere question ?")

    prompts = _script(monkeypatch, [_plan(), "Suspicious Service Path, high, encore."])
    Chat(tmp_path, Tools(), history=history, conversation=history.latest()).ask("Et ensuite ?")

    assert "Premiere question ?" in prompts[0]
    assert "CONVERSATION SO FAR" in prompts[0]


def test_the_engine_being_off_is_not_a_lookup(monkeypatch, tmp_path):
    monkeypatch.setattr(
        assistant_module.Assistant,
        "status",
        lambda self: types.SimpleNamespace(
            can_answer=False,
            enabled=False,
            state="missing",
            detail="The local model is not installed.",
        ),
    )
    called = []
    monkeypatch.setattr(assistant_module, "ask", lambda *a, **k: called.append(a))

    turn = Chat(tmp_path, Tools()).ask("Bonjour")

    assert turn.text == "The local model is not installed."
    assert called == []
    assert turn.engine == "missing"


def test_the_prompts_carry_the_method_the_lookups_and_the_read_only_rule():
    text = answer_prompt("Quels hotes ?", [], "brief", "evidence")
    assert "Observation and inference are different sentences" in text
    assert "the language the analyst used" in text
    assert "You never change a case" in text
    plan = plan_prompt("question", [], "brief")
    for tool in (
        "overview",
        "findings",
        "search",
        "artifact",
        "around",
        "sequence",
        "timeline",
        "entity",
        "rare",
        "stats",
    ):
        assert tool in plan


def test_the_language_of_a_question_is_recognised():
    assert language_of("Que s'est-il passe sur cet hote ?") == "fr"
    assert language_of("What happened on this host and should I worry?") == "en"
    assert language_of("7045") == ""


def test_one_lookup_cannot_fill_the_whole_prompt():
    """Sixty rows of sequence pushed the method out of an 8k context."""
    from fireblade.core.assistant_chat import MAX_STEP_CHARS, _clip_page

    page = "\n".join("[%d] row %s" % (index, "x" * 80) for index in range(200))

    clipped = _clip_page(page)

    assert len(clipped) < MAX_STEP_CHARS + 200
    assert "not shown" in clipped


def test_the_evidence_sent_to_the_model_is_bounded():
    from fireblade.core.assistant_chat import MAX_EVIDENCE_CHARS, _clip_evidence

    huge = "line\n" * (MAX_EVIDENCE_CHARS // 4)

    clipped = _clip_evidence(huge)

    assert len(clipped) <= MAX_EVIDENCE_CHARS + 100
    assert "not sent" in clipped


def test_a_review_that_asks_for_a_fix_rewrites_the_answer(monkeypatch, tmp_path):
    _ready(monkeypatch)
    _script(
        monkeypatch,
        [
            _plan(),
            "Suspicious Service Path, high, sur FBVM a 10:02:52. Sans explication benigne.",
            "FIX: name the benign explanation that fits these rows",
            "Suspicious Service Path, high, sur FBVM a 10:02:52 ; la sauvegarde de 09:00 peut "
            "expliquer le reste, mais le chemin C:\\Temp reste a verifier.",
        ],
    )

    turn = Chat(tmp_path, Tools()).ask("Que s est-il passe sur cet hote ?")

    assert "benigne" in turn.text or "sauvegarde" in turn.text


def test_a_review_that_says_ok_keeps_the_draft(monkeypatch, tmp_path):
    _ready(monkeypatch)
    prompts = _script(
        monkeypatch,
        [
            _plan(),
            "Suspicious Service Path, high, sur FBVM a 10:02:52, rien d autre.",
            "OK",
        ],
    )

    turn = Chat(tmp_path, Tools()).ask("Que s est-il passe sur cet hote ?")

    assert turn.text == "Suspicious Service Path, high, sur FBVM a 10:02:52, rien d autre."
    assert any("You review one draft answer" in prompt for prompt in prompts)


def test_a_two_billion_model_is_not_asked_to_review_itself(monkeypatch, tmp_path):
    monkeypatch.setattr(
        assistant_module.Assistant,
        "status",
        lambda self: types.SimpleNamespace(
            can_answer=True, enabled=True, state="ready", detail="ready", model="MiniCPM5-2B"
        ),
    )
    monkeypatch.setattr(
        assistant_module,
        "shared_server",
        lambda root, assistant=None: types.SimpleNamespace(port=1, stop=lambda: None),
    )
    prompts = _script(
        monkeypatch,
        [
            _plan(),
            "Suspicious Service Path, high, sur FBVM a 10:02:52.",
        ],
    )

    Chat(tmp_path, Tools()).ask("Que s est-il passe sur cet hote ?")

    assert not any("You review one draft answer" in prompt for prompt in prompts)
