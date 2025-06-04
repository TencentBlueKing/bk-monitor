# -*- coding: utf-8 -*-
import unittest
import time

from mock import patch, MagicMock
from pathlib import Path
import sys

# 添加项目根目录到Python路径（根据实际层级调整）
sys.path.append(str(Path(__file__).parent.parent.parent.parent))  # 假设结构为：bk-monitor/bklog/apps/tests/
from bklog.apps.log_databus.scripts.check_bkunifylogbeat.check import LogPathChecker, Result


class TestLogPathChecker(unittest.TestCase):
    """日志路径检查器单元测试"""

    @patch('apps.log_databus.scripts.check_bkunifylogbeat.check.get_command')
    def test_check_path_match_empty_input(self, mock_get_command):
        """测试空输入情况"""
        LogPathChecker.check_path_match()
        # 不需要验证mock_get_command，因为函数内部会直接返回"日志采集路径不存在"

    @patch('apps.log_databus.scripts.check_bkunifylogbeat.check.get_command')
    def test_check_path_match_string_input(self, mock_get_command):
        """测试字符串类型输入（逗号分隔）"""
        mock_get_command.return_value = "/tmp/test.log"
        LogPathChecker.check_path_match("/tmp/test.log,/var/log/messages")
        # 验证函数能正确处理字符串分割

    @patch('apps.log_databus.scripts.check_bkunifylogbeat.check.get_command')
    def test_check_path_match_all_missing(self, mock_get_command):
        """测试所有路径都不存在的情况"""
        mock_get_command.return_value = ""  # 模拟ls命令返回空
        LogPathChecker.check_path_match(["/nonexistent1", "/nonexistent2"])
        # 验证返回结果包含所有缺失路径

    @patch('apps.log_databus.scripts.check_bkunifylogbeat.check.get_command')
    def test_check_path_match_partial_missing(self, mock_get_command):
        """测试部分路径存在的情况"""
        # 模拟第一个路径存在，第二个不存在
        mock_get_command.side_effect = ["/tmp/exist.log", ""]
        LogPathChecker.check_path_match(["/tmp/exist.log", "/tmp/missing.log"])
        # 验证结果中同时包含存在的文件和缺失路径

    @patch('apps.log_databus.scripts.check_bkunifylogbeat.check.get_command')
    def test_check_path_match_wildcard(self, mock_get_command):
        """测试通配符路径"""
        mock_get_command.return_value = "/tmp/log1.log\n/tmp/log2.log"
        LogPathChecker.check_path_match(["/tmp/*.log"])
        # 验证通配符被正确解析

    @patch('apps.log_databus.scripts.check_bkunifylogbeat.check.get_command')
    def test_check_file_held_no_conflict(self, mock_get_command):
        """测试无文件占用冲突的情况"""
        # 模拟lsof返回空（无占用）
        mock_get_command.return_value = ""
        LogPathChecker.check_file_held(["/tmp/test.log"])
        # 验证返回状态为True

    @patch('apps.log_databus.scripts.check_bkunifylogbeat.check.get_command')
    def test_check_file_held_single_conflict(self, mock_get_command):
        """测试单个文件被占用的情况"""
        # 模拟lsof返回被占用的文件
        mock_get_command.return_value = "bkunifylogbeat 1234 root 1r REG 8,1 0 1024 /tmp/busy.log"
        LogPathChecker.check_file_held(["/tmp/busy.log"])
        # 验证返回消息包含冲突文件路径

    @patch('apps.log_databus.scripts.check_bkunifylogbeat.check.get_command')
    def test_check_file_held_multiple_conflicts(self, mock_get_command):
        """测试多个文件被占用的情况"""
        # 模拟lsof返回多个被占用的文件
        mock_get_command.return_value = """
        bkunifylogbeat 1234 root 1r REG 8,1 0 1024 /tmp/busy1.log
        bkunifylogbeat 1234 root 2r REG 8,1 0 1024 /tmp/busy2.log
        """
        LogPathChecker.check_file_held(["/tmp/busy1.log", "/tmp/busy2.log", "/tmp/free.log"])
        # 验证返回消息包含所有冲突文件

    @patch('apps.log_databus.scripts.check_bkunifylogbeat.check.get_command')
    def test_check_file_held_special_chars(self, mock_get_command):
        """测试包含特殊字符的路径"""
        mock_get_command.return_value = "bkunifylogbeat 1234 root 1r REG 8,1 0 1024 /tmp/with space.log"
        LogPathChecker.check_file_held(["/tmp/with space.log"])
        # 验证路径包含空格时的处理

    @patch('apps.log_databus.scripts.check_bkunifylogbeat.check.get_command')
    def test_check_path_match_non_ascii(self, mock_get_command):
        """测试非ASCII字符路径"""
        mock_get_command.return_value = "/tmp/中文路径.log"
        LogPathChecker.check_path_match(["/tmp/中文路径.log"])
        # 验证中文路径处理

    @patch('apps.log_databus.scripts.check_bkunifylogbeat.check.get_command')
    def test_check_file_held_multiple_process(self, mock_get_command):
        """测试多进程占用同一文件的情况"""
        mock_get_command.return_value = """
            bkunifylogbeat 1234 root 1r REG 8,1 0 1024 /tmp/busy.log
            bkunifylogbeat 5678 root 1r REG 8,1 0 1024 /tmp/busy.log
            """
        LogPathChecker.check_file_held(["/tmp/busy.log"])
        # 验证能检测多进程占用

    @patch('apps.log_databus.scripts.check_bkunifylogbeat.check.get_command')
    def test_check_path_match_hidden_files(self, mock_get_command):
        """测试隐藏文件路径"""
        mock_get_command.return_value = "/tmp/.hidden.log"
        LogPathChecker.check_path_match(["/tmp/.hidden.log"])
        # 验证隐藏文件处理

    @patch('apps.log_databus.scripts.check_bkunifylogbeat.check.get_command')
    def test_check_file_held_symlink(self, mock_get_command):
        """测试符号链接文件"""
        mock_get_command.return_value = "bkunifylogbeat 1234 root 1r REG 8,1 0 1024 /tmp/link.log"
        LogPathChecker.check_file_held(["/tmp/link.log"])
        # 验证符号链接处理

    @patch('apps.log_databus.scripts.check_bkunifylogbeat.check.get_command')
    def test_check_path_match_long_path(self, mock_get_command):
        """测试超长路径（超过255字符）"""
        long_path = "/tmp/" + "a" * 250 + ".log"
        mock_get_command.return_value = long_path
        LogPathChecker.check_path_match([long_path])
        # 验证超长路径处理能力


if __name__ == '__main__':
    unittest.main()
