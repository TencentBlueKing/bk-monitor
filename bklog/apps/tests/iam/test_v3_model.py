import json
from pathlib import Path


def test_monitor_app_codes_can_query_log_policies():
    model_path = Path(__file__).resolve().parents[3] / "support-files" / "iam" / "initial.json"
    model = json.loads(model_path.read_text())
    system = next(operation["data"] for operation in model["operations"] if operation["operation"] == "upsert_system")
    clients = system["clients"].split(",")

    assert len(clients) == len(set(clients))
    assert {"bk_log_search", "bk_monitorv3", "bkmonitorv3"}.issubset(clients)
