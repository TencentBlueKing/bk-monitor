# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""


import json
import logging

import six
from django.conf import settings
from django.utils.translation import gettext as _

from core.drf_resource import resource

logger = logging.getLogger(__name__)


class Host(object):
    def __init__(self, kwargs, bk_biz_id=None):
        self._bk_biz_id = bk_biz_id

        if isinstance(kwargs, six.string_types):
            temp = kwargs.split("|")
            if len(temp) == 1:
                kwargs = {
                    "bk_host_innerip": temp[0],
                    "bk_cloud_id": [
                        {
                            "bk_inst_id": 0,
                            "bk_inst_name": "",
                            "bk_obj_icon": "",
                            "bk_obj_id": "plat",
                            "bk_obj_name": "",
                            "id": "0",
                        }
                    ],
                }
            else:
                kwargs = {
                    "bk_host_innerip": temp[0],
                    "bk_cloud_id": [
                        {
                            "bk_inst_id": int(temp[1]),
                            "bk_inst_name": "",
                            "bk_obj_icon": "",
                            "bk_obj_id": "plat",
                            "bk_obj_name": "",
                            "id": temp[1],
                        }
                    ],
                    "plat_id": int(temp[1]),
                }
        elif isinstance(kwargs, dict):
            kwargs = json.loads(json.dumps(kwargs))
            if "ip" in kwargs:
                kwargs["bk_host_innerip"] = kwargs["ip"]
                del kwargs["ip"]
                if "bk_cloud_id" in kwargs:
                    bk_cloud_id = kwargs["bk_cloud_id"]
                elif "plat_id" in kwargs:
                    bk_cloud_id = kwargs["plat_id"]
                else:
                    bk_cloud_id = None

                if bk_cloud_id is not None:
                    kwargs["bk_cloud_id"] = [
                        {
                            "bk_inst_id": int(bk_cloud_id),
                            "bk_inst_name": _("默认"),
                            "bk_obj_icon": "",
                            "bk_obj_id": "plat",
                            "bk_obj_name": _("云区域"),
                            "id": str(bk_cloud_id),
                        }
                    ]
                    kwargs["plat_id"] = int(bk_cloud_id)
            elif "host" in kwargs:
                kwargs.update(kwargs["host"])
                del kwargs["host"]
        else:
            raise TypeError("Host: expect str or dict but get {}".format(type(kwargs)))
        self.__dict__.update(kwargs)

    def __str__(self):
        return json.dumps(self.__dict__)

    def __getattr__(self, item):
        return self.__dict__.get(item, None)

    def __getitem__(self, item):
        return self.__dict__[item]

    def __setitem__(self, key, value):
        self.__dict__[key] = value

    def __contains__(self, item):
        return item in self.__dict__

    def __bool__(self):
        return "bk_host_innerip" in self.__dict__

    def __hash__(self):
        return hash(self.host_id)

    def to_dict(self):
        return self.__dict__

    @property
    def host_id(self):
        if self.bk_cloud_id:
            return "{}|{}".format(self.bk_host_innerip, self.bk_cloud_id[0]["bk_inst_id"])
        else:
            return self.bk_host_innerip

    @property
    def host_dict(self):
        data = {"ip": self.bk_host_innerip}
        if self.bk_cloud_id:
            data["plat_id"] = self.bk_cloud_id[0]["bk_inst_id"]
            data["bk_cloud_id"] = self.bk_cloud_id[0]["bk_inst_id"]
        return data

    @property
    def bk_os_type_name(self):
        if self.bk_os_type:
            return settings.OS_TYPE_NAME_DICT.get(int(self.bk_os_type), "")
        return None

    @property
    def host_dict_with_os_type(self):
        data = self.host_dict
        if self.bk_os_type:
            data["os_type"] = self.bk_os_type_name
        else:
            data["os_type"] = ""
            logger.debug("Host(%s) can't get os type" % self.host_id)

        return data

    def get_bk_host_id(self):
        if self.bk_host_id:
            return self.bk_host_id
        else:
            return self.host_id

    def get_bk_cloud_id(self):
        if self.bk_cloud_id:
            return self.bk_cloud_id[0]["bk_inst_id"]

    def get_bk_cloud_name(self):
        if self.bk_cloud_id:
            return self.bk_cloud_id[0]["bk_inst_name"]

    def fetch_all_host_field(self):
        """
        查询host详情
        """
        if not self.bk_cloud_id or not self.bk_host_innerip or self._bk_biz_id is None:
            raise ValueError("fetch_all_host_field() host need bk_host_innerip and bk_cloud_id")
        result = resource.cc.host_detail(self.bk_host_innerip, self.get_bk_cloud_id(), self._bk_biz_id)
        if result:
            self.__init__(result.__dict__)
            return True
        else:
            return False

    @classmethod
    def create_host_list(cls, hosts):
        if isinstance(hosts, str):
            hosts = [hosts]

        result = []
        for host in hosts:
            result.append(cls(host))
        return result
