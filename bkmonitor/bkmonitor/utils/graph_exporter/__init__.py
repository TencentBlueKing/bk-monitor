# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import os
import platform


def _install_font():
    """
    install chinese font for linux system
    :return: None
    """
    apt_script = 'apt-get -y install xfonts-wqy'
    yum_script = 'yum -y install bitmap-fonts bitmap-fonts-cjk'
    script_mapping = {
        'ubuntu': apt_script,
        'debian': apt_script,
        'devuan': apt_script,
        'centos': yum_script,
        'fedora': yum_script,
        'rhel': yum_script,
    }
    for linux_platform, script in script_mapping.items():
        if linux_platform in platform.platform().lower():
            os.system(script)
            break


bin_path = os.path.join(os.path.dirname(__file__), 'bin', "linux", "phantomjs")

# install font for linux system
if os.getenv('INSTALL_FONT_FOR_GRAPH_EXPORTER') and platform.system() == 'Linux':
    _install_font()
