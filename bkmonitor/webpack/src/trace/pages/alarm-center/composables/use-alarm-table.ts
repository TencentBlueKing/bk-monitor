/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
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
import { onMounted, onScopeDispose, shallowRef, watchEffect } from 'vue';

import { getOperatorDisabled } from '../utils';
import { useAlarmCenterStore } from '@/store/modules/alarm-center';

import type { ActionTableItem, AlertTableItem, IncidentTableItem } from '../typings';

export function useAlarmTable() {
  const alarmStore = useAlarmCenterStore();
  // 分页参数
  const pageSize = shallowRef(50);
  // 当前页
  const page = shallowRef(1);
  // 总条数
  const total = shallowRef(0);
  // 数据
  const data = shallowRef<(ActionTableItem | AlertTableItem | IncidentTableItem)[]>([]);
  // 排序
  const ordering = shallowRef('');
  // 是否加载中
  const loading = shallowRef(false);
  // 请求中止控制器
  let abortController: AbortController | null = null;

  const effectFunc = async () => {
    // 中止上一次未完成的请求
    if (abortController) {
      abortController.abort();
    }
    // 创建新的中止控制器
    abortController = new AbortController();
    const { signal } = abortController;

    loading.value = true;
    data.value = [];
    const res = await alarmStore.alarmService.getFilterTableList(
      {
        ...alarmStore.commonFilterParams,
        page_size: pageSize.value,
        page: page.value,
        ordering: ordering.value ? [ordering.value] : [],
      },
      { signal }
    );
    // 获取告警关联事件数 和 关联告警信息
    await alarmStore.alarmService.getAlterRelevance(res.data, { signal }).then(result => {
      if (!result) return;
      // eslint-disable-next-line @typescript-eslint/naming-convention
      const { event_count, extend_info } = result;
      for (const item of res.data as AlertTableItem[]) {
        item.event_count = event_count?.[item.id];
        item.extend_info = extend_info?.[item.id];
        item.followerDisabled = getOperatorDisabled(item.follower, item.assignee);
      }
    });
    // 检查请求是否已被中止，确保不会更新过期数据
    if (signal.aborted) return;
    total.value = res.total;
    data.value = res.data;
    loading.value = false;
  };
  // 由于在 setup(create) | BeforeMount 时机可能需要获取路由参数对变量进行初始化
  // 如果不在 onMounted 时机进行 watchEffect 可能会导致 effect 首次执行是错误的且是非必要的
  onMounted(() => {
    watchEffect(effectFunc);
  });

  onScopeDispose(() => {
    // 中止未完成的请求
    if (abortController) {
      abortController.abort();
      abortController = null;
    }
    pageSize.value = 10;
    page.value = 1;
    total.value = 0;
    data.value = [];
    loading.value = false;
    ordering.value = '';
  });
  return {
    pageSize,
    page,
    total,
    data,
    loading,
    ordering,
  };
}
