"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

import base64

from cloudpickle import cloudpickle

from apps.api import BkDataAIOPSApi
from apps.log_clustering.handlers.aiops.aiops_model.data_cls import (
    AiopsReleaseModelReleaseIdModelFileCls,
)
from apps.log_clustering.handlers.aiops.base import BaseAiopsHandler


class AiopsModelHandler(BaseAiopsHandler):
    def aiops_release_model_release_id_model_file(self, model_id: str, model_release_id: str):
        """
        获取发布的模型对应的模型文件
        @param model_id 模型id
        @param model_release_id 发布模型配置ID
        """
        aiops_release_model_release_id_model_file_request = AiopsReleaseModelReleaseIdModelFileCls(
            model_id=model_id, model_release_id=model_release_id
        )
        request_dict = self._set_username(aiops_release_model_release_id_model_file_request)
        return BkDataAIOPSApi.aiops_release_model_release_id_model_file(request_dict)

    def model_output_rt_model_file(self, model_output_rt: str):
        """
        获取模型输出对应的模型文件
        @param model_output_rt 模型输出结果表名称
        """
        request_dict = self._set_username({"data_processing_id": model_output_rt, "compat": "true"})
        return BkDataAIOPSApi.serving_data_processing_id_model_file(request_dict)

    @classmethod
    def pickle_decode(cls, content: str):
        model_original_content = base64.b64decode(content)
        model = cloudpickle.loads(model_original_content)
        return model
