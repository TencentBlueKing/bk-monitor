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

import { onBeforeUnmount, shallowRef, watch } from 'vue';
import type { WatchSource } from 'vue';

import { random } from 'monitor-common/utils';
import { echartsConnect, echartsDisconnect } from 'monitor-ui/monitor-echarts/utils';

/** random ID 默认长度 */
const DEFAULT_ID_LENGTH = 8;

export interface UseEchartsGroupConnectOptions<T = unknown> {
  /** 是否立即执行 watch（默认 true） */
  immediate?: boolean;
  /** 是否在数据源为空时跳过 connect（默认 true） */
  skipOnEmpty?: boolean;
  /** 判断数据源是否为空的函数（默认检查 Array 长度） */
  isEmpty?: (value: T) => boolean;
}

/**
 * @description 管理 echarts 图表联动组的生命周期：数据变化时自动 disconnect 旧组 → connect 新组，卸载时自动清理
 * @param {WatchSource<T>} source - 触发重建联动的数据源(与 watch 首参行为一致)
 * @param {UseEchartsGroupConnectOptions<T>} options - 可选配置
 * @returns {{ chartGroupId: ShallowRef<string> }} 当前联动组 ID
 */
export const useEchartsGroupConnect = <T = unknown>(
  source: WatchSource<T>,
  options: UseEchartsGroupConnectOptions<T> = {}
) => {
  const { skipOnEmpty = true, isEmpty = defaultIsEmpty, immediate = true } = options;

  /** 图表联动组 ID */
  const chartGroupId = shallowRef(random(DEFAULT_ID_LENGTH));

  watch(
    source,
    value => {
      echartsDisconnect(chartGroupId.value);
      if (skipOnEmpty && isEmpty(value)) return;
      const newId = random(DEFAULT_ID_LENGTH);
      echartsConnect(newId);
      chartGroupId.value = newId;
    },
    { immediate }
  );

  onBeforeUnmount(() => {
    echartsDisconnect(chartGroupId.value);
  });

  return { chartGroupId };
};

/**
 * @description 默认的空值判断：数组检查长度，其他类型检查 falsy
 * @param {unknown} value - 待检查的值
 * @returns {boolean} 是否为空
 */
function defaultIsEmpty(value: unknown): boolean {
  if (Array.isArray(value)) return !value.length;
  return !value;
}
