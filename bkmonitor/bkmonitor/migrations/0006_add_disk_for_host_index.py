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

insert_sql = """
INSERT INTO `app_snapshot_host_index` VALUES 
(130,'disk','avgqu_sz','int','system_io','平均队列长度','device_name',1,'','system.io.avgqu_sz',1,1,1),
(131,'disk','avgrq_sz','int','system_io','平均数据大小','device_name',1,'sector','system.io.avgrq_sz',1,1,1),
(132,'disk','await','int','system_io','平均等待时长','device_name',1,'ms','system.io.await',1,1,1),
(133,'disk','rkb_s','int','system_io','读速率','device_name',1024,'KB/s','system.io.rkb_s',1,1,1),
(134,'disk','svctm','int','system_io','平均服务时长','device_name',1,'ms','system.io.svctm',1,1,1),
(135,'disk','wkb_s','int','system_io','写速率','device_name',1024,'KB/s','system.io.wkb_s',1,1,1);
"""
update_rs = """
UPDATE `app_snapshot_host_index` SET `description`='读次数' WHERE `ID`=86;
"""
update_ws = """
UPDATE `app_snapshot_host_index` SET `description`='写次数' WHERE `ID`=87;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("bkmonitor", "0005_event_shield_type"),
    ]

    operations = [migrations.RunSQL(insert_sql), migrations.RunSQL(update_rs), migrations.RunSQL(update_ws)]
