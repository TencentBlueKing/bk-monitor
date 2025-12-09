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

import { type MaybeRef, shallowRef, watchEffect } from 'vue';

import { get } from '@vueuse/core';

import { type ALertTracesData } from '../typings';

/**
 * @method useAlertTraces 调用链数据 hook
 * @description 告警详情 - 调用链 - 表格数据 获取及相关的处理逻辑
 * @param {MaybeRef<string>} alertId 告警ID
 */
export const useAlertTraces = (alertId: MaybeRef<string>) => {
  /** 调用链表格展示数据 */
  const traceList = shallowRef([]);
  /** 调用链查询配置 */
  const traceQueryConfig = shallowRef({});

  /**
   * @method getTraceList 请求接口
   * @description 获取调用链表格数据
   */
  const getTraceList = async () => {
    const data = await generationTraceMockData<ALertTracesData>(get(alertId));
    traceList.value = data.list;
    traceQueryConfig.value = data.query_config;
  };
  watchEffect(getTraceList);

  return {
    traceList,
    traceQueryConfig,
  };
};

const mockData: ALertTracesData = {
  query_config: {
    app_name: 'bkop',
    sceneMode: 'span',
    where: [
      {
        key: 'resource.service.name',
        operator: 'equal',
        value: ['example.greeter'],
      },
    ],
  },
  list: [
    {
      app_name: 'bkop',
      trace_id: '84608839c9c45c074d5b0edf96d3ed0f',
      root_service: 'example.greeter',
      root_span_name: 'trpc.example.greeter.http/timeout',
      root_service_span_name: '/timeout',
      error_msg:
        'http client transport RoundTrip timeout: Get http://trpc-otlp-oteam-demo-service:8080/timeout: context deadline exceeded, cost:2.000525304s',
    },
  ],
};

/** 生成调用链 mock 数据 */
const generationTraceMockData = <T extends ALertTracesData>(alertId: string): Promise<T> | T => {
  return new Promise(res => {
    setTimeout(() => {
      res(mockData as T);
    }, 600);
  });
};
