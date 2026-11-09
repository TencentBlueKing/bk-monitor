/* Copyright (C) 2021 THL A29 Limited, a Tencent company.
 * 蓝鲸智云PaaS平台 (BlueKing PaaS), MIT License. */
import type { createStoreState } from './state';
import type retrieve from './retrieve';
import type collect from './collect';
import type globals from './globals';
import type { useApplicationStores } from './application-runtime';

export interface UserMetadata {
  chname: string; language: string; operator: string; time_zone: string; username: string;
  bk_tenant_id?: string; bk_tenant_name?: string;
}
export interface TenantMismatch { current_tenant_id: string; target_tenant_id: string; }
export type ApplicationState = ReturnType<typeof createStoreState> & {
  retrieve: typeof retrieve.state;
  collect: typeof collect.state;
  globals: typeof globals.state;
};
/** Actual Pinia domains plus the published Monitor compatibility envelope. */
export type ApplicationStore = ReturnType<typeof useApplicationStores>;
