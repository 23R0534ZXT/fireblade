"""The chat: a plan, a lookup, then plain prose — and the language of the question."""
import types

from fireblade.core import assistant as assistant_module
from fireblade.core.assistant_chat import (Chat, answer_prompt, language_of,
                                          names_a_finding, plan_prompt)
from fireblade.core.case_tools import CaseTools


def _ready(monkeypatch, tmp_path):
    monkeypatch.setattr(assistant_module.Assistant, 'status', lambda self: types.SimpleNamespace(
        can_answer=True, enabled=True, state='ready', detail='ready', model='MiniCPM5-2B'))
    monkeypatch.setattr(assistant_module, 'shared_server',
                        lambda root, assistant=None: types.SimpleNamespace(port=1, stop=lambda: None))


def _script(monkeypatch, answers):
    """The stub engine answers in order and records the prompts it was given."""
    prompts = []

    def fake_ask(port, prompt, max_tokens=480, timeout=600, schema=None):
        prompts.append(prompt)
        if not answers:
            raise AssertionError('the model was asked more times than the test scripted')
        text = answers.pop(0)
        return dict(text=text, seconds=0.5, finish='stop')

    monkeypatch.setattr(assistant_module, 'ask', fake_ask)
    return prompts


def _tools():
    return CaseTools(lambda sql, params: [('FBVM', 12), ('WS01', 3)],
                     findings=lambda: [dict(level='high', title='Suspicious Service Path',
                                            host='FBVM', count=1, start='2026-11-17 10:02:52')])


def test_a_question_looks_something_up_before_it_answers(tmp_path, monkeypatch):
    _ready(monkeypatch, tmp_path)
    prompts = _script(monkeypatch, [
        '{"tool": "findings", "text": "", "host": "FBVM", "event_id": "", "artifact": "", "limit": 5}',
        'Suspicious Service Path, niveau high, sur FBVM a 10:02:52 : un service pointe '
        'vers un binaire temporaire.',
    ])
    chat = Chat(tmp_path, _tools())

    turn = chat.ask('Explique-moi ce qui se passe sur FBVM')

    assert turn.text.startswith('Suspicious Service Path')
    assert [step.tool for step in turn.steps] == ['findings']
    assert turn.steps[0].rows == 1
    assert 'Suspicious Service Path' in turn.steps[0].text
    assert turn.seconds > 0
    assert 'CONVERSATION SO FAR' not in prompts[0]
    assert 'Explique-moi ce qui se passe' in prompts[0]


def test_the_transcript_carries_the_previous_turn(tmp_path, monkeypatch):
    _ready(monkeypatch, tmp_path)
    _script(monkeypatch, [
        '{"tool": "none", "text": "", "host": "", "event_id": "", "artifact": "", "limit": 0}',
        'Deux hotes : FBVM et WS01.',
        '{"tool": "none", "text": "", "host": "", "event_id": "", "artifact": "", "limit": 0}',
        'Le second est WS01.',
    ])
    chat = Chat(tmp_path, _tools())
    chat.ask('Combien d hotes ?')
    prompts = _script(monkeypatch, [
        '{"tool": "none", "text": "", "host": "", "event_id": "", "artifact": "", "limit": 0}',
        'Le second est WS01.',
    ])

    chat.ask('Et le second ?')

    assert 'Combien d hotes ?' in prompts[0]
    assert 'Deux hotes : FBVM et WS01.' in prompts[0]


def test_a_mangled_plan_still_produces_an_answer(tmp_path, monkeypatch):
    _ready(monkeypatch, tmp_path)
    _script(monkeypatch, ['I think I should look at the logs', 'Voici ce que je vois.'])
    chat = Chat(tmp_path, _tools())

    turn = chat.ask('Alors ?')

    assert turn.steps == []
    assert turn.text == 'Voici ce que je vois.'


def test_an_unavailable_engine_says_why_and_never_calls_it(tmp_path, monkeypatch):
    monkeypatch.setattr(assistant_module.Assistant, 'status', lambda self: types.SimpleNamespace(
        can_answer=False, enabled=False, state='missing', detail='The local model is not installed.'))
    called = []
    monkeypatch.setattr(assistant_module, 'ask', lambda *a, **k: called.append(a))

    turn = Chat(tmp_path, _tools()).ask('Bonjour')

    assert turn.text == 'The local model is not installed.'
    assert called == []
    assert turn.engine == 'missing'


def test_the_prompt_asks_for_the_language_of_the_question():
    text = answer_prompt('Quels hôtes ?', [], 'brief', '')
    assert 'Answer in the language of the question' in text
    assert 'French' in text


def test_the_plan_prompt_offers_every_lookup_and_none():
    text = plan_prompt('question', [], 'brief')
    for tool in ('overview', 'search', 'findings', 'artifact', 'none'):
        assert tool in text

def test_an_empty_search_falls_back_on_the_detections(tmp_path, monkeypatch):
    """A search that read nothing must not be handed to the model as an empty page."""
    _ready(monkeypatch, tmp_path)
    _script(monkeypatch, [
        '{"tool": "search", "text": "zzz", "host": "", "event_id": "", "artifact": "", "limit": 0}',
        'Suspicious Service Path, high, sur FBVM a 10:02:52 : le service updsvc est '
        'installe depuis un chemin systeme.',
    ])

    class Tools(CaseTools):
        def __init__(self):
            super().__init__(lambda sql, params: [], findings=lambda: [
                dict(level='high', title='Suspicious Service Path', host='FBVM', count=1,
                     start='2026-11-17 10:02:52')])

        def call(self, name, arguments):
            if name == 'search':
                return 'Nothing matches in this case.', 0
            return super().call(name, arguments)

    turn = Chat(tmp_path, Tools()).ask('Que s est-il passe ?')

    assert [step.tool for step in turn.steps] == ['search', 'findings']
    assert turn.steps[-1].rows == 1
    assert 'Suspicious Service Path' in turn.steps[-1].text


def test_a_search_plan_with_no_filter_asks_for_the_detections(tmp_path, monkeypatch):
    _ready(monkeypatch, tmp_path)
    _script(monkeypatch, [
        '{"tool": "search", "text": "", "host": "", "event_id": "", "artifact": "", "limit": 0}',
        'Suspicious Service Path, high, sur FBVM a 10:02:52 : un service suspect a ete installe.',
    ])

    turn = Chat(tmp_path, _tools()).ask('Que s est-il passe ?')

    assert [step.tool for step in turn.steps] == ['findings']
    assert turn.steps[0].rows == 1


def test_the_answer_prompt_forbids_invented_brackets():
    text = answer_prompt('question', [], 'brief', 'rows')
    assert 'Never write a number in square brackets' in text

def test_the_language_of_a_question_is_recognised():
    assert language_of("Que s'est-il passe sur cet hote ?") == 'fr'
    assert language_of('What happened on this host and should I worry?') == 'en'
    assert language_of('7045') == ''


def test_an_answer_in_the_wrong_language_is_asked_again(tmp_path, monkeypatch):
    _ready(monkeypatch, tmp_path)
    _script(monkeypatch, [
        '{"tool": "none", "text": "", "host": "", "event_id": "", "artifact": "", "limit": 0}',
        'Nothing happened on this host at all, everything is calm and fine.',
        'Rien ne s est passe sur cet hote, tout est calme.',
    ])

    turn = Chat(tmp_path, _tools()).ask('Que s est-il passe sur cet hote ?')

    assert turn.text == 'Rien ne s est passe sur cet hote, tout est calme.'


def test_an_answer_that_names_no_detection_is_asked_again(tmp_path, monkeypatch):
    _ready(monkeypatch, tmp_path)
    _script(monkeypatch, [
        '{"tool": "findings", "text": "", "host": "", "event_id": "", "artifact": "", "limit": 0}',
        'Il y a des detections sur cet hote mais rien de grave.',
        'Suspicious Service Path, niveau high, sur FBVM a 10:02:52.',
    ])

    turn = Chat(tmp_path, _tools()).ask('Que s est-il passe sur cet hote ?')

    assert 'Suspicious Service Path' in turn.text


def test_a_good_answer_is_not_asked_again(tmp_path, monkeypatch):
    _ready(monkeypatch, tmp_path)
    prompts = _script(monkeypatch, [
        '{"tool": "findings", "text": "", "host": "", "event_id": "", "artifact": "", "limit": 0}',
        'Suspicious Service Path, niveau high, sur FBVM a 10:02:52 : le service pointe vers '
        'un chemin systeme, ce qui est le point a verifier.',
    ])

    turn = Chat(tmp_path, _tools()).ask('Que s est-il passe sur cet hote ?')

    assert 'Suspicious Service Path' in turn.text
    assert len(prompts) == 2
