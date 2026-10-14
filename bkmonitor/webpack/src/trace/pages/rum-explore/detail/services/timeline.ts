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
import { rumTimeline } from 'monitor-api/modules/rum_query';

import type { IRumTimelineResponse } from '../typings';
import type { RequestConfig } from 'monitor-api/base';

/** 请求失败时不弹全局错误提示，由链路上下文面板展示异常态 */
const SILENT = { needMessage: false };

/**
 * @description 按 View 查询链路上下文（会话时间线接口的 view_id 模式，只返回该 View 一个顶层节点）
 * @param params 应用名与视图 ID
 * @returns 接口失败时返回 null，与「无数据」区分
 */
export async function getViewTimeline(
  params: { app_name: string; view_id: string },
  requestConfig?: RequestConfig
): Promise<IRumTimelineResponse | null> {
  const res = await rumTimeline(params, { ...SILENT, ...requestConfig }).catch(() => null);
  return res || null;
}
