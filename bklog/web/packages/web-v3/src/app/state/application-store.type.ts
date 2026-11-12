/* Copyright (C) 2021 THL A29 Limited, a Tencent company.
 * 蓝鲸智云PaaS平台 (BlueKing PaaS), MIT License. */
import type { createStoreState } from './state';
import type { createRetrieveState } from './domains/retrieve-store';
import type { CollectionState } from './collect';
import type { GlobalsState } from './globals';
import type { NativeApplicationStore } from './domains/application-store';

export interface UserMetadata {
  chname: string;
  language: string;
  operator: string;
  time_zone: string;
  username: string;
  bk_tenant_id?: string;
  bk_tenant_name?: string;
}
export interface TenantMismatch {
  current_tenant_id: string;
  target_tenant_id: string;
}
export type ApplicationState = ReturnType<typeof createStoreState> & {
  retrieve: ReturnType<typeof createRetrieveState>;
  collect: CollectionState;
  globals: GlobalsState;
};
/** Actual Pinia domains plus the published Monitor compatibility envelope. */
export type ApplicationStore = NativeApplicationStore;
