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
"""
@summary: 始化logger实例(对logging的封装)
@usage：
          >>> from common.log import logger
          >>> logger.error(u'系统开小差了！')
"""

# 使用python的logging模块，配合settings的LOGGING属性
import logging
import os
import sys
import traceback

# ===============================================================================
# 更改标准库log的monkey patch ，主要是为了打印日志时能打印出准确调用log位置
# ===============================================================================
try:
    if __file__[-4:].lower() in [".pyc", ".pyo"]:
        current_file = __file__[:-4] + ".py"
    else:
        current_file = __file__
    current_file = os.path.normcase(current_file)
except Exception:
    current_file = ""


def findCaller_patch(self):
    """
    Find the stack frame of the caller so that we can note the source
    file name, line number and function name.
    """
    f = logging.currentframe()
    # On some versions of IronPython, currentframe() returns None if
    # IronPython isn't run with -X:Frames.
    rv = "(unknown file)", 0, "(unknown function)"
    if f is not None:
        f = f.f_back
    else:
        return rv
    while hasattr(f, "f_code"):
        co = f.f_code
        filename = os.path.normcase(co.co_filename)
        if filename == logging._srcfile or filename == current_file:
            f = f.f_back
            continue
        rv = (co.co_filename, f.f_lineno, co.co_name)
        break
    return rv


# ===============================================================================
# 控制打印信息长度，防止过多
# ===============================================================================
TRUNCATED_LENGTH = 10000
try:
    str
    _unicode = True
except NameError:
    _unicode = False


def truncate(message):
    if not _unicode:  # if no unicode support...
        msg = str(message)
    else:
        msg = message
        if not isinstance(msg, str):
            try:
                msg = str(message)
            except UnicodeError:
                msg = message  # Defer encoding till later
    if len(msg) < TRUNCATED_LENGTH:
        return msg
    return "%s ...[truncated]" % msg[:TRUNCATED_LENGTH]


# ===============================================================================
# 配置日志
# ===============================================================================
# root--用于平台的日志记录
logger_detail = logging.getLogger("root")
# component--用于组件调用的日志记录
logger_component = logging.getLogger("component")


# ===============================================================================
# 自定义添加打印内容
# ===============================================================================
# traceback--打印详细错误日志
class logger_traceback:
    """
    详细异常信息追踪
    """

    def __init__(self):
        pass

    def error(self, message=""):
        """
        error 日志
        """
        message = self.get_error_info(message)
        logger_detail.error(message)

    def info(self, message=""):
        """
        info 日志
        """
        message = self.get_error_info(message)
        logger_detail.info(message)

    def warning(self, message=""):
        """
        warning 日志
        """
        message = self.get_error_info(message)
        logger_detail.warning(message)

    def debug(self, message=""):
        """
        debug 日志
        """
        message = self.get_error_info(message)
        logger_detail.debug(message)

    def critical(self, message=""):
        """
        critical 日志
        """
        message = self.get_error_info(message)
        logger_detail.critical(message)

    def exception(self, message=""):
        """
        exception 日志(包含堆栈信息)
        """
        message = truncate(message)
        logger_detail.exception(message)

    def get_error_info(self, message):
        """
        获取日志信息
        """
        try:
            # 用户自定义日志信息进行防止过长截断
            message = truncate(message)
            # 获取堆栈信息
            info = sys.exc_info()
            # 打印堆栈信息
            traceback_msg = ""
            for filename, lineno, function, text in traceback.extract_tb(info[2]):
                msg = "{} line: {} in {}".format(filename, lineno, function)
                traceback_msg = "{}{}\n{}\n".format(traceback_msg, msg, text)
            if traceback_msg:
                message = "{}\n{}".format(message, traceback_msg)
            sys.exc_clear()
            return message
        except Exception:
            return message


# traceback--打印详细错误日志
logger = logger_traceback()
