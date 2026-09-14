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
import { rumRecordDetail } from 'monitor-api/modules/rum_query';

import { USE_DETAIL_MOCK } from '../constants';
import { getMockRecordDetail } from './mock/record-detail.mock';

import type { RumModeType } from '../../typings';
import type { IRumDetailContext, IRumRecordDetail } from '../typings';
import type { RequestConfig } from 'monitor-api/base';

/** 请求失败时不弹全局错误提示，由调用方降级展示 */
const SILENT = { needMessage: false };

/**
 * @description 查询单条记录的详情
 * @param context 详情上下文（应用、记录 ID、span 类型、时间范围）
 * @param mode 查询层级，与列表侧保持一致
 */
export async function getRecordDetail(
  context: IRumDetailContext,
  mode: RumModeType,
  requestConfig?: RequestConfig
): Promise<IRumRecordDetail | null> {
  if (USE_DETAIL_MOCK) {
    return getMockRecordDetail(context.span_type, context.record_id);
  }
  const res = await rumRecordDetail(
    { app_name: context.app_name, mode, record_id: context.record_id },
    { ...SILENT, ...requestConfig }
  ).catch(() => null);
  return res || null;
}
