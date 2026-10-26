from automationstudio.conditions import WaitCondition, WaitConditionType


def test_wait_condition_roundtrip():
    c = WaitCondition(type=WaitConditionType.PROCESS, target="notepad.exe", timeout=10, stable_ms=500, after=0.2)
    restored = WaitCondition.from_dict(c.to_dict())
    assert restored is not None
    assert restored.type is WaitConditionType.PROCESS
    assert restored.target == "notepad.exe"
    assert restored.timeout == 10
    assert restored.stable_ms == 500
    assert restored.after == 0.2


def test_wait_condition_validation():
    assert WaitCondition(type=WaitConditionType.PROCESS, target="notepad.exe").validate() == []
    assert WaitCondition(type=WaitConditionType.PROCESS).validate()


def test_wait_condition_delay_validation_and_roundtrip():
    c = WaitCondition(type=WaitConditionType.DELAY, timeout=0.25)
    assert c.validate() == []
    restored = WaitCondition.from_dict(c.to_dict())
    assert restored is not None and restored.type is WaitConditionType.DELAY
    assert restored.timeout == 0.25

def test_command_conditions_roundtrip_and_timeline_attachment():
    from automationstudio.core import AutomationMap, Command, InputType, ActionType, build_timeline
    c = Command(type=InputType.KEY, target="A", action=ActionType.PRESS_AND_RELEASE, duration=0.1,
                conditions=[WaitCondition(type=WaitConditionType.DELAY, timeout=0.25)])
    m = AutomationMap(name="T", commands=[c])
    restored = AutomationMap.from_dict(m.to_dict())
    assert len(restored.commands[0].conditions) == 1
    assert restored.commands[0].conditions[0].type is WaitConditionType.DELAY
    events = build_timeline(restored)
    assert events[0].wait_conditions[0].timeout == 0.25
    assert events[1].wait_conditions == []


def test_command_condition_validation_propagates():
    from automationstudio.core import Command, InputType
    c = Command(type=InputType.KEY, target='A', duration=0.1,
                conditions=[WaitCondition(type=WaitConditionType.PROCESS, target='')])
    errors = c.validate()
    assert any('processo' in e.lower() for e in errors)


def test_wait_command_builds_wait_event():
    from automationstudio.core import AutomationMap, Command, InputType, build_timeline, EventKind
    c = Command(type=InputType.WAIT, start=1.0, conditions=[WaitCondition(type=WaitConditionType.DELAY, timeout=0.5)])
    m = AutomationMap(name="T", commands=[c])
    events = build_timeline(m)
    assert events[0].kind is EventKind.WAIT
    assert events[0].wait_conditions[0].timeout == 0.5
    assert c.validate() == []


def test_wait_condition_unknown_type_downgrades_safely():
    c = WaitCondition.from_dict({"type": "future_condition", "target": "x"})
    assert c is not None and c.type is WaitConditionType.NONE
