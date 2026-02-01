import json
import os
import tempfile

import jarvis
from tools import jarvis_manage


def test_export_import_memory(monkeypatch, tmp_path):
    # Replace memory collection with a fake that exposes .get()
    class FakeCol:
        def __init__(self):
            self.ids = ["a", "b"]
            self.docs = ["hello", "world"]
            self.metas = [{"k": 1}, {"k": 2}]

        def get(self):
            return {"ids": self.ids, "documents": self.docs, "metadatas": self.metas}

        def add(self, ids, documents, metadatas):
            self.ids.extend(ids)
            self.docs.extend(documents)
            self.metas.extend(metadatas)

    fake = FakeCol()
    monkeypatch.setattr(jarvis, "_memory_col", fake)

    out = tmp_path / "mem.json"
    jarvis_manage.export_memories(str(out))
    data = json.loads(out.read_text())
    assert any(r["text"] == "hello" for r in data)

    # Now import; reset and import
    fake2 = FakeCol()
    monkeypatch.setattr(jarvis, "_memory_col", fake2)
    jarvis_manage.import_memories(str(out))
    assert any("hello" in d for d in fake2.docs)
