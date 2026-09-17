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

import type { IRumField } from '../../typings';
import type { RumCardToneType, RumRatingType, RumSectionType } from './enum';

/** 徽标：标题右侧的关键指标与状态 */
export interface IRumBadgeVM {
  /** 背景色 */
  bgColor: string;
  /** 文本色 */
  color?: string;
  /** 前置图标 class（如计时器） */
  icon?: string;
  key: string;
  text: string;
}

/**
 * 卡片描述符：把区块里的一个字段分组翻译成若干张统计卡片。
 * 一个分组可以拆成多张卡（如 http_result 在 XHR 场景下拆成「HTTP 状态」与「业务结果」），
 * 返回空数组表示该分组不渲染。这是新增 span 类型时最主要的扩展点，见 registry/card-registry。
 */
export type IRumCardDescriptor = (
  data: Record<string, unknown>,
  ctx: IRumCardResolveCtx
) => Array<Omit<IRumSummaryCardVM, 'key'>>;

/** 卡片底部辅助说明的一段文本 */
export interface IRumCardFooterPart {
  text: string;
  tone?: RumCardToneType;
}

/** 卡片描述符的推导上下文 */
export interface IRumCardResolveCtx {
  /** 当前 span 的原始数据，用于取分组外的字段 */
  originData: Record<string, any>;
  /** 关联接口拉回的补充数据，未就绪时为空对象 */
  related: Record<string, unknown>;
  /** 复制文本到剪贴板并给出提示 */
  copyText: (value: string) => void;
  /** 按字段元信息格式化值（单位换算 + 枚举别名） */
  formatField: (fieldName: string, value: unknown) => string;
  /** 按字段名取字段元信息（别名、单位、枚举） */
  getField: (fieldName: string) => IRumField | undefined;
  /** 按字段名取展示别名，无别名时回退字段名 */
  getFieldAlias: (fieldName: string) => string;
}

/** 标题区视图模型 */
export interface IRumDetailHeaderVM {
  badges: IRumBadgeVM[];
  /** 公共信息按每行 5 项分组 */
  items: IRumOverviewItemVM[];
  /** 类型图标（svg 资源地址） */
  logo: string;
  title: string;
}

/** 归一化后的区块视图模型，渲染层只认这个结构 */
export interface IRumDetailSectionVM {
  /** 卡片按行分组，一行内的卡片等宽平铺 */
  cardRows?: IRumSummaryCardVM[][];
  key: string;
  /** 键值列表区块的数据 */
  keyValues?: Array<{ label: string; value: string }>;
  /** 是否处于关联数据加载中（骨架态） */
  loading?: boolean;
  /** 评级条区块的数据 */
  ratingBar?: IRumRatingBarVM;
  /** 区块标题右侧的补充说明（如「总耗时：122.2ms」） */
  subTitle?: string;
  /** 区块顶部的提示条 */
  tip?: string;
  /** 区块标题，为空时不渲染标题行 */
  title: string;
  type: RumSectionType;
  /** 瀑布图区块的数据 */
  waterfall?: IRumWaterfallVM;
}

/** 原始数据面板的一个折叠块 */
export interface IRumOriginBlockVM {
  /** 分组块：Links 按 trace_id 分组、Events 按事件名分组，组内为键值列表 */
  groups?: Array<{ name: string; rows: IRumOriginRowVM[] }>;
  key: string;
  /** 普通块：平铺键值列表 */
  rows?: IRumOriginRowVM[];
  /** 展开时标题右侧是否展示块内搜索框（当前仅 Events） */
  searchable?: boolean;
  /** 折叠时展示的单行摘要 */
  summary: string;
  title: string;
}

/** 原始数据面板的一行键值 */
export interface IRumOriginRowVM {
  key: string;
  /** 展示用的值文本 */
  value: string;
  /** 值的原始类型，决定前置的数据类型图标 */
  valueType: 'boolean' | 'number' | 'object' | 'string';
}

/** 公共信息行里的一项 */
export interface IRumOverviewItemVM {
  /** 蓝色可点击（会话 / 视图 / View 详情） */
  isLink?: boolean;
  key: string;
  label: string;
  value: string;
}

/** 评级条视图模型 */
export interface IRumRatingBarVM {
  /** 指标全称，如「累积布局偏移（Cumulative Layout Shift，CLS）」 */
  metricLabel: string;
  /** 当前命中的评级 */
  rating: RumRatingType | string;
  /** 评级别名，如「需改进」 */
  ratingAlias: string;
  /** 各评级分段 */
  segments: IRumRatingSegmentVM[];
  /** 指针在整条评级条上的百分比位置（0~100） */
  thumbPercent: number;
  /** 格式化后的指标值 */
  valueText: string;
}

/** 评级条的一个分段 */
export interface IRumRatingSegmentVM {
  /** 分段颜色 */
  color: string;
  /** 分段文案，如「良好 ≦ 2500ms」 */
  label: string;
  rating: RumRatingType | string;
  /** 分段右侧的阈值刻度文案，最后一段为空 */
  threshold: string;
}

/** 统计卡片视图模型 */
export interface IRumSummaryCardVM {
  /** 卡片的类名 */
  cardCls?: string;
  /** 卡片底部辅助说明，支持分段着色 */
  footer?: IRumCardFooterPart[];
  key: string;
  /** 卡片标题 */
  label: string;
  /** 主值右上角的操作入口（如「复制完整地址」） */
  operation?: { label: string; onClick: () => void };
  /** 主值前缀标签（如 HTTP Method 的 POST 色块） */
  prefixTag?: { bgColor: string; text: string };
  /** 以迷你柱状图代替主值展示（如 24 小时趋势） */
  sparkline?: number[];
  /** 卡片右上角的状态标签（如「低可信度」） */
  tag?: { bgColor: string; color: string; text: string };
  /** 主值语义配色 */
  tone?: RumCardToneType;
  /** 主值右侧的次要文本（单位或环比） */
  unit?: { text: string; tone?: RumCardToneType };
  /** 主值 */
  value: string;
}

/** 瀑布图的一行 */
export interface IRumWaterfallRowVM {
  /** 色块颜色 */
  color: string;
  /** 色块宽度百分比 */
  durationPercent: number;
  durationText: string;
  key: string;
  label: string;
  /** 色块左偏移百分比 */
  startPercent: number;
}

/** 瀑布图视图模型 */
export interface IRumWaterfallVM {
  /** 时间点标记 */
  markers?: Array<{ key: string; label: string; percent: number }>;
  /** 跨阶段的合并说明（如「连接复用：DNS、TCP、TLS」） */
  mergedTip?: string;
  rows: IRumWaterfallRowVM[];
}
