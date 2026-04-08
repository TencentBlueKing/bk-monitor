"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import os

ES_INDEX_SETTINGS = {
    "number_of_shards": int(os.getenv("BKMONITOR_DOCUMENT_ES_INDEX_SHARDS", 3)),
    "number_of_replicas": int(os.getenv("BKMONITOR_DOCUMENT_ES_INDEX_REPLICAS", 1)),
    "refresh_interval": os.getenv("BKMONITOR_DOCUMENT_ES_INDEX_REFRESH_INTERVAL", "1s"),
}
