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
INSERT INTO `app_snapshot_host_index` VALUES 
(3,'cpu','load5','double','system_load','5分钟平均负载','',1,'','system.load.load5',1,0,1),
(7,'cpu','usage','double','system_cpu_summary','CPU总使用率','',1,'%','system.cpu_summary.usage',1,1,1),
(8,'cpu','usage','double','system_cpu_detail','CPU单核使用率','device_name',1,'%','system.cpu_detail.usage',1,1,1),
(10,'net','speedRecv','double','system_net','接收字节流量','device_name',1024,'KB/s','system.net.speedRecv',1,1,1),
(14,'net','speedSent','double','system_net','发送字节流量','device_name',1024,'KB/s','system.net.speedSent',1,1,1),
(16,'net','speedPacketsSent','double','system_net','发送包速率','device_name',1,'个/s','system.net.speedPacketsSent',1,1,1),
(20,'net','speedPacketsRecv','double','system_net','接收包速率','device_name',1,'个/s','system.net.speedPacketsRecv',1,1,1),
(60,'mem','free','int','system_mem','可用物理内存','',1048576,'MB','system.mem.free',1,1,1),
(63,'mem','used','int','system_swap','交换分区使用量','',1048576,'MB','system.swap.used',1,0,1),
(64,'mem','psc_pct_used','double','system_mem','物理内存使用率','',1,'%','system.mem.psc_pct_used',1,1,1),
(81,'disk','in_use','float','system_disk','磁盘使用率','mount_point',1,'%','system.disk.in_use',1,1,1),
(86,'disk','r_s','double','system_io','读速率','device_name',1,'次/秒','system.io.r_s',1,1,1),
(87,'disk','w_s','double','system_io','写速率','device_name',1,'次/秒','system.io.w_s',1,1,1),
(96,'disk','util','double','system_io','磁盘IO使用率','device_name',0.01,'%','system.io.util',1,1,1),
(97,'mem','psc_used','int','system_mem','物理内存使用量','',1048576,'MB','system.mem.psc_used',1,1,1),
(98,'mem','used','int','system_mem','应用内存使用量','',1048576,'MB','system.mem.used',1,1,1),
(99,'mem','pct_used','int','system_mem','应用内存使用率','',1,' %','system.mem.pct_used',1,1,1),
(110,'net','cur_tcp_estab','int','system_netstat','ESTABLISHED连接数','',1,'','system.netstat.cur_tcp_estab',1,1,1),
(111,'net','cur_tcp_timewait','int','system_netstat','TIME_WAIT连接数','',1,'','system.netstat.cur_tcp_timewait',1,1,1),
(112,'net','cur_tcp_listen','int','system_netstat','LISTEN连接数','',1,'','system.netstat.cur_tcp_listen',1,1,1),
(113,'net','cur_tcp_lastack','int','system_netstat','LAST_ACK连接数','',1,'','system.netstat.cur_tcp_lastack',1,1,1),
(114,'net','cur_tcp_syn_recv','int','system_netstat','SYN_RECV连接数','',1,'','system.netstat.cur_tcp_syn_recv',1,1,1),
(115,'net','cur_tcp_syn_sent','int','system_netstat','SYN_SENT连接数','',1,'','system.netstat.cur_tcp_syn_sent',1,1,1),
(116,'net','cur_tcp_finwait1','int','system_netstat','FIN_WAIT1连接数','',1,'','system.netstat.cur_tcp_finwait1',1,1,1),
(117,'net','cur_tcp_finwait2','int','system_netstat','FIN_WAIT2连接数','',1,'','system.netstat.cur_tcp_finwait2',1,1,1),
(118,'net','cur_tcp_closing','int','system_netstat','CLOSING连接数','',1,'','system.netstat.cur_tcp_closing',1,1,1),
(119,'net','cur_tcp_closed','int','system_netstat','CLOSED状态连接数','',1,'','system.netstat.cur_tcp_closed',1,1,1),
(120,'net','cur_udp_indatagrams','int','system_netstat','UDP接收包量','',1,'','system.netstat.cur_udp_indatagrams',1,1,1),
(121,'net','cur_udp_outdatagrams','int','system_netstat','UDP发送包量','',1,'','system.netstat.cur_udp_outdatagrams',1,1,1),
(122,'process','cpu_usage_pct','double','system_proc','CPU使用率','display_name,pid',0.01,'%','system.proc.cpu_usage_pct',1,1,1),
(123,'process','mem_usage_pct','double','system_proc','内存使用率','display_name,pid',0.01,'%','system.proc.mem_usage_pct',1,1,1),
(124,'process','mem_res','double','system_proc','物理内存使用量','display_name,pid',1048576,'MB','system.proc.mem_res',1,1,1),
(125,'process','mem_virt','double','system_proc','虚拟内存使用量','display_name,pid',1048576,'MB','system.proc.mem_virt',1,1,1),
(126,'process','fd_num','int','system_proc','文件句柄数','display_name,pid',1,'','system.proc.fd_num',1,1,1),
(127,'system_env','procs','int','system_env','系统进程数','',1,'','system.env.procs',1,1,1),
(128,'net','cur_tcp_closewait','int','system_netstat','CLOSE_WAIT连接数','',1,'','system.netstat.cur_tcp_closewait',1,1,1),
(129,'mem','pct_used','int','system_swap','已用的交换分区占比','',1,'%','system.swap.pct_used',1,0,1);
"""


class Migration(migrations.Migration):

    dependencies = [
        ("bkmonitor", "0001_initial"),
    ]

    operations = [migrations.RunSQL(init_sql)]
