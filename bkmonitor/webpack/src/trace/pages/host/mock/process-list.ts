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

import { type ProcessItem, EProcessPortStatus } from '../types/process';

/** MiB → 字节，便于按设计稿原值（92 MiB 等）声明 mock */
const mib = (value: number) => value * 1024 * 1024;
/** 小时 → 秒，便于按设计稿原值（6.4 h 等）声明 mock */
const hours = (value: number) => Math.round(value * 3600);
/** 进程详情头部「启动命令」mock，统一按设计稿原值声明 */
const START_COMMAND = 'agent run p/opt/datadog-agent/run/agent.pid';

/**
 * @description 进程列表 mock 数据，严格对齐设计稿（node 197:7291）的 5 行示例。
 * 字段与 ProcessItem 一一对应，后续接入真实接口时仅需替换 service 取数逻辑。
 */
const MOCK_PROCESS_LIST: Omit<ProcessItem, 'startCommand'>[] = [
  {
    id: 'influx-proxy@10.0.0.1',
    name: 'influx-proxy',
    pid: 10001,
    protocol: 'TCP',
    bindIp: '0.0.0.0',
    port: 8086,
    portStatus: EProcessPortStatus.Normal,
    user: 'root',
    hostIp: '10.0.0.1',
    cpuUsage: 22.5,
    memRss: Math.round(1.84 * 1024 * 1024 * 1024),
    memUsage: 18,
    uptime: 1324800,
    instanceCount: 3,
    cpuChangePercent: 8,
    cpuChangeStatus: 'rising',
    connectionCount: 843,
    fileHandleCount: 5431,
    fileHandleUsagePercent: 18,
    uptimeRange: '2.1h - 15.3d',
    subtitle: '命令匹配：cmd contains influx-proxy',
  },
  {
    id: 'mongodb@10.0.0.2',
    name: 'Mongodb',
    pid: 10002,
    protocol: 'TCP',
    bindIp: '0.0.0.0',
    port: 27017,
    portStatus: EProcessPortStatus.Normal,
    user: 'root',
    hostIp: '10.0.0.2',
    cpuUsage: 2.4,
    memRss: mib(92),
    memUsage: 23,
    uptime: 483840,
    instanceCount: 1,
    cpuChangePercent: -2,
    cpuChangeStatus: 'falling',
    connectionCount: 128,
    fileHandleCount: 923,
    fileHandleUsagePercent: 23,
    uptimeRange: '5.6d',
    subtitle: '名称匹配：process.name = mongodb',
  },
  {
    id: 'zookeeper@10.0.0.3',
    name: 'zookeeper',
    pid: 10003,
    protocol: 'TCP',
    bindIp: '0.0.0.0',
    port: 2181,
    portStatus: EProcessPortStatus.Normal,
    user: 'user01',
    hostIp: '10.0.0.3',
    cpuUsage: 8.7,
    memRss: mib(176),
    memUsage: 21,
    uptime: 362880,
    instanceCount: 4,
    cpuChangePercent: 4,
    cpuChangeStatus: 'rising',
    connectionCount: 242,
    fileHandleCount: 1342,
    fileHandleUsagePercent: 21,
    uptimeRange: '4.2d - 4.3d',
    subtitle: '命令匹配：process.name = mysql',
  },
  {
    id: 'mysql@10.0.0.4',
    name: 'mysql',
    pid: 10004,
    protocol: 'TCP',
    bindIp: '0.0.0.0',
    port: 3306,
    portStatus: EProcessPortStatus.Normal,
    user: 'root',
    hostIp: '10.0.0.4',
    cpuUsage: 8.4,
    memRss: mib(68),
    memUsage: 17,
    uptime: 190080,
    instanceCount: 6,
    cpuChangePercent: -1,
    cpuChangeStatus: 'falling',
    connectionCount: 200,
    fileHandleCount: 630,
    fileHandleUsagePercent: 17,
    uptimeRange: '2.2d',
    subtitle: '名称匹配：process.name = mysql',
  },
  {
    id: 'bkmonitorbeat@10.0.0.5',
    name: 'bkmonitorbeat',
    pid: 10005,
    protocol: 'TCP',
    bindIp: '0.0.0.0',
    port: 8888,
    portStatus: EProcessPortStatus.Normal,
    user: 'root',
    hostIp: '10.0.0.5',
    cpuUsage: 4.8,
    memRss: mib(210),
    memUsage: 14,
    uptime: 2730240,
    instanceCount: 12,
    cpuChangePercent: 0,
    cpuChangeStatus: 'stable',
    connectionCount: 134,
    fileHandleCount: 54,
    fileHandleUsagePercent: 14,
    uptimeRange: '18m - 31.6d',
    subtitle: '命令匹配：cmd contains bkmonitorbeat',
  },
];

/** @description 获取进程列表 mock 数据（返回副本，避免外部修改污染源数据） */
export const getMockProcessList = (): ProcessItem[] =>
  MOCK_PROCESS_LIST.map(item => ({ ...item, startCommand: START_COMMAND }));
