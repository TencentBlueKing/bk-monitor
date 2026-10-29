/* Copyright (C) 2021 THL A29 Limited, a Tencent company.
 * 蓝鲸智云PaaS平台 (BlueKing PaaS), MIT License. */
import type store from '@/app/state';
import type { Instance as PopoverInstance, Props as PopoverProps } from 'tippy.js';
import type { VNode } from 'vue';
import type { HttpClient } from '@/platform/http/types';
import type i18n from '@/platform/i18n/i18n';
import type useSourceRouter from '@/shared/composables/use-router';
import type { RouteLocationNormalizedLoaded } from 'vue-router';
import type { renderHeader, xssFilter } from '@/shared/lib/util';
import type { createInfoService } from '@/platform/compat/tdesign/info-box-contract';

export interface ApplicationInjections {
  $bkNotify: typeof import('bk-magic-vue').bkNotify;
  messageError: typeof import('@/shared/lib/bkmagic').messageError;
  messageSuccess: typeof import('@/shared/lib/bkmagic').messageSuccess;
  messageInfo: typeof import('@/shared/lib/bkmagic').messageInfo;
  messageWarn: typeof import('@/shared/lib/bkmagic').messageWarn;
  $services: import('@/platform/services').ApplicationServices;
  $bkPopover: (target: Element | EventTarget | string | null, options?: Partial<PopoverProps> & { [key: string]: unknown }) => PopoverInstance;
  $bkMessage: (options: string | { message: string | VNode; theme?: string; delay?: number; [key: string]: unknown }) => { close(): void };
  $store: typeof store;
  $http: HttpClient;
  $t: typeof i18n.t;
  $i18n: typeof i18n;
  $router: ReturnType<typeof useSourceRouter>;
  $route: RouteLocationNormalizedLoaded;
  $renderHeader: typeof renderHeader;
  $xss: typeof xssFilter;
  $bkInfo: ReturnType<typeof createInfoService>;
}
// Existing Class components still receive these via the compatibility host.
// Declare the installed contract in both type universes, without adding an index signature.
declare module 'vue/types/vue' {
  interface Vue extends ApplicationInjections {}
}
declare module '@vue/runtime-core' {
  interface ComponentCustomProperties extends ApplicationInjections {}
}
// Augment the public Vue entry used by SFCs as well. The workspace and the
// package can resolve different transitive runtime-core declaration paths.
declare module 'vue' {
  interface ComponentCustomProperties extends ApplicationInjections {}
}
export {};
