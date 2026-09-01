from bkmonitor.iam import ActionEnum
from kernel_api.views.v4.log_extract import LogExtractViewSet


def test_log_extract_view_requires_dedicated_mcp_permission():
    permissions = LogExtractViewSet().get_permissions()

    assert len(permissions) == 1
    assert permissions[0].actions == [ActionEnum.USING_LOG_EXTRACT_MCP]
