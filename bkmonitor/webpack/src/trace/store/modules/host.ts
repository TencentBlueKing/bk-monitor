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
import { computed, customRef, ref as deepRef, onScopeDispose, watch, ref } from 'vue';
import { shallowRef } from 'vue';

import { random } from 'monitor-common/utils';
import { defineStore } from 'pinia';

import { handleTransformToTimestamp } from '@/components/time-range/utils';
import { getDefaultTimezone } from '@/i18n/dayjs';

import type { HostPageScene } from '@/pages/host/constants/constants';
import type { EHostQuickCategory } from '@/pages/host/types/host-list';
import type { IWhereItem } from 'trace/components/retrieval-filter/typing';
const REFRESH_EFFECT_KEY = '__REFRESH_EFFECT_KEY__';

export const useHostStore = defineStore('host', () => {
  const timeRange = deepRef(['now-7d', 'now']);
  const timezone = shallowRef(getDefaultTimezone());
  const innerRefreshInterval = shallowRef(-1);
  const refreshImmediate = shallowRef('');
  const refreshId = shallowRef(random(4));
  // 主机监控 场景 host | process
  const scene = shallowRef<HostPageScene>('host');

  /** retrieval-filter ui 模式 where 条件 */
  const where = shallowRef<IWhereItem[]>([]);
  /** 主机列表高级过滤是否展开 */
  const filterExpanded = shallowRef(false);
  /** 当前激活的快捷过滤分类（空为不过滤） */
  const activeCategory = shallowRef<'' | EHostQuickCategory>('');
  /** 关键字模糊搜索 */
  const keyword = shallowRef('');

  /** 当前激活的 Tab */
  const activeTab = ref('');

  const timeRangeTimestamp = computed(() => {
    const [start, end] = handleTransformToTimestamp(timeRange.value);
    const params = {
      start_time: start,
      end_time: end,
      [REFRESH_EFFECT_KEY]: refreshId.value,
    };
    // 用于主动触发 依赖副作用 更新
    delete params[REFRESH_EFFECT_KEY];
    return params;
  });

  const refreshInterval = customRef((track, trigger) => {
    let timer: ReturnType<typeof setInterval>;
    return {
      get() {
        track();
        return innerRefreshInterval.value;
      },
      set(value) {
        if (timer) {
          clearInterval(timer);
        }
        if (value > 0) {
          timer = setInterval(
            () => {
              effectRefresh();
            },
            Math.max(value, 1000 * 60)
          );
        }
        innerRefreshInterval.value = value;
        trigger();
      },
    };
  });

  const effectRefresh = () => {
    refreshId.value = random(4);
  };

  watch(refreshImmediate, () => {
    effectRefresh();
  });

  onScopeDispose(() => {
    timeRange.value = ['now-7d', 'now'];
    timezone.value = getDefaultTimezone();
    refreshInterval.value = -1;
    refreshImmediate.value = '';
  });
  return {
    timeRange,
    timezone,
    refreshInterval,
    refreshImmediate,
    timeRangeTimestamp,
    scene,
    where,
    filterExpanded,
    activeCategory,
    keyword,
    activeTab,
  };
});
