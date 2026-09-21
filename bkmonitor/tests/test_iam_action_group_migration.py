import copy
import json
from pathlib import Path


IAM_CONFIG_DIR = Path(__file__).parents[1] / "support-files" / "iam"


def load_action_groups(filename):
    config = json.loads((IAM_CONFIG_DIR / filename).read_text())
    return next(
        operation["data"] for operation in config["operations"] if operation["operation"] == "upsert_action_groups"
    )


def test_correct_action_groups_preserves_existing_groups():
    previous_groups = load_action_groups("0013_alarm_handling_mcp.json")
    corrected_groups = load_action_groups("0016_correct_action_groups.json")

    expected_groups = copy.deepcopy(previous_groups)
    mcp_group = next(group for group in expected_groups if group["name_en"] == "Monitor MCP")
    mcp_group["actions"].extend(
        [
            {"id": "using_log_collection_mcp"},
            {"id": "using_log_extract_mcp"},
        ]
    )

    assert corrected_groups == expected_groups
