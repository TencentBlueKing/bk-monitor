"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT

平台 API 能力 catalog 聚合入口。

已注册 domain —— bkdata（bk-base 只读查询）、nodeman（节点管理订阅实例状态，只读）。
后续 domain（cmdb / metadata / gse / ...）在此 import 子模块触发注册。
"""

from . import _catalog, _lint, bkdata, nodeman  # noqa: F401

__all__ = ["_catalog", "_lint", "bkdata", "nodeman"]
