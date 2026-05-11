/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
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

/**
 * 客户端日志检索页面 - 类型定义
 */

/** 数据来源类型 */
export type DataSource = 'task' | 'report';

/** 任务处理状态 */
export type ProcessStatus = 'init' | 'pending' | 'running' | 'success' | 'failed';

/** 单个日志条目类型 */
export interface LogItem {
  source: DataSource;                // 数据来源：task 表示日志捞取任务，report 表示用户上报
  id: number | null;                 // 任务实例 ID，仅 source=task 时有值
  task_id: string | null;            // 后台任务 ID，仅 source=task 时有值
  openid: string;                    // openid
  file_name: string;                 // 文件名
  os_type: string;                   // 操作系统类型
  os_version: string;                // 操作系统版本
  sdk_version: string;               // SDK 版本；task 来源自任务明细，report 来源自 os_sdk
  model: string;                     // 设备型号
  xid: string;                       // 客户端标识
  report_time: string | null;        // 展示排序时间。task 使用 processed_at，report 使用 report_time
  process_status: ProcessStatus | null; // 处理状态
  processed_at: string | null;       // 处理时间
}

/** 用户累计上报统计（来自独立接口） */
export interface UserReportStats {
  total_count: number;               // 累计数量
  range_count: number;               // 指定时间范围内数量
}

/** 文件树节点类型 */
export interface FileTreeNode {
  name: string;                      // 文件名
  isFolder?: boolean;                // 是否为文件夹
  children?: FileTreeNode[];         // 子节点
}

/** 搜索参数类型 */
export interface SearchParams {
  openid: string;                    // openid（搜索关键词）
  timeRange: [string, string];      // 时间范围 [start, end]
  timezone: string;                  // 时区标识
}
