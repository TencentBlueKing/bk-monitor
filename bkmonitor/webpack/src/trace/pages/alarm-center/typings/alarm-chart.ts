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

import type { ExploreTableRequestParams, IFormData } from 'monitor-pc/pages/event-explore/typing';

export enum EventTab {
  All = 'all',
  Warning = 'warning',
}

export interface AlertEventTagDetailParams {
  alert_id?: string;
  bk_biz_id?: number;
  interval?: number;
  limit?: number;
  sources?: string[];
  start_time?: number;
}

export interface AlertScatterClickEvent extends AlertEventTagDetailParams {
  bizId?: number;
  query_config?: Omit<ExploreTableRequestParams, 'query_configs'> & {
    query_configs: (IFormData & { interval?: number })[];
  };
}

export interface IEventListItem {
  [key: string]: any;
  'event.content': { detail: Record<string, { alias?: string; label: string; url?: string; value: string }> };
  event_name: { alias?: string; value: string };
  source: { alias?: string; value: string };
  target: { alias?: string; url?: string; value?: string };
  time?: { value: string };
}

export interface IEventTopkItem {
  [key: string]: any;
  count: number;
  event_name: { alias?: string; value: string };
  proportions: number;
  source: { alias?: string; value: string };
}

export interface IPosition {
  left: number;
  top: number;
}
