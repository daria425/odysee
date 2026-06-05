from app.agent.nodes import trimmer


def test_trims_when_over_window():
    messages = list(range(15))
    assert trimmer(messages, 10) == list(range(5, 15))


def test_returns_all_when_under_window():
    messages = list(range(5))
    assert trimmer(messages, 10) == list(range(5))


def test_returns_all_when_exactly_window():
    messages = list(range(10))
    assert trimmer(messages, 10) == list(range(10))


def test_empty_messages():
    assert trimmer([], 10) == []
