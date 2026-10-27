"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import subprocess
import sys

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        if not getattr(settings, "SYNC_APIGATEWAY_ENABLED", True):
            self.stdout.write("Skipping API gateway synchronization: SYNC_APIGATEWAY_ENABLED=False")
            return

        # 合并 resources 目录下的所有 yaml 文件，执行脚本 `scripts/merge_resources.py`
        merge_resources_path = f"{settings.BASE_DIR}/support-files/apigw/scripts/merge_resources.py"
        try:
            result = subprocess.run(
                [sys.executable, merge_resources_path],
                capture_output=True,
                text=True,
                check=True,
            )
            self.stdout.write(result.stdout)
        except subprocess.CalledProcessError as e:
            if e.stdout:
                self.stderr.write(e.stdout)
            if e.stderr:
                self.stderr.write(e.stderr)
            # A successful exit would let deployment continue with stale gateway routes.
            raise CommandError(f"合并网关资源失败（退出码 {e.returncode}），未执行网关同步") from e
        except OSError as e:
            raise CommandError(f"无法启动网关资源合并，未执行网关同步: {e}") from e

        # 待同步网关名，需修改为实际网关名；直接指定网关名，则不需要配置 Django settings BK_APIGW_NAME
        gateway_name = "bk-monitor"

        # 待同步网关、资源定义文件，需调整为实际的配置文件地址
        definition_path = f"{settings.BASE_DIR}/support-files/apigw/definition.yaml"
        resources_path = f"{settings.BASE_DIR}/support-files/apigw/resources.yaml"

        call_command("sync_apigw_config", f"--gateway-name={gateway_name}", f"--file={definition_path}")
        call_command("sync_apigw_stage", f"--gateway-name={gateway_name}", f"--file={definition_path}")
        call_command("sync_apigw_resources", f"--gateway-name={gateway_name}", "--delete", f"--file={resources_path}")
        call_command(
            "sync_resource_docs_by_archive",
            f"--gateway-name={gateway_name}",
            f"--file={definition_path}",
            "--safe-mode",
        )
        call_command(
            "create_version_and_release_apigw",
            f"--gateway-name={gateway_name}",
            f"--file={definition_path}",
            f"--stage={settings.APIGW_STAGE}",
        )
        call_command("grant_apigw_permissions", f"--gateway-name={gateway_name}", f"--file={definition_path}")
        call_command("fetch_apigw_public_key", f"--gateway-name={gateway_name}")
