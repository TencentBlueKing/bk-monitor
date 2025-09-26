"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.conf import settings
from django.utils.translation import gettext_lazy as _
from opentelemetry import trace

from apm_web.constants import SamplerTypeChoices
from apm_web.models import ApmMetaConfig, Application
from common.log import logger
from constants.apm import DataSamplingLogTypeChoices, FlowType
from core.drf_resource import api
from core.errors.api import BKAPIError

tracer = trace.get_tracer(__name__)


class SamplingHelpers:
    """采样应用辅助类"""

    def __init__(self, application_id):
        self.application = Application.get_application_by_app_id(application_id)
        self.application_id = application_id
        self.bk_biz_id = self.application.bk_biz_id
        self.app_name = self.application.app_name

    def log(self, span, content, level="info"):
        getattr(logger, level)(content)
        span.add_event("log", {"content": content})

    def setup(self, config):
        """
        配置应用的采样配置
        @param config 采样配置 格式为SamplerConfigSerializer定义的格式
        """
        with tracer.start_as_current_span(
            "sampling_setup",
            attributes={
                "application_id": self.application.application_id,
                "bk_biz_id": self.bk_biz_id,
                "app_name": self.app_name,
                "config": config,
            },
        ) as span:
            self.log(span, f"start setup, config: {config}")
            sample_config = ApmMetaConfig.get_application_config_value(
                self.application_id, Application.SAMPLER_CONFIG_KEY
            )

            if sample_config:
                self.log(span, f"config in DB value: {sample_config.config_value}")

            # 检查此应用入库在哪一侧进行
            if sample_config == config:
                self.log(span, "check [DB]sample_config == [New]sample_config, skip update")
                return

            if not self._tail_opened and (
                config[Application.SamplerConfig.SAMPLER_TYPE]
                == sample_config.config_value[Application.SamplerConfig.SAMPLER_TYPE]
                == SamplerTypeChoices.RANDOM
            ):
                # 如果未开启尾部采样且都为随机类型 —> 直接更新DB
                self.log(
                    span,
                    "detected application does not enable tail sampling,"
                    "this will update directly the random-sampling configuration",
                )
                self.application.setup_config(
                    self.application.sampler_config,
                    new_config=config,
                    config_key=self.application.SAMPLER_CONFIG_KEY,
                    override=True,
                )
                self.application.sampler_config = config
                self.log(span, "update random-sampling configuration successfully, overwrite DB config with new config")
                return

            # 环境中无计算平台 -> 报错
            if not settings.IS_ACCESS_BK_DATA:
                self.log(
                    span,
                    f"bkbase not found in this environment of settings.IS_ACCESS_BK_DATA: {settings.IS_ACCESS_BK_DATA}",
                    level="error",
                )
                raise ValueError(_("设置中未开启计算平台支持，无法创建尾部采样"))

            # 创建or更新尾部采样
            try:
                p = self._change_to_tail_sampling_config(config)
                self.log(
                    span,
                    f"start to enable tail-sampling, convert config to tail-sampling param.config: {config} ----> {p}",
                )
                api.apm_api.create_or_update_bkdata_flow(
                    bk_biz_id=self.bk_biz_id,
                    app_name=self.app_name,
                    flow_type=FlowType.TAIL_SAMPLING.value,
                    config=p,
                )
                self.log(span, "setup successfully")
            except BKAPIError as e:
                self.log(span, f"failed to enable tail-sampling, error: {e}", level="error")
                raise ValueError(f"启动尾部采样失败，请求API错误：{e}")

            # 暂停transfer入库
            try:
                self.log(span, "start to stop apm_data_id trace datalink")
                response = api.apm_api.operate_apm_data_id(
                    bk_biz_id=self.bk_biz_id,
                    app_name=self.app_name,
                    datasource_type=DataSamplingLogTypeChoices.TRACE,
                    operate="stop",
                )
                self.log(span, f"stop dataId: {response} successfully")
            except Exception as e:  # noqa
                self.log(span, f"failed to stop transfer/bk-collect datalink, error: {e}", level="error")
                raise ValueError(f"暂停transfer Trace入库链路失败：{e}")

            # 更新数据库
            self.application.setup_config(
                self.application.sampler_config,
                new_config=config,
                config_key=self.application.SAMPLER_CONFIG_KEY,
                override=True,
            )
            self.application.sampler_config = config

    def _change_to_tail_sampling_config(self, sample_config):
        """将完整的采样配置转为尾部采样配置"""
        if sample_config[Application.SamplerConfig.SAMPLER_TYPE] == SamplerTypeChoices.RANDOM:
            return {
                "tail_percentage": sample_config["sampler_percentage"],
                "tail_conditions": [],
            }
        elif sample_config[Application.SamplerConfig.SAMPLER_TYPE] == SamplerTypeChoices.EMPTY:
            # 不采样 -> 采样100%
            return {
                "tail_percentage": 100,
                "tail_conditions": [],
            }

        return {
            "tail_percentage": sample_config["sampler_percentage"],
            "tail_conditions": sample_config.get("tail_conditions", []),
        }

    @property
    def _tail_opened(self):
        """判断此应用是否曾经开启过尾部采样"""
        return bool(self._tail_detail)

    @property
    def _tail_detail(self):
        """获取尾部采样详情"""

        return api.apm_api.get_bkdata_flow_detail(
            bk_biz_id=self.bk_biz_id,
            app_name=self.app_name,
            flow_type=FlowType.TAIL_SAMPLING.value,
        )

    def get_transfer_config(self):
        return self.application.get_sampler_config()
