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

/** 异步弹窗确认事件，通过 { resolve, reject, promise } 将控制权交给调用方 */
export interface AsyncDialogConfirmEvent<T extends Record<string, unknown> = Record<string, unknown>> {
  /** 业务数据 */
  payload: T;
  /** 异步结果，可供调用方 await */
  promise: Promise<void>;
  /** 业务失败时调用 */
  reject: () => void;
  /** 业务成功时调用 */
  resolve: () => void;
}

/** 告警色块数据项 — 每个时间点的告警级别和数值 */
export interface IAlertBarItem {
  /** 告警级别，来自 AlertLevelEnum */
  level: string;
  /** 时间戳（毫秒） */
  time: number;
  /** 原始数值 */
  value: null | number;
}

/** 告警趋势图配置 */
export interface IAlertGraphConfig {
  /** 图表 ID */
  id: number;
  /** 查询目标列表 */
  targets: IAlertGraphTarget[];
  /** 图表标题 */
  title: string;
  /** 图表类型 */
  type: string;
}

/** 告警图查询目标 */
export interface IAlertGraphTarget {
  /** 查询 API，如 "rum_metric.alertQuery" */
  api: string;
  /** 查询参数 */
  data: Record<string, unknown>;
  /** 数据源 */
  datasource: string;
  /** 数据类型 */
  dataType: string;
}

/** 1.15 GetDataSamplingResource 采样数据项 */
export interface IDataSamplingItem {
  /** 原始样例数据 */
  raw_log: Record<string, unknown>;
  /** 采样时间 */
  sampling_time: string;
}

/** 1.17-1.18 开启/关闭无数据告警策略参数 */
export interface INoDataStrategyParams {
  /** 应用 ID */
  application_id: number;
}

/** 通知组项 */
export interface INoticeGroupItem {
  /** 通知组 ID */
  id: number;
  /** 通知组名称 */
  name: string;
}

/** RUM 应用基础请求参数 */
export interface IRumAppBaseParams {
  /** 应用名称 */
  app_name: string;
  /** 业务 ID */
  bk_biz_id: number;
}

/** 告警策略数据 */
export interface IStrategyData {
  /** 告警数量 */
  alert_count: number;
  /** 告警趋势图配置 */
  alert_graph: IAlertGraphConfig | null;
  /** 告警状态 */
  alert_status: number;
  /** 策略 ID */
  id: number;
  /** 是否启用 */
  is_enabled: boolean;
  /** 策略名称 */
  name: string;
  /** 通知组 */
  notice_group: INoticeGroupItem[];
}
