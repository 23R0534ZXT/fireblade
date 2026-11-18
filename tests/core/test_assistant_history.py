"""A conversation belongs to a case: it is written as it happens and read back later."""
from fireblade.core.assistant_history import History, conversations_folder


def _case(tmp_path, name='case-1'):
    path = tmp_path / name / 'case.duckdb'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'')
    return path


def test_a_turn_is_written_the_moment_it_happens(tmp_path):
    history = History(_case(tmp_path))
    conversation = history.start('Que se passe-t-il sur FBVM ?')

    history.append(conversation, 'user', 'Que se passe-t-il sur FBVM ?', question='Que se passe-t-il ?')
    history.append(conversation, 'assistant', 'Un service suspect.')

    reopened = History(_case(tmp_path)).latest()
    assert reopened is not None
    assert [message.role for message in reopened.messages] == ['user', 'assistant']
    assert reopened.messages[1].text == 'Un service suspect.'


def test_the_conversations_live_beside_the_case_not_in_a_temp_folder(tmp_path):
    case = _case(tmp_path)
    history = History(case)
    history.append(history.start('q'), 'user', 'q', question='q')

    assert conversations_folder(case) == case.parent / 'assistant'
    assert list((case.parent / 'assistant').glob('conversation-*.jsonl'))


def test_two_cases_do_not_share_a_conversation(tmp_path):
    first = History(_case(tmp_path, 'one'))
    second = History(_case(tmp_path, 'two'))
    first.append(first.start('question du premier'), 'user', 'question du premier')

    assert second.conversations() == []
    assert first.latest().messages[0].text == 'question du premier'


def test_a_half_written_line_costs_one_turn_not_the_thread(tmp_path):
    case = _case(tmp_path)
    history = History(case)
    conversation = history.start('premiere')
    history.append(conversation, 'user', 'premiere')
    path = case.parent / 'assistant' / (conversation.identifier + '.jsonl')
    with path.open('a', encoding='utf-8') as handle:
        handle.write('{"role": "assistant", "text": "une reponse cou')

    reopened = History(case).latest()

    assert len(reopened.messages) == 1
    assert reopened.messages[0].text == 'premiere'


def test_the_newest_conversation_comes_first_and_keeps_its_title(tmp_path):
    case = _case(tmp_path)
    history = History(case)
    older = history.start('premiere question')
    history.append(older, 'user', 'premiere question', question='premiere question')
    newer = history.start('seconde question')
    history.append(newer, 'user', 'seconde question', question='seconde question')

    found = History(case).conversations()

    assert [item.title for item in found] == ['seconde question', 'premiere question']
    assert found[0].identifier == newer.identifier


def test_a_conversation_can_be_reopened_by_its_identifier(tmp_path):
    case = _case(tmp_path)
    history = History(case)
    conversation = history.start('garder celle-ci')
    history.append(conversation, 'user', 'garder celle-ci')
    other = history.start('oublier celle-ci')
    history.append(other, 'user', 'oublier celle-ci')

    reopened = History(case).load(conversation.identifier)

    assert reopened.messages[0].text == 'garder celle-ci'
    assert History(case).forget(other.identifier) is True
    assert [item.identifier for item in History(case).conversations()] == [conversation.identifier]


def test_the_steps_of_an_answer_are_kept_with_it(tmp_path):
    class Step:
        tool = 'findings'
        rows = 3
        arguments = {'limit': 20}

    history = History(_case(tmp_path))
    conversation = history.start('q')
    history.append(conversation, 'assistant', 'trois constats', steps=[Step()])

    saved = History(_case(tmp_path)).latest().messages[0]
    assert saved.steps == [dict(tool='findings', rows=3, arguments={'limit': 20})]


def test_an_empty_folder_has_no_conversation(tmp_path):
    assert History(_case(tmp_path)).latest() is None
    assert History(_case(tmp_path)).conversations() == []
