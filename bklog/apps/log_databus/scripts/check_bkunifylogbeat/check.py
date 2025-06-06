#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import glob
import os
import subprocess
import sys
from optparse import OptionParser
import datetime
import platform
import json

MODULE_BKUNIFYLOGBEAT = "bkunifylogbeat"
MODULE_GSEAGENT = "gse_agent"
MODULE_LOG_PATH = "log_path"

STEP_CHECK_LOG_PATH_LOGPATH_MATCH = "logpath_match"
STEP_CHECK_LOG_PATH_LOGPATH_HELD = "logpath_held"

STEP_CHECK_BKUNIFYLOGBEAT_BIN_FILE = "bin_file"
STEP_CHECK_BKUNIFYLOGBEAT_PROCESS = "process"
STEP_CHECK_BKUNIFYLOGBEAT_MAIN_CONFIG = "main_config"
STEP_CHECK_BKUNIFYLOGBEAT_CONFIG = "config"
STEP_CHECK_BKUNIFYLOGBEAT_HOSTED = "hosted"
STEP_CHECK_BKUNIFYLOGBEAT_PATH_PATTERN = "path_pattern"
STEP_CHECK_BKUNIFYLOGBEAT_HEALTHZ = "healthz"

STEP_CHECK_GSEAGENT_PROCESS = "process"
STEP_CHECK_GSEAGENT_SOCKET = "socket"
STEP_CHECK_GSEAGENT_SOCKET_QUEUE_STATUS = "socket_queue_status"
STEP_CHECK_GSEAGENT_DATASERVER_PORT = "dataserver_port"

COLLECTOR_MAIN_CONFIG_FILE_NAME = "bkunifylogbeat.conf"

DATASERVER_PORT = "58625"

subscription_id = 0
collector_config_id = 0
socket_between_gse_agent_and_beat = "/var/run/ipc.state.report"
gse_path = "/usr/local/gse/"
collector_bin_path = os.path.join(gse_path, "plugins/bin", MODULE_BKUNIFYLOGBEAT)
collector_etc_main_config_path = os.path.join(gse_path, "plugins/etc", COLLECTOR_MAIN_CONFIG_FILE_NAME)
collector_etc_path = os.path.join(gse_path, "plugins/etc", MODULE_BKUNIFYLOGBEAT)
procinfo_file_path = os.path.join(gse_path, "agent/etc/procinfo.json")
config_name_suffix = "%s_sub_" % MODULE_BKUNIFYLOGBEAT

check_result = {"status": False, "data": []}


def convert_to_str(t):
    if platform.python_version()[0] == "3":
        if isinstance(t, bytes):
            return t.decode("utf-8")
    return t


def get_command(cmd):
    ps = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output = ps.stdout.read()
    ps.stdout.close()
    ps.wait()
    return convert_to_str(output).strip()


class Result(object):
    def __init__(self, module, item, status=False, message=""):
        self.module = module
        self.item = item
        self.status = status
        self.message = message

    def add_to_result(self):
        d = {
            "module": self.module,
            "item": self.item,
            "status": self.status,
            "message": self.message,
        }
        global check_result
        check_result["data"].append(d)


class LogPathChecker(object):

    @staticmethod
    def check_path_match(log_paths=None):
        result = Result(MODULE_LOG_PATH, STEP_CHECK_LOG_PATH_LOGPATH_MATCH)
        if not log_paths:
            result.message = "日志采集路径为空"
            result.add_to_result()
            return
        paths = log_paths.split(",") if isinstance(log_paths, str) else log_paths
        missing_paths = []
        existing_files = []
        for path in paths:
            cmd = "ls -d -- {}".format(path)
            ls_output = get_command(cmd)
            files = ls_output.splitlines()
            if files:
                existing_files.extend(files)
            else:
                missing_paths.append(path)
        if missing_paths:
            result.message = "以下路径无匹配文件: {}".format(", ".join(missing_paths))
            if existing_files:
                result.message += "\n已存在的文件:\n{}".format("\n".join(existing_files[:10]))
            result.add_to_result()
            return
        result.status = True
        result.message = "所有路径检查通过" + (
            "\n匹配到的文件:\n{}".format("\n".join(existing_files[:10]))
            if existing_files
            else ""
        )
        result.add_to_result()

    @staticmethod
    def check_file_held(log_paths=None):
        result = Result(MODULE_LOG_PATH, STEP_CHECK_LOG_PATH_LOGPATH_HELD)
        if not log_paths:
            result.message = "日志采集路径为空"
            result.add_to_result()
            return
        # 原有逻辑
        lsof_output = get_command("lsof -c {}".format(MODULE_BKUNIFYLOGBEAT))
        held_files = set(line.split()[-1] for line in lsof_output.splitlines() if line.strip())
        check_paths = log_paths.split(",") if isinstance(log_paths, str) else log_paths
        matched_files = sum((glob.glob(path) for path in check_paths), [])
        conflict_files = [f for f in matched_files if f in held_files]
        if conflict_files:
            result.message = "文件被占用: {}".format(", ".join(conflict_files))
        else:
            result.status = True
            result.message = "无文件占用冲突"
        result.add_to_result()


class BKUnifyLogBeatCheck(object):
    def __init__(self):
        self.subscription_id = subscription_id

    @staticmethod
    def check_bin_file():
        result = Result(MODULE_BKUNIFYLOGBEAT, STEP_CHECK_BKUNIFYLOGBEAT_BIN_FILE)
        if os.path.exists(collector_bin_path):
            result.status = True
        result.add_to_result()

    @staticmethod
    def check_process():
        result = Result(MODULE_BKUNIFYLOGBEAT, STEP_CHECK_BKUNIFYLOGBEAT_PROCESS)
        output = get_command("ps -ef | grep bkunifylogbeat | awk '{print $2}' | xargs pwdx")
        if gse_path not in str(output):
            result.message = "bkunifylogbeat is not running"
            result.add_to_result()
            return

        pid_to_dir = [line.split(":") for line in output.split("\n") if line.strip()]
        pid = pid_to_dir[0][0]
        for pid_dir in pid_to_dir:
            pid, bin_dir = pid_dir
            if bin_dir.strip().startswith(gse_path):
                break

        # 是否频繁重启
        restart_times = 10
        restart_records_file = "/tmp/bkc.log"
        today = datetime.datetime.now().strftime("%Y%m%d")
        output = get_command(
            "cat {0} | grep {1} | grep {2} | wc -l".format(restart_records_file, today, MODULE_BKUNIFYLOGBEAT)
        )
        if not output or int(output) > restart_times:
            result.message = "restart/reload times is over %d" % restart_times
            result.add_to_result()
            return

        # 当前资源
        cpu_usage = get_command("ps aux | grep %s | awk '{print $3}' | head -n 1" % pid)
        mem_usage = get_command("ps aux | grep %s | awk '{print $4}' | head -n 1" % pid)
        result.message = "cpu_usage: {0}%, mem_usage: {1}%".format(str(cpu_usage), str(mem_usage))
        result.status = True
        result.add_to_result()

    @staticmethod
    def check_main_config():
        result = Result(MODULE_BKUNIFYLOGBEAT, STEP_CHECK_BKUNIFYLOGBEAT_MAIN_CONFIG)
        if not os.path.exists(collector_etc_main_config_path):
            result.message = "main config file is not exists"
            result.add_to_result()
            return

        output = get_command(
            "sed -n '/^bkunifylogbeat.multi_config/,/^$/p' %s | grep path | awk -F: '{print $2}'"
            % collector_etc_main_config_path
        )
        output = output.replace(" ", "")
        path_list = output.split("\n")
        if collector_etc_path not in path_list:
            result.message = "multi_config not have path [{0}]".format(collector_etc_main_config_path)
            result.add_to_result()
            return

        result.status = True
        result.add_to_result()

    @staticmethod
    def check_config():
        result = Result(MODULE_BKUNIFYLOGBEAT, STEP_CHECK_BKUNIFYLOGBEAT_CONFIG)
        real_config_name = ""
        g = os.walk(collector_etc_path)
        for path, dir_list, file_list in g:
            for file_name in file_list:
                config_name_suffix_with_subscription_id = "%s%d" % (config_name_suffix, subscription_id)
                if config_name_suffix_with_subscription_id in file_name:
                    real_config_name = file_name
                    result.message = "real_config_name: %s" % real_config_name
                    break
        if real_config_name:
            result.status = True
        result.add_to_result()

    @staticmethod
    def check_gseagent_hosted():
        result = Result(MODULE_BKUNIFYLOGBEAT, STEP_CHECK_BKUNIFYLOGBEAT_HOSTED)
        output = get_command("cat {0} | grep {1}".format(procinfo_file_path, MODULE_BKUNIFYLOGBEAT))
        if MODULE_BKUNIFYLOGBEAT in str(output):
            result.status = True
        result.add_to_result()

    @staticmethod
    def check_collector_healthz():
        result = Result(MODULE_BKUNIFYLOGBEAT, STEP_CHECK_BKUNIFYLOGBEAT_HEALTHZ)
        result.message = get_command("%s healthz" % collector_bin_path)
        result.status = True
        result.add_to_result()


class GseAgentCheck(object):
    @staticmethod
    def check_process():
        result = Result(MODULE_GSEAGENT, STEP_CHECK_GSEAGENT_PROCESS)
        output = get_command("netstat -antulp | grep %s | grep LISTEN | awk '{print $7}'" % MODULE_GSEAGENT)
        if MODULE_GSEAGENT in str(output):
            result.status = True
        result.add_to_result()

    @staticmethod
    def check_socket_between_gse_agent_and_beat():
        result = Result(MODULE_GSEAGENT, STEP_CHECK_GSEAGENT_SOCKET)
        if os.path.exists(socket_between_gse_agent_and_beat):
            result.status = True
        result.add_to_result()

    @staticmethod
    def check_socket():
        result = Result(MODULE_GSEAGENT, STEP_CHECK_GSEAGENT_SOCKET_QUEUE_STATUS)
        output = get_command("ss -x -p | grep -E 'REC|%s' |awk '{print $6}'" % socket_between_gse_agent_and_beat)
        if not output:
            result.message = "socket not used"
            result.add_to_result()
            return
        port = output.split("-")[-1]
        queue_status = get_command("ss -x -p | grep -E 'Rec|%s' |awk 'NR>1{print $3;print $4}'" % port)
        queue_status = list(map(int, queue_status.split("\n")))
        if any(queue_status):
            result.message = "socket queue blocking"
            result.add_to_result()
            return
        result.status = True
        result.add_to_result()

    @staticmethod
    def check_dataserver():
        result = Result(MODULE_GSEAGENT, STEP_CHECK_GSEAGENT_DATASERVER_PORT)
        output = get_command("netstat -anplut | grep %s" % DATASERVER_PORT)
        if not output:
            result.message = "dataserver not exist"
            result.add_to_result()
            return
        result.status = True
        result.add_to_result()


def _get_opt_parser():
    """get option parser"""
    opt_parser = OptionParser()

    opt_parser.add_option(
        "-p", "--gse_path", action="store", type="string", dest="path", help="""gse_path""", default=""
    )

    opt_parser.add_option(
        "-s",
        "--subscription_id",
        action="store",
        type="int",
        dest="subscription_id",
        help="""subscription_id""",
        default=subscription_id,
    )

    opt_parser.add_option(
        "-i",
        "--ipc_socket_file",
        action="store",
        type="string",
        dest="ipc_socket_file",
        help="""ipc_socket_file""",
        default=socket_between_gse_agent_and_beat,
    )

    opt_parser.add_option(
        "-c",
        "--collector_config_id",
        action="store",
        type="int",
        dest="collector_config_id",
        help="""采集配置ID""",
        default=0,
    )

    opt_parser.add_option(
        "-l",
        "--log_paths",
        action="store",
        type="string",
        dest="log_paths",
        help="""采集路径，多个路径用逗号分隔""",
        default="",
    )

    return opt_parser


def arg_parse():
    global gse_path
    global subscription_id
    global socket_between_gse_agent_and_beat
    global collector_bin_path
    global collector_etc_main_config_path
    global collector_etc_path
    global procinfo_file_path
    global log_paths
    global collector_config_id

    parser = _get_opt_parser()
    (options, args) = parser.parse_args(sys.argv)

    if options.path:
        gse_path = options.path
        collector_bin_path = os.path.join(gse_path, "plugins/bin", MODULE_BKUNIFYLOGBEAT)
        collector_etc_main_config_path = os.path.join(gse_path, "plugins/etc", COLLECTOR_MAIN_CONFIG_FILE_NAME)
        collector_etc_path = os.path.join(gse_path, "plugins/etc", MODULE_BKUNIFYLOGBEAT)
        procinfo_file_path = os.path.join(gse_path, "agent/etc/procinfo.json")
    if options.subscription_id:
        subscription_id = options.subscription_id
    if options.ipc_socket_file:
        socket_between_gse_agent_and_beat = options.ipc_socket_file
    if options.collector_config_id:
        collector_config_id = options.collector_config_id
    log_paths = []
    if options.log_paths and options.log_paths.strip():
        log_paths = options.log_paths.split(",")


def main():
    arg_parse()
    global log_paths
    # 新增路径检查
    if log_paths:
        logpath_checker = LogPathChecker()
        logpath_checker.check_path_match(log_paths)
        logpath_checker.check_file_held(log_paths)

    global subscription_id
    if subscription_id:
        bkunifylogbeat_checker = BKUnifyLogBeatCheck()
        bkunifylogbeat_checker.check_bin_file()
        bkunifylogbeat_checker.check_process()
        bkunifylogbeat_checker.check_main_config()
        bkunifylogbeat_checker.check_config()
        bkunifylogbeat_checker.check_gseagent_hosted()
        bkunifylogbeat_checker.check_collector_healthz()

    gse_agent_checker = GseAgentCheck()
    gse_agent_checker.check_process()
    gse_agent_checker.check_socket_between_gse_agent_and_beat()
    gse_agent_checker.check_socket()
    gse_agent_checker.check_dataserver()

    global check_result
    if all([i["status"] for i in check_result["data"]]):
        check_result["status"] = True

    print(json.dumps(check_result))


if __name__ == "__main__":
    main()
