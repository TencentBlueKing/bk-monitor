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

import { computed } from 'vue';

import { useAlarmCenterStore } from '@/store/modules/alarm-center';
import { useStorage } from '@vueuse/core';

import { MY_ALARM_BIZ_ID, MY_AUTH_BIZ_ID, type TableColumnItem } from '../typings';

import type { BkUiSettings } from '@blueking/tdesign-ui';
/** 业务名称/空间名称 字段 */
const BK_BIZ_NAME_FIELD = 'bk_biz_name';
export function useAlarmTableColumns() {
  const alarmStore = useAlarmCenterStore();
  const defaultTableFields = computed(() => {
    return alarmStore.alarmService.allTableColumns.filter(item => item.is_default).map(item => item.colKey);
  });

  // 不通过 computed 计算属性过渡会无法正确收集到响应式Effect，导致storageKey 变更时无法触发 useStorage 的响应式逻辑
  const storageKey = computed(() => alarmStore.alarmService.storageKey);
  const storageColumns = useStorage<string[]>(storageKey, defaultTableFields);

  const tableColumns = computed<TableColumnItem[]>(() => {
    return storageColumns.value
      .map(field => {
        if (
          field === BK_BIZ_NAME_FIELD &&
          alarmStore.bizIds.length < 2 &&
          ![MY_AUTH_BIZ_ID, MY_ALARM_BIZ_ID].includes(alarmStore.bizIds[0])
        ) {
          return undefined;
        }
        const column = alarmStore.alarmService.allTableColumns.find(col => col.colKey === field);
        return {
          ...column,
        };
      })
      .filter(Boolean);
  });
  const allTableFields = computed<BkUiSettings['fields']>(() => {
    return alarmStore.alarmService.allTableColumns.map(item => ({
      label: item.title.toString(),
      field: item.colKey,
    }));
  });
  return {
    storageColumns,
    tableColumns,
    allTableFields,
  };
}
