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

from dataclasses import asdict

from apps.log_clustering.constants import LATEST_PUBLISH_STATUS
from apps.log_clustering.handlers.aiops.aiops_model.data_cls import AiopsReleaseCls
from apps.log_clustering.handlers.aiops.config import get_online_clustering_config
from apps.feature_toggle.handlers.toggle import FeatureToggleObject
from apps.feature_toggle.plugins.constants import BKDATA_CLUSTERING_TOGGLE
from apps.log_clustering.exceptions import ClusteringClosedException, ModelReleaseNotFoundException
from apps.api import BkDataAIOPSApi


class BaseAiopsHandler:
    def __init__(self):
        if not FeatureToggleObject.switch(BKDATA_CLUSTERING_TOGGLE):
            raise ClusteringClosedException()
        self.conf = FeatureToggleObject.toggle(BKDATA_CLUSTERING_TOGGLE).feature_config

    def _set_username(
        self,
        request_data_cls,
        bk_username: str = "",
        bk_biz_id: int = None,
        no_request: bool = None,
        with_operator: bool = False,
    ):
        if isinstance(request_data_cls, dict):
            request_dict = request_data_cls
        else:
            request_dict = asdict(request_data_cls)
        if bk_biz_id is not None:
            request_dict["bk_biz_id"] = bk_biz_id

        request_username = bk_username or self.conf.get("bk_username")
        if request_username:
            request_dict["bk_username"] = request_username
            if with_operator:
                request_dict.setdefault("operator", request_username)
        if no_request is not None:
            request_dict["no_request"] = no_request

        return request_dict

    def _set_bkdata_request_params(self, request_data_cls, bk_biz_id: int = None, bk_username: str = ""):
        return self._set_username(
            request_data_cls=request_data_cls,
            bk_username=bk_username,
            bk_biz_id=bk_biz_id,
            no_request=True,
            with_operator=True,
        )

    def _use_biz_config(self, bk_biz_id: int = None):
        if bk_biz_id is not None:
            self.conf = get_online_clustering_config(bk_biz_id)

    def _get_request_bk_biz_id(self, bk_biz_id: int = None):
        return bk_biz_id if bk_biz_id is not None else self.conf.get("bk_biz_id")

    def aiops_release(self, model_id: str, bk_biz_id: int = None):
        """
        备选模型列表
        @param model_id 模型id
        """
        self._use_biz_config(bk_biz_id)
        request_bk_biz_id = self._get_request_bk_biz_id(bk_biz_id)
        aiops_release_request = AiopsReleaseCls(model_id=model_id, project_id=self.conf.get("project_id"))
        request_dict = self._set_bkdata_request_params(aiops_release_request, bk_biz_id=request_bk_biz_id)
        return BkDataAIOPSApi.aiops_release(request_dict)

    def get_latest_released_id(self, model_id: str, bk_biz_id: int = None):
        """
        获取最新release_id
        """
        release_info = self.aiops_release(model_id=model_id, bk_biz_id=bk_biz_id).get("list", [])
        release_ids = [
            info["model_release_id"] for info in release_info if info.get("publish_status") == LATEST_PUBLISH_STATUS
        ]
        if not release_ids:
            raise ModelReleaseNotFoundException(ModelReleaseNotFoundException.MESSAGE.format(model_id=model_id))
        release_id, *_ = release_ids
        return release_id

    def transfer_fields_to_origin(self):
        pass
