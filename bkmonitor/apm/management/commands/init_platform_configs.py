"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
from django.core.management.base import BaseCommand

from apm.models.config import PlatformConfig


class Command(BaseCommand):
    help = "初始化平台配置"

    def add_arguments(self, parser):
        parser.add_argument("--config-type", type=str, default="field_normalizer", help="配置类型")
        parser.add_argument("--config-file", type=str, help="配置文件路径（JSON格式）")
        parser.add_argument("--config-json", type=str, help="配置JSON字符串")

    def handle(self, *args, **options):
        """初始化平台配置"""
        config_type = options.get("config_type", "field_normalizer")
        config_file = options.get("config_file")
        config_json = options.get("config_json")

        try:
            # 获取配置数据
            config_data = None
            if config_file:
                with open(config_file, encoding="utf-8") as f:
                    config_data = json.load(f)
                self.stdout.write(f"从文件加载配置: {config_file}")
            elif config_json:
                config_data = json.loads(config_json)
                self.stdout.write("从JSON字符串加载配置")
            else:
                self.stdout.write(self.style.ERROR("请提供配置文件或JSON字符串"))

            # 初始化配置
            PlatformConfig.init_builtin_config_with_data(config_type, config_data)
            self.stdout.write(self.style.SUCCESS(f"{config_type} 配置初始化成功"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"配置初始化失败: {e}"))
