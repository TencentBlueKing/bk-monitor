"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

API_PIPELINE_OVERVIEW_RESPONSE = {
    "result": True,
    "code": 200,
    "message": "ok",
    "data": [
        {
            "project_id": "bkee",
            "project_name": "蓝鲸企业版",
            "count": 6,
            "items": [
                {
                    "project_id": "bkee",
                    "pipeline_id": "p-9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4",
                    "pipeline_name": "蓝盾镜像提交",
                },
                {"project_id": "bkee", "pipeline_id": "p-1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6", "pipeline_name": "打包构建"},
                {
                    "project_id": "bkee",
                    "pipeline_id": "p-0f1e2d3c4b5a6978f0e1d2c3b4a5f6e",
                    "pipeline_name": "服务缩容流水线",
                },
                {
                    "project_id": "bkee",
                    "pipeline_id": "p-5a7d4b3c1e2f8a9b0c1d2e3f4a5b6c7d",
                    "pipeline_name": "PR 自动检查",
                },
                {
                    "project_id": "bkee",
                    "pipeline_id": "p-1234567890abcdef1234567890abcdef",
                    "pipeline_name": "平台代码检查",
                },
            ],
        },
        {
            "project_id": "bkcc",
            "project_name": "蓝鲸社区版",
            "count": 1,
            "items": [
                {"project_id": "bkcc", "pipeline_id": "p-1b2c3d4e5f6a7b8c9d0edf1a2b4c5c3", "pipeline_name": "构建镜像"}
            ],
        },
    ],
}

API_LIST_PIPELINE_RESPONSE = {
    "result": True,
    "code": 200,
    "message": "OK",
    "data": {
        "count": 3,
        "items": [
            {"project_id": "bkee", "pipeline_id": "p-9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4", "pipeline_name": "蓝盾镜像提交"},
            {"project_id": "bkee", "pipeline_id": "p-1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6", "pipeline_name": "打包构建"},
            {
                "project_id": "bkee",
                "pipeline_id": "p-0f1e2d3c4b5a6978f0e1d2c3b4a5f6e",
                "pipeline_name": "服务缩容流水线",
            },
        ],
    },
}
