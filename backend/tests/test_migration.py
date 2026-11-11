import importlib.util
import json
from pathlib import Path

import pytest

root = Path(__file__).resolve().parents[2] / "migration"
if not root.exists():
    root = Path("/migration")
spec = importlib.util.spec_from_file_location("migration_validation", root / "python/validation.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
cases = json.loads((root / "shared-test-cases/validation_cases.json").read_text())


@pytest.mark.parametrize("case", cases, ids=lambda c: c["name"])
def test_shared_validation(case):
    assert module.validate(case["input"]) == case["expected"]
