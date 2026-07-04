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

/**
 * @description 判断请求错误是否为终止状态
 * @param {unknown} err - 错误对象
 * @returns {boolean} 是否为终止状态
 */
const requestErrorMessage = (err: unknown): boolean => {
  const message = (err as Error)?.message;
  return message === 'canceled' || message === 'aborted' || (err as Error)?.name === 'AbortError';
};

/**
 * @description 获取无数据策略信息（Service 中间层）
 * @description 封装底层 API 调用，统一错误兜底
 * @param {IRumAppBaseParams} params - 请求参数
 * @param {{ signal?: AbortSignal }} [requestConfig] - 请求配置
 * @returns {Promise<{ data: IStrategyData; isAborted: boolean }>} 策略数据与终止状态
 */
export const fetchNoDataStrategyInfo = async (
  params: IRumAppBaseParams,
  requestConfig: { signal?: AbortSignal } = {}
): Promise<{ data: IStrategyData; isAborted: boolean }> => {
  let isAborted = false;

  const data = await getNoDataStrategyInfo(params, requestConfig).catch((err: unknown) => {
    isAborted = requestErrorMessage(err);
    return null;
  });

  return { data, isAborted };
};

/**
 * @description 获取数据视图配置（Service 中间层）
 * @description 封装底层 API 调用，统一处理数据转换和错误兜底
 * @param {IRumAppBaseParams} params - 请求参数
 * @param {{ signal?: AbortSignal }} [requestConfig] - 请求配置
 * @returns {Promise<{ data: IPanelModel[]; isAborted: boolean }>} 面板配置列表与终止状态
 */
export const fetchDataViewConfig = async (
  params: IRumAppBaseParams,
  requestConfig: { signal?: AbortSignal } = {}
): Promise<{ data: IPanelModel[]; isAborted: boolean }> => {
  let isAborted = false;

  const rawData = await getDataViewConfig(params, requestConfig).catch((err: unknown) => {
    isAborted = requestErrorMessage(err);
    return [] as IPanelModel[];
  });

  return { data: rawData, isAborted };
};

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

/**
 * @description 获取数据采样（Service 中间层）
 * @description 封装底层 API 调用，统一处理数据转换和错误兜底
 * @param {IRumAppBaseParams} params - 请求参数
 * @param {{ signal?: AbortSignal }} [requestConfig] - 请求配置
 * @returns {Promise<{ data: IDataSamplingItem[]; isAborted: boolean }>} 采样数据列表与终止状态
 */
export const fetchDataSampling = async (
  params: IRumAppBaseParams,
  requestConfig: { signal?: AbortSignal } = {}
): Promise<{ data: IDataSamplingItem[]; isAborted: boolean }> => {
  let isAborted = false;

  const rawData = await getDataSampling(params, requestConfig).catch((err: unknown) => {
    isAborted = requestErrorMessage(err);
    return [] as IDataSamplingItem[];
  });

  return { data: rawData, isAborted };
};
