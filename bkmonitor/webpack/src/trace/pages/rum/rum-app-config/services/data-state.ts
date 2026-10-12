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
  getDataSampling,
  getDataViewConfig,
  getNoDataStrategyInfo,
  noDataStrategyDisable,
  noDataStrategyEnable,
} from 'monitor-api/modules/rum_meta';

import type { IDataSamplingItem, INoDataStrategyParams, IRumAppBaseParams, IStrategyData } from '../../typings';
import type { IPanelModel } from 'monitor-ui/chart-plugins/typings';

/** 获取配置失败由对应区域展示重试，取消请求由调用方的 signal 判断。 */
export const fetchNoDataStrategyInfo = (
  params: IRumAppBaseParams,
  requestConfig: { signal?: AbortSignal } = {}
): Promise<IStrategyData> => getNoDataStrategyInfo(params, { ...requestConfig, needMessage: false });

export const fetchDataViewConfig = (
  params: IRumAppBaseParams,
  requestConfig: { signal?: AbortSignal } = {}
): Promise<IPanelModel[]> => getDataViewConfig(params, { ...requestConfig, needMessage: false });

/**
 * @description 开启无数据告警策略
 * @param {INoDataStrategyParams} params - 请求参数
 * @returns {Promise<void>}
 */
export const enableNoDataStrategy = async (params: INoDataStrategyParams): Promise<void> => {
  await noDataStrategyEnable(params);
};

/**
 * @description 关闭无数据告警策略
 * @param {INoDataStrategyParams} params - 请求参数
 * @returns {Promise<void>}
 */
export const disableNoDataStrategy = async (params: INoDataStrategyParams): Promise<void> => {
  await noDataStrategyDisable(params);
};

export const fetchDataSampling = (
  params: IRumAppBaseParams,
  requestConfig: { signal?: AbortSignal } = {}
): Promise<IDataSamplingItem[]> => getDataSampling(params, { ...requestConfig, needMessage: false });
