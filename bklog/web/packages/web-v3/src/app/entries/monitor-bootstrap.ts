import { h } from 'vue';
import LocaleProvider from '@/platform/i18n/locale-provider';
/* Copyright (C) 2021 THL A29 Limited, a Tencent company.
 * 蓝鲸智云PaaS平台 (BlueKing PaaS), MIT License. */
import '../bootstrap/register-services';
import '@/platform/compat/tdesign/legacy-control-styles';
import '@/shared/lib/preload-import';
import '@/shared/directives';
import '@/platform/compat/tdesign/runtime-contract';
import '@/shared/styles/theme/theme-dark.scss';
import '@/shared/styles/theme/theme-light.scss';
import '@/shared/styles/theme/tdesign-bklog.scss';
import 'vue-virtual-scroller/dist/vue-virtual-scroller.css';
import '@blueking/bk-user-selector/vue3/vue3.css';
import type { App } from 'vue';
import { configureApp } from '../bootstrap/configure-app';
import store from '../state';
import i18n from '@/platform/i18n/i18n';

/** Embedding owns its router and mount point; application services remain shared. */
export function configureMonitorApp(app: App): void {
  configureApp(app);
  app.use(store);
  app.use(i18n);
}

import { createMonitorApplication } from '@/platform/embedding/monitor-application';


import Vue from '@/platform/compat/vue-runtime.mjs';
import { messageError, messageSuccess, messageInfo, messageWarn } from '@/shared/lib/message';
const feedback = {
  $bkInfo: Vue.prototype.$bkInfo,
  messageError, messageSuccess, messageInfo, messageWarn,
};

export const Vue2 = createMonitorApplication({ configure: configureMonitorApp, store, i18n, feedback, wrapRoot: node => h(LocaleProvider, null, { default: () => node }) });
