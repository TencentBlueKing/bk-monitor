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

/** 进程端口状态：决定端口列状态圆点颜色（正常绿点 / 异常红点） */
export enum EProcessPortStatus {
  /** 异常 */
  Abnormal = 1,
  /** 正常 */
  Normal = 0,
}

/** 进程列表行数据 */
export interface ProcessItem {
  /** 监听地址 */
  bindIp: string;
  /** 连接数 */
  connectionCount: number;
  /** CPU 变化百分比（正值上升 / 负值下降 / 0 稳定） */
  cpuChangePercent: number;
  /** CPU 变化状态：rising 上升 / falling 下降 / stable 稳定 */
  cpuChangeStatus: 'falling' | 'rising' | 'stable';
  /** 占用 CPU 百分比 */
  cpuUsage: number;
  /** 文件句柄数 */
  fileHandleCount: number;
  /** 文件句柄使用率百分比 */
  fileHandleUsagePercent: number;
  /** 所属主机 IP（蓝色链接） */
  hostIp: string;
  /** 行唯一 key（进程名 + 主机 IP，保证同主机内唯一） */
  id: string;
  /** 实例数 */
  instanceCount: number;
  /** 物理内存 RSS（字节） */
  memRss: number;
  /** 物理内存使用率百分比（进度条 + 文案） */
  memUsage: number;
  /** 进程名（蓝色链接，点击打开进程详情） */
  name: string;
  /** 进程 PID（用于「进程名/PID」搜索） */
  pid: number;
  /** 监听端口 */
  port: number;
  /** 端口状态（决定状态圆点颜色） */
  portStatus: EProcessPortStatus;
  /** 监听协议（TCP / UDP） */
  protocol: string;
  /** 启动命令（进程详情头部展示） */
  startCommand: string;
  /** 进程名副标题（如 命令匹配：cmd contains influx-proxy） */
  subtitle: string;
  /** 运行时长（秒） */
  uptime: number;
  /** 运行时长范围（如 2.1h - 15.3d） */
  uptimeRange: string;
  /** 运行用户 */
  user: string;
}
