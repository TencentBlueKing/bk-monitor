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
import type { RumRatingType, RumSectionType } from './enum';

/** 详情抽屉打开时由列表侧传入的上下文 */
export interface IRumDetailContext {
  app_name: string;
  /** 秒级结束时间，关联数据查询以此为基准偏移 */
  end_time: number;
  record_id: string;
  /** 当前 span 类型，决定走哪套扩展配置 */
  span_type: string;
  /** 秒级开始时间 */
  start_time: number;
}

/**
 * 详情里的一个字段项。
 * field_name 以 `display.` 开头时为后端计算出的展示字段，此时 field_alias / alias 必定由后端给出；
 * 其余为原始字段，别名与单位优先从 view_config 的字段元信息取，接口只回传原始值。
 */
export interface IRumDetailItem {
  /** 格式化后的值或枚举别名 */
  alias?: string;
  /** 字段展示名称 */
  field_alias?: string;
  field_name: string;
  value: unknown;
}

/** 标题区：标题、关键指标徽标与公共信息 */
export interface IRumDetailOverview {
  badges: IRumDetailItem[];
  items: IRumDetailItem[];
  title: string;
}

/** 接口返回的详情区块，data 与 items 按区块结构二选一 */
export interface IRumDetailSection {
  data?: IRumRatingBarData | IRumSummaryCardsData | IRumWaterfallData;
  items?: IRumDetailItem[];
  key: string;
  type: RumSectionType;
}

export interface IRumRatingBarData {
  'attributes.vital.metric': string;
  'attributes.vital.value': number;
  'display.rating_config': IRumRatingConfig[];
}

/** 评级阈值配置，按 value 从小到大排列，最差评级不带 value */
export interface IRumRatingConfig {
  alias?: string;
  rating: RumRatingType | string;
  value?: number;
}

/** record_detail 接口返回结构 */
export interface IRumRecordDetail {
  /** 原始 Span，保留嵌套结构，用于底部原始数据面板 */
  origin_data: Record<string, any>;
  overview: IRumDetailOverview;
  sections: IRumDetailSection[];
  span_id: string;
}

/**
 * 统计卡片区块的数据：key 为分组标识（如 request / duration / http_result），
 * value 为该分组下的字段字典。分组标识决定卡片的展示形态，见 card-registry。
 */
export type IRumSummaryCardsData = Record<string, Record<string, unknown>>;

export interface IRumWaterfallData {
  markers?: IRumWaterfallMarker[];
  phases: IRumWaterfallPhase[];
  /** 总耗时，缺失时由各阶段推导 */
  total_duration?: number;
  unit: string;
}

/** 瀑布图上的时间点标记（如 TTFB / FCP / LCP） */
export interface IRumWaterfallMarker {
  field_name: string;
  key: string;
  value: number;
}

/** 瀑布图的一个阶段 */
export interface IRumWaterfallPhase {
  alias: string;
  /** 阶段耗时，单位见 IRumWaterfallData.unit */
  duration: number;
  key: string;
  /** 相对起点的偏移量，单位见 IRumWaterfallData.unit */
  start: number;
}
