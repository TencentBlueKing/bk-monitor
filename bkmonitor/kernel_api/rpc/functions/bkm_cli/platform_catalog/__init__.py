"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT

平台 API 能力 catalog 聚合入口。

Phase 0：catalog 空载，仅暴露 PlatformSourceCatalog 数据结构与 _lint 工具。
Phase 1+：在此 import 各 domain 子模块（cmdb / metadata / gse / ...）触发注册。
"""

from . import _catalog, _lint  # noqa: F401

__all__ = ["_catalog", "_lint"]
