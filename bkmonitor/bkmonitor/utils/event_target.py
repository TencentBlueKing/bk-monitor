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


class BaseKeyGenerator(object):
    """
    生成事件的Target Key
    """

    PREFIX = ""

    @classmethod
    def get_key(cls, *args, **kwargs):
        return ""


class HostKeyGenerator(BaseKeyGenerator):

    PREFIX = "host"

    def __init__(self, ip, bk_cloud_id):
        self.ip = ip
        self.bk_cloud_id = bk_cloud_id

    @classmethod
    def get_key(cls, ip, bk_cloud_id):
        return "{}|{}|{}".format(cls.PREFIX, ip, bk_cloud_id)

    @classmethod
    def parse(cls, target_key):
        keys = target_key.split("|")
        assert len(keys) == 3, "invalid host key"
        return cls(keys[1], keys[2])


class ServiceInstanceKeyGenerator(BaseKeyGenerator):

    PREFIX = "service"

    def __init__(self, bk_service_instance_id):
        self.bk_service_instance_id = bk_service_instance_id

    @classmethod
    def get_key(cls, instance_id):
        return "{}|{}".format(cls.PREFIX, instance_id)

    @classmethod
    def parse(cls, target_key):
        keys = target_key.split("|")
        assert len(keys) == 2, "invalid service instance key"
        return cls(keys[1])


class TopoKeyGenerator(BaseKeyGenerator):

    PREFIX = "topo"

    def __init__(self, bk_obj_id, bk_inst_id):
        self.bk_obj_id = bk_obj_id
        self.bk_inst_id = bk_inst_id

    @classmethod
    def get_key(cls, bk_obj_id, bk_inst_id):
        return "{}|{}|{}".format(cls.PREFIX, bk_obj_id, bk_inst_id)

    @classmethod
    def parse(cls, target_key):
        keys = target_key.split("|")
        assert len(keys) == 3, "invalid topo key"
        return cls(keys[1], keys[2])


def parse_target_key(target_key):
    """
    解析 target，返回对应的生成类
    """
    generators_cls = [
        HostKeyGenerator,
        ServiceInstanceKeyGenerator,
        TopoKeyGenerator,
    ]
    for generator_cls in generators_cls:
        if target_key.startswith(generator_cls.PREFIX):
            return generator_cls.parse(target_key)
