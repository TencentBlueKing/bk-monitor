"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

# iam.__init__ — 懒加载导出，避免 Django apps.populate() 阶段触发重模块导入。
# 使用方式不变：from bkmonitor.iam import ActionEnum / ResourceEnum / Permission

__all__ = [
    "ActionEnum",
    "ResourceEnum",
    "Permission",
]


def __getattr__(name: str):
    if name == "ActionEnum":
        from bkmonitor.iam.action import ActionEnum as _v

        return _v
    if name == "ResourceEnum":
        from bkmonitor.iam.resource import ResourceEnum as _v

        return _v
    if name == "Permission":
        from bkmonitor.iam.permission import Permission as _v

        return _v
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
