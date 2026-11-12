/* Copyright (C) 2021 THL A29 Limited, a Tencent company.
 * 蓝鲸智云PaaS平台 (BlueKing PaaS), MIT License. */

import { useApplicationStore } from '@/app/state/domains/application-store';
import { computed } from 'vue';

import { isFeatureToggleOn } from '@/shared/composables/use-feature-toggle';

/** Preserve V2 on/off/debug and business/space allow-list semantics. */
export function useManageVersion() {
  const store = useApplicationStore();
  return computed(() =>
    isFeatureToggleOn('log_manage_v2', [String(store.bkBizId), String(store.spaceUid)]),
  );
}
