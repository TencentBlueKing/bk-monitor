#!/usr/bin/env python
# -*- coding: utf-8 -*-
import glob
import os
import re
import subprocess
from packaging.utils import _
from apps.log_databus.handlers.check_collector.base import CheckCollectorRecord
from apps.log_databus.handlers.check_collector.checker.base_checker import Checker
from apps.log_databus.models import CollectorConfig


class LogPathChecker(Checker):
    HANDLER_NAME = _("启动入口")
    CHECKER_NAME = "log_path checker"

    def __init__(self, collector_config_id: int, check_collector_record: CheckCollectorRecord = None):
        super().__init__(check_collector_record=check_collector_record)
        self.collector_config_id = collector_config_id
        self.params = None  # 日志路径参数
        self.paths = []  # 路径数组
        self.exclude_files = []  # 黑名单路径数组
        self.record.append_normal_info("check start", self.HANDLER_NAME)

    def pre_run(self):
        try:
            collector_config = CollectorConfig.objects.get(collector_config_id=self.collector_config_id)
            self.params = collector_config.params
            self.paths = self.params.get("paths", [])
            self.exclude_files = self.params.get("exclude_files", [])

            if not self.paths:
                self.append_error_info(_("[采集配置中缺少paths参数]"))
                return False

            return True

        except CollectorConfig.DoesNotExist:
            self.append_error_info(_("[采集配置不存在]: {id}").format(id=self.collector_config_id))
            return False

    def _run(self):
        # 执行所有检查项
        if not self.pre_run():
            self.append_error_info(_("[预检查失败，跳过后续LogPathChecker检查]"))
            return
        self.record.append_normal_info(_("初始化检查成功"), self.HANDLER_NAME)
        self.check_wildcard_paths()
        self.check_excludes()

    def check_wildcard_paths(self):
        """
            检查路径数组中的通配符语法是否合法（非目录深度达文件）
        """
        wildcard_pattern = re.compile(r'''
                ^
                (?: 
                    [^\*\?$$$$/]+      # 普通字符（排除特殊字符）
                    | \*{1,2}          # * 或 **（保留**以备未来扩展）
                    | \?               # ?
                    | $$ [^$$]* \]     # 字符组
                    | /                # 路径分隔符（但不应出现在非目录深度匹配中）
                )*
                $
            ''', re.VERBOSE)
        error_messages = []
        all_valid = True
        for path in self.paths:
            if not path:
                error_messages.append(_("[路径匹配是否符合通配符语法][路径不能为空]"))
                all_valid = False
            if not wildcard_pattern.fullmatch(path):
                error_messages.append(
                    _("[路径匹配是否符合通配符语法][包含非法通配符语法]: {path}").format(path=path)
                )
                all_valid = False
            if '***' in path:
                error_messages.append(
                    _("[路径匹配是否符合通配符语法][不允许连续三个星号]: {path}").format(path=path)
                )
                all_valid = False
            if path.endswith('/'):
                error_messages.append(
                    _("[路径匹配是否符合通配符语法][非目录深度路径不应以/结尾]: {path}").format(path=path)
                )
                all_valid = False
            if not os.path.basename(path):
                error_messages.append(
                    _("[路径匹配是否符合通配符语法][路径必须包含文件名部分]: {path}").format(path=path)
                )
                all_valid = False
        if all_valid:
            self.append_normal_info(
                _("[路径匹配是否符合通配符语法][通配符路径检查通过]: {paths}").format(paths=", ".join(self.paths))
            )
        else:
            for msg in error_messages:
                self.append_error_info(msg)

    def check_excludes(self):
        """
        检查黑名单输入框内的文件是否附近对应的正则语法
        """
        all_valid = True
        error_messages = []
        for pattern in self.exclude_files:
            try:
                if '*' in pattern or '?' in pattern:
                    # 转换逻辑：
                    # * → .*
                    # ? → .
                    # 保留原有的正则语法
                    regex_pattern = '^' + \
                                    re.escape(pattern) \
                                        .replace(r'\*', '.*') \
                                        .replace(r'\?', '.') + \
                                    '$'
                else:
                    regex_pattern = pattern
                re.compile(regex_pattern)
                if re.search(r'[/\\]{2,}', pattern):
                    error_messages.append(
                        f"[黑名单语法是否符合正则标准]规则 '{pattern}' 包含连续路径分隔符"
                    )
                    all_valid = False
            except re.error as e:
                error_messages.append(
                    f"[黑名单语法是否符合正则标准]无效的正则/通配符语法 '{pattern}': {str(e)}"
                )
                all_valid = False
        if len(self.exclude_files) == 0:
            self.append_normal_info(
                _("[黑名单语法是否符合正则标准][未配置黑名单路径，跳过检查]")
            )
        elif all_valid:
            self.append_normal_info(
                _("[黑名单语法是否符合正则标准][黑名单路径匹配通过]: {paths}").format(
                    paths=", ".join(self.exclude_files))
            )
        else:
            for msg in error_messages:
                self.append_error_info(msg)
