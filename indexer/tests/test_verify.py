"""Verification stage (A1): bad documents go to quarantine with a reason. No network."""

import json
from pathlib import Path

from pipeline.ingest import verify_incoming
from pipeline.lake import Lake

GOOD = "Attendance below 80 percent bars a student from the final exam. " * 10 + "End."


def put(lake: Lake, name: str, text: str, **meta: str) -> None:
    (lake.area("incoming") / name).write_text(text, encoding="utf-8")
    base = {"doc_id": Path(name).stem, "title": name, "source": "test", "doc_version": "1"}
    (lake.area("incoming") / f"{name}.meta.json").write_text(json.dumps({**base, **meta}))


def test_bad_documents_are_quarantined(tmp_path: Path) -> None:
    lake = Lake(tmp_path)
    lake.init()
    put(lake, "a.md", GOOD)
    put(lake, "b.md", GOOD)                                   # exact duplicate of a.md
    put(lake, "empty.md", "  ")
    put(lake, "garbled.md", "ÃƒÂ©Ã¢â‚¬â„¢ ¤¤¤ ÿþÿþ ˜˜˜ " * 40)
    put(lake, "cut.md", GOOD + " and then the rule says that stu")
    put(lake, "nometa.md", GOOD.replace("80", "75"), title="", doc_version="")
    put(lake, "old.md", GOOD.replace("80", "70"), doc_id="rules", doc_version="2023")
    put(lake, "new.md", GOOD.replace("80", "60"), doc_id="rules", doc_version="2026")
    status = {v.file: (v.status, v.reasons) for v in verify_incoming(lake, None)}
    assert status["a.md"][0] == "verified"
    assert status["b.md"][0] == "quarantined" and "exact duplicate" in status["b.md"][1][0]
    assert status["empty.md"][0] == "quarantined"
    assert "garbled" in " ".join(status["garbled.md"][1])
    assert "truncated" in " ".join(status["cut.md"][1])
    assert "missing metadata" in " ".join(status["nometa.md"][1])
    assert status["old.md"][0] == "archived" and status["new.md"][0] == "verified"
    manifest = lake.load()["docs"]
    assert manifest["b@1"]["file"].startswith("quarantine/")
    assert not list(lake.area("incoming").iterdir())
    # a second run with the same file is skipped as unchanged
    put(lake, "a.md", GOOD)
    assert verify_incoming(lake, None) == []
