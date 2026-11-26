from unittest.mock import Mock

import pytest

from bkmonitor.iam import ActionEnum, Permission
from bkmonitor.iam import permission as permission_module
from iam_engine.core.config import AuthMode
from iam_engine.provider.bundle import ProviderBundle
from tests.iam.test_v3_provider import _make_provider
from tests.iam.test_v4_auth_payload import _build_provider


@pytest.mark.parametrize(
    "mode,policy,v4_ids,expected,loads_full",
    [
        (AuthMode.V3, {"op": "eq", "field": "space.id", "value": "-42"}, [], [-42], False),
        (AuthMode.V3, {"op": "in", "field": "space.id", "value": [2, "-42"]}, [], [-42], True),
        (AuthMode.V3, {"op": "none"}, [], [], False),
        (AuthMode.V3, {"op": "any"}, [], [2, -42, 8], True),
        (AuthMode.V4, {}, ["-42", "stale"], [-42], False),
        (AuthMode.V4, {}, [], [], False),
        (AuthMode.V4, {}, ["*"], [2, -42, 8], True),
        (AuthMode.UNION, {"op": "in", "field": "space.id", "value": ["8"]}, ["2"], [2, 8], False),
        (AuthMode.UNION, {"op": "starts_with", "field": "space.id", "value": "-"}, ["2"], [2, -42], True),
        (AuthMode.UNION, {"op": "eq", "field": "space.id", "value": "8"}, RuntimeError("offline"), [8], False),
        (AuthMode.UNION, RuntimeError("offline"), ["2"], [2], False),
        (AuthMode.UNION, RuntimeError("offline"), RuntimeError("offline"), [], False),
        (AuthMode.V4, {}, RuntimeError("offline"), [], False),
    ],
)
def test_page_space_scope_matches_candidate_filter(mode, policy, v4_ids, expected, loads_full, monkeypatch):
    spaces = [{"bk_biz_id": i, "space_name": str(i)} for i in (2, -42, 8)]
    v3 = _make_provider()
    v3.query_policy = Mock(side_effect=policy) if isinstance(policy, Exception) else Mock(return_value=policy)
    v4, client = _build_provider()
    if isinstance(v4_ids, Exception):
        client.list_authorized_resource.side_effect = v4_ids
    else:
        client.list_authorized_resource.return_value = {"ids": v4_ids}

    permission = Permission(username="tester", bk_tenant_id="system")
    permission.skip_check = False
    permission.mode_provider = Mock()
    permission.mode_provider.get_mode.return_value = mode
    permission._provider_bundles = {AuthMode.V3: ProviderBundle(scope=v3), AuthMode.V4: ProviderBundle(scope=v4)}

    def read_spaces(*, bk_tenant_id, using_cache=True, authorized_ids=None):
        assert bk_tenant_id == "system"
        return [s for s in spaces if authorized_ids is None or str(s["bk_biz_id"]) in authorized_ids]

    read = Mock(side_effect=read_spaces)
    monkeypatch.setattr(permission_module.SpaceApi, "list_spaces_dict", read)
    previous = permission.filter_space_list_by_action(ActionEnum.VIEW_BUSINESS)
    read.reset_mock()
    current = permission.list_visible_spaces(ActionEnum.VIEW_BUSINESS)
    assert current == previous
    assert [s["bk_biz_id"] for s in current] == expected
    assert any("authorized_ids" not in call.kwargs for call in read.call_args_list) == loads_full
    assert read.call_count == int(bool(expected) or loads_full)
