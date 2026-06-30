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

import { cloneDeep } from 'lodash';

import { data as MOCK_GRAPH_UNIFY_QUERY } from '../../../mock/graph_unify_query';

/**
 * 图表取数 API 的最小契约：与 useEcharts 中 `$api[apiModule][apiFunc](params, config)` 对齐。
 * 当前仅 mock，后续切真实接口时保持同款签名即可零改动替换。
 */
export type GraphApi = Record<string, Record<string, (params: Record<string, any>, config?: any) => Promise<any>>>;

/** mock 接口的网络延迟（ms），用于复现 loading 态 */
const MOCK_DELAY = 300;

/**
 * 创建图表取数 $api。
 * 现阶段返回 mock 数据；正式接入时把 grafana.graphUnifyQuery 换成真实 $api 调用即可。
 */
export function createGraphApi(): GraphApi {
  return {
    grafana: {
      graphUnifyQuery: () =>
        new Promise(resolve => {
          setTimeout(() => resolve(cloneDeep(MOCK_GRAPH_UNIFY_QUERY)), MOCK_DELAY);
        }),
    },
  };
}
