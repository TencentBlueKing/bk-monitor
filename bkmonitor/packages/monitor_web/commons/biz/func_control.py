"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from api.cmdb import client

# 空间功能控制
from bkm_space.api import SpaceApi
from bkm_space.define import SpaceFunction, SpaceTypeEnum
from core.drf_resource import resource
from core.errors.api import BKAPIError
from bk_monitor_base.uptime_check import list_tasks


class ControlManager:
    # 功能控制管理器
    _controller = {}

    def get_controller(self, func_name, bk_biz_id):
        return self._controller.get(func_name)(bk_biz_id=bk_biz_id)

    def register(self, func_name, controller_cls):
        self._controller[func_name] = controller_cls


CM = ControlManager()


def register_controller(func_name):
    # 注册功能控制
    def register(cls):
        cls.func_name = func_name
        CM.register(func_name, cls)
        return cls

    return register


class BaseController:
    func_name = ""

    def __init__(self, bk_biz_id=None, space_uid=None, space=None):
        if space:
            self.space = space
            return

        if not bk_biz_id and not space_uid:
            raise f"{self.__class__.__name__} init error, need bk_biz_id or space_uid"
        if bk_biz_id:
            space = SpaceApi.get_space_detail(bk_biz_id=bk_biz_id)
        else:
            space = SpaceApi.get_space_detail(space_uid)

        self.space = space

    @property
    def accessed(self):
        # 如果该场景未配置，需要引导接入
        raise NotImplementedError

    @property
    def related(self):
        # 如果资源关联，无法使用对应场景功能
        raise NotImplementedError


@register_controller(SpaceFunction.APM.value)
class APMController(BaseController):
    @property
    def related(self):
        return True

    @property
    def accessed(self):
        from apm_web.models import Application

        return Application.objects.filter(bk_biz_id=self.space.bk_biz_id, is_deleted=False).exists()


@register_controller(SpaceFunction.HOST_PROCESS.value)
class HController(BaseController):
    @property
    def related(self):
        return cmdb_require(self.space)

    @property
    def accessed(self):
        def check_host_count(bk_biz_id):
            params = {
                "page": {"start": 0, "limit": 1},
                "fields": ["bk_host_id"],
                "bk_biz_id": bk_biz_id,
            }
            return client.list_biz_hosts(params)["count"]

        return self.related and check_host_count(self.space.bk_biz_id) > 0


@register_controller(SpaceFunction.UPTIMECHECK.value)
class UCController(BaseController):
    @property
    def related(self):
        return self.space.bk_biz_id > 0

    @property
    def accessed(self):
        tasks = list_tasks(bk_biz_id=self.space.bk_biz_id, fields=["id"])
        return self.related and len(tasks) > 0


@register_controller(SpaceFunction.K8S.value)
class K8SController(BaseController):
    @property
    def related(self):
        return self.space.space_code or self.space.bk_biz_id > 0

    @property
    def accessed(self):
        return (
            self.related
            and resource.scene_view.get_kubernetes_cluster_list(bk_biz_id=self.space.bk_biz_id)["total"] > 0
        )


@register_controller(SpaceFunction.CUSTOM_REPORT.value)
class CRController(BaseController):
    @property
    def related(self):
        return True

    @property
    def accessed(self):
        return len(resource.scene_view.get_observation_scene_list(bk_biz_id=self.space.bk_biz_id)) > 0


@register_controller(SpaceFunction.HOST_COLLECT.value)
class HCController(BaseController):
    @property
    def related(self):
        return self.space.bk_biz_id > 0

    @property
    def accessed(self):
        return self.related and resource.collecting.collect_config_list.exists_by_biz(bk_biz_id=self.space.bk_biz_id)


@register_controller(SpaceFunction.CI_BUILDER.value)
class CIController(BaseController):
    @property
    def related(self):
        return self.space.space_type_id == SpaceTypeEnum.BKCI.value

    @property
    def accessed(self):
        # todo 构建集监控功能待完善
        return False


@register_controller(SpaceFunction.PAAS_APP.value)
class PaaSController(BaseController):
    @property
    def related(self):
        return self.space.space_type_id == SpaceTypeEnum.BKSAAS.value

    @property
    def accessed(self):
        # todo 蓝鲸应用监控功能待完善
        return False


def cmdb_require(space):
    if space.bk_biz_id > 0:
        return True
    try:
        space = SpaceApi.get_related_space(space.space_uid, SpaceTypeEnum.BKCC.value)
    except (ValueError, BKAPIError):
        space = None
    return space is not None
