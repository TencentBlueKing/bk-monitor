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

import {
  getHostMetricGroupPanelOrder,
  getHostViewsPanels,
  getProcessMetricGroupPanelOrder,
  getProcessViewsPanels,
} from 'monitor-api/modules/performance';

import { requestHost } from './host-request';

import type { MetricGroupPanelOrder } from '../types/panel-order';
import type { HostViewsRowPanel } from '../types/panels';

/** 保存或重置后传入 afterPending，等待旧读取结束再读取最新配置。 */
export const getHostViewsPanelsApi = (afterPending = false): Promise<HostViewsRowPanel[]> =>
  requestHost('scene_view/get_host_views_panels', {}, params => getHostViewsPanels(params), { afterPending });

export const getProcessViewsPanelsApi = (afterPending = false): Promise<HostViewsRowPanel[]> =>
  requestHost('scene_view/get_process_views_panels', {}, params => getProcessViewsPanels(params).catch(() => []), {
    afterPending,
  });

export const getHostMetricGroupPanelOrderApi = (afterPending = false): Promise<MetricGroupPanelOrder[]> =>
  requestHost('scene_view/get_host_metric_group_panel_order', {}, params => getHostMetricGroupPanelOrder(params), {
    afterPending,
  });

export const getProcessMetricGroupPanelOrderApi = (afterPending = false): Promise<MetricGroupPanelOrder[]> =>
  requestHost(
    'scene_view/get_process_metric_group_panel_order',
    {},
    params => getProcessMetricGroupPanelOrder(params).catch(() => []),
    { afterPending }
  );
