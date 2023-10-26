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


import logging

from django.db import migrations

logger = logging.getLogger("metadata")

models = {
    "ClusterInfo": None,
    "DataSource": None,
    "ResultTableField": None,
    "ResultTable": None,
    "DataSourceResultTable": None,
    "KafkaTopicInfo": None,
    "InfluxDBStorage": None,
    "Label": None,
}


def init_label_info(apps, schema_editor):
    """增加默认的label信息"""

    # 获取APP models
    for model_name in list(models.keys()):
        models[model_name] = apps.get_model("metadata", model_name)

    ResultTable = models["ResultTable"]

    # 创建数据源类型标签
    # 所有的结果表都先置为others，如果有特殊配置的，会在下面单独处理
    ResultTable.objects.all().update(label="others")

    # ====================== 主机 -- 操作系统 -- start=================
    # system.cpu_summary
    rt = ResultTable.objects.get(table_id="system.cpu_summary")
    rt.label = "os"
    rt.save()

    # system.io
    rt = ResultTable.objects.get(table_id="system.io")
    rt.label = "os"
    rt.save()

    # system.env
    rt = ResultTable.objects.get(table_id="system.env")
    rt.label = "os"
    rt.save()

    # system.cpu_detail
    rt = ResultTable.objects.get(table_id="system.cpu_detail")
    rt.label = "os"
    rt.save()

    # system.mem
    rt = ResultTable.objects.get(table_id="system.mem")
    rt.label = "os"
    rt.save()

    # system.netstat
    rt = ResultTable.objects.get(table_id="system.netstat")
    rt.label = "os"
    rt.save()

    # system.disk
    rt = ResultTable.objects.get(table_id="system.disk")
    rt.label = "os"
    rt.save()

    # system.net
    rt = ResultTable.objects.get(table_id="system.net")
    rt.label = "os"
    rt.save()

    # system.inode
    rt = ResultTable.objects.get(table_id="system.inode")
    rt.label = "os"
    rt.save()

    # system.swap
    rt = ResultTable.objects.get(table_id="system.swap")
    rt.label = "os"
    rt.save()

    # system.load
    rt = ResultTable.objects.get(table_id="system.load")
    rt.label = "os"
    rt.save()

    # ====================== 主机 -- 操作系统 -- end=================

    # ====================== 主机 -- 进程 -- start=================
    # system.proc
    rt = ResultTable.objects.get(table_id="system.proc")
    rt.label = "host_process"
    rt.save()

    # system.proc_port
    rt = ResultTable.objects.get(table_id="system.proc_port")
    rt.label = "host_process"
    rt.save()
    # ====================== 主机 -- 进程 -- end=================

    # ====================== 服务 -- 组件 -- start=================
    # apache.net
    rt = ResultTable.objects.get(table_id="apache.net")
    rt.label = "component"
    rt.save()

    # apache.performance
    rt = ResultTable.objects.get(table_id="apache.performance")
    rt.label = "component"
    rt.save()

    # mysql.innodb
    rt = ResultTable.objects.get(table_id="mysql.innodb")
    rt.label = "component"
    rt.save()

    # mysql.net
    rt = ResultTable.objects.get(table_id="mysql.net")
    rt.label = "component"
    rt.save()

    # mysql.performance
    rt = ResultTable.objects.get(table_id="mysql.performance")
    rt.label = "component"
    rt.save()

    # mysql.rep
    rt = ResultTable.objects.get(table_id="mysql.rep")
    rt.label = "component"
    rt.save()

    # nginx.net
    rt = ResultTable.objects.get(table_id="nginx.net")
    rt.label = "component"
    rt.save()

    # tomcat.cache
    rt = ResultTable.objects.get(table_id="tomcat.cache")
    rt.label = "component"
    rt.save()

    # tomcat.thread
    rt = ResultTable.objects.get(table_id="tomcat.thread")
    rt.label = "component"
    rt.save()

    # tomcat.jsp
    rt = ResultTable.objects.get(table_id="tomcat.jsp")
    rt.label = "component"
    rt.save()

    # tomcat.net
    rt = ResultTable.objects.get(table_id="tomcat.net")
    rt.label = "component"
    rt.save()

    # tomcat.servlet
    rt = ResultTable.objects.get(table_id="tomcat.servlet")
    rt.label = "component"
    rt.save()

    # redis.client
    rt = ResultTable.objects.get(table_id="redis.client")
    rt.label = "component"
    rt.save()

    # redis.repl
    rt = ResultTable.objects.get(table_id="redis.repl")
    rt.label = "component"
    rt.save()

    # redis.mem
    rt = ResultTable.objects.get(table_id="redis.mem")
    rt.label = "component"
    rt.save()

    # redis.aof
    rt = ResultTable.objects.get(table_id="redis.aof")
    rt.label = "component"
    rt.save()

    # redis.cpu
    rt = ResultTable.objects.get(table_id="redis.cpu")
    rt.label = "component"
    rt.save()

    # redis.rdb
    rt = ResultTable.objects.get(table_id="redis.rdb")
    rt.label = "component"
    rt.save()

    # redis.stat
    rt = ResultTable.objects.get(table_id="redis.stat")
    rt.label = "component"
    rt.save()
    # ====================== 服务 -- 组件 -- end=================

    # ====================== 应用 -- 拨测 -- start=================
    # uptimecheck.tcp
    rt = ResultTable.objects.get(table_id="uptimecheck.tcp")
    rt.label = "uptimecheck"
    rt.save()

    # uptimecheck.udp
    rt = ResultTable.objects.get(table_id="uptimecheck.udp")
    rt.label = "uptimecheck"
    rt.save()

    # uptimecheck.http
    rt = ResultTable.objects.get(table_id="uptimecheck.http")
    rt.label = "uptimecheck"
    rt.save()

    # uptimecheck.heartbeat
    rt = ResultTable.objects.get(table_id="uptimecheck.heartbeat")
    rt.label = "uptimecheck"
    rt.save()
    # ====================== 应用 -- 拨测 -- end=================


class Migration(migrations.Migration):

    dependencies = [
        ("metadata", "0025_init_label_info"),
    ]

    operations = [
        migrations.RunPython(init_label_info),
    ]
