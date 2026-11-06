"""RecordingRule MCP 用户入口，业务执行复用公共配置 Resource。"""

from rest_framework import serializers

from bkmonitor.iam import ActionEnum, Permission
from bkmonitor.utils.request import get_request
from kernel_api.resource import recording_rule
from kernel_api.unified_mcp.permissions import _principal


class RecordingRuleMCPMixin:
    requires_confirmation = False

    def validate_request_data(self, request_data):
        # MCP 必须提供明确的业务上下文；身份只取经过网关验证的请求用户。
        bk_biz_id = serializers.IntegerField().run_validation(request_data.get("bk_biz_id"))
        user = _principal(get_request(), bk_biz_id)
        permission = Permission(user.username, bk_tenant_id=user.tenant_id)
        permission.skip_check = False
        action = ActionEnum.MANAGE_RECORDING_RULE if self.requires_confirmation else ActionEnum.VIEW_RECORDING_RULE
        permission.is_allowed_by_biz(bk_biz_id, action.id, raise_exception=True)
        if self.requires_confirmation and request_data.get("confirm") is not True:
            raise serializers.ValidationError({"confirm": "用户确认后必须传 true"})
        return super().validate_request_data(request_data)


class PreviewConfigResource(RecordingRuleMCPMixin, recording_rule.PreviewConfigResource):
    pass


class CreateConfigResource(RecordingRuleMCPMixin, recording_rule.CreateConfigResource):
    requires_confirmation = True


class UpdateConfigResource(RecordingRuleMCPMixin, recording_rule.UpdateConfigResource):
    requires_confirmation = True


class DeleteConfigResource(RecordingRuleMCPMixin, recording_rule.DeleteConfigResource):
    requires_confirmation = True


class GetConfigResource(RecordingRuleMCPMixin, recording_rule.GetConfigResource):
    pass


class ApplyConfigResource(RecordingRuleMCPMixin, recording_rule.ApplyConfigResource):
    requires_confirmation = True


class ListConfigsResource(RecordingRuleMCPMixin, recording_rule.ListConfigsResource):
    pass
