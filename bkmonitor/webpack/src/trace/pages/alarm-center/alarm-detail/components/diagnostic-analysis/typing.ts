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

import type { Message } from '@blueking/chat-x';
import type { GetEnumTypeTool } from 'monitor-pc/pages/query-template/typings/constants';

import type { DiagnosticTypeEnum } from './constant';
import type { AlertLevelEnum, AlarmStatusEnum } from '@/pages/alarm-center/typings';

export type DiagnosticTypeEnumType = GetEnumTypeTool<typeof DiagnosticTypeEnum>;

/** 内容项 */
export interface IContentItem {
  title: string;
  value: string[];
}

/** 表格项 */
export interface ITableItem {
  name: string;
  value: string;
}

/** 告警分析消息类型：前端适配层 envelope，不是面板原始响应 */
export const AlertAnalysisMessageType = {
  ANALYSIS_RESULT: 'alert.analysis_result',
} as const;

/** 告警分析结果种类：当前落地指标趋势、维度命中告警、日志聚类与事件列表 */
export const AlertAnalysisResultKind = {
  METRIC_SERIES: 'metric_series',
  ALERT_LIST: 'alert_list',
  LOG_RECORDS: 'log_records',
  EVENT_RECORDS: 'event_records',
} as const;

export type AlertAnalysisResultKindType = (typeof AlertAnalysisResultKind)[keyof typeof AlertAnalysisResultKind];

/** 指标趋势维度标签 */
export interface IMetricSeriesDimension {
  alias: string;
  key: string;
  value: string;
}

/** 指标趋势系列：key 为系列标识，alias 为图表接口返回的展示名 */
export interface IMetricSeriesLine {
  alias: string;
  color: string;
  datapoints: [number, number][];
  key: string;
}

/** 本地 UI 演示用的指标趋势结果，不是已核实的时序接口契约 */
export interface IMetricSeriesResult {
  dimensions: IMetricSeriesDimension[];
  series: IMetricSeriesLine[];
  title: string;
}

/** 日志聚类文本片段：wildcard 为 Pattern 占位，value 为示例日志中的对应值 */
export interface ILogTextToken {
  highlight?: 'value' | 'wildcard';
  text: string;
}

/** 日志条数趋势系列 */
export type LogSeriesKey = 'count';

export interface ILogSeriesLine {
  color: string;
  datapoints: [number, number][];
  key: LogSeriesKey;
}

/** 本地 UI 演示用的日志聚类结果，趋势曲线不是已核实的接口契约 */
export interface ILogRecordsResult {
  matchCount: number;
  pattern: ILogTextToken[];
  samples: ILogTextToken[][];
  series: ILogSeriesLine[];
}

/** 告警列表字段行：设计稿中的内容 / 目标 / 空间 */
export interface IAlertListField {
  key: string;
  value: string;
}

export type AlertListStatus = (typeof AlarmStatusEnum)[keyof typeof AlarmStatusEnum];

/** 本地 UI 演示用的告警列表项，不是已核实的监控告警模型 */
export interface IAlertListItem {
  beginTime: number;
  fields: IAlertListField[];
  id: string;
  notifyText: string;
  severity: AlertLevelEnum;
  status: AlertListStatus;
  title: string;
}

/** 本地 UI 演示用的维度命中告警列表，不是已核实的告警接口契约 */
export interface IAlertListResult {
  alerts: IAlertListItem[];
}

/** 事件来源：与告警详情事件表 SourceTypeEnum 对齐，仅用于本地卡片图标 */
export const EventRecordSourceType = {
  BCS: 'BCS',
  BKCI: 'BKCI',
  DEFAULT: 'DEFAULT',
  HOST: 'HOST',
} as const;

export type EventRecordSourceTypeValue = (typeof EventRecordSourceType)[keyof typeof EventRecordSourceType];

export interface IEventRecordField {
  key: string;
  url?: string;
  value: string;
}

/** 本地 UI 演示用的事件列表项，不是已核实的 panel_detail 记录 */
export interface IEventRecordItem {
  eventName: string;
  fields: IEventRecordField[];
  id: string;
  source: {
    alias: string;
    type: EventRecordSourceTypeValue;
  };
  time: number;
}

/** 本地 UI 演示用的事件列表，total 是卡片标题计数，不必等于当前已加载条数 */
export interface IEventRecordsResult {
  items: IEventRecordItem[];
  total: number;
}

interface IAlertAnalysisPayloadBase {
  referenceIds: string[];
  requestMessageId: string;
  source: { type: 'local_ui_mock' };
  subject: { alert_id: string; type: 'alert' };
}

export interface IMetricSeriesPayload extends IAlertAnalysisPayloadBase {
  result: IMetricSeriesResult;
  resultKind: typeof AlertAnalysisResultKind.METRIC_SERIES;
}

export interface ILogRecordsPayload extends IAlertAnalysisPayloadBase {
  result: ILogRecordsResult;
  resultKind: typeof AlertAnalysisResultKind.LOG_RECORDS;
}

export interface IAlertListPayload extends IAlertAnalysisPayloadBase {
  result: IAlertListResult;
  resultKind: typeof AlertAnalysisResultKind.ALERT_LIST;
}

export interface IEventRecordsPayload extends IAlertAnalysisPayloadBase {
  result: IEventRecordsResult;
  resultKind: typeof AlertAnalysisResultKind.EVENT_RECORDS;
}

export type IAlertAnalysisResultPayload =
  | IAlertListPayload
  | IEventRecordsPayload
  | ILogRecordsPayload
  | IMetricSeriesPayload;

export interface IAlertAnalysisMessage {
  eventId: string;
  messageType: typeof AlertAnalysisMessageType.ANALYSIS_RESULT;
  payload: IAlertAnalysisResultPayload;
  schemaVersion: 1;
}

export interface IAlertAnalysisMessageExtra {
  alert_analysis_message?: IAlertAnalysisMessage;
}

/**
 * 从消息的 `property.extra` 中取出告警分析 envelope。
 * 校验 schemaVersion 与 messageType，避免误解析其他来源的 extra 数据。
 */
const getAlertAnalysisEnvelope = (message: Message): IAlertAnalysisMessage | null => {
  const extra = message.property?.extra as IAlertAnalysisMessageExtra | undefined;
  const envelope = extra?.alert_analysis_message;
  if (envelope?.schemaVersion === 1 && envelope.messageType === AlertAnalysisMessageType.ANALYSIS_RESULT) {
    return envelope;
  }
  return null;
};

/** 提取指标趋势结果，消息不属于该种类时返回 null */
export const getMetricSeriesResult = (message: Message): IMetricSeriesResult | null => {
  const envelope = getAlertAnalysisEnvelope(message);
  if (envelope?.payload?.resultKind === AlertAnalysisResultKind.METRIC_SERIES) {
    return envelope.payload.result ?? null;
  }
  return null;
};

/** 提取日志聚类结果，消息不属于该种类时返回 null */
export const getLogRecordsResult = (message: Message): ILogRecordsResult | null => {
  const envelope = getAlertAnalysisEnvelope(message);
  if (envelope?.payload?.resultKind === AlertAnalysisResultKind.LOG_RECORDS) {
    return envelope.payload.result ?? null;
  }
  return null;
};

/** 提取维度命中告警列表结果，消息不属于该种类时返回 null */
export const getAlertListResult = (message: Message): IAlertListResult | null => {
  const envelope = getAlertAnalysisEnvelope(message);
  if (envelope?.payload?.resultKind === AlertAnalysisResultKind.ALERT_LIST) {
    return envelope.payload.result ?? null;
  }
  return null;
};

/** 提取事件列表结果，消息不属于该种类时返回 null */
export const getEventRecordsResult = (message: Message): IEventRecordsResult | null => {
  const envelope = getAlertAnalysisEnvelope(message);
  if (envelope?.payload?.resultKind === AlertAnalysisResultKind.EVENT_RECORDS) {
    return envelope.payload.result ?? null;
  }
  return null;
};
