import json
from pathlib import Path

from validation import validate

cases = json.loads(
    (Path(__file__).parents[1] / "shared-test-cases/validation_cases.json").read_text()
)
for case in cases:
    result = validate(case["input"])
    assert result == case["expected"], case["name"]
    print(
        json.dumps(
            {"name": case["name"], "result": result},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
    )
