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


import inspect
import logging
from contextlib import contextmanager
from importlib import import_module

from django.conf import settings
from django.utils.module_loading import import_string

from bkmonitor.utils.text import camel_to_underscore, path_to_dotted
from core.drf_resource.base import Resource
from core.drf_resource.management.exceptions import (
    ResourceModuleConflict,
    ResourceModuleNotRegistered,
    ResourceNotRegistered,
)
from core.drf_resource.management.finder import API_DIR, ResourceFinder

logger = logging.getLogger(__name__)


__setup__ = False
__doc__ = """
自动发现项目下resource和adapter和api
    cc
    ├── adapter
    │   ├── default.py
    │       ├── community
    │       │       └── resources.py
    │       └── enterprise
    │           └── resources.py
    └── resources.py
    使用:
        # api: 代表基于ESB/APIGW调用的接口调用
        # api.$module.$api_name
            api.bkdata.query_data -> api/bkdata/default.py: QueryDataResource
        # resource: 基于业务逻辑的封装
        resource.plugin -> plugin/resources.py
            resource.plugin.install_plugin -> plugin/resources.py: InstallPluginResource
        # adapter: 针对不同版本的逻辑差异进行的封装
        adapter.cc -> cc/adapter/default.py -> cc/adapter/${platform}/resources.py
        # 调用adapter.cc 即可访问对应文件下的resource，
        # 如果在${platform}/resources.py里面有相同定义，会重载default.py下的resource
    """


@contextmanager
def _lazy_load(_instance):
    if not _instance.loaded:
        getattr(_instance, "_setup", lambda: None)()
    yield _instance


def lazy_load(func):
    def wrapper(resource_module_instance, *args, **kwargs):
        with _lazy_load(resource_module_instance):
            return func(resource_module_instance, *args, **kwargs)

    return wrapper


class ResourceShortcut(object):
    _package_pool = {}

    _entry = "resources"

    def __new__(cls, module_path):
        def init_instance(self, m_path):
            if not m_path.endswith(self._entry):
                m_path += ".{}".format(self._entry)
            self._path = m_path
            self._package = None
            self._methods = {}
            self.loaded = False
            # 新增单元测试 patch 支持
            self.__deleted_methods = {}

        if module_path not in cls._package_pool:
            instance = object.__new__(cls)
            init_instance(instance, module_path)
            cls._package_pool[module_path] = instance
        return cls._package_pool[module_path]

    def __init__(self, module_path):
        # init in __new__ function
        pass

    def __getitem__(self, x):
        # delete _entry(replace once from right)
        path = "".join(self._path.rsplit(self._entry, 1)).strip(".")
        dotted_path = path.split(".")
        if not isinstance(x, slice):
            return dotted_path[x]
        rm = resource
        while dotted_path[:-1]:
            rm = getattr(rm, dotted_path.pop(0))
        return tuple(rm)

    def _setup(self):
        try:
            self._package = import_module(self._path)
        except ImportError as e:
            raise ImportError("resource called before {} setup. detail: {}".format(self._path, e))
        for name, obj in list(self._package.__dict__.items()):
            if name.startswith("_"):
                continue

            if inspect.isabstract(obj):
                continue

            if inspect.isclass(obj) and issubclass(obj, Resource):
                cleaned_name = "".join(name.rsplit("Resource", 1)) if name.endswith("Resource") else name
                property_name = camel_to_underscore(cleaned_name)
                setattr(self, property_name, obj())
                self._methods[property_name] = obj

            if inspect.isfunction(obj):
                setattr(self, name, obj)
                self._methods[name] = obj

        self.loaded = True

    def __delattr__(self, name):
        if name in self._methods:
            self.__deleted_methods[name] = self._methods.pop(name)
        super(ResourceShortcut, self).__delattr__(name)

    @lazy_load
    def __getattr__(self, item):
        if item in self._methods:
            return getattr(self, item)
        try:
            return ResourceShortcut(import_module("{}.{}".format(self._path, item)).__name__)
        except ImportError:
            try:
                return import_string("{}.{}".format(self._path, item))
            except ImportError:
                if item in self.__deleted_methods:
                    return self.__deleted_methods[item]
                raise ResourceNotRegistered("Resource {} not in [{}]".format(item, self._package.__name__))

    @lazy_load
    def list_method(self):
        return list(self._methods.keys())

    def reload_method(self, method, func):
        setattr(self, method, func)
        self._methods[method] = func


class AdapterResourceShortcut(ResourceShortcut):
    _entry = "adapter.default"
    _package_pool = {}


class APIResourceShortcut(ResourceShortcut):
    _entry = "default"
    _package_pool = {}


class ResourceManager(tuple):
    __parent__ = None

    def __contains__(self, item):
        return item is not None and (self is item or item[: len(self)] == self)

    def __getattr__(self, name):
        if __setup__:
            got = getattr(self.transform(), name, None)
            if got is None:
                raise ResourceModuleNotRegistered(
                    'module: "%s" is not registered, maybe not in `INSTALLED_APPS` ?' % name
                )
            return got

        new = ResourceManager(self + (name,))
        setattr(self, name, new)
        new.__parent__ = self
        return new

    def __repr__(self):
        return "resource" + ("." if self else "") + ".".join(self)

    def __bool__(self):
        return bool(len(self))

    @property
    def __root__(self):
        target = self
        while target.__parent__ is not None:
            target = target.__parent__
        return target

    def transform(self):
        """make the little tuple instance get stronger(callable) ^_^"""
        func_finder = self.__root__
        for attr in self:
            func_finder = getattr(func_finder, attr)

        if isinstance(func_finder, self.__class__):
            return None
            # raise Exception("func called before resource setup."
            #                 " detail: %s" % str(self))

        return func_finder

    def __call__(self, *args, **kwargs):
        return self.transform()(*args, **kwargs)


def setup():
    global __setup__
    if __setup__:
        return

    finder = ResourceFinder()
    for path in finder.resource_path:
        install_resource(path)

    __setup__ = True
    resource.__finder__ = finder


def install_resource(rs_path):
    dotted_path = rs_path.path
    _resource = None
    endpoint = None

    # adapter, api
    if is_api(dotted_path) or is_adapter(dotted_path):
        return install_adapter(rs_path)

    # resource
    for p in dotted_path.split("."):
        if isinstance(_resource, ResourceShortcut):
            logger.debug("ignored: {}".format(dotted_path))
            rs_path.ignored()
            return
        _resource = getattr(_resource or resource, p)
        endpoint = p

    if _resource:
        try:
            resource_module = ResourceShortcut(".".join(_resource))
            logger.debug("success: {}".format(dotted_path))
            rs_path.loaded()
        except ResourceNotRegistered:
            logger.warning("failed: {}".format(dotted_path))
            rs_path.error()
            return

        # register shortcut
        shortcut = getattr(resource, endpoint)
        if isinstance(shortcut, ResourceShortcut):
            raise ResourceModuleConflict(
                "resources conflict:\n>>> {}\n<<< {}".format(shortcut._path, ".".join(_resource))
            )
        setattr(_resource.__parent__, endpoint, resource_module)
        setattr(resource, endpoint, resource_module)


def install_adapter(rs_path):
    dotted_path = rs_path.path
    adapter_cls = AdapterResourceShortcut
    # adapter 和 api 代码结构一致， 唯一区别是entry不同，adapter多了一层`adapter`目录
    if is_api(dotted_path):
        api_root = path_to_dotted(API_DIR)
        result = dotted_path[(len(API_DIR) + 1) :].split(".", 1)
        if len(result) == 2:
            rs, ada = result
        else:
            rs = result[0]
            ada = ""
        rs = "{}.{}".format(api_root, rs)
        adapter_cls = APIResourceShortcut
    else:
        rs, ada = [path.strip(".") for path in dotted_path.split("adapter")]

    try:
        default_adapter = adapter_cls(rs)
        defined_method = default_adapter.list_method()
    except ImportError as e:
        logger.warning("error: {}\n{}".format(dotted_path, e))
        rs_path.error()
        return

    if ada.startswith(settings.PLATFORM):
        platform_adapter = ResourceShortcut(dotted_path)
        # load method from platform adapter to default adapter
        for method in defined_method:
            if method in platform_adapter.list_method():
                default_adapter.reload_method(method, getattr(platform_adapter, method))

    root = adapter
    if is_api(dotted_path):
        root = api
    setattr(root, rs.split(".")[-1], default_adapter)
    logger.debug("success: {}".format(dotted_path))
    rs_path.loaded()


def is_api(dotted_path):
    return dotted_path.startswith(path_to_dotted(API_DIR))


def is_adapter(dotted_path):
    return "adapter" in dotted_path.split(".")


resource = ResourceManager()

adapter = ResourceManager()

api = ResourceManager()
