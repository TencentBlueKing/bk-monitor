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

import type { ProcessPortStatusType } from '../types/enum';
import type { ProcessItem } from '../types/process';

/** 进程名候选池 */
const PROCESS_NAME_POOL = [
  'bash',
  'mysqld',
  'nginx',
  'redis-server',
  'java',
  'python',
  'node',
  'dockerd',
  'sshd',
  'systemd',
  'kubelet',
  'etcd',
  'prometheus',
  'zookeeper',
  'kafka',
  'elasticsearch',
  'postgres',
  'memcached',
  'httpd',
  'containerd',
];

/** 运行用户候选池 */
const USER_POOL = ['root', 'user01', 'user02', 'www-data', 'mysql', 'redis', 'nginx', 'nobody', 'admin', 'deploy'];

/** 主机 IP 候选池 */
const HOST_IP_POOL = [
  '123.234.34.34',
  '43.84.75.498',
  '10.0.12.45',
  '172.16.8.120',
  '192.168.1.30',
  '9.21.55.102',
  '11.15.88.201',
  '100.68.4.17',
];

/** 监听地址候选池 */
const BIND_IP_POOL = ['0.0.0.0', '127.0.0.1', '10.0.12.45', '192.168.1.30', '172.16.8.120'];

/** 根据索引生成单条 mock 数据，保证排序相关字段（cpuUsage / memUsage / memRss / fdNum / fdUsageRate / uptime / port / instanceCount / portStatus / status）各不相同 */
const buildProcessItem = (index: number): ProcessItem => {
  const name = PROCESS_NAME_POOL[index % PROCESS_NAME_POOL.length];
  const protocol = index % 2 === 0 ? 'TCP' : 'UDP';
  const port = 1024 + index * 37; // 端口单调递增，便于排序校验
  const portStatus = (index % 3 === 0 ? 1 : 0) as ProcessPortStatusType;
  const cpuUsage = (index * 7) % 101; // 0~100 区间波动
  const memUsage = (index * 13) % 101; // 0~100 区间波动
  const memRss = 50 * 1024 * 1024 + index * 1024 * 1024; // 50MB 起每条约 +1MB
  const uptime = 3600_000 + index * 73_000; // 运行时长各不相同
  const fdNum = (index % 50) + 1; // 1~50 波动
  const fdUsageRate = `${(index * 3) % 100}`; // 字符串使用率
  const status = index % 4 === 0 ? 0 : 1;
  const instanceCount = (index % 6) + 1; // 1~6

  return {
    id: `${328392 + index}`,
    name,
    protocol,
    bindIp: BIND_IP_POOL[index % BIND_IP_POOL.length],
    port,
    portStatus,
    user: USER_POOL[index % USER_POOL.length],
    hostIp: HOST_IP_POOL[index % HOST_IP_POOL.length],
    cpuUsage,
    memRss,
    memUsage,
    uptime,
    startCommand: `/usr/sbin/${name} --defaults-file=/etc/${name}.conf`,
    status,
    fdNum,
    fdUsageRate,
    instanceCount,
  };
};

/**
 * @description 进程列表 mock 数据（对应 get_host_process_list）。
 * 字段严格对齐接口文档的 ProcessItem 定义：bindIp / cpuUsage / fdNum / fdUsageRate /
 * hostIp / id / instanceCount / memRss / memUsage / name / port / portStatus /
 * protocol / startCommand / status / uptime / user。文档中已删除的 pid 等字段不返回。
 * 排序相关字段逐条不同，便于前端排序功能校验。
 */
export const getMockHostProcessList = (): ProcessItem[] =>
  Array.from({ length: 100 }, (_, index) => buildProcessItem(index));
