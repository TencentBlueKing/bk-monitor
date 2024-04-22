# -*- coding: utf-8 -*-
import abc
import logging

import six
from django.conf import settings
from django.utils.translation import ugettext as _

from bkmonitor.utils.request import get_request
from core.drf_resource.contrib.api import APIResource
from core.errors.api import DevopsNotDeployedError

logger = logging.getLogger("bcs_storage")


class DevopsBaseResource(six.with_metaclass(abc.ABCMeta, APIResource)):
    base_url = settings.DEVOPS_API_BASE_URL or "%s/api/c/compapi/v2/devops/prod/" % settings.BK_COMPONENT_API_URL
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
        data = super(DevopsBaseResource, self).request(request_data, **kwargs)
        return data

    def full_request_data(self, validated_request_data):
        data = super(DevopsBaseResource, self).full_request_data(validated_request_data)
        if hasattr(self, "bk_ticket"):
            data.update({"bk_ticket": self.bk_ticket})
        return data

    def perform_request(self, validated_request_data):
        if not settings.BK_CI_HOST:
            self.report_api_failure_metric(
                error_code=DevopsNotDeployedError.code, exception_type=DevopsNotDeployedError.__name__
            )
            raise DevopsNotDeployedError(system_name=self.module_name, url=self.action, result=_("蓝盾环境未部署"))
        return super(DevopsBaseResource, self).perform_request(validated_request_data)


class ListUserProjectResource(DevopsBaseResource):
    """
    用户态查询蓝盾项目列表
    """

    action = "/v4/apigw-user/projects/project_list"
    method = "GET"

    def request(self, request_data=None, **kwargs):
        if not settings.BK_CI_HOST:
            return []
        return super(ListUserProjectResource, self).request(request_data, **kwargs)


class UserProjectCreateResource(DevopsBaseResource):
    """
    用户态创建蓝盾项目
    """

    action = "/v4/apigw-user/projects/project_create"
    method = "POST"
