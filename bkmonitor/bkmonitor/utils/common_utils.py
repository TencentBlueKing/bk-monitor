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

import base64
import datetime
import decimal
import hashlib
import inspect
import json
import logging
import math
import os
import pkgutil
import re
import socket
import traceback
import uuid
from collections import OrderedDict, defaultdict
from contextlib import contextmanager
from io import StringIO
from pipes import quote
from typing import Dict, List, Union
from zipfile import ZipFile

from django.conf import settings
from django.utils.encoding import force_text
from django.utils.functional import Promise
from django.utils.timezone import is_aware
from django.utils.translation import ugettext as _
from six.moves import map, range

from bkmonitor.utils import time_tools
from bkmonitor.utils.text import camel_to_underscore
from constants.cmdb import BIZ_ID_FIELD_NAMES
from constants.result_table import RT_RESERVED_WORD_EXACT, RT_RESERVED_WORD_FUZZY
from core.errors import ErrorDetails
from core.errors.dataapi import TSDBParseError

logger = logging.getLogger(__name__)


def package_contents(package):
    if isinstance(package, str):
        return package_contents(__import__(package, fromlist=[str("*")]))
    return [name for _, name, _ in pkgutil.iter_modules([os.path.dirname(package.__file__)])]


class DictObj(object):
    __non_zero = False

    def __init__(self, kwargs=None):
        if kwargs is None:
            kwargs = dict()
        self.__dict__.update(kwargs)
        for k, v in kwargs.items():
            if not self.__non_zero:
                self.__non_zero = True
            try:
                setattr(self, k, v)
            except AttributeError:
                msg = "[%s] attribute: `%s` has already exists, " "check your class definition `@property`" % (
                    self.__class__.__name__,
                    k,
                )
                raise AttributeError(msg)

    def __str__(self):
        return json.dumps(self.__dict__)

    def __getattr__(self, item):
        return None

    def __bool__(self):
        return self.__non_zero


class DatetimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return time_tools.strftime_local(obj)
        elif isinstance(obj, datetime.date):
            return obj.strftime("%Y-%m-%d")
        elif isinstance(obj, datetime.time):
            if is_aware(obj):
                raise ValueError("JSON can't represent timezone-aware times.")
            r = obj.isoformat()
            if obj.microsecond:
                r = r[:12]
            return r
        if isinstance(obj, decimal.Decimal):
            return str(obj)
        if isinstance(obj, set):
            return list(obj)
        if isinstance(obj, Promise):
            return force_text(obj)
        if issubclass(obj.__class__, DictObj):
            return obj.__dict__
        if isinstance(obj, bytes):
            return obj.decode("utf-8")
        return json.JSONEncoder.default(self, obj)


@contextmanager
def ignored(*exceptions, **kwargs):
    try:
        yield
    except exceptions:
        if kwargs.get("log_exception", True):
            logger.warning(traceback.format_exc())
        pass


def _host_key(host_info):
    """
    机器唯一标识
    :param host_info: 至少包含的key：InnerIP Source
    :return:
    """
    assert (
        "InnerIP" in host_info and "Source" in host_info
    ), '"InnerIP" in host_info and "Source" in host_info return false'
    # if host_info["Source"] == "0":
    #     host_info["Source"] = "1"
    return "{}|{}".format(host_info["InnerIP"], host_info["Source"])


def parse_host_id(host_id):
    # 针对只有ip的情况
    host_split = host_id.split("|")
    ip, plat_id = host_split if len(host_split) > 1 else (host_split[-1], "0")
    return ip, plat_id


def to_host_id(host_info):
    ip = host_info["ip"]
    bk_cloud_id = host_info.get("bk_cloud_id")
    if bk_cloud_id is None:
        bk_cloud_id = host_info.get("plat_id", "0")
    return f"{ip}|{bk_cloud_id}"


def ok(message="", **options):
    result = {"result": True, "message": message, "msg": message}
    result.update(**options)
    return result


def failed(message="", error_code=None, error_name=None, exc_type=None, popup_type=None, **options):
    """
    生成标准化错误响应字典
    :param message: 错误信息，可以是任何类型。它将被转换为字符串。
    :param error_code 错误编码
    :param error_name 错误名称
    :param exc_type 错误类型
    :param popup_type 弹窗类型（danger为红框，warn为黄框）
    :param options: 附加的键值对，将包含在响应字典中。

    :return: 包含错误响应的字典，键包括：'code' 'name' 'result', 'message', 'data', 'msg' 'error_details'。
    """
    if not isinstance(message, str):
        if isinstance(message, str):
            message = message.encode("utf-8")
        message = str(message)
    result = {
        "code": error_code,
        "name": error_name,
        "result": False,
        "message": message,
        "data": {},
        "msg": message,
        "error_details": ErrorDetails(
            exc_type=exc_type,
            exc_code=error_code,
            overview=message,
            detail=message,
            popup_message=popup_type if popup_type else "warning",  # 默认均为warn
        ).to_dict(),
    }
    result.update(**options)
    return result


def failed_data(message, data, **options):
    if not isinstance(message, str):
        if isinstance(message, str):
            message = message.encode("utf-8")
        message = str(message)
    result = {"result": False, "message": message, "data": data, "msg": message}
    result.update(**options)
    return result


def ok_data(data=None, **options):
    if data is None:
        data = {}
    result = {"result": True, "message": "", "data": data, "msg": ""}
    result.update(**options)
    return result


def href_link(text, href):
    return """<a href="{}">{}</a>""".format(href, text)


def strip(obj):
    if isinstance(obj, dict):
        return {key: strip(value) for key, value in list(obj.items())}
    elif isinstance(obj, list):
        return [strip(item) for item in obj]
    elif isinstance(obj, str):
        return obj.strip()
    else:
        return obj


def convert_textarea_to_list(ips):
    return ips.replace("\r\n", "\n").split("\n")


def base_hostindex_id_to_page_id(_id):
    alarm_type = safe_int(_id)
    if alarm_type <= 10**4:
        return alarm_type + 10**4
    return alarm_type


def page_id_to_base_hostindex_id(_id):
    alarm_type = safe_int(_id)
    if alarm_type >= 10**4:
        return int(alarm_type) - 10**4
    return _id


def is_base_hostindex(_id):
    return safe_int(_id) > 10**4


def check_permission(obj, request_cc_biz_id):
    cc_biz_id = fetch_biz_id_from_obj(obj)
    if cc_biz_id and int(cc_biz_id) != int(request_cc_biz_id):
        logger.exception(
            "权限不通过！ 当前请求的业务ID为{}，而对象[{}]({})所属业务ID为{}".format(
                request_cc_biz_id, obj.__class__.__name__, obj.pk, cc_biz_id
            )
        )
        return False
    return True


def filter_alarms(alarms, params):
    filter_alarm_list = []
    for alarm in alarms:
        hit = True
        for k, v in list(params.items()):
            if k in alarm.dimensions:
                if v and v != str(alarm.dimensions[k]):
                    hit = False
            else:
                if v:
                    hit = False
        if hit:
            filter_alarm_list.append(alarm)
    return filter_alarm_list


def get_unique_list(_list):
    """
    list去重，并保持原有数据顺序
    :param _list:
    :return:
    """
    return list(OrderedDict.fromkeys(_list))


def today_start_timestamp(the_day=None):
    if the_day is None:
        the_day = datetime.date.today()
    if isinstance(the_day, datetime.datetime):
        the_day = the_day.date()
    days = (the_day - datetime.date(1970, 1, 1)).days
    return days * 3600 * 24 * 1000


def dict_slice(adict, start, end):
    """
    字典切片
    :param adict:
    :param start:
    :param end:
    """
    keys = list(adict.keys())
    dict_slice = {}
    for k in keys[start:end]:
        dict_slice[k] = adict[k]
    return dict_slice


def to_page(data, index):
    """
    分页函数
    :param data:
    :return:
    """
    new_dict = {}
    if not data:
        new_dict.update({"page": 0})
        new_dict.update({"data": data})
        return new_dict

    total = len(data)  # 总数
    pagesize = 10  # 每页个数
    start = (int(index) - 1) * pagesize  # 起始数
    end = total if total - start < pagesize else start + pagesize  # 结束
    new_data = data[start:end]
    page = math.ceil(float(total) / float(pagesize))  # 页数
    new_dict.update({"data": new_data})
    new_dict.update({"page": page})
    new_dict.update({"total": total})

    return new_dict


def parse_tsdb_rt(result_table_id, table_name="", has_biz_id=True):
    """
    解析tsdb数据结构
    :param result_table_id: rt表
    :return:
    """
    sep = "_"
    if not has_biz_id:
        result_table_id = "0{}{}".format(sep, result_table_id)
    try:
        if table_name:
            item_list = result_table_id[: result_table_id.rfind(table_name) - 1].split(sep)
            cc_biz_id = safe_int(item_list[0])
            db_category = sep.join(item_list[1:])
        else:
            item_list = result_table_id.split(sep)
            cc_biz_id = safe_int(item_list[0])
            db_category = item_list[1]
            table_name = sep.join(item_list[2:])
        return cc_biz_id, db_category, table_name
    except Exception:
        raise TSDBParseError(rt_id=result_table_id)


def gen_tsdb_rt(biz_id, db_name, table_name):
    assert "_" not in db_name, _("tsdb库名不支持下划线")
    return "_".join(map(str, [biz_id, db_name, table_name]))


def get_metric_fields(result_table):
    """
    :param result_table_id:
    :return:
    """
    return [f["field"] for f in result_table["fields"] if f["field"] != "timestamp" and not f["is_dimension"]]


def get_first(objs, default=""):
    """get the first element in a list or get blank"""
    if len(objs) > 0:
        return objs[0]
    return default


def get_list(obj):
    return obj if isinstance(obj, list) else [obj]


def get_one(obj):
    return obj[0] if isinstance(obj, (list, tuple)) else obj


def uniqid():
    # 不带横杠
    return uuid.uuid3(uuid.uuid1(), uuid.uuid4().hex).hex


def uniqid4():
    # 带横杠
    return str(uuid.uuid4())


def check_rt_reserved_word(word):
    """
    检查RT表名或字段名称是否存在保留字
    :param word: 需要检查的名称
    :return 是否通过校验
    """

    # 精确匹配保留字
    if word.upper() in RT_RESERVED_WORD_EXACT:
        return False

    # 模糊匹配保留字
    return not [w for w in RT_RESERVED_WORD_FUZZY if w in word.upper()]


def file_read(filename):
    """
    打开utf-8编码文件
    """
    with open(filename) as f:
        return f.read().decode("utf-8")


def file_md5sum(file):
    """
    计算文件的md5值
    """
    # 文件指针指向开头
    file.seek(0, 0)

    md5 = hashlib.md5()
    for chunk in file.chunks():
        md5.update(chunk)

    file.seek(0, 0)
    return md5.hexdigest()


def file_rename(file, new_file_name=None):
    """
    文件重命名，保留后缀
    :param file: 文件
    :param new_file_name: 新文件名，没有则默认取文件的md5
    :return: 新文件名
    """
    new_file_name = new_file_name or file_md5sum(file)
    ext = ""
    if "." in file.name:
        ext = file.name.split(".")[-1]

    if ext:
        new_file_name = "{}.{}".format(new_file_name, ext)
    return new_file_name


def tree():
    return defaultdict(tree)


def _count_md5(content):
    if content is None:
        return None
    m2 = hashlib.md5()
    if isinstance(content, str):
        m2.update(content.encode("utf8"))
    else:
        m2.update(content)
    return m2.hexdigest()


def count_md5(content, dict_sort=True, list_sort=True):
    if dict_sort and isinstance(content, dict):
        # dict的顺序受到hash的影响，所以这里先排序再计算MD5
        return count_md5(
            [(str(k), count_md5(content[k], dict_sort, list_sort)) for k in sorted(content.keys())],
            dict_sort,
            list_sort,
        )
    elif isinstance(content, (list, tuple)):
        content = (
            sorted([count_md5(k, dict_sort) for k in content])
            if list_sort
            else [count_md5(k, dict_sort, list_sort) for k in content]
        )
    elif callable(content):
        return make_callable_hash(content)
    return _count_md5(str(content))


def make_callable_hash(content):
    """
    计算callable的hash
    """
    if inspect.isclass(content):
        h = []
        for attr in [i for i in sorted(dir(content)) if not i.startswith("__")]:
            v = getattr(content, attr)
            h.append(count_md5(v))

        return _count_md5("".join(h))
    try:
        return _count_md5(content.__name__)
    except AttributeError:
        try:
            return _count_md5(content.func.__name__)
        except AttributeError:
            return _count_md5(str(content))


def get_md5(content):
    if isinstance(content, list):
        return [count_md5(c) for c in content]
    else:
        return count_md5(content)


REG_SPLIT_LIST = re.compile(r"\s*[;,]\s*")


def split_list(raw_string):
    if isinstance(raw_string, (tuple, list, set)):
        return raw_string
    return [x for x in REG_SPLIT_LIST.split(raw_string) if x]


def get_local_ip():
    """
    Returns the actual ip of the local machine.
    This code figures out what source address would be used if some traffic
    were to be sent out to some well known address on the Internet. In this
    case, a Google DNS server is used, but the specific address does not
    matter much.  No traffic is actually sent.

    stackoverflow上有人说用socket.gethostbyname(socket.getfqdn())
    但实测后发现有些机器会返回127.0.0.1
    """
    try:
        csock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        csock.connect(("8.8.8.8", 80))
        (addr, port) = csock.getsockname()
        csock.close()
        return addr
    except socket.error:
        return "127.0.0.1"


def number_format(v):
    try:
        # 字符型转为数值型 其他保持不变
        if isinstance(v, str):
            if v.find(".") > -1:
                try:
                    return float(v)
                except:  # noqa
                    return v
            else:
                try:
                    return int(v)
                except:  # noqa
                    return v
        elif v:
            return v
        else:
            return 0
    except Exception as e:
        raise Exception(e)


def convert_to_cmdline_args_str(kv_dict):
    """
    命令行参数组装
    :param kv_dict: 参数key-value对
    {
        "version": None,
        "-s": "xxx",
        "--some": "yyy",
    }
    :return:
    """
    result = ""
    for k, v in list(kv_dict.items()):
        if v:
            # 进行shell转义
            v = quote(v)
        else:
            v = ""
        if k.startswith("--"):
            result += "{}={} ".format(k, v)
        else:
            result += "{} {} ".format(k, v)
    return result


def escape_cmd_argument(arg):
    # Escape the argument for the cmd.exe shell.
    # First we escape the quote chars to produce a argument suitable for
    # CommandLineToArgvW. We don't need to do this for simple arguments.

    # if not arg or re.search(r'(["\s])', arg):
    #     arg = '"' + arg.replace('"', r'\"') + '"'

    meta_chars = '()%!^"<>&|'
    meta_re = re.compile("(" + "|".join(re.escape(char) for char in list(meta_chars)) + ")")
    meta_map = {char: "^%s" % char for char in meta_chars}

    def escape_meta_chars(m):
        char = m.group(1)
        return meta_map[char]

    return meta_re.sub(escape_meta_chars, arg)


def extract_zip(input_zip):
    """
    解压文件，获取文件列表
    """
    input_zip = ZipFile(input_zip)
    return {name: StringIO(input_zip.read(name).decode("utf8")) for name in input_zip.namelist()}


def gen_bk_data_rt_id_without_biz_id(table_id):
    """
    计算平台表名只能是50个字节，需要进行截断
    """
    if table_id.endswith("__default__"):
        table_id = table_id.split(".__default__")[0]
    rt_id = "{}_{}".format(settings.BK_DATA_RT_ID_PREFIX, table_id.replace(".", "_"))[-32:].lower()
    return rt_id.strip("_")


def to_bk_data_rt_id(table_id, suffix=None):
    if not table_id:
        return

    prefix_list = [str(settings.BK_DATA_BK_BIZ_ID), gen_bk_data_rt_id_without_biz_id(table_id)]
    if suffix:
        prefix_list.append(str(suffix))

    return "_".join(prefix_list)


def convert_img_to_base64(image, format="PNG"):
    """
    :param image: Image图片对象
    :param format: 保存格式
    :return: base64 string
    """
    img_buffer = StringIO()
    image.save(img_buffer, format=format, quality=95)
    base64_value = base64.b64encode(img_buffer.getvalue().encode("utf8"))
    return "data:image/{format};base64,{value}".format(format=format.lower(), value=base64_value)


def fetch_biz_id_from_dict(data, default=None):
    """
    从字典对象中提取出biz_id属性
    """
    if not hasattr(data, "__getitem__"):
        return default

    with ignored(Exception):
        for field in data:
            if field in BIZ_ID_FIELD_NAMES:
                return str(data[field])
    return default


def fetch_biz_id_from_obj(obj):
    """
    从实例对象中提取出biz_id属性
    """
    with ignored(Exception):
        for field in BIZ_ID_FIELD_NAMES:
            if hasattr(obj, field):
                return str(getattr(obj, field))
    return None


def parse_filter_condition_dict(settings_condition_item, filter_key):
    if "method" in settings_condition_item:
        filter_key = "{}__{}".format(filter_key, settings_condition_item["method"])
    if "sql_statement" not in settings_condition_item:
        return None, None
    return filter_key, settings_condition_item["sql_statement"]


def safe_int(int_str, dft=0):
    try:
        int_val = int(int_str)
    except Exception:
        try:
            int_val = int(float(int_str))
        except Exception:
            int_val = dft
    return int_val


def safe_float(value):
    try:
        return float(value)
    except (ValueError, TypeError):
        return float("nan")


def proxy(obj):
    class Proxy(object):
        def __getattribute__(self, item):
            return getattr(obj, item)

    return Proxy()


# create a new context for this task
ctx = decimal.Context()

# 20 digits should be enough for everyone :D
ctx.prec = 20


def float_to_str(f):
    """
    Convert the given float to a string,
    without resorting to scientific notation
    """
    d1 = ctx.create_decimal(repr(f))
    return format(d1, "f")


def host_key(host_info=None, ip="", plat_id="", bk_cloud_id=""):
    if host_info is None:
        assert ip and (str(plat_id) or str(bk_cloud_id)), "ip and plat_id return false"
        host_info = {"InnerIP": str(ip), "Source": str(plat_id) or str(bk_cloud_id)}
    return _host_key(host_info)


def fetch_biz_id_from_request(request, view_kwargs):
    # 业务id解析方式：
    # 1. url带上业务id（monitor_adapter）
    biz_id = fetch_biz_id_from_dict(view_kwargs)
    if not biz_id:
        # 2. request.GET (resource的get方法)
        # 3. request.POST (未改造成resource的ajax的post方法)
        biz_id = fetch_biz_id_from_dict(request.POST) or fetch_biz_id_from_dict(request.GET)

    if not biz_id:
        # 4. request.body(resource的post方法)
        try:
            body_unicode = request.body.decode("utf-8")
            body = json.loads(body_unicode)
            biz_id = fetch_biz_id_from_dict(body)
        except Exception:
            pass
    return biz_id


def to_dict(obj):
    """
    python 对象递归转成字典
    """
    if isinstance(obj, dict):
        data = {}
        for k, v in list(obj.items()):
            data[k] = to_dict(v)
        return data
    elif hasattr(obj, "__iter__") and not isinstance(obj, str):
        return [to_dict(v) for v in obj]
    elif hasattr(obj, "__dict__"):
        data = {}
        for key in dir(obj):
            value = getattr(obj, key)
            if not key.startswith("_") and not callable(value):
                data[key] = to_dict(value)
        return data
    else:
        return obj


def replce_special_val(s, replace_dict):
    """
    替换特殊变量
    :param s: 待替换字符串
    :param replace_dict: 替换映射
    :return: 替换结果
    """
    for key, value in replace_dict.items():
        s = s.replace(key, value)
    return s


def chunks(data, n):
    """分隔数组 ."""
    return (data[i : i + n] for i in range(0, len(data), n))


def camel_obj_key_to_underscore(obj: Union[List, Dict, str]) -> object:
    """将一个对象中包含的字典的key全部转换为下划线格式 ."""
    if isinstance(obj, str):
        return camel_to_underscore(obj)
    if isinstance(obj, dict):
        new_obj = {}
        for key, value in obj.items():
            if isinstance(value, (list, dict)):
                value = camel_obj_key_to_underscore(value)
            if isinstance(key, str):
                new_obj[camel_to_underscore(key)] = value
            else:
                new_obj[key] = value
        return new_obj
    new_obj = []
    if isinstance(obj, list):
        for value in obj:
            if isinstance(value, dict):
                value = camel_obj_key_to_underscore(value)
            new_obj.append(value)
            return new_obj
    return obj
