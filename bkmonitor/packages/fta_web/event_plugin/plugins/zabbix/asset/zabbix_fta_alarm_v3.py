#!/usr/bin/env python
# -*- coding: utf-8 -*
import getopt
import json
import logging
import socket
import ssl
import sys
import time

# python3 compatibility
try:
    import urllib2 as request
except Exception:
    from urllib import request

try:
    from urlparse import urlparse  # noqa
except Exception:
    from urllib.parse import urlparse

# python2 encoding compatibility
try:
    reload(sys)  # noqa
    sys.setdefaultencoding("utf-8")
except Exception:
    pass

LOG_FORMAT = "[%(asctime)s] %(levelname)s %(name)s: %(message)s"
LOG_FILE = "/tmp/zabbix_fta_alarm.log"
logging.basicConfig()
LOG = logging.getLogger("fta")

try:
    ssl._create_default_https_context = ssl._create_unverified_context
except AttributeError as e:
    LOG.info("ssl set _create_unverified_https_context error %s " % e)
    pass

VERSION = "v3.X"
FTA_SECERT = "{{ plugin.token }}"
FTA_URL = "{{ plugin.ingest_config.push_url }}"
PARAM = int("7")
STATUS_ABNORMAL = "ABNORMAL"
HOST_TARGET_TYPE = "HOST"

# 告警消息体
ACTION_MESSAGE_BODY = """
========================
HOST.IP: {HOST.IP}
HOST.HOST: {HOST.HOST}
HOST.DESCRIPTION: {HOST.DESCRIPTION}
ITEM.ID: {ITEM.ID}
ITEM.KEY: {ITEM.KEY}
ITEM.VALUE: {ITEM.VALUE}
ITEM.NAME: {ITEM.NAME}
ITEM.DESCRIPTION: {ITEM.DESCRIPTION}
TRIGGER.ID: {TRIGGER.ID}
TRIGGER.NAME: {TRIGGER.NAME}
TRIGGER.EXPRESSION: {TRIGGER.EXPRESSION}
TRIGGER.DESCRIPTION: {TRIGGER.DESCRIPTION}
TRIGGER.URL: {TRIGGER.URL}
TRIGGER.SEVERITY: {TRIGGER.SEVERITY}
TRIGGER.STATUS: {TRIGGER.STATUS}
TRIGGER.NSEVERITY: {TRIGGER.NSEVERITY}
EVENT.ID: {EVENT.ID}
EVENT.TIME: {EVENT.TIME}
EVENT.DATE: {EVENT.DATE}
EVENT.VALUE: {EVENT.VALUE}
EVENT.NAME: {EVENT.NAME}
ACTION.ID: {ACTION.ID}
ACTION.NAME: {ACTION.NAME}
========================
"""


def _setup_logging(verbose=None, filename=None):
    """
    设置日志级别
    """
    if verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO

    logging.basicConfig(format=LOG_FORMAT, level=level, filename=filename)


def force_bytes(s, encoding="utf-8", strings_only=False, errors="strict"):
    if isinstance(s, bytes):
        if encoding == "utf-8":
            return s
        else:
            return s.decode("utf-8", errors).encode(encoding, errors)
    return s.encode(encoding, errors)


def force_str(s, encoding="utf-8", strings_only=False, errors="strict"):
    if issubclass(type(s), str):
        return s

    if isinstance(s, bytes):
        s = str(s, encoding, errors)
    else:
        s = str(s)

    return s


def http_post(url, data, resp_fmt="json"):
    """
    POST方法封装
    data is dict or string
    """
    st = time.time()

    if isinstance(data, dict):
        data = json.dumps(data)
    data = force_bytes(data)

    LOG.debug("curl -X POST '%s' -d '%s' -H 'Content-Type: application/json'", url, data)

    req = request.Request(url, data=data, headers={"Content-Type": "application/json", "X-Bk-Fta-Token": FTA_SECERT})
    resp = request.urlopen(req, timeout=5).read()
    LOG.debug("RESP: %.2fms %s", (time.time() - st) * 1000, resp)
    if resp_fmt == "json":
        resp = json.loads(resp)
    return resp


def get_local_ip():
    """
    当告警目标为本机时，获取本机IP
    @return:
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    finally:
        s.close()

    return ip


class APIError(Exception):
    pass


class ZabbixApi(object):
    def __init__(self, parse_url, user, password):
        self.parse_url = parse_url
        self.user = user
        self.password = password
        self.url = "{}://{}{}".format(parse_url.scheme, parse_url.netloc, parse_url.path or "")

        self.auth_token = None
        self.userid = None
        self.mediatypeid = None
        self.usrgrpid = 7  # Zabbix administrators

        self.script_name = "zabbix_fta_alarm.py"
        self.media_name = "FTA_Event_Handler"
        self.user_name = "FTA_Mgr"
        self.action_name = "FTA_Act"

    def user_login(self):
        """
        用户登录，获取token
        """
        payload = {
            "jsonrpc": "2.0",
            "method": "user.login",
            "params": {"user": self.user, "password": self.password},
            "id": 1,
            "auth": None,
        }
        resp = http_post(self.url, data=payload)
        token = resp.get("result")
        LOG.info("get auth token: %s" % token)
        if not token:
            raise APIError("Zabbix account password is incorrect, please enter the administrator account password")
        self.auth_token = token

    def mediatype_get(self):
        """
        获取以前老的mediatype
        """
        payload = {
            "jsonrpc": "2.0",
            "method": "mediatype.get",
            "params": {
                "output": "mediatypeid",
                "filter": {"description": self.media_name},
            },
            "auth": self.auth_token,
            "id": 1,
        }
        resp = http_post(self.url, data=payload)
        LOG.info(u"mediatype_get success: %s", resp)
        return [i["mediatypeid"] for i in resp["result"]]

    def mediatype_delete(self, media_type_ids):
        """
        删除mediatype
        """
        payload = {
            "jsonrpc": "2.0",
            "method": "mediatype.delete",
            "params": media_type_ids,
            "auth": self.auth_token,
            "id": 1,
        }
        resp = http_post(self.url, data=payload)
        LOG.info(u"mediatype_delete success: %s", resp)

    def mediatype_create(self):
        """
        创建脚本
        """
        exec_params = [
            # '{ALERT.SUBJECT}',
            "{ALERT.MESSAGE}",
        ]
        payload = {
            "jsonrpc": "2.0",
            "method": "mediatype.create",
            "params": {
                "description": self.media_name,
                "exec_path": self.script_name,
                "exec_params": "\r\n".join(exec_params) + "\r\n",
                "type": 1,  # script type
                "status": 0,  # enable default
            },
            "auth": self.auth_token,
            "id": 1,
        }
        resp = http_post(self.url, data=payload)
        LOG.info("mediatype_create success: %s", resp)
        self.mediatypeid = resp["result"]["mediatypeids"][0]

    def user_get(self):
        """
        获取以前老的mediatype
        """
        payload = {
            "jsonrpc": "2.0",
            "method": "user.get",
            "params": {
                "output": "userid",
                "filter": {"alias": self.user_name},
            },
            "auth": self.auth_token,
            "id": 1,
        }
        resp = http_post(self.url, data=payload)
        LOG.info(u"user_get success: %s", resp)
        return [i["userid"] for i in resp["result"]]

    def user_delete(self, user_ids):
        """
        删除mediatype
        """
        payload = {"jsonrpc": "2.0", "method": "user.delete", "params": user_ids, "auth": self.auth_token, "id": 1}
        resp = http_post(self.url, data=payload)
        LOG.info(u"user_delete success: %s", resp)

    def user_create(self):
        """创建FTA用户"""
        payload = {
            "jsonrpc": "2.0",
            "method": "user.create",
            "params": {
                "alias": self.user_name,
                "name": self.user_name,
                "surname": self.user_name,
                "passwd": self.password,
                "type": 3,  # Zabbix super admin
                "usrgrps": [{"usrgrpid": self.usrgrpid}],
                "user_medias": [
                    {
                        "mediatypeid": self.mediatypeid,
                        "sendto": self.user_name,
                        "active": 0,
                        "severity": 63,  # all severity
                        "period": "1-7,00:00-24:00",
                    }
                ],
            },
            "auth": self.auth_token,
            "id": 1,
        }
        resp = http_post(self.url, data=payload)
        LOG.info(u"user_create success: %s", resp)
        self.userid = resp["result"]["userids"][0]

    def action_get(self):
        payload = {
            "jsonrpc": "2.0",
            "method": "action.get",
            "params": {
                "output": "actionids",
                "filter": {"name": self.action_name},
            },
            "auth": self.auth_token,
            "id": 1,
        }
        resp = http_post(self.url, data=payload)
        LOG.info(u"action_get success: %s", resp)
        return [i["actionid"] for i in resp["result"]]

    def action_delete(self, action_ids):
        """
        删除mediatype
        """
        payload = {"jsonrpc": "2.0", "method": "action.delete", "params": action_ids, "auth": self.auth_token, "id": 1}
        resp = http_post(self.url, data=payload)
        LOG.info(u"action_delete success: %s", resp)

    def action_create(self):
        """创建触发器"""
        payload = {
            "jsonrpc": "2.0",
            "method": "action.create",
            "params": {
                "name": self.action_name,
                "eventsource": 0,
                "status": 0,
                "esc_period": 3600,
                "def_shortdata": self.action_name + " {TRIGGER.NAME}: {TRIGGER.STATUS}",
                "def_longdata": ACTION_MESSAGE_BODY,
                "filter": {
                    "evaltype": 0,  # and/or
                    "conditions": [
                        {
                            "conditiontype": 16,  # version 3.x is Maintenance status,4.0 is Problem is suppressed
                            "operator": PARAM,  # not in or No
                            "value": "",  # must be empty
                        },
                        # zabbix 3.2/3.4 don't have trigger value
                        # {
                        #     "conditiontype": 5,  # trigger value
                        #     "operator": 0,  # =
                        #     "value": 1  # problem
                        # }
                    ],
                },
                "operations": [
                    {
                        "operationtype": 0,  # send message
                        "esc_period": 0,
                        "esc_step_from": 1,
                        "esc_step_to": 1,
                        "evaltype": 0,
                        "opmessage_usr": [{"userid": self.userid}],
                        "opmessage": {"default_msg": 1, "mediatypeid": self.mediatypeid},
                    }
                ],
            },
            "auth": self.auth_token,
            "id": 1,
        }
        resp = http_post(self.url, data=payload)
        LOG.info(u"action_create success: %s", resp)

    def clean(self):
        """清理数据"""
        action_ids = self.action_get()
        if action_ids:
            self.action_delete(action_ids)

        user_ids = self.user_get()
        if user_ids:
            self.user_delete(user_ids)

        media_type_ids = self.mediatype_get()
        if media_type_ids:
            self.mediatype_delete(media_type_ids)


class Event(object):

    # def __init__(self, message, format="base64"):
    def __init__(self, message):
        self.message = message
        # self.format = format

    def parse(self, data):
        alarm = {}
        data = data.strip("=\r\n ")
        # 格式化数据
        for line in data.splitlines():

            try:
                key, value = line.split(":", 1)
            except Exception as error:
                LOG.info(u"parse line {} error: {}, just ignore.".format(line, error))
                continue

            key = key.strip()
            value = value.strip()
            alarm[key] = value
        return alarm

    def clean_alert_name(self, alarm):
        """
        获取告警名称
        @return: 事件名称
        """
        return alarm["EVENT.NAME"]

    def clean_event_id(self, alarm):
        """
        获取事件ID
        @return: 监控项ID-触发器ID-动作ID-事件ID
        """
        return "{}-{}-{}-{}".format(alarm["ITEM.ID"], alarm["TRIGGER.ID"], alarm["ACTION.ID"], alarm["EVENT.ID"])

    def clean_description(self, alarm):
        """
        获取描述：
        @return: 监控项名称: 监控项取得值
        """
        return alarm["TRIGGER.DESCRIPTION"]

    def clean_metric(self, alarm):
        """
        获取指标
        @return: 监控项key
        """
        return alarm["ITEM.KEY"]

    def clean_category(self, alarm):
        """
        获取分类
        @return:
        """
        # TODO: 获取分类
        pass

    def clean_target_type(self, alarm):
        """
        获取告警类型
        :return: "HOST"
        """
        return HOST_TARGET_TYPE

    def clean_target(self, alarm):
        """
        获取告警ip，如果是本机ip则获取本机外网ip
        :return:
        """
        target = alarm["HOST.IP"]
        if target == "127.0.0.1":
            return get_local_ip()
        return target

    def clean_severity(self, alarm):
        severity = alarm["TRIGGER.NSEVERITY"]
        if severity == 1 | 0:
            return 3
        elif severity == 2:
            return 2
        else:
            return 1

    def clean_bk_biz_id(self, alarm):
        pass

    def clean_tags(self, alarm):
        return alarm

    def clean_assignee(self, alarm):
        pass

    def clean_time(self, alarm):
        return time.time()

    def clean_anomaly_time(self, alarm):
        datetime = "{} {}".format(alarm["EVENT.DATE"], alarm["EVENT.TIME"])
        # 转换成时间数组
        time_array = time.strptime(datetime, "%Y.%m.%d %H:%M:%S")
        # 转换成时间戳
        return time.mktime(time_array)

    def clean_status(self, alarm):
        status = alarm.get("TRIGGER.STATUS", STATUS_ABNORMAL)
        return status

    def clean_data(self):
        alarm = self.parse(self.message)

        # 告警名称
        alert_name = self.clean_alert_name(alarm)
        # 事件ID
        event_id = self.clean_event_id(alarm)
        # 描述
        description = self.clean_description(alarm)
        # 指标项
        metric = self.clean_metric(alarm)
        # 分类
        category = self.clean_category(alarm)
        # 目标类型
        target_type = self.clean_target_type(alarm)
        # 目标
        target = self.clean_target(alarm)
        # 级别
        severity = self.clean_severity(alarm)
        # 业务ID
        bk_biz_id = self.clean_bk_biz_id(alarm)
        # 标签
        tags = self.clean_tags(alarm)
        # 受理人
        assignee = self.clean_assignee(alarm)
        # 事件事件
        time = self.clean_time(alarm)
        # 异常时间
        anomaly_time = self.clean_anomaly_time(alarm)
        # 状态
        status = self.clean_status(alarm)

        data = {
            "alert_name": alert_name,
            "event_id": event_id,
            "description": description,
            "metric": metric,
            "category": category,
            "target_type": target_type,
            "target": target,
            "severity": severity,
            "bk_biz_id": bk_biz_id,
            "tags": tags,
            "assignee": assignee,
            "time": time,
            "anomaly_time": anomaly_time,
            "status": status,
        }
        return data

    def send(self):
        """消息处理函数"""
        data = self.clean_data()
        resp = http_post(FTA_URL, data=data, resp_fmt=None)
        LOG.info(u"send alarm resp: %s", resp)


def launcher(init, verbose, params):

    if init:
        _setup_logging(verbose)
        # params[0] is api host
        # params[1] is api user
        # params[2] is api password
        # 注意文件权限

        if len(params) < 3:
            raise APIError(
                "Incorrect initialization parameters, enter the Zabbix API address,"
                " administrator account, administrator account password in order"
            )
        # 校验URL
        parse_url = urlparse(params[0])
        if parse_url.scheme not in ["http", "https"] or not parse_url.netloc:
            raise APIError("Zabbix API ({}) address is incorrect".format(params[0]))

        api_client = ZabbixApi(parse_url, params[1], params[2])
        api_client.user_login()

        api_client.clean()

        api_client.mediatype_create()
        api_client.user_create()
        api_client.action_create()
    else:
        # params[0] is {ALERT.MESSAGE}
        _setup_logging(True, filename=LOG_FILE)
        event = Event(params[0])
        event.send()


USAGE = """
usage: zabbix_fta_alarm.py [-h] [--init] [--verbose] params [params ...]

Blueking FTA Application

positional arguments:
  params         zabbix params

optional arguments:
  -h, --help     show this help message and exit
  --init         init zabbix action config
  --verbose, -v  verbose mode
"""


def usage():
    print(USAGE.strip())


def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hv", ["help", "verbose", "init"])
    except getopt.GetoptError as err:
        print(err)
        usage()
        sys.exit(2)

    init = False
    verbose = False

    for o, a in opts:
        if o in ("-h", "--help"):
            usage()
            sys.exit(0)
        elif o in ("-v", "--verbose"):
            verbose = True
        elif o in ("--init",):
            init = True
        else:
            print(u"unhandled option, ({}, {})".format(o, a))
            sys.exit(2)

    if not args:
        usage()
        sys.exit(2)

    try:
        launcher(init, verbose, args)
    except APIError as error:
        # 安装提示错误
        LOG.error(u"%s", error)
    except Exception:
        LOG.exception("fta script error")
        sys.exit(1)


if __name__ == "__main__":
    main()
