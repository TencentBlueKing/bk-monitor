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
import { shallowRef, watch } from 'vue';
import { onScopeDispose } from 'vue';

import { searchAction } from 'monitor-api/modules/alert_v2';

import { useAlarmCenterDetailStore } from '../../../store/modules/alarm-center-detail';

import type { ActionTableItem, AlertActionOverview } from '../typings';

export function useAlarmBasicInfo() {
  const alarmCenterDetailStore = useAlarmCenterDetailStore();

  /** 告警状态 */
  const alarmStatusOverview = shallowRef<AlertActionOverview>(null);
  /** 告警状态处理数据 */
  const alarmStatusActions = shallowRef<ActionTableItem[]>([]);
  /** 告警状态总条数 */
  const alarmStatusTotal = shallowRef(0);

  // 获取处理状态数据
  const getHandleListData = async () => {
    const params = {
      bk_biz_id: alarmCenterDetailStore.alarmDetail.bk_biz_id,
      page: 1,
      page_size: 100,
      alert_ids: [alarmCenterDetailStore.alarmId],
      status: ['failure', 'success', 'partial_failure'],
      ordering: ['-create_time'],
      conditions: [{ key: 'parent_action_id', value: [0], method: 'eq' }], // 处理状态数据写死条件
    };
    const data = await searchAction(params);
    alarmStatusOverview.value = data.overview;
    alarmStatusActions.value = data.actions;
    alarmStatusTotal.value = data.total;
  };

  watch(
    () => alarmCenterDetailStore.alarmDetail,
    newVal => {
      if (newVal && !alarmCenterDetailStore.loading) {
        getHandleListData();
      }
    },
    { immediate: true }
  );

  onScopeDispose(() => {
    alarmStatusOverview.value = null;
  });

  return {
    alarmStatusOverview,
    alarmStatusActions,
    alarmStatusTotal,
  };
}
