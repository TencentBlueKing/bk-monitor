import json
from pathlib import Path


def test_itsm_ticket_detail_url_keeps_path_separator():
    initial_file = Path(__file__).resolve().parents[1] / "support-files/fta/action_plugin_initial.json"
    plugins = json.loads(initial_file.read_text(encoding="utf-8"))

    itsm_plugin = next(plugin for plugin in plugins if plugin["plugin_key"] == "itsm")
    create_task = next(config for config in itsm_plugin["backend_config"] if config["function"] == "create_task")
    url_template = next(output["value"] for output in create_task["outputs"] if output["key"] == "url")

    assert url_template == "{{itsm_site_url}}/#/ticket/detail?id={{id}}"
