"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

"""
生成前端API调用函数
"""

import abc
import os
from collections import namedtuple
from importlib import import_module

import six
from django.conf import settings
from django.template import engines
from rest_framework.reverse import reverse
from rest_framework.viewsets import GenericViewSet, ModelViewSet

from bkmonitor.utils.common_utils import uniqid
from bkmonitor.utils.text import camel_to_underscore, underscore_to_camel
from core.drf_resource.routers import ResourceRouter
from core.drf_resource.tools import (
    get_serializer_fields,
    get_underscore_viewset_name,
    render_schema,
)
from core.drf_resource.viewsets import ResourceViewSet
from core.drf_resource.viewsets import ResourceViewSet as OldResourceViewSet

django_engine = engines["django"]

TEMPLATE = """{% autoescape off %}/**
 * @module: resource.js 
 * @author: 蓝鲸智云
 * @create: Auto generated at {% now 'Y-m-d H:i:s' %}
 */

const localCache = {};

const BaseRestAPI = function (method, url, data, options, async) {
  // 所有请求默认加上bk_biz_id
  if (data) {
    if (!data.bk_biz_id && data.bk_biz_id !== 0) {
      data.bk_biz_id = window.cc_biz_id;
    }
  } else {
    data = {
      bk_biz_id: window.cc_biz_id,
    };
  }
  let allOptions = {
    type: method,
    url: window.site_url + url,
    dataType: "json",
  };

  if (async) {
    allOptions.headers = {
      "X-Async-Task": true,
    };
  }

  allOptions = Object.assign(allOptions, options);
  if (method === "GET") {
    allOptions.data = data;
  } else {
    let isFile = false;
    for (const key in data) {
      const type = String(data[key]);
      if (type === "[object FileList]" || type === "[object File]") {
        isFile = true;
        break;
      }
    }

    if (isFile) {
      const formData = new FormData();
      for (const key in data) {
        formData.append(key, data[key]);
      }
      allOptions.data = formData;
      allOptions.contentType = "multipart/form-data";
      allOptions.processData = false;
      allOptions.contentType = false;
    } else {
      allOptions.data = JSON.stringify(data);
      allOptions.contentType = "application/json";
    }
  }
  const cacheKey = `${url}|${method}|${JSON.stringify(data)}`;

  if (cacheKey in localCache && options && options.cache === true) {
    return localCache[cacheKey];
  } else {
    localCache[cacheKey] = window.$.ajax(allOptions);
    return localCache[cacheKey];
  }
};

/*
  列表类型的API
 */
const RestListAPI = function (method, url) {
  const restAPI = function (data, options) {
    return BaseRestAPI(method, url, data, options);
  };
  restAPI.polling = function (data, callBack, options) {
    return BaseRestAPI(method, url, data, options, true).then(function (
      result
    ) {
      if (result.result) {
        const polling = function () {
          Resource.commons
            .queryAsyncTaskResult(result.data)
            .done(function (pollingResult) {
              if (pollingResult.result) {
                const taskData = pollingResult.data;
                callBack &&
                  callBack(
                    taskData.is_completed,
                    taskData.state,
                    taskData.data,
                    taskData.message
                  );
                if (!taskData.is_completed) {
                  // 若任务未完成，1秒后再次轮询
                  setTimeout(polling, 1000);
                }
              } else {
                // 异常处理
                // eslint-disable-next-line standard/no-callback-literal
                callBack &&
                  callBack(
                    true,
                    "FAILURE",
                    pollingResult.data,
                    pollingResult.message
                  );
              }
            });
        };
        polling();
      } else {
        // 异常处理
        // eslint-disable-next-line standard/no-callback-literal
        callBack && callBack(true, "FAILURE", result.data, result.message);
      }
    });
  };
  return restAPI;
};

/*
  详情类型的API，需要替换掉URL字符串模版中的"{pk}"，以生成合法的URL
 */
const RestDetailAPI = function (method, url) {
  const restAPI = function (id, data, options) {
    const requestURL = url.replace("{pk}", id);
    return BaseRestAPI(method, requestURL, data, options);
  };
  restAPI.polling = function (id, data, callBack, options) {
    const requestURL = url.replace("{pk}", id);
    return BaseRestAPI(method, requestURL, data, options, true).then(function (
      result
    ) {
      if (result.result) {
        const polling = function () {
          Resource.commons
            .queryAsyncTaskResult(result.data)
            .done(function (pollingResult) {
              if (pollingResult.result) {
                const taskData = pollingResult.data;
                callBack &&
                  callBack(
                    taskData.is_completed,
                    taskData.state,
                    taskData.data,
                    taskData.message
                  );
                if (!taskData.is_completed) {
                  setTimeout(polling, 1000);
                }
              } else {
                // 异常处理
                callBack &&
                  callBack(
                    true,
                    "FAILURE",
                    pollingResult.data,
                    pollingResult.message
                  );
              }
            });
        };
        polling();
      } else {
        // 异常处理
        callBack && callBack(true, "FAILURE", result.data, result.message);
      }
    });
  };

  return restAPI;
};

/* Resource API */
const Resource = {
{% for module in resource_modules %}
  {{ module.name }}: {
    {% for resource in module.resources %}
    /**
     * {% if resource.api_description %}@apiDescription {{ resource.api_description | safe }}{% endif %}
     * @api { {{ resource.method }} } {{ resource.url }} {{ resource.api_name }}
     * @apiName {{ resource.api_name }}
     * @apiGroup {{ module.name }}
     {% for param in resource.params.request_params %}* @apiParam {{ param }}
     {% endfor %}*
     {% for param in resource.params.response_params %}* @apiSuccess {{ param }}
     {% endfor %}*
    */
    {{ resource.function_name }}: {% if resource.is_detail %}RestDetailAPI{% else %}RestListAPI{% endif %}('{{ resource.method }}', '{{ resource.request_url | safe }}'),
    {% endfor %}
  },
{% endfor %}
}


/* Model API */
const Model = {
{% for model in models %}
  {{ model.name }}: {
    {% for method in model.methods %}
    /**
     * {% if method.api_description %}@apiDescription {{ method.api_description | safe }}{% endif %}
     * @api { {{ method.method }} } {{ method.url }} {{ method.api_name }}
     * @apiName {{ method.api_name }}
     * @apiGroup {{ model.name }}
     {% for param in method.params %}* @apiParam {{ param }}
     {% endfor %}*
    */
    {{ method.function_name }}: {% if method.is_detail %}RestDetailAPI{% else %}RestListAPI{% endif %}('{{ method.method }}', '{{ method.request_url | safe }}'),
    {% endfor %}
  },
{% endfor %}
}

export {
  Model,
  Resource
}
{% endautoescape %}
"""  # noqa

NEW_TEMPLATE = """import { request } from '../base';

{% for resource in resources %}export const {{ resource.function_name }} = request('{{ resource.method }}', '{{ resource.request_url | safe }}');
{% endfor %}
export default {{% for resource in resources %}\n  {{ resource.function_name }},{% endfor %}
};
"""  # noqa

template = django_engine.from_string(TEMPLATE)
new_template = django_engine.from_string(NEW_TEMPLATE)


def generate_new_js_api(resource_modules, models):
    model_module = {"name": "model", "resources": []}

    for model in models:
        for method in model["methods"]:
            method["function_name"] = method["function_name"] + model["name"][0].upper() + model["name"][1:]
            model_module["resources"].append(method)

    resource_modules.append(model_module)

    for module in resource_modules:
        if module["resources"]:
            code = new_template.render({"resources": module["resources"]})
            file_path = os.path.join(
                settings.PROJECT_ROOT, "webpack", "src", "monitor-api", "modules", module["name"] + ".js"
            )
            with open(file_path, "w+", encoding="utf-8") as fp:
                fp.write(code)


def generate_js_api():
    """
    主入口
    """
    resource_modules = []
    models = []
    for app_name, view_modules in list(settings.ACTIVE_VIEWS.items()):
        for view_name, view_path in list(view_modules.items()):
            views = import_module(view_path)
            resource_context, model_context = _generate_js_api_by_module(views, app_name)
            resource_modules.append({"name": view_name, "resources": resource_context})
            models += model_context

    for resource_module in resource_modules:
        for resource in resource_module["resources"]:
            # 微信端接口特殊处理
            if resource["request_url"].startswith("weixin/"):
                resource["request_url"] = resource["request_url"][7:]
            # 图表查询接口特殊处理
            if resource["request_url"] in [
                "rest/v2/grafana/time_series/unify_query_raw/",
                "rest/v2/grafana/time_series/unify_query/",
                "rest/v2/grafana/get_variable_value/",
                "rest/v2/grafana/graph_promql_query/",
                "rest/v2/grafana/dimension_promql_query/",
                "rest/v2/grafana/log/query/",
                "rest/v2/grafana/time_series/query/",
                "rest/v2/grafana/bk_log_search/grafana/query/",
                "rest/v2/grafana/bk_log_search/grafana/query_log/",
                "rest/v2/grafana/bk_log_search/grafana/dimension/",
                "rest/v2/grafana/bk_log_search/grafana/get_variable_value/",
            ]:
                resource["request_url"] = f"query-api/{resource['request_url']}"

    generate_new_js_api(resource_modules, models)


def _generate_js_api_by_module(views, app_name=""):
    router = ResourceRouter()
    router.register_module(views)

    resource_api = []
    model_api = []
    for attr, val in list(views.__dict__.items()):
        if attr.startswith("_") or attr[0].islower():
            continue
        if isinstance(val, type):
            if issubclass(val, ResourceViewSet | OldResourceViewSet):
                resource_api += ResourceViewSetParser.parse(val, app_name)
            elif issubclass(val, GenericViewSet) and val not in [GenericViewSet, ModelViewSet]:
                model_api.append(GenericViewSetParser.parse(val, app_name))
    return resource_api, model_api


class BaseParser(six.with_metaclass(abc.ABCMeta, object)):
    """
    ViewSet解析器基类，将viewset中的每一个view的url、method等属性解析出来
    """

    ViewFunction = namedtuple("ViewFunction", ["method", "is_detail"])

    default_view_functions = {
        "list": ViewFunction("GET", False),
        "create": ViewFunction("POST", False),
        "retrieve": ViewFunction("GET", True),
        "update": ViewFunction("PUT", True),
        "partial_update": ViewFunction("PATCH", True),
        "destroy": ViewFunction("DELETE", True),
    }

    class ViewNameFormat:
        default_list_route = "{basename}-list"
        custom_list_route = "{basename}-{methodnamehyphen}"
        default_detail_route = "{basename}-detail"
        custom_detail_route = "{basename}-{methodnamehyphen}"

    @classmethod
    def parse(cls, viewset_cls, app_name=""):
        raise NotImplementedError

    @staticmethod
    def replace_methodname(format_string, basename, methodname):
        """
        Partially format a format_string, swapping out any
        '{basename}' or '{methodnamehyphen}' components.
        """
        methodnamehyphen = methodname.replace("_", "-")
        ret = format_string
        ret = ret.replace("{basename}", basename)
        ret = ret.replace("{methodnamehyphen}", methodnamehyphen)
        return ret


class ResourceViewSetParser(BaseParser):
    """
    ResourceViewSet解析器
    """

    @classmethod
    def parse(cls, viewset_cls, app_name=""):
        viewset_name = get_underscore_viewset_name(viewset_cls)
        result = []
        for route in viewset_cls.resource_routes:
            api_description = route.resource_class.__doc__
            if api_description:
                api_description = api_description.strip()

            resource_name = route.resource_class.get_resource_name().split(".")[-1]
            if resource_name.endswith("Resource"):
                resource_name = resource_name[:-8]
            resource_name = underscore_to_camel(camel_to_underscore(resource_name))
            function_name = resource_name[0].lower() + resource_name[1:]

            if route.endpoint:
                if route.pk_field:
                    url_name_format = cls.ViewNameFormat.custom_detail_route
                else:
                    url_name_format = cls.ViewNameFormat.custom_list_route
            else:
                if route.pk_field:
                    url_name_format = cls.ViewNameFormat.default_detail_route
                else:
                    url_name_format = cls.ViewNameFormat.default_list_route

            url_name = cls.replace_methodname(url_name_format, viewset_name, route.endpoint)

            if app_name:
                url_name = f"{app_name}:{url_name}"
            kwargs = {}
            pk_placeholder = uniqid()
            if route.pk_field:
                kwargs = {viewset_cls.lookup_field: pk_placeholder}
            request_url = reverse(url_name, kwargs=kwargs).replace(pk_placeholder, "{pk}")

            js_code_context = {
                "is_detail": bool(route.pk_field),
                "api_description": api_description,
                "url": request_url,
                "method": route.method,
                "api_name": resource_name,
                "params": route.resource_class.generate_doc(),
                "function_name": function_name,
                "request_url": request_url[1:],
            }

            result.append(js_code_context)
        return result


class GenericViewSetParser(BaseParser):
    """
    GenericViewSet解析器
    """

    @classmethod
    def parse(cls, viewset_cls, app_name=""):
        viewset_name = get_underscore_viewset_name(viewset_cls)
        viewset_name_camel = underscore_to_camel(viewset_name)
        viewset_name_camel = viewset_name_camel[0].lower() + viewset_name_camel[1:]

        result = []
        for methodname in dir(viewset_cls):
            attr = getattr(viewset_cls, methodname)

            if methodname in cls.default_view_functions:
                view_func = cls.default_view_functions[methodname]
                is_custom = False
                is_detail = view_func.is_detail
                httpmethod = view_func.method
            elif getattr(attr, "mapping", None) and isinstance(attr.mapping, dict):
                is_custom = True
                is_detail = getattr(attr, "detail", True)
                httpmethod = list(attr.mapping.keys())[0].upper()
            else:
                continue

            if is_custom:
                if is_detail:
                    url_name_format = cls.ViewNameFormat.custom_detail_route
                else:
                    url_name_format = cls.ViewNameFormat.custom_list_route
            else:
                if is_detail:
                    url_name_format = cls.ViewNameFormat.default_detail_route
                else:
                    url_name_format = cls.ViewNameFormat.default_list_route

            url_name = cls.replace_methodname(url_name_format, viewset_name, methodname)

            if app_name:
                url_name = f"{app_name}:{url_name}"

            kwargs = {}
            pk_placeholder = uniqid()
            if is_detail:
                kwargs = {viewset_cls.lookup_field: pk_placeholder}
            try:
                request_url = reverse(url_name, kwargs=kwargs).replace(pk_placeholder, "{pk}")
            except Exception as error:
                print(error)
                continue

            api_name = underscore_to_camel(methodname)
            function_name = api_name[0].lower() + api_name[1:]

            api_description = attr.__doc__
            if api_description:
                api_description = api_description.strip()

            js_code_context = {
                "api_description": api_description,
                "url": request_url,
                "method": httpmethod,
                "api_name": api_name,
                "function_name": function_name,
                "request_url": request_url[1:],
                "is_detail": is_detail,
                "params": render_schema(get_serializer_fields(viewset_cls.serializer_class)),
            }
            result.append(js_code_context)
        return {
            "name": viewset_name_camel,
            "methods": result,
        }
