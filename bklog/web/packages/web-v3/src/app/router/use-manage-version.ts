/* Copyright (C) 2021 THL A29 Limited, a Tencent company.
 * 蓝鲸智云PaaS平台 (BlueKing PaaS), MIT License. */
import { computed } from 'vue';
import useStore from '@/shared/composables/use-store';
import { isFeatureToggleOn } from '@/shared/composables/use-feature-toggle';

/** Preserve V2 on/off/debug and business/space allow-list semantics. */
export function useManageVersion() {
  const store = useStore();
  return computed(() =>
    isFeatureToggleOn('log_manage_v2', [String(store.state.bkBizId), String(store.state.spaceUid)]),
  );
}
