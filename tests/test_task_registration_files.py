from pathlib import Path


def test_task_files_exist():
    root = Path(__file__).resolve().parents[1]
    tmpl = root / "scripts" / "jarvis_task_template.xml"
    ps = root / "scripts" / "register_task.ps1"
    assert tmpl.exists(), "Template XML missing"
    assert ps.exists(), "PowerShell helper missing"
    content = tmpl.read_text()
    assert "%%PYTHON%%" in content and "%%SCRIPT%%" in content and "%%USER%%" in content
