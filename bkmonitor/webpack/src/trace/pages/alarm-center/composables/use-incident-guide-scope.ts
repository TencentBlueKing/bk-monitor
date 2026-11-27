/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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

import { type Ref, computed, shallowRef, watch } from 'vue';

import { supportsSpaceDirectoryPages } from 'monitor-common/utils/space-directory';
import { resolveSelectedSpaces } from 'monitor-common/utils/space-selection';

import { AlarmType, MY_ALARM_BIZ_ID, MY_AUTH_BIZ_ID } from '../typings/constants';
import { useAlarmCenterStore } from '@/store/modules/alarm-center';
import { useAppStore } from '@/store/modules/app';

import type { ISpaceItem } from 'monitor-common/typings';

export function useIncidentGuideScope(
  authorizedCount: Ref<number | undefined>,
  enabled: Ref<number[]>,
  hasLoaded: Ref<boolean>
) {
  const alarm = useAlarmCenterStore();
  const app = useAppStore();
  const isVirtual = computed(() => alarm.bizIds.some(id => [MY_AUTH_BIZ_ID, MY_ALARM_BIZ_ID].includes(id)));
  const pagedVirtualGuide = computed(() => isVirtual.value && supportsSpaceDirectoryPages());
  const resolved = shallowRef<ISpaceItem[]>([]);
  const guideLookupFailed = shallowRef(false);
  const retry = shallowRef(0);
  const reloadGuideSpaces = () => {
    retry.value++;
  };
  watch(
    () => [alarm.alarmType, alarm.bizIds, app.bizList, retry.value] as const,
    async ([type, ids, known], _, onCleanup) => {
      let active = true;
      onCleanup(() => {
        active = false;
      });
      resolved.value = [];
      guideLookupFailed.value = false;
      if (type !== AlarmType.INCIDENT || isVirtual.value || !ids.length || !supportsSpaceDirectoryPages()) return;
      try {
        const rows = await resolveSelectedSpaces(ids, known, true);
        if (active) resolved.value = rows;
      } catch {
        if (active) guideLookupFailed.value = true;
      }
    },
    { immediate: true }
  );
  const sidesliderSpaceList = computed(() => {
    const rows = supportsSpaceDirectoryPages() ? resolved.value : app.bizList;
    const selected = isVirtual.value ? null : new Set(alarm.bizIds);
    const excluded = new Set(app.noAuthBizIds);
    return rows.filter(row => !excluded.has(row.bk_biz_id) && (!selected || selected.has(row.bk_biz_id)));
  });
  const enabledIds = computed(() => new Set(enabled.value));
  const disabled = computed(() => sidesliderSpaceList.value.filter(row => !enabledIds.value.has(row.bk_biz_id)));
  const unconnectedSpaceList = computed(() => (disabled.value.length ? disabled.value : null));
  const sidesliderTotal = computed(() => sidesliderSpaceList.value.length);
  const selectedHasEnabled = computed(() => sidesliderSpaceList.value.some(row => enabledIds.value.has(row.bk_biz_id)));
  const accessGuideTipCount = computed(() => {
    if (!pagedVirtualGuide.value) return disabled.value.length;
    if (authorizedCount.value !== undefined) return authorizedCount.value - enabledIds.value.size;
    return undefined;
  });
  const ready = computed(() => alarm.alarmType === AlarmType.INCIDENT && hasLoaded.value);
  const showAccessGuideTip = computed(
    () => ready.value && (isVirtual.value || selectedHasEnabled.value) && (accessGuideTipCount.value ?? 0) > 0
  );
  const showDataAccessDirect = computed(
    () => ready.value && !isVirtual.value && !selectedHasEnabled.value && disabled.value.length > 0
  );
  const sidesliderMode = computed(() => (selectedHasEnabled.value ? 'guide' : 'empty'));
  return {
    accessGuideTipCount,
    pagedVirtualGuide,
    showAccessGuideTip,
    showDataAccessDirect,
    sidesliderSpaceList,
    sidesliderTotal,
    sidesliderMode,
    unconnectedSpaceList,
    reloadGuideSpaces,
    guideLookupFailed,
  };
}
