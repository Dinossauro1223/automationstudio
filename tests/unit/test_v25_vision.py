from automationstudio.conditions import WaitCondition, WaitConditionType

def test_image_condition_roundtrip_and_validation():
    c=WaitCondition(type=WaitConditionType.IMAGE, timeout=10, parameters={"image_path":"screen.png","confidence":0.95,"interval":0.5,"region":{"x":0,"y":0,"w":100,"h":80}})
    d=WaitCondition.from_dict(c.to_dict())
    assert d is not None and d.type is WaitConditionType.IMAGE
    assert d.parameters["image_path"]=="screen.png"
    assert d.validate()==[]
    assert d.parameters.get("search") is not True

def test_image_condition_requires_path():
    assert WaitCondition(type=WaitConditionType.IMAGE).validate()
