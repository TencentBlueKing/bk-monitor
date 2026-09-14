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
/**
 * 详情区块的展示类型，取值需与 record_detail 接口的 sections[].type 对齐。
 * 新增展示类型时：这里加枚举 -> section-registry 注册渲染组件，其余代码无需改动。
 */
export const RumSectionTypeEnum = {
  /** 统计卡片组 */
  SUMMARY_CARDS: 'summary_cards',
  /** 瀑布时序图 */
  WATERFALL: 'waterfall',
  /** 指标评级条 */
  RATING_BAR: 'rating_bar',
  /** 平铺键值列表（前端扩展类型，用于「版本关联」这类无对应接口结构的区块） */
  KEY_VALUE_LIST: 'key_value_list',
} as const;

export type RumSectionType = (typeof RumSectionTypeEnum)[keyof typeof RumSectionTypeEnum];

/** 详情抽屉的 Tab，「链路上下文」本期未实现，渲染为禁用态 */
export const RumDetailTabEnum = {
  /** 基础信息 */
  BASIC: 'basic',
  /** 链路上下文 */
  TRACE_CONTEXT: 'trace_context',
} as const;

export type RumDetailTabType = (typeof RumDetailTabEnum)[keyof typeof RumDetailTabEnum];

/** Web Vitals 指标评级，取值需与 rating_config[].rating 对齐 */
export const RumRatingEnum = {
  /** 良好 */
  GOOD: 'good',
  /** 需改进 */
  NEEDS_IMPROVEMENT: 'needs_improvement',
  /** 差 */
  POOR: 'poor',
} as const;

export type RumRatingType = (typeof RumRatingEnum)[keyof typeof RumRatingEnum];

/** 统计卡片主值的语义配色，卡片描述符声明语义、样式层决定具体色值 */
export const RumCardToneEnum = {
  /** 默认（深灰文本） */
  DEFAULT: 'default',
  /** 成功（绿） */
  SUCCESS: 'success',
  /** 警告（橙） */
  WARNING: 'warning',
  /** 危险（红） */
  DANGER: 'danger',
  /** 链接（蓝，可点击） */
  LINK: 'link',
} as const;

export type RumCardToneType = (typeof RumCardToneEnum)[keyof typeof RumCardToneEnum];
