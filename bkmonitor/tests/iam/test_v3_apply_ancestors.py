"""V3 URL payloads retain the same hierarchy as permission-denied prompts."""

from unittest.mock import Mock

import pytest

from bkmonitor.iam.backends.config import build_provider
from bkmonitor.iam.backends.v3.client import V3Client
from iam_engine.core.requests import ResourceInstance


@pytest.mark.parametrize(
    "resource_type,resource_id,actions",
    [
        ("apm_application", "31", ["view_apm_application", "manage_apm_application"]),
        ("rum_application", "32", ["view_rum_application", "manage_rum_application"]),
        ("grafana_dashboard", "8|dashboard", ["view_single_dashboard", "edit_single_dashboard"]),
        ("grafana_dashboard", "folder:8|9", ["view_single_dashboard", "edit_single_dashboard"]),
    ],
)
@pytest.mark.parametrize("space_id", ["12", "-12"])
def test_v3_apply_url_and_prompt_include_space(resource_type, resource_id, actions, space_id):
    provider = build_provider(
        "v3",
        options={
            "base_url": "https://iam.example.test",
            "credentials": {"app_code": "offline", "app_secret": "offline"},
            "system": {"id": "bk_monitorv3", "name": "Monitor"},
        },
    )
    provider.resolver = None
    client = V3Client("offline", "offline", "https://iam.example.test", "bk_monitorv3", provider.codec)
    client.get_apply_url = Mock(return_value=(True, "", "https://iam.example.test/apply"))
    provider._get_client = Mock(return_value=client)
    resources = [
        ResourceInstance(resource_type, rid, name="Resource", ancestor_chain=(ResourceInstance("space", space_id),))
        for rid in (resource_id, resource_id + "-other")
    ]
    data, url = provider.get_apply_data(actions, resources)
    application = client.get_apply_url.call_args.args[0]
    application.validate()
    payload = application.to_dict()
    assert url == "https://iam.example.test/apply"
    assert len(payload["actions"]) == len(actions)
    for prompt, action in zip(data["actions"], payload["actions"]):
        assert action["id"] == prompt["id"]
        instances = action["related_resource_types"][0]["instances"]
        assert len(instances) == 2
        for instance, resource, prompt_path in zip(
            instances, resources, prompt["related_resource_types"][0]["instances"]
        ):
            assert [(n["type"], n["id"]) for n in instance] == [("space", space_id), (resource_type, resource.id)]
            assert instance == [{k: n[k] for k in ("type", "id", "name")} for n in prompt_path]
    assert all(resource.attributes == {} for resource in resources)
