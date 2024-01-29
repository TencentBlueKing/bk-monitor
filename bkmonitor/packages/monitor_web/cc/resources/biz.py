# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
"""
业务相关（业务，人员，角色，权限）
"""


import logging
from typing import List

from django.conf import settings
from django.utils.translation import ugettext as _

from bkm_space.define import Space
from bkmonitor.iam import ActionEnum, Permission
from bkmonitor.utils.cache import CacheType, using_cache
from bkmonitor.utils.common_utils import to_dict
from bkmonitor.utils.user import get_global_user
from core.drf_resource import api
from core.drf_resource.exceptions import CustomException
from monitor_web.commons.biz.resources import ListSpacesResource

logger = logging.getLogger(__name__)


class Business(object):
    def __init__(self, kwargs=None):
        if kwargs is None:
            kwargs = dict()
        # display_name 在api.cmdb.define中已经定义，这里直接更新到了self.__dict__中，因此不需要额外再实现property
        self.__dict__.update(kwargs)

    def _get(self, key):
        return self.__dict__.get(key)

    def __getitem__(self, item):
        return self._get(item)

    @property
    def id(self):
        # 这里id是字符串
        return str(self._get("bk_biz_id"))

    @property
    def name(self):
        return self._get("bk_biz_name")

    @property
    def operation_planning(self):
        return self._get("OperationPlanning")

    @property
    def company_id(self):
        return self._get("CompanyID")

    @property
    def maintainers(self):
        return self._get("bk_biz_maintainer")

    def select_fields(self, field_list):
        """
        获取字段值
        :param field_list: 查询的字段列表
        """
        result = {}
        for field in field_list:
            result[field] = getattr(self, field, None)
        return result


def _init(biz_info):
    return Business(biz_info)


@using_cache(CacheType.BIZ, is_cache_func=lambda res: res)
def _get_application():
    """
    拉取全部业务信息，超级权限
    """
    business_list = api.cmdb.get_business(all=True)

    data = [to_dict(biz) for biz in business_list]
    return data


def get_biz_map(use_cache=True):
    """
    获取所有业务信息
    :return: dict
    """
    if use_cache:
        biz_list = _get_application()
    else:
        biz_list = _get_application.refresh()

    data = {}
    for biz_info in biz_list:
        biz = _init(biz_info)
        data[biz.id] = biz

    return data


def get_app_by_user(user=None, use_cache=True):
    """
    获取用户拥有的业务列表
    :return: list
    """
    if user is None:
        username = get_global_user()
    else:
        username = user.username
    biz_map = get_biz_map(use_cache)

    # 根据权限中心的【业务访问】权限，对业务列表进行过滤
    perm_client = Permission(username)
    business_list = perm_client.filter_business_list_by_action(ActionEnum.VIEW_BUSINESS, list(biz_map.values()))

    return business_list


def get_app_ids_by_user(user=None, use_cache=True):
    """
    获取用户拥有的业务id列表
    :return: list
    """
    biz_list = get_app_by_user(user, use_cache)
    biz_id_list = [biz.id for biz in biz_list]
    return biz_id_list


@using_cache(CacheType.BIZ)
def _get_app_by_id(bk_biz_id):
    """
    调用CC接口获取业务信息
    """
    res = api.cmdb.get_business(bk_biz_ids=[bk_biz_id])
    if not res:
        raise CustomException(_("业务信息获取失败: %s") % bk_biz_id)
    return to_dict(res[0])


def get_app_by_id(bk_biz_id):
    """
    根据业务ID获取App，ID不存在则抛出异常
    :param bk_biz_id: 业务ID
    """
    return _init(_get_app_by_id(bk_biz_id))


def get_notify_roles():
    """
    获取通知角色
    :return: {
        'bk_biz_tester': '测试人员',
        'bk_biz_developer': '开发人员',
        'bk_biz_maintainer': '运维人员',
        'operator': '操作人员',
        'bk_biz_productor': '产品人员',
        'bk_oper_plan': '运管PM',
        'bk_app_director': '产品负责人',
    }
    """
    roles = settings.NOTIRY_MAN_DICT.copy()
    for attr in api.cmdb.get_object_attribute(bk_obj_id="biz"):
        if (
            attr["bk_property_type"] == "objuser"
            and attr["bk_property_group"] == "role"
            and attr["bk_property_id"] not in roles
        ):
            roles[attr["bk_property_id"]] = attr["bk_property_name"]
    return roles


@using_cache(CacheType.OVERVIEW(60 * 2))
def fetch_allow_biz_ids_by_user(username: str) -> List[int]:
    spaces: List[Space] = ListSpacesResource.get_space_by_user(username)
    return [space.bk_biz_id for space in spaces]
