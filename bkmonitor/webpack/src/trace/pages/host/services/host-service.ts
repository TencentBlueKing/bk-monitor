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

import { getTopoTree } from 'monitor-api/modules/commons';
import { searchHostInfo, searchHostMetric } from 'monitor-api/modules/performance';

import type { IHostTopoTree } from '../types';
import type { IHostBaseInfo, IHostMetricInfo } from '../types/host';

/**
 * @description: 获取基础主机列表, 这个 API 要更快，但是不包含指标数据, 用于主机列表第一屏渲染
 * @returns {Promise<IHostBaseInfo[]>} 基础主机列表
 */
export const getHostInfoList = async () => {
  const data: IHostBaseInfo[] = await searchHostInfo().catch(() => []);
  return data;
};

/**
 * @description: 获取带指标数据的主机列表 , 这个 API 要慢一些，但是包含所有的 host 指标数据，用于主机列表补充渲染
 * @returns {Promise<IHostMetricInfo[]>} 带指标数据的主机列表
 */
export const getHostMetricInfoList = async () => {
  const { hosts }: { hosts: IHostMetricInfo[] } = await searchHostMetric().catch(() => {
    return { hosts: [] };
  });
  return hosts;
};

/**
 * @description: 获取主机拓扑树, 根据业务ID获取主机拓扑树
 * @param bizId 业务ID
 * @returns {Promise<IHostTopoTree[]>} 主机拓扑树
 */
export const getHostTopoTreeByBizId = async (bizId: number | string = window.cc_biz_id) => {
  const data: IHostTopoTree[] = await getTopoTree({
    bk_biz_id: bizId,
    condition_list: [],
    instance_type: 'host',
    remove_empty_nodes: false,
  }).catch(() => []);
  return data;
};
