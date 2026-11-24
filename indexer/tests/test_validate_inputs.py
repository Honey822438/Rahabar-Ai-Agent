"""scripts/validate_inputs.py: the real inputs pass, a broken edit is caught. No network."""

import importlib.util
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("validate_inputs", ROOT / "scripts" / "validate_inputs.py")
assert spec and spec.loader
validate_inputs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validate_inputs)


def test_committed_inputs_are_valid() -> None:
    assert validate_inputs.validate() == []


def test_bad_edits_are_caught(tmp_path: Path) -> None:
    eval_dir = tmp_path / "eval"
    shutil.copytree(ROOT / "eval", eval_dir, ignore=shutil.ignore_patterns("results", "*.py"))
    golden = eval_dir / "golden.jsonl"
    rows = [json.loads(line) for line in golden.read_text().splitlines()]
    rows[1]["id"] = rows[0]["id"]                      # duplicate id
    rows[2]["reviewed"] = "yes"                        # wrong type
    rows[3]["type"] = "maybe"                          # bad value
    golden.write_text("\n".join(json.dumps(r) for r in rows) + "\n{broken\n")
    (eval_dir / "labels").mkdir(exist_ok=True)
    (eval_dir / "labels" / "faithfulness.jsonl").write_text('{"id": "f1"}\n')
    errors = " | ".join(validate_inputs.validate(eval_dir))
    for expected in ("duplicate id", "'reviewed' must be bool", "type must be",
                     "not valid JSON", "missing field 'label'"):
        assert expected in errors
