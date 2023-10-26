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

import os
import re
import traceback
import urllib.parse
from collections import OrderedDict, namedtuple
from textwrap import dedent

import coreapi
import mock
import yaml
from django.conf import settings
from django.core.management.base import BaseCommand
from django.template import Context, loader
from rest_framework.schemas import SchemaGenerator, insert_into, is_list_view

from core.drf_resource.viewsets import ResourceViewSet
from kernel_api.urls import API_NAMESPACE

DOC_REGEX = re.compile(
    r"(?:(?P<name>\w+)\s*:)?\s*(?P<title>[^\n]*)(?P<description>(?:\s*.*)+)(?=[\n\r]{2}|$)?", re.M | re.S
)
DocItem = namedtuple("DocItem", ["name", "title", "description"])


def fake_args(url):
    return {k: "{%s}" % k for k in url.regex.groupindex}


def format_doc(content, **kwargs):
    docs = {}
    docs.update(kwargs)

    items = DOC_REGEX.findall(content)
    for name, title, description in items:
        description = dedent(description)
        if not description and not title:
            continue
        docs[name] = DocItem(name=name, title=title, description=description)
        for method in ["get", "post", "put", "delete"]:
            item = DocItem(name=name, title=title, description=description)
            docs["{}/{}".format(method, name)] = item
    return docs


class ViewLinkWraper(object):
    def __init__(self, link, view, title="", request_serializer=None, response_serializer=None, module=None):
        self._link = link
        self.view = view
        self.title = title or link.description.split("\n", 1)[0]
        self.request_serializer = request_serializer
        self.response_serializer = response_serializer
        self.module = module or view.__class__.__module__

    def __getattr__(self, item):
        return getattr(self._link, item)


class APISchemaGenerator(SchemaGenerator):
    ViewItem = namedtuple("ViewItem", ["path", "subpath", "method", "view"])

    def __init__(self, strict=True, *args, **kwargs):
        self.strict = strict
        super(APISchemaGenerator, self).__init__(*args, **kwargs)

    def iter_views(self, request=None):
        # Generate (path, method, view) given (path, method, callback).
        paths = []
        view_endpoints = []
        for path, method, callback in self.endpoints:
            view = self.create_view(callback, method, request)
            if getattr(view, "exclude_from_schema", False):
                continue
            path = self.coerce_path(path, method, view)
            paths.append(path)
            view_endpoints.append((path, method, view))

        # Only generate the path prefix for paths that will be included
        if paths:
            prefix = self.determine_path_prefix(paths)

            for path, method, view in view_endpoints:
                if not self.has_view_permissions(path, method, view):
                    continue
                subpath = path[len(prefix) :]
                yield self.ViewItem(path, subpath, method, view)

    def iter_resource_links(self, path, method, view, schema):
        url = urllib.parse.urljoin(self.url, path)
        base_doc = format_doc(view.__doc__.decode("utf-8"))
        for route in view.resource_routes:
            if route.method != method:
                continue
            if route.endpoint and route.endpoint != getattr(schema, "action", ""):
                continue
            method = route.method.lower()
            resource_docstr = dedent(route.resource_class.__doc__ or "")
            resource_doc = format_doc(resource_docstr.decode("utf-8"))
            resource_doc.update(base_doc)
            doc_item = resource_doc.get("{}/{}".format(method, route.endpoint))
            if doc_item:
                api_description = "{}\n{}".format(doc_item.title, doc_item.description)
                title = doc_item.title
            else:
                api_description = resource_docstr
                title = ""

            mock_view = mock.MagicMock(
                get_serializer=route.resource_class.RequestSerializer,
            )
            fields = self.get_serializer_fields(path, route.method, mock_view)
            request_serializer = route.resource_class.RequestSerializer
            response_serializer = route.resource_class.ResponseSerializer
            yield ViewLinkWraper(
                coreapi.Link(
                    url=urllib.parse.urljoin(url, route.endpoint),
                    action=method,
                    encoding=None,
                    description=api_description,
                    fields=fields,
                ),
                view=route,
                title=title,
                request_serializer=request_serializer() if request_serializer else None,
                response_serializer=response_serializer() if response_serializer else None,
                module=view.__class__.__module__,
            )

    def iter_links(self, path, method, view, schema=None):
        if isinstance(view, ResourceViewSet):
            for i in self.iter_resource_links(path, method, view, schema):
                yield i
        else:
            request_serializer = None
            response_serializer = None
            if hasattr(view, "get_serializer"):
                request_serializer = view.get_serializer()
                response_serializer = view.get_serializer(many=is_list_view(path, method, view))
            yield ViewLinkWraper(
                self.get_link(path, method, view),
                view=view,
                request_serializer=request_serializer,
                response_serializer=response_serializer,
            )

    def get_links(self, request=None):
        """
        Return a dictionary containing all the links that should be
        included in the API schema.
        """
        links = OrderedDict()

        for view in self.iter_views(request):
            keys = self.get_keys(view.subpath, view.method, view.view)
            try:
                for link in self.iter_links(view.path, view.method, view.view, view):
                    insert_into(links, keys, link)
            except Exception as err:
                traceback.print_exception(None, err, None)
        return links

    def has_view_permissions(self, path, method, view):
        try:
            self.get_link(path, method, view)
        except Exception as err:
            traceback.print_exception(None, err, None)
            if not self.strict:
                return False
        return super(APISchemaGenerator, self).has_view_permissions(path, method, view)


class Command(BaseCommand):
    reverse_template = "{namespace}:{url.name}" if API_NAMESPACE else "{url.name}"
    doc_template = "kernel_api/doc_zh.md"
    yaml_name = "monitor.yaml"
    yaml_output = "kernel_api/docs"
    doc_output = "kernel_api/docs/apidocs/zh_hans"
    module = ""

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)
        parser.add_argument("-o", "--yaml_output", default=self.yaml_output)
        parser.add_argument("-O", "--doc_output", default=self.doc_output)
        parser.add_argument("--doc_template", default=self.doc_template)
        parser.add_argument("--yaml_name", default=self.yaml_name)
        parser.add_argument("--readonly_yaml", default=False, action="store_true")
        parser.add_argument("--rewrite_markdown", default=False, action="store_true")
        parser.add_argument("--disable_docs", default=False, action="store_true")
        parser.add_argument("--ignore_errors", default=False, action="store_true")
        parser.add_argument("--module", default=self.module)

    def handle_viewset(self, name, obj):
        for method, view in list(obj.items()):
            if isinstance(view, coreapi.Object):
                for i in self.handle_viewset("{}_{}".format(method, name), view):
                    yield i
            else:
                yield ("{}_{}".format(method, name), view)

    def render_markdown(self, name, info, config):
        config_item = config[info.url]
        path = os.path.join(self.doc_output, "%s.md" % config_item["name"])
        if self.rewrite_markdown or not os.path.exists(path):
            with open(path, "wt") as fp:
                fp.write(
                    loader.render_to_string(
                        self.doc_template, Context({"api": info, "settings": settings, "config": config_item})
                    )
                )

    def render_yaml(self, info):
        yml = []
        for name, item in list(info.items()):
            yml.append(
                {
                    "path": "",
                    "name": name,
                    "label": item.title,
                    "label_en": "",
                    "suggest_method": item.action.upper(),
                    "api_type": "query" if item.action == "get" else "operate",
                    "comp_codename": "generic.v2.monitor.monitor_component",
                    "dest_path": item.url,
                    "dest_http_method": item.action.upper(),
                    "is_hidden": True if item.description == "" else False,
                }
            )

        yml_path = os.path.join(self.yaml_output, self.yaml_name)
        if os.path.exists(yml_path):
            with open(yml_path, "rt") as fp:
                config = {i["dest_path"]: i for i in yaml.load(fp.read(), Loader=yaml.FullLoader) or []}
                for i in yml:
                    config.setdefault(i["dest_path"], i)
                yml = list(config.values())
        if not self.readonly_yaml:
            with open(yml_path, "wt") as fp:
                fp.write(yaml.safe_dump(yml, default_flow_style=False, allow_unicode=True, encoding="utf-8"))
        return {i["dest_path"]: i for i in yml}

    def ensure_folder_exists(self, path):
        if not os.path.exists(path):
            os.makedirs(path)

    def init(self, **kwargs):
        for k, v in list(kwargs.items()):
            setattr(self, k, v)

    def handle(self, *args, **options):
        self.init(**options)
        self.ensure_folder_exists(self.yaml_output)
        self.ensure_folder_exists(self.doc_output)

        schema_gen = APISchemaGenerator(strict=not self.ignore_errors)
        doc = schema_gen.get_schema()
        info = {}
        for k, obj in list(doc.items()):
            for name, item in self.handle_viewset(k, obj):
                if not item.module.startswith(self.module):
                    continue
                info[name] = item

        config = self.render_yaml(info)

        if not self.disable_docs:
            for n, i in list(info.items()):
                self.render_markdown(n, i, config)
