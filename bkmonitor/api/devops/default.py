import abc
import json
import logging

from django.conf import settings
from django.utils.translation import gettext as _

from bkmonitor.utils.request import get_request, get_request_username
from core.drf_resource.contrib.api import APIResource
from core.errors.api import DevopsNotDeployedError

logger = logging.getLogger("bcs_storage")


class DevopsBaseResource(APIResource, metaclass=abc.ABCMeta):
    base_url = settings.DEVOPS_API_BASE_URL or f"{settings.BK_COMPONENT_API_URL}/api/c/compapi/v2/devops/prod/"
    module_name = "devops"

    def request(self, request_data=None, **kwargs):
        request_data = request_data or kwargs
        # 获取request中的用户凭证
        request = get_request(peaceful=True)
        bk_ticket = None
        if request:
            bk_ticket = request.COOKIES.get("bk_ticket", "")
        bk_ticket = bk_ticket or request_data.get("bk_ticket", "")
        if bk_ticket:
            setattr(self, "bk_ticket", bk_ticket)
        data = super().request(request_data, **kwargs)
        return data

    def full_request_data(self, validated_request_data):
        data = super().full_request_data(validated_request_data)
        if hasattr(self, "bk_ticket"):
            data.update({"bk_ticket": self.bk_ticket})
        return data

    def get_headers(self):
        headers = super().get_headers()

        if not (settings.BKCI_APP_CODE and settings.BKCI_APP_SECRET):
            return headers

        auth_header = json.loads(headers["x-bkapi-authorization"])
        auth_header.update(
            {
                "bk_app_code": settings.BKCI_APP_CODE,
                "bk_app_secret": settings.BKCI_APP_SECRET,
            }
        )
        headers["x-bkapi-authorization"] = json.dumps(auth_header)
        return headers

    def perform_request(self, validated_request_data):
        if not settings.BK_CI_URL:
            self.report_api_failure_metric(
                error_code=DevopsNotDeployedError.code, exception_type=DevopsNotDeployedError.__name__
            )
            raise DevopsNotDeployedError(system_name=self.module_name, url=self.action, result=_("蓝盾环境未部署"))
        return super().perform_request(validated_request_data)


class ListUserProjectResource(DevopsBaseResource):
    """
    用户态查询蓝盾项目列表
    """

    action = "/v4/apigw-user/projects/project_list"
    method = "GET"

    def request(self, request_data=None, **kwargs):
        if not settings.BK_CI_URL:
            return []
        return super().request(request_data, **kwargs)


class UserProjectCreateResource(DevopsBaseResource):
    """
    用户态创建蓝盾项目
    """

    action = "/v4/apigw-user/projects/project_create"
    method = "POST"


class ListAppProjectResource(DevopsBaseResource):
    """
    查询用户有权限的蓝盾项目列表
    """

    action = "/v4/apigw-app/projects/project_list"
    method = "GET"

    def request(self, request_data=None, **kwargs):
        if not settings.BK_CI_URL:
            return []
        return super().request(request_data, **kwargs)

    def get_headers(self):
        headers = super().get_headers()
        headers["X-DEVOPS-UID"] = get_request_username()
        return headers


class ListPipelineResource(DevopsBaseResource):
    """
    查询流水线列表
    """

    action = "v4/apigw-app/projects/{project_id}/pipelineView/listViewPipelines"
    method = "GET"

    def request(self, request_data=None, **kwargs):
        if not settings.BK_CI_URL:
            return []
        return super().request(request_data, **kwargs)

    def get_headers(self):
        headers = super().get_headers()
        headers["X-DEVOPS-UID"] = get_request_username()
        return headers

    def get_request_url(self, validated_request_data):
        return super().get_request_url(validated_request_data).format(project_id=validated_request_data["project_id"])
