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

/** 全局检索接口的 data 帧，只关心包含 Trace 命中项的事件。 */
export interface IRumSearchEvent {
  /** 当前流式帧累计返回的 Trace 命中项。 */
  items?: IRumTraceInfo[];
  /** 全局检索的结果类别，Trace 命中帧的类型为 trace。 */
  type?: string;
}
/** 关联 Trace 的检索结果，打开 Trace 详情需要其所属的 APM 应用与业务。 */
export interface IRumTraceInfo {
  /** Trace 所属的 APM 应用，作为详情请求的应用名。 */
  app_name: string;
  /** Trace 所属业务，跨业务检索时与当前 RUM 记录的业务不同。 */
  bk_biz_id?: number | string;
  /** 命中的 Trace ID，供列表关联与详情定位使用。 */
  trace_id: string;
}
