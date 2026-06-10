"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from typing import Any

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apm_web.models import ApmMetaConfig, Application


class CodeRemarkHandler:
    APM_CODE_REMARK_CONFIG_KEY: str = "code_remarks"
    TRPC_DEFAULT_CODE_REMARK: dict[str, str] = {
        "1": _("服务端解码错误"),
        "2": _("服务端编码错误"),
        "11": _("服务端无对应 Service 实现"),
        "12": _("服务端无对应接口实现"),
        "21": _("服务端处理超时"),
        "22": _("服务端过载保护丢弃请求"),
        "23": _("服务端限流"),
        "24": _("服务端全链路超时"),
        "31": _("服务端系统错误"),
        "41": _("服务端鉴权失败"),
        "51": _("服务端请求参数校验失败"),
        "101": _("客户端调用超时"),
        "102": _("客户端全链路超时"),
        "111": _("客户端连接错误"),
        "121": _("客户端编码错误"),
        "122": _("客户端解码错误"),
        "123": _("客户端限流"),
        "124": _("客户端过载保护丢弃请求"),
        "131": _("客户端路由错误"),
        "141": _("客户端网络错误"),
        "151": _("客户端响应参数校验失败"),
        "161": _("上游主动取消请求"),
        "171": _("客户端读取 Frame 错误"),
        "201": _("服务端流式网络错误"),
        "211": _("服务端流消息超限"),
        "221": _("服务端流式编码错误"),
        "222": _("服务端流式解码错误"),
        "231": _("服务端流写结束"),
        "232": _("服务端流写溢出"),
        "233": _("服务端流写关闭"),
        "234": _("服务端流写超时"),
        "251": _("服务端流读结束"),
        "252": _("服务端流读关闭"),
        "253": _("服务端流读空数据"),
        "254": _("服务端流读超时"),
        "255": _("服务端流空闲超时"),
        "301": _("客户端流式网络错误"),
        "311": _("客户端流消息超限"),
        "321": _("客户端流式编码错误"),
        "322": _("客户端流式解码错误"),
        "331": _("客户端流写结束"),
        "332": _("客户端流写溢出"),
        "333": _("客户端流写关闭"),
        "334": _("客户端流写超时"),
        "351": _("客户端流读结束"),
        "352": _("客户端流读关闭"),
        "353": _("客户端流读空数据"),
        "354": _("客户端流读超时"),
        "355": _("客户端流空闲超时"),
        "361": _("客户端流初始化错误"),
        "999": _("未明确错误"),
        "1000": _("未明确流式错误"),
    }

    @classmethod
    def get_app_remark_configs(cls, bk_biz_id: int, app_name: str) -> list[dict[str, Any]]:
        """获取应用级返回码备注配置。"""
        app: Application = Application.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name).first()
        if not app:
            raise serializers.ValidationError(_("应用不存在"))

        config_obj: ApmMetaConfig = ApmMetaConfig.get_application_config_value(
            app.application_id, cls.APM_CODE_REMARK_CONFIG_KEY
        )
        config_value: dict[str, Any] = (config_obj and config_obj.config_value) or {}
        return config_value.get("remarks", [])

    @classmethod
    def build_service_code_remark_config(
        cls,
        remark_configs: list[dict[str, Any]],
        service_name: str,
        kind: str,
    ) -> dict[str, str]:
        """按从高到低的优先级（服务级 > 全局 > 内置）构造返回码备注。"""
        service_config: dict[str, str] = {
            **cls.TRPC_DEFAULT_CODE_REMARK,
            **{f"err_{code}": remark for code, remark in cls.TRPC_DEFAULT_CODE_REMARK.items()},
        }
        for remark_dict in sorted(remark_configs, key=lambda item: item.get("is_global", False), reverse=True):
            if remark_dict.get("kind") != kind:
                continue
            if not remark_dict.get("is_global") and service_name not in remark_dict.get("service_names", []):
                continue
            service_config[remark_dict.get("code", "")] = remark_dict.get("remark", "")

        return service_config
