/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */

import type { ProcessItem } from '../types/process';

/**
 * @description 进程列表 mock 数据（对应 get_host_process_list）。
 * 字段严格对齐接口文档的 ProcessItem 定义：bindIp / cpuUsage / fdNum / fdUsageRate /
 * hostIp / id / instanceCount / memRss / memUsage / name / port / portStatus /
 * protocol / startCommand / status / uptime / user。文档中已删除的 pid 等字段不返回。
 */
export const getMockHostProcessList = (): ProcessItem[] => [
  {
    id: '328392',
    name: 'bash',
    protocol: 'TCP',
    bindIp: '0.0.0.0',
    port: 18000,
    portStatus: 1,
    user: 'root',
    hostIp: '123.234.34.34',
    cpuUsage: 90,
    memRss: 96468992,
    memUsage: 23,
    uptime: 23040,
    startCommand: 'agent run p/opt/datadog-agent/run/agent.pid',
    status: 1,
    fdNum: 10,
    fdUsageRate: '2',
    instanceCount: 1,
  },
  {
    id: '94854',
    name: 'mysqld',
    protocol: 'TCP',
    bindIp: '0.0.0.0',
    port: 3306,
    portStatus: 0,
    user: 'user01',
    hostIp: '43.84.75.498',
    cpuUsage: 12,
    memRss: 134217728,
    memUsage: 90,
    uptime: 8648980,
    startCommand: '/usr/sbin/mysqld --defaults-file=/etc/my.cnf',
    status: 1,
    fdNum: 10,
    fdUsageRate: '2',
    instanceCount: 1,
  },
];
