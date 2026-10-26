from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def test_adaptive_timeout_source_contains_unlimited_mode():
    text = (ROOT / "automationstudio" / "input_system.py").read_text(encoding="utf-8")
    assert 'deadline = float("inf") if timeout_value <= 0' in text
    assert 'avg_ready_seconds' in text

def test_settings_defaults():
    text = (ROOT / "automationstudio" / "project.py").read_text(encoding="utf-8")
    assert "app_wait_timeout" in text
    assert "app_adaptive_learning" in text
