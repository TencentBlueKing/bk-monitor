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
import pytest
from django.conf import settings
from django.core.management import CommandError, call_command

from metadata.models.vm.constants import QUERY_VM_SPACE_UID_LIST_KEY
from metadata.utils.redis_tools import RedisTools


def test_failed_case():
    params = {"action": "add", "space_uids": ""}
    with pytest.raises(CommandError):
        call_command("switch_query_vm_space", **params)

    params = {"action": "", "space_uids": "bkcc_test"}
    with pytest.raises(CommandError):
        call_command("switch_query_vm_space", **params)


def test_add_space_uid(patch_redis_tools):
    # 添加一个
    space_uid = "bkcc__121"
    params = {"action": "add", "space_uids": space_uid}
    call_command("switch_query_vm_space", **params)

    val = list(RedisTools.smembers(QUERY_VM_SPACE_UID_LIST_KEY))
    assert val[0].decode("utf-8") == space_uid
    assert set(getattr(settings, "QUERY_VM_SPACE_UID_LIST", [])) == {space_uid}

    # 添加多个
    space_uids = "bkcc__121;bkci__test"
    params = {"action": "add", "space_uids": space_uids}
    call_command("switch_query_vm_space", **params)

    val = RedisTools.smembers(QUERY_VM_SPACE_UID_LIST_KEY)
    assert len(val) == 2
    # 处理数据
    str_val = set()
    for v in val:
        str_val.add(v.decode("utf-8"))
    assert str_val == {"bkcc__121", "bkci__test"}
    assert set(getattr(settings, "QUERY_VM_SPACE_UID_LIST", [])) == str_val


def test_del_space_uid(patch_redis_tools):
    # 添加数据
    space_uids = "bkcc__121;bkci__test;bksaas__sops"
    params = {"action": "add", "space_uids": space_uids}
    call_command("switch_query_vm_space", **params)

    # 检测已经存在
    assert len(RedisTools.smembers(QUERY_VM_SPACE_UID_LIST_KEY)) == 3

    # 删除数据
    deleted_space_uids = "bkcc__121;bksaas__sops"
    params = {"action": "delete", "space_uids": deleted_space_uids}
    call_command("switch_query_vm_space", **params)

    val = list(RedisTools.smembers(QUERY_VM_SPACE_UID_LIST_KEY))
    assert len(val) == 1
    assert val[0].decode("utf-8") == "bkci__test"
    assert set(getattr(settings, "QUERY_VM_SPACE_UID_LIST", [])) == {"bkci__test"}

    # 全部删除时，不会更新 admin 中动态配置数据
    params = {"action": "delete", "space_uids": "bkci__test"}
    call_command("switch_query_vm_space", **params)
    assert set(getattr(settings, "QUERY_VM_SPACE_UID_LIST", [])) == {"bkci__test"}
