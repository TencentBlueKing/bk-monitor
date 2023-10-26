# encoding=utf-8
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import functools
import os
import tempfile
import threading

import six
from selenium import webdriver

from . import bin_path

# lock to ensure thread safe
lock = threading.Lock()


def synchronized(_lock):
    def wrapper(f):
        @functools.wraps(f)
        def inner_wrapper(*args, **kwargs):
            with _lock:
                return f(*args, **kwargs)

        return inner_wrapper

    return wrapper


class Singleton(type):
    """
    thread safe singleton
    """

    _instances = {}

    @synchronized(lock)
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


@six.add_metaclass(Singleton)
class GraphExporter:
    """
    The Graph Exporter class to render graph
    """

    __name__ = "graph_exporter"

    def __init__(self):
        self._browser = None

    @staticmethod
    def _generate_temp_file(html_string, base_dir=None):
        """
        生成临时文件，并将 HTML 字符串写入到该文件
        """
        if base_dir:
            fd, path = tempfile.mkstemp(suffix=".html", dir=base_dir, text=True)
        else:
            fd, path = tempfile.mkstemp(suffix=".html", text=True)
        os.write(fd, html_string.encode('utf-8'))
        os.close(fd)
        return path

    @staticmethod
    def _clean_temp_file(path):
        """
        清理临时文件
        """
        try:
            os.remove(path)
        except FileNotFoundError:
            pass

    @staticmethod
    def convert_file_path_to_url(path):
        """
        将文件路径转换为浏览器能够识别的 url
        :param path: 需要被转换的文件路径
        :return: 转换后的 url
        """
        url = u"file:///%s" % path.replace("\\", "/")
        return url

    @property
    def browser(self):
        """
        获取浏览器实例
        """
        if not self._browser:
            self._browser = webdriver.PhantomJS(executable_path=bin_path)
        return self._browser

    def get_browser_log(self):
        """
        获取浏览器控制台日志
        """
        return self.browser.get_log('browser')

    def open_url(self, url, options=None):
        """
        url访问逻辑（子类可根据需要进行重写）
        :param url: 需要导出的页面 url
        :param options: 自定义选项
        """
        return self.browser.get(url)

    def perform_render(self, options=None):
        """
        图片导出逻辑（子类可根据需要进行重写）
        :param options: 自定义选项
        :return 图片的 base64 编码（PNG格式）
        """
        return self.browser.get_screenshot_as_base64()

    def render_string(self, html_string, base_dir=None, options=None):
        """
        将 HTML 字符串导出为图片
        :param html_string: 需要导出的 HTML 字符串
        :param base_dir: HTML 临时文件生成的路径，若引用了相对路径的静态文件，该项需要指定
        :param options: 自定义选项
        :return: 图片的 base64 编码（PNG格式）
        """
        temp_file_path = self._generate_temp_file(html_string, base_dir)
        file_url = self.convert_file_path_to_url(temp_file_path)
        try:
            return self.render_url(file_url, options)
        finally:
            self._clean_temp_file(temp_file_path)

    @synchronized(lock)
    def render_url(self, url, options=None):
        """
        将特定 url 页面导出为图片
        :param url: 需要导出的页面 url
        :param options: 自定义选项
        :return:
        """
        self.open_url(url, options)
        return self.perform_render(options)

    @synchronized(lock)
    def quit(self):
        """
        退出浏览器，并进行资源回收
        """
        if not self._browser:
            return
        self._browser.quit()
        self._browser = None
