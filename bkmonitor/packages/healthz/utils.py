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


import abc
import logging
import random
import time

import six
from django.conf import settings
from django.utils.translation import ugettext as _
from kombu import Connection

from api.cmdb import client as cmdb_client
from bkmonitor.utils.healthz import deep_parsing_metric_info as _deep_parsing_metric_info
from bkmonitor.utils.request import get_request
from bkmonitor.utils.thread_backend import ThreadPool
from core.drf_resource import api
from healthz.healthz_test import (
    bk_data_test_cases,
    cc_test_cases,
    gse_test_cases,
    job_test_cases,
    metadata_test_cases,
    nodeman_test_cases,
)
from monitor.tasks import test_celery

logger = logging.getLogger("utils")


def monitor_time_elapsed(func):
    """
    用于监听函数运行时间的装饰器
    :param func:
    :return:
    """

    def wrapper(*args, **kwargs):
        start_time = time.time()
        logger.debug("the function %s starts", func.__name__)
        result = func(*args, **kwargs)
        logger.debug("the function %s ends", func.__name__)
        end_time = time.time()
        elapsed_time = end_time - start_time
        logger.debug("the function %s takes %s seconds", func.__name__, elapsed_time)
        return result

    return wrapper


class BaseHealthzChecker(six.with_metaclass(abc.ABCMeta, object)):
    """
    healthz checker的基类，其他的 checker 只需要继承自此类，然后将 name 和 category 赋值，并且实现 check 方法即可
    如果 checker 本身具有 solution ，则直接直接在 checker 中给出自身的 solution 即可
    如果 checker 有自定义的 clean 方法，可以先调用父类的 clean 方法，然后自定义其返回值即可
    """

    @abc.abstractproperty
    def name(self):
        raise NotImplementedError

    @abc.abstractmethod
    def check(self):
        raise NotImplementedError

    @abc.abstractmethod
    def category(self):
        raise NotImplementedError

    def __init__(self):
        self._api_list = []

    def clean_data(self):
        """
        用于清洗数据，给前端返回
        :return: data，清洗过后的数据
        """
        is_ok, details = self.check()
        data = {
            "collect_args": "{}",
            "collect_interval": 60,
            "solution": ((_("第三方组件%s异常") % self.name, _("请检查esb及对应组件服务是否正常")),),
            "result": {"status": 2, "message": "", "name": "", "value": None},
            "last_update": "2018-07-03 16:33:00+0800",
            "server_ip": "",
            "node_name": self.name,
            "description": self.name + _("状态"),
            "category": self.category,
            "collect_metric": self.name + ".status",
            "metric_alias": self.name + ".status",
        }
        data["result"] = {"status": 0 if is_ok else 2, "message": details, "name": data["metric_alias"], "value": None}
        data["solution"] = [
            {"reason": reason, "solution": solution} for reason, solution in getattr(self, "solution", data["solution"])
        ]
        return data

    def _find_children_list_of_api(self, api_name, test_cases):
        """
        查找依赖于 api_name 的接口
        :param api_name:
        :return:
        """
        for api_item, params in six.iteritems(test_cases):
            if api_name in params.get("dependencies", []):
                yield api_item, params["description"], params["args"]

    def _fill_self_api_list(self, test_cases):
        """
        解析 cc_test_cases 用于填充 api_list
        :return:
        """
        # 读取 cc_test_cases 将根 api 的 args 和其对应的子 api ，并填充到 api_list 中
        for base_api in test_cases:
            # 解析根接口
            if len(test_cases[base_api]["dependencies"]) == 0:
                self._api_list.append(
                    {
                        "api_name": base_api,
                        "description": _(test_cases[base_api]["description"]),
                        "children_api_list": [],
                        "results": {},
                        "args": test_cases[base_api]["args"],
                    }
                )
        # 根据依赖读取子接口
        for root_api in self._api_list:
            for child_api in self._find_children_list_of_api(root_api["api_name"], test_cases):
                root_api["children_api_list"].append(
                    {"api_name": child_api[0], "description": _(child_api[1]), "args": child_api[2], "results": {}}
                )


class CcHealthzChecker(BaseHealthzChecker):
    name = "cmdb"
    category = "esb"

    def check(self):
        """
        检查 cc_test_cases 是否为空
        :return:
        """
        if not cc_test_cases:
            return False, _("cc 不存在对应的测试用例")
        return True, "OK"

    @monitor_time_elapsed
    def clean_data(self):
        clean_data = super(CcHealthzChecker, self).clean_data()
        self._fill_self_api_list(cc_test_cases)
        clean_data["result"]["api_list"] = self._api_list
        return clean_data

    def test_root_api(self, method_name):
        """
        需要测试的根api名称
        :param method_name:
        :return:
        """
        request = get_request()
        # 获取到请求参数
        args = cc_test_cases.get(method_name, {}).get("args", None)
        if not args:
            args = {}
        args.update({"bk_biz_id": request.biz_id, "operator": request.user.username})
        self._fill_self_api_list(cc_test_cases)
        if not any([i["api_name"] == method_name for i in self._api_list]):
            return False, method_name, _("cc中不存在{method_name}").format(method_name=method_name), args, {}
        method_func = getattr(cmdb_client, method_name)
        try:
            result = method_func(args)
        except Exception as e:
            return False, method_name, str(e), args, {}
        return True, method_name, "OK", args, {"data": result}

    def test_non_root_api(self, api_name, parent_api, kwargs):
        """
        测试一个根api下的子api
        :param api_name: 要测试的api
        :param parent_api: 所依赖的api
        :param kwargs: 相关请求参数
        :return:
        """
        request = get_request()
        if parent_api not in cc_test_cases.get(api_name, {}).get("dependencies", []):
            return False, api_name, parent_api, _("接口不具有依赖关系"), kwargs, []
        method_func = getattr(cmdb_client, api_name, None)
        if not method_func:
            return False, api_name, parent_api, _("cc中没有此接口"), kwargs, []
        # 默认测试数据为2
        args = {}
        if cc_test_cases[api_name].get("args", None):
            args = cc_test_cases[api_name]["args"]
        args.update({"bk_biz_id": request.biz_id, "operator": request.user.username})
        if kwargs["data"]:
            args.update(kwargs["data"])

        try:
            result = method_func(args)
        except Exception as e:
            return False, api_name, parent_api, e, args, []
        return True, api_name, parent_api, "OK", args, list(result)


class NodemanHealthzChecker(BaseHealthzChecker):
    name = "nodeman"
    category = "esb"

    def check(self):
        """
        检查 nodeman_test_cases 是否为空
        :return:
        """
        if not nodeman_test_cases:
            return False, _("cc 不存在对应的测试用例")
        return True, "OK"

    @monitor_time_elapsed
    def clean_data(self):
        clean_data = super(NodemanHealthzChecker, self).clean_data()
        self._fill_self_api_list(nodeman_test_cases)
        clean_data["result"]["api_list"] = self._api_list
        return clean_data

    def test_root_api(self, method_name):
        """
        需要测试的根api名称
        :param method_name:
        :return:
        """
        request = get_request()
        # 获取到请求参数
        args = nodeman_test_cases.get(method_name, {}).get("args", None)
        if not args:
            args = {}
        args.update({"bk_biz_id": request.biz_id, "operator": request.user.username})
        self._fill_self_api_list(nodeman_test_cases)
        if not any([i["api_name"] == method_name for i in self._api_list]):
            return False, method_name, _("cc中不存在{method_name}").format(method_name=method_name), args, {}
        method_func = getattr(api.node_man, method_name)
        try:
            result = method_func(args)
        except Exception as e:
            return False, method_name, str(e), args, {}
        return True, method_name, "OK", args, {"data": result}

    def test_non_root_api(self, api_name, parent_api, kwargs):
        """
        测试一个根api下的子api
        :param api_name: 要测试的api
        :param parent_api: 所依赖的api
        :param kwargs: 相关请求参数
        :return:
        """
        request = get_request()
        if parent_api not in nodeman_test_cases.get(api_name, {}).get("dependencies", []):
            return False, api_name, parent_api, _("接口不具有依赖关系"), kwargs, []
        method_func = getattr(api.node_man, api_name, None)
        if not method_func:
            return False, api_name, parent_api, _("cc中没有此接口"), kwargs, []
        # 默认测试数据为2
        args = {}
        if nodeman_test_cases[api_name].get("args", None):
            args = nodeman_test_cases[api_name]["args"]
        args.update({"bk_biz_id": request.biz_id, "operator": request.user.username})
        if kwargs["data"]:
            args.update(kwargs["data"])

        try:
            result = method_func(args)
        except Exception as e:
            return False, api_name, parent_api, e, args, []
        return True, api_name, parent_api, "OK", args, list(result)


class MetadataHealthzChecker(BaseHealthzChecker):
    name = "metadata"
    category = "esb"

    def check(self):
        """
        检查 metadata_test_cases 是否为空
        :return:
        """
        if not metadata_test_cases:
            return False, _("cc 不存在对应的测试用例")
        return True, "OK"

    @monitor_time_elapsed
    def clean_data(self):
        clean_data = super(MetadataHealthzChecker, self).clean_data()
        self._fill_self_api_list(metadata_test_cases)
        clean_data["result"]["api_list"] = self._api_list
        return clean_data

    def test_root_api(self, method_name):
        """
        需要测试的根api名称
        :param method_name:
        :return:
        """
        request = get_request()
        # 获取到请求参数
        args = metadata_test_cases.get(method_name, {}).get("args", None)
        if not args:
            args = {}
        args.update({"bk_biz_id": request.biz_id, "operator": request.user.username})
        self._fill_self_api_list(metadata_test_cases)
        if not any([i["api_name"] == method_name for i in self._api_list]):
            return False, method_name, _("cc中不存在{method_name}").format(method_name=method_name), args, {}
        method_func = getattr(api.metadata, method_name)
        try:
            result = method_func(args)
        except Exception as e:
            return False, method_name, str(e), args, {}
        if method_name == "list_result_table":
            result = result[:2]
        return True, method_name, "OK", args, {"data": result}

    def test_non_root_api(self, api_name, parent_api, kwargs):
        """
        测试一个根api下的子api
        :param api_name: 要测试的api
        :param parent_api: 所依赖的api
        :param kwargs: 相关请求参数
        :return:
        """
        request = get_request()
        if parent_api not in metadata_test_cases.get(api_name, {}).get("dependencies", []):
            return False, api_name, parent_api, _("接口不具有依赖关系"), kwargs, []
        method_func = getattr(api.metadata, api_name, None)
        if not method_func:
            return False, api_name, parent_api, _("cc中没有此接口"), kwargs, []
        # 默认测试数据为2
        args = {}
        if metadata_test_cases[api_name].get("args", None):
            args = metadata_test_cases[api_name]["args"]
        args.update({"bk_biz_id": request.biz_id, "operator": request.user.username})
        if kwargs["data"]:
            args.update(kwargs["data"])

        try:
            result = method_func(args)
        except Exception as e:
            return False, api_name, parent_api, e, args, []
        return True, api_name, parent_api, "OK", args, list(result)


class GseHealthzChecker(BaseHealthzChecker):
    name = "gse"
    category = "esb"

    def check(self):
        """
        检查 gse_test_cases 是否为空
        :return:
        """
        if not gse_test_cases:
            return False, _("cc 不存在对应的测试用例")
        return True, "OK"

    @monitor_time_elapsed
    def clean_data(self):
        clean_data = super(GseHealthzChecker, self).clean_data()
        self._fill_self_api_list(gse_test_cases)
        clean_data["result"]["api_list"] = self._api_list
        return clean_data

    def test_root_api(self, method_name):
        """
        需要测试的根api名称
        :param method_name:
        :return:
        """
        request = get_request()
        # 获取到请求参数
        args = gse_test_cases.get(method_name, {}).get("args", None)
        if not args:
            args = {}
        args.update({"bk_biz_id": request.biz_id, "operator": request.user.username})
        self._fill_self_api_list(gse_test_cases)
        if not any([i["api_name"] == method_name for i in self._api_list]):
            return False, method_name, _("cc中不存在{method_name}").format(method_name=method_name), args, {}
        method_func = getattr(api.gse, method_name)
        # 特殊处理
        if method_name == "get_agent_status":
            hosts_result = api.cmdb.get_host_by_topo_node(bk_biz_id=args["bk_biz_id"])
            if hosts_result:
                host = hosts_result[0].bk_host_innerip
                bk_cloud_id = hosts_result[0].bk_cloud_id
                args.update({"hosts": [{"ip": host, "bk_cloud_id": bk_cloud_id}]})
        try:
            result = method_func(args)
        except Exception as e:
            return False, method_name, str(e), args, {}
        return True, method_name, "OK", args, {"data": result}

    def test_non_root_api(self, api_name, parent_api, kwargs):
        """
        测试一个根api下的子api
        :param api_name: 要测试的api
        :param parent_api: 所依赖的api
        :param kwargs: 相关请求参数
        :return:
        """
        request = get_request()
        if parent_api not in gse_test_cases.get(api_name, {}).get("dependencies", []):
            return False, api_name, parent_api, _("接口不具有依赖关系"), kwargs, []
        method_func = getattr(api.gse, api_name, None)
        if not method_func:
            return False, api_name, parent_api, _("cc中没有此接口"), kwargs, []
        # 默认测试数据为2
        args = {}
        if gse_test_cases[api_name].get("args", None):
            args = gse_test_cases[api_name]["args"]
        args.update({"bk_biz_id": request.biz_id, "operator": request.user.username})
        if kwargs["data"]:
            args.update(kwargs["data"])

        try:
            result = method_func(args)
        except Exception as e:
            return False, api_name, parent_api, e, args, []
        return True, api_name, parent_api, "OK", args, list(result)


class MysqlHealthzChecker(BaseHealthzChecker):
    name = "mysql"
    category = "esb"

    def check(self):
        from django.contrib.auth import get_user_model

        user_model = get_user_model()

        try:
            user_model.objects.filter(pk=1).exists()
        except Exception as e:
            return False, six.text_type(e)

        return True, "OK"


class JobHealthzChecker(BaseHealthzChecker):
    name = "job"
    category = "esb"

    def check(self):
        """
        检查 job_test_cases 是否为空
        :return:
        """
        if not job_test_cases:
            return False, _("job不存在对应的测试用例")
        # 检查是否存在 fast_execute_script 接口及其对应参数
        if not job_test_cases.get("fast_execute_script"):
            return False, _("job 中不存在接口 fast_execute_script 的相关参数")
        return True, "OK"

    @monitor_time_elapsed
    def clean_data(self):
        clean_data = super(JobHealthzChecker, self).clean_data()
        self._fill_self_api_list(job_test_cases)
        # 检查是否存在对应的主机列表，不存在的话，则不显示fast_execute_script接口
        request = get_request()
        if hasattr(request, "biz_id"):
            app_id = request.biz_id
        else:
            args = job_test_cases.get("fast_execute_script", {}).get("args", None)
            app_id = args["app_id"]
        try:
            hosts_result = api.cmdb.get_host_by_topo_node(bk_biz_id=app_id)
            # 如果没有主机数据，则需要删除fast_execute_script接口
            if not hosts_result:
                for index, item in enumerate(self._api_list):
                    if item.get("api_name") == "fast_execute_script":
                        del self._api_list[index]
                        break
        except Exception:
            pass
        clean_data["result"]["api_list"] = self._api_list
        return clean_data

    def test_root_api(self, method_name):
        """
        需要测试的根api名称
        :param method_name:
        :return: status: 运行状态
                 api_name: 测试的根节点名称
                 message: 具体信息
                 args: 请求参数
                 result: 返回结果
        """
        # 获取到全局的request
        request = get_request()
        # 填充 self.api_list
        self._fill_self_api_list(job_test_cases)
        # 获取到请求参数
        args = job_test_cases.get(method_name, {}).get("args", None)
        args.update({"bk_biz_id": request.biz_id, "operator": request.user.username})
        if not any([i["api_name"] == method_name for i in self._api_list]):
            return False, method_name, _("job中不存在{method_name}").format(method_name=method_name), args, {}
        method_func = getattr(api.job, method_name)
        # 执行脚本
        if method_name == "fast_execute_script":
            # 通过app_id获取到host地址，然后取第一个用于测试
            try:
                hosts_result = api.cmdb.get_host_by_topo_node(bk_biz_id=args["bk_biz_id"])
                if hosts_result:
                    host = hosts_result[0].bk_host_innerip
                    args.update({"ip": host, "ip_list": [{"ip": host, "bk_cloud_id": args["bk_cloud_id"]}]})
                else:
                    return False, method_name, _("查找业务下主机失败,主机查询结果:%s") % str(hosts_result), args, {}
            except Exception as e:
                return False, method_name, str(e), args, {}

        try:
            result = method_func(args)
        except Exception as e:
            return False, method_name, str(e), args, {}
        return True, method_name, "OK", args, {"data": result}

    def test_non_root_api(self, api_name, parent_api, kwargs):
        """
        测试一个根api下的子api
        :param api_name: 要测试的api
        :param parent_api: 所依赖的api
        :param kwargs: 相关请求参数
        :return:
        """
        # 获取到全局的request
        request = get_request()
        if parent_api not in job_test_cases.get(api_name, {}).get("dependencies", []):
            return False, api_name, parent_api, _("接口不具有依赖关系"), kwargs, []
        method_func = getattr(api.job, api_name, None)
        if not method_func:
            return False, api_name, parent_api, _("job中没有此接口"), kwargs, []
        # 默认测试数据为2
        args = {}
        if job_test_cases[api_name].get("args", None):
            args = job_test_cases[api_name]["args"]
        if kwargs["data"]:
            args.update(kwargs["data"])
        args.update({"bk_biz_id": request.biz_id, "operator": request.user.username})
        try:
            result = method_func(args)
        except Exception as e:
            return False, api_name, parent_api, str(e), args, []
        return True, api_name, parent_api, "OK", args, list(result)


class BkdataHealthzChecker(BaseHealthzChecker):
    name = "bk_data"
    category = "esb"

    def check(self):
        """
        检查 bk_data_test_cases 是否为空
        :return:
        """
        if not bk_data_test_cases:
            return False, _("bk_data中不存在对应的测试用例")
        return True, "OK"

    @monitor_time_elapsed
    def clean_data(self):
        clean_data = super(BkdataHealthzChecker, self).clean_data()
        self._fill_self_api_list(bk_data_test_cases)
        clean_data["result"]["api_list"] = self._api_list
        return clean_data

    def test_root_api(self, method_name):
        """
        需要测试的根api名称
        :param method_name:
        :return: status: 运行状态
                 api_name: 测试的根节点名称
                 message: 具体信息
                 args: 请求参数
                 result: 返回结果
        """
        # 获取到全局的request
        request = get_request()
        # 填充 self.api_list
        self._fill_self_api_list(bk_data_test_cases)
        # 获取到请求参数
        args = bk_data_test_cases.get(method_name, {}).get("args", None)
        args.update({"bk_biz_id": request.biz_id, "operator": request.user.username})
        if not any([i["api_name"] == method_name for i in self._api_list]):
            return False, method_name, _("job中不存在{method_name}").format(method_name=method_name), args, {}
        method_func = getattr(api.bkdata, method_name)
        try:
            result = method_func(args)
        except Exception as e:
            return False, method_name, str(e), args, {}
        # 针对一些接口特殊处理
        if method_name == "list_result_table":
            result = result[:2]
        return True, method_name, "OK", args, {"data": result}


class SaasCeleryChecker(BaseHealthzChecker):
    name = "saas_celery"
    category = "celery"
    solution = ((_("saas的celery状态阻塞"), _("重启saas的celery服务")),)

    @monitor_time_elapsed
    def check(self):
        # 检查celery的队列是否阻塞
        number = random.randint(1, 10)
        try:
            result = test_celery.delay(number)
            # 过期时间设置为2秒
            result.get(timeout=2)
            return True, "OK"
        except Exception as e:
            return False, six.text_type(e)


class RabbitmqHealthzChecker(BaseHealthzChecker):
    name = "rabbitmq"
    category = "rabbitmq"
    solution = (
        (_("rabbitmq服务未开启"), _("请检查服务[%s]是否启动") % settings.BROKER_URL),
        (_("账户无权限访问rabbitmq"), _("创建账户及v_host: %s") % settings.APP_CODE),
    )

    def check(self):

        try:
            conn = Connection(settings.BROKER_URL)
            conn.connect()
        except Exception as e:
            return False, six.text_type(e)

        return True, "OK"


@monitor_time_elapsed
def get_saas_healthz():
    def do_checker(checker):
        return checker.clean_data()

    metric_infos = []

    pool = ThreadPool()
    results = pool.map_ignore_exception(
        do_checker,
        (
            CcHealthzChecker(),
            JobHealthzChecker(),
            BkdataHealthzChecker(),
            NodemanHealthzChecker(),
            MetadataHealthzChecker(),
            GseHealthzChecker(),
            RabbitmqHealthzChecker(),
            SaasCeleryChecker(),
        ),
    )
    pool.close()
    pool.join()

    for result in results:
        if isinstance(result, list):
            metric_infos.extend(result)
        else:
            metric_infos.append(result)

    return metric_infos


deep_parsing_metric_info = monitor_time_elapsed(_deep_parsing_metric_info)
