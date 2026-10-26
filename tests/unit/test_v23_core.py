from automationstudio.core import AutomationMap, Command, InputType, ActionType
from automationstudio.project import MapHistory


def _key(start: float, duration: float, target: str = "E"):
    return Command(type=InputType.KEY, target=target, action=ActionType.PRESS_AND_RELEASE, start=start, duration=duration)


def test_reflow_timeline_preserves_gaps_from_single_source():
    # D6 (decidido na 25.5): com preserve_gaps=True cada lacuna existente é mantida, então o reflow é a identidade
    # quando as lacunas já estão certas. A expectativa antiga (B=1.2) não é produzida por regra nenhuma e era erro do teste.
    m = AutomationMap(name="T", commands=[_key(0.0, 1.0, "A"), _key(1.5, 0.5, "B"), _key(2.2, 0.2, "C")])
    m.commands[0].delay = 0.2
    m.commands[1].delay = 0.1
    m.reflow_timeline(True)
    assert [round(c.start, 3) for c in m.commands] == [0.0, 1.5, 2.2]


def test_reflow_sem_preservar_lacunas_encosta_cada_comando_no_anterior():
    m = AutomationMap(name="T", commands=[_key(0.0, 1.0, "A"), _key(1.5, 0.5, "B"), _key(2.2, 0.2, "C")])
    m.commands[0].delay = 0.2
    m.commands[1].delay = 0.1
    m.reflow_timeline(False)
    assert [round(c.start, 3) for c in m.commands] == [0.0, 1.2, 1.8]


def test_duplicate_commands_get_new_ids_and_keep_relative_offsets():
    a = _key(0.0, 1.0, "A")
    b = _key(1.5, 0.5, "B")
    m = AutomationMap(name="T", commands=[a, b])
    copies = m.duplicate_commands({a.id, b.id}, insert_at=2)
    assert [c.target for c in copies] == ["A", "B"]
    assert all(c.id not in {a.id, b.id} for c in copies)
    assert round(copies[1].start - copies[0].start, 3) == 1.5
    assert len(m.commands) == 4


def test_remove_commands_compacts_occupied_time():
    a = _key(0.0, 1.0, "A")
    b = _key(1.5, 0.5, "B")
    c = _key(2.5, 1.0, "C")
    m = AutomationMap(name="T", commands=[a, b, c])
    m.remove_commands({b.id}, compact=True)
    assert [x.target for x in m.commands] == ["A", "C"]
    assert round(m.commands[1].start, 3) == 2.0


def test_history_keeps_transaction_label_across_undo_and_redo():
    m = AutomationMap(name="T", commands=[_key(0.0, 1.0)])
    h = MapHistory(16)
    h.prime(m)
    m.commands[0].description = "novo"
    h.commit(m, "Editar comando")
    assert h.can_undo(m)
    h.undo(m)
    assert m.commands[0].description == ""
    assert h.can_redo(m)
    h.redo(m)
    assert m.commands[0].description == "novo"
