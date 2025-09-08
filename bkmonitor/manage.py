# -*- coding: utf-8 -*-
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
import sys

import dotenv

dotenv.load_dotenv()

if __name__ == "__main__":
    # 我希望判断当前是否有ai_agent模块，如果没有，执行ln软链接命令，将当面目录上层的ai_agent目录链接到当前目录，同时需要支持跨平台的能力
    current_dir = os.path.dirname(os.path.abspath(__file__))
    target_dir = os.path.join(current_dir, "ai_agent")
    source_path = os.path.normpath(os.path.join(current_dir, "../ai_agent"))

    if not os.path.exists(target_dir):
        try:
            # 跨平台创建符号链接
            if os.name == 'nt':  # Windows
                import _winapi

                if not os.path.exists(source_path):
                    raise FileNotFoundError(f"source path {source_path} does not exist")
                _winapi.CreateJunction(source_path, target_dir)
            else:  # POSIX
                os.symlink(source_path, target_dir)
        except OSError as e:
            sys.stderr.write(f"create symlink failed: {str(e)}\n")
            sys.exit(1)

    if "celery" in sys.argv and "gevent" in sys.argv:
        from gevent import monkey

        monkey.patch_all()

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
