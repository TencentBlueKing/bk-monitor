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

import glob

import yaml
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    config = "kernel_api/docs/monitor.yaml"
    doc_path = "kernel_api/docs/apidocs/zh_hans"

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)
        parser.add_argument("-c", "--config", default=self.config)
        parser.add_argument("--doc_path", default=self.doc_path)

    def append_invalids(self, config, message):
        self.invalids[config["_"]].append(message)

    def for_each_config(self, config, f):
        ok = True
        for i in config:
            message = f(i)
            if message:
                self.append_invalids(i, message)
                ok = False
        return ok

    def check_name(self, config):
        return self.for_each_config(config, lambda x: "" if x["name"] else "name not found")

    def check_label(self, config):
        return self.for_each_config(config, lambda x: "" if x["label"] else "label not found")

    def check_path_unique(self, config):
        path_set = set()
        return self.for_each_config(
            config, lambda x: path_set.add(x["path"]) if x["path"] not in path_set else "path not unique"
        )

    def check_doc_exists(self, config):
        return self.for_each_config(
            config, lambda x: "" if glob.glob1(self.doc_path, "%s.*" % x["name"]) else "doc not exists"
        )

    def handle(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

        with open(self.config, "rt") as fp:
            config = yaml.load(fp.read(), Loader=yaml.FullLoader)

        if not config:
            return

        for i, e in enumerate(config):
            e["_"] = i

        checkers = [
            self.check_name,
            self.check_label,
            self.check_path_unique,
            self.check_doc_exists,
        ]

        for checker in checkers:
            checker(config)

        for i in config:
            errors = self.invalids.get(i["_"])
            if errors:
                print("{}: {}".format(i["path"], ",".join(errors)))
