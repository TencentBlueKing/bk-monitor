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
 * @description 进程列表 mock 数据，严格对齐设计稿（node 79:9451）的 7 行示例。
 * 字段与 ProcessItem 一一对应，后续接入真实接口时仅需替换 service 取数逻辑。
 */
const MOCK_PROCESS_LIST: Omit<ProcessItem, 'startCommand'>[] = [
  {
    id: 'bash@123.234.34.34',
    name: 'bash',
    pid: 10086,
    protocol: 'TCP',
    bindIp: '0.0.0.0',
    port: 18000,
    portStatus: EProcessPortStatus.Abnormal,
    user: 'root',
    hostIp: '123.234.34.34',
    cpuUsage: 19,
    memRss: mib(92),
    memUsage: 23,
    uptime: hours(6.4),
  },
  {
    id: 'zookeeper@2.534.45.342',
    name: 'zookeeper',
    pid: 10087,
    protocol: 'TCP',
    bindIp: '0.0.0.0',
    port: 18000,
    portStatus: EProcessPortStatus.Abnormal,
    user: 'root',
    hostIp: '2.534.45.342',
    cpuUsage: 45,
    memRss: mib(88),
    memUsage: 13,
    uptime: hours(1.2),
  },
  {
    id: 'mysqld@43.84.75.498',
    name: 'mysqld',
    pid: 10088,
    protocol: 'TCP',
    bindIp: '0.0.0.0',
    port: 18000,
    portStatus: EProcessPortStatus.Abnormal,
    user: 'user01',
    hostIp: '43.84.75.498',
    cpuUsage: 22,
    memRss: mib(32),
    memUsage: 8,
    uptime: hours(6.4),
  },
  {
    id: 'kafka@45.23.134.23',
    name: 'kafka',
    pid: 10089,
    protocol: 'TCP',
    bindIp: '0.0.0.0',
    port: 21000,
    portStatus: EProcessPortStatus.Normal,
    user: 'root',
    hostIp: '45.23.134.23',
    cpuUsage: 27,
    memRss: mib(92),
    memUsage: 23,
    uptime: hours(1.2),
  },
  {
    id: 'kubernetes@453.234.32.12',
    name: 'kubernetes',
    pid: 10090,
    protocol: 'TCP',
    bindIp: '0.0.0.0',
    port: 21000,
    portStatus: EProcessPortStatus.Normal,
    user: 'root',
    hostIp: '453.234.32.12',
    cpuUsage: 2,
    memRss: mib(88),
    memUsage: 13,
    uptime: hours(6.4),
  },
  {
    id: 'redis@234.543.32.64',
    name: 'redis',
    pid: 10091,
    protocol: 'TCP',
    bindIp: '0.0.0.0',
    port: 21000,
    portStatus: EProcessPortStatus.Normal,
    user: 'root',
    hostIp: '234.543.32.64',
    cpuUsage: 5,
    memRss: mib(32),
    memUsage: 8,
    uptime: hours(1.2),
  },
  {
    id: 'nginx@341.23.12.23',
    name: 'nginx',
    pid: 10092,
    protocol: 'TCP',
    bindIp: '0.0.0.0',
    port: 21000,
    portStatus: EProcessPortStatus.Normal,
    user: 'user01',
    hostIp: '341.23.12.23',
    cpuUsage: 54,
    memRss: mib(92),
    memUsage: 23,
    uptime: hours(1.2),
  },
];

/** @description 获取进程列表 mock 数据（返回副本，避免外部修改污染源数据） */
export const getMockProcessList = (): ProcessItem[] =>
  MOCK_PROCESS_LIST.map(item => ({ ...item, startCommand: START_COMMAND }));
