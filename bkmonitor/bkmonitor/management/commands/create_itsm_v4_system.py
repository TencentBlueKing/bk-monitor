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
import sys
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from api.common.default import CommonBaseResource
from core.errors.api import BKAPIError


class ItsmSystemCreateResource(CommonBaseResource):
    """
    ITSM 创建系统ID资源类
    """

    def __init__(self):
        super().__init__(url="{{itsm_v4_api_url}}/api/v1/system/create/", method="POST")


class ItsmSystemWorkflowListResource(CommonBaseResource):
    """
    ITSM 获取系统流程列表资源类
    """

    def __init__(self):
        """
        初始化资源类
        """
        super().__init__(url="{{itsm_v4_api_url}}/api/v1/system_workflow/list/", method="GET")


class Command(BaseCommand):
    """
    创建 ITSM V4 系统ID的管理命令

    使用示例:
        # 使用配置文件中的系统ID创建
        python manage.py create_itsm_v4_system

        # 指定系统名称创建（code 默认与 name 相同）
        python manage.py create_itsm_v4_system --name bk_monitorv3"

        # 指定系统名称和代码创建
        python manage.py create_itsm_v4_system --name bk_monitorv3 --code bk_monitorv3
    """

    help = "创建 ITSM 系统ID（可指定 name 和 code，或使用配置文件中的 BK_ITSM_V4_SYSTEM_ID）"

    def add_arguments(self, parser):
        """
        添加命令行参数

        参数说明:
            --name: 系统名称（可选），不指定时使用配置文件中的 BK_ITSM_V4_SYSTEM_ID
            --code: 系统代码（可选），不指定时默认与 name 相同
        """
        parser.add_argument(
            "--name",
            type=str,
            help="系统名称（不指定时使用配置文件中的 BK_ITSM_V4_SYSTEM_ID）",
        )
        parser.add_argument(
            "--code",
            type=str,
            help="系统代码（不指定时默认与 name 相同）",
        )

    def handle(self, *args, **options):
        """
        命令执行入口

        执行步骤:
        1. 检查 ITSM 配置（包括环境变量）
        2. 解析命令行参数，确定系统名称和代码
        3. 检查系统是否已存在
        4. 创建系统
        """
        # 检查 ITSM 配置（包括环境变量）
        self._check_itsm_config()

        # 解析系统信息
        system_info = self._parse_system_info(options)

        # 检查系统是否存在
        self._check_system_exists(system_info["code"])

        # 创建系统
        self._create_system(system_info)

    def _check_itsm_config(self):
        """
        检查 ITSM 配置是否正确（包括环境变量）

        执行步骤:
        1. 检查 BK_ITSM_V4_API_URL 配置是否存在
        2. 如果配置不存在或为空，抛出异常并提示
        3. 输出配置信息
        """
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("检查 ITSM 环境变量配置...")
        self.stdout.write("=" * 60)

        # 检查 BK_ITSM_V4_API_URL
        if not hasattr(settings, "BK_ITSM_V4_API_URL") or not settings.BK_ITSM_V4_API_URL:
            raise CommandError(
                "\n✗ ITSM 配置错误：settings.BK_ITSM_V4_API_URL 未配置或为空\n"
                "  请在 Django settings 中配置 BK_ITSM_V4_API_URL\n"
                "  例如: BK_ITSM_V4_API_URL = 'https://apps.paas.com/cw--aitsm'\n"
            )

        self.stdout.write(self.style.SUCCESS(f"✓ BK_ITSM_V4_API_URL: {settings.BK_ITSM_V4_API_URL}"))
        self.stdout.write("=" * 60 + "\n")

    def _parse_system_info(self, options):
        """
        解析系统信息

        参数:
            options: 命令行选项参数字典

        返回:
            dict: 包含 name 和 code 的系统信息字典

        执行步骤:
        1. 从命令行参数获取 name 和 code
        2. 如果未指定 name，从配置文件获取 BK_ITSM_V4_SYSTEM_ID
        3. 如果未指定 code，使用 name 作为 code
        4. 验证系统信息的有效性
        5. 输出系统信息
        """
        name = options.get("name")
        code = options.get("code")

        # 如果未指定 name，从配置文件获取
        if not name:
            if not hasattr(settings, "BK_ITSM_V4_SYSTEM_ID") or not settings.BK_ITSM_V4_SYSTEM_ID:
                raise CommandError(
                    "\n✗ 系统信息错误：未指定 --name 参数，且 settings.BK_ITSM_V4_SYSTEM_ID 未配置或为空\n"
                    "  请使用以下方式之一：\n"
                    "  1. 指定 --name 参数: python manage.py create_itsm_v4_system --name my-system\n"
                    "  2. 在 Django settings 中配置 BK_ITSM_V4_SYSTEM_ID\n"
                )
            name = settings.BK_ITSM_V4_SYSTEM_ID
            self.stdout.write(self.style.SUCCESS(f"✓ 使用配置文件中的系统ID: {name}\n"))

        # 如果未指定 code，使用 name 作为 code
        if not code:
            code = name
            self.stdout.write(self.style.SUCCESS(f"✓ 系统代码未指定，使用系统名称作为代码: {code}\n"))

        # 输出系统信息
        self.stdout.write("=" * 60)
        self.stdout.write("即将创建以下系统:")
        self.stdout.write("=" * 60)
        self.stdout.write(f"系统名称 (name):  {name}")
        self.stdout.write(f"系统代码 (code):  {code}")
        self.stdout.write("=" * 60 + "\n")

        return {
            "name": name,
            "code": code,
        }

    def _check_system_exists(self, code):
        """
        检查系统是否存在

        参数:
            code: 系统代码

        执行步骤:
        1. 调用 ITSM API 查询系统流程列表
        2. 如果请求成功，说明系统已存在，退出命令
        3. 如果返回"系统不存在"错误，说明系统未创建，继续执行
        4. 处理其他异常情况
        """
        self.stdout.write(f"正在检查系统 [{code}] 是否存在...\n")

        try:
            # 使用获取系统流程接口来验证系统是否存在
            resource = ItsmSystemWorkflowListResource()
            resource.request(
                system_id=code,
                page=1,
                page_size=1,
            )

            # 如果请求成功，说明系统存在
            self.stdout.write(self.style.WARNING(f"✓ 系统ID [{code}] 已存在，无需重复创建\n"))
            sys.exit(0)

        except BKAPIError as e:
            # 尝试解码错误消息
            error_msg = self._decode_error_message(e)

            # 检查是否是"系统不存在"错误
            if "系统不存在" in error_msg or "系统不存在" in str(e.data):
                # 系统不存在，这是正常情况，继续创建流程
                self.stdout.write(self.style.SUCCESS(f"✓ 系统 [{code}] 不存在，准备创建...\n"))
                return
            else:
                # 其他错误
                self.stdout.write(self.style.ERROR(f"✗ 检查系统时发生错误: {error_msg}\n"))
                raise CommandError(f"检查系统失败: {error_msg}")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ 检查系统时发生未知错误: {str(e)}\n"))
            raise CommandError(f"检查系统失败: {str(e)}")

    def _decode_error_message(self, error):
        """
        解码错误消息，处理中文编码问题

        参数:
            error: BKAPIError 异常对象

        返回:
            str: 解码后的错误消息

        执行步骤:
        1. 尝试从 error.data 中获取 message 字段
        2. 如果 message 是字节字符串，尝试解码
        3. 如果解码失败，返回原始错误消息
        4. 处理嵌套的 JSON 字符串
        """
        try:
            # 获取错误数据
            error_data = error.data if hasattr(error, "data") else {}

            # 尝试获取 message 字段
            message = error_data.get("message", str(error))

            # 如果 message 是字节字符串（以 b' 开头），尝试解码
            if isinstance(message, str) and message.startswith("b'"):
                # 移除 b' 前缀和 ' 后缀
                message = message[2:-1]

                # 尝试将转义的字节序列转换为实际字节
                try:
                    # 使用 encode().decode('unicode_escape') 处理转义序列
                    message_bytes = message.encode("utf-8").decode("unicode_escape").encode("latin1")
                    message = message_bytes.decode("utf-8")
                except Exception:
                    pass

            # 尝试解析 JSON
            if isinstance(message, str) and (message.startswith("{") or message.startswith("[")):
                try:
                    parsed = json.loads(message)
                    if isinstance(parsed, dict):
                        # 提取实际的错误消息
                        message = parsed.get("message", message)
                        if "detail" in parsed.get("data", {}):
                            message = parsed["data"]["detail"]
                except Exception:
                    pass

            return message

        except Exception:
            # 如果所有解码尝试都失败，返回原始错误消息
            return str(error)

    def _create_system(self, system_info):
        """
        创建 ITSM 系统

        参数:
            system_info: 系统信息字典，包含 name 和 code

        执行步骤:
        1. 调用 ITSM API 创建系统
        2. 处理创建成功的响应
        3. 输出系统信息
        4. 处理异常情况
        """
        self.stdout.write("正在创建系统...\n")
        try:
            resource = ItsmSystemCreateResource()
            response = resource.request(**system_info)

            # 创建成功
            self.stdout.write(self.style.SUCCESS("✓ 系统创建成功！\n"))

            # 显示返回的系统信息
            if isinstance(response, dict):
                self.stdout.write("=" * 60)
                self.stdout.write("系统信息:")
                self.stdout.write("=" * 60)
                self.stdout.write(json.dumps(response, indent=2, ensure_ascii=False))
                self.stdout.write("=" * 60 + "\n")

            # 提示后续操作
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n✓ 系统 [{system_info['code']}] 创建完成！\n  您现在可以使用该系统ID创建流程和工单。\n"
                )
            )

        except BKAPIError as e:
            # API 调用失败
            error_msg = self._decode_error_message(e)
            self.stdout.write(self.style.ERROR(f"\n✗ 创建系统失败: {error_msg}\n"))

            raise CommandError(f"创建系统失败: {error_msg}")

        except Exception as e:
            # 其他未知错误
            self.stdout.write(self.style.ERROR(f"\n✗ 创建系统时发生未知错误: {str(e)}\n"))
            raise CommandError(f"创建系统失败: {str(e)}")
