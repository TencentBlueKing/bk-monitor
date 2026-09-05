"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

# ---------------------------------------------------------------------------
# 监控平台 IAM V4 callback 适配层
#
# 本包由 callback 项目持有：资源 handler、协议分发、HTTP 鉴权、配置和 URL View
# 都在这里完成。它可以复用 V4Client 与 NameCodec，但不依赖 V4PermissionProvider、
# IAM_FRAMEWORK 或 Provider 的生命周期。
# ---------------------------------------------------------------------------
