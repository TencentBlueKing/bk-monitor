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
import { SPAN_TYPE_META } from '../../constants';

/**
 * 链路上下文里 Span 行的类型差异配置。
 * 链路本身与 span 类型无关，只有行内展示随类型变化；新增差异时在 TIMELINE_SPAN_TYPE_CONFIG 补一条即可。
 */
export interface IRumTimelineSpanTypeConfig {
  /** 是否在行尾展示 HTTP 状态码 */
  showStatusCode?: boolean;
  /** 类型标签文案，入参为 origin_data.attributes，未登记时取 SPAN_TYPE_META 的 label */
  tagLabel?: (attributes: Record<string, unknown>) => string;
}

const TIMELINE_SPAN_TYPE_CONFIG: Record<string, IRumTimelineSpanTypeConfig> = {
  resource: {
    showStatusCode: true,
    tagLabel: attributes => {
      const resourceType = attributes['resource.type'];
      return resourceType ? `Resource(${resourceType})` : SPAN_TYPE_META.resource.label;
    },
  },
};

/** @description 取 span 类型在链路上下文里的展示配置，未登记的类型走默认展示 */
export function getTimelineSpanTypeConfig(spanType: string): IRumTimelineSpanTypeConfig {
  return TIMELINE_SPAN_TYPE_CONFIG[spanType] ?? {};
}
