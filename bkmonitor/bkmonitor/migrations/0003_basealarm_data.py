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


from django.db import migrations

init_sql = """
INSERT INTO `dict_base_alarm` VALUES 
(1,0,'os-restart-gse','机器重启',0),
(2,1,'clock-unsync-gse','时间不同步',0),
(3,2,'agent-gse','Agent心跳丢失',1),
(4,3,'disk-readonly-gse','磁盘只读',1),
(5,4,'port-missing-gse','端口未打开',0),
(6,5,'process-missing-gse','进程告警',0),
(7,6,'disk-full-gse','磁盘写满',1),
(8,7,'corefile-gse','Corefile产生',1),
(9,8,'ping-gse','PING不可达告警',1);
"""


class Migration(migrations.Migration):
    dependencies = [
        ("bkmonitor", "0002_appsnapshothostindexdata"),
    ]

    operations = [migrations.RunSQL(init_sql)]
