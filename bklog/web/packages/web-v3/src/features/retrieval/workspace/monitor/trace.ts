
import { Alert as TAlert, Badge as TBadge, Progress as TProgress, Tag as TTag } from 'tdesign-vue-next';

import { Checkbox as TCheckbox, CheckboxGroup as TCheckboxGroup, Radio as TRadio, RadioButton as TRadioButton, RadioGroup as TRadioGroup, Switch as TSwitch, Loading as TLoading } from 'tdesign-vue-next';

import { Button as TButton } from 'tdesign-vue-next';
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
import Vue from '@/platform/compat/vue-runtime.mjs';

import i18n from '@/platform/i18n/i18n';
import JsonFormatWrapper from '@/shared/global/json-format-wrapper.vue';
import useStore from '@/shared/composables/use-store';
import { performanceMonitorService } from '@/platform/persistence/index';

import MonitorTraceLog from './monitor';

if (!window.mainComponent?.$t) {
  window.mainComponent = {
    $t: i18n.t.bind(i18n),
    $i18n: i18n,
  };
}

const logStore = useStore();

const initMonitorState = (payload: unknown) => {
  logStore.commit('initMonitorState', payload);
};
const initGlobalComponents = () => {
  Vue.component('JsonFormatWrapper', JsonFormatWrapper);
  Vue.component('TAlert', TAlert);
  Vue.component('TBadge', TBadge);
  Vue.component('TButton', TButton);
  Vue.component('TCheckbox', TCheckbox);
  Vue.component('TCheckboxGroup', TCheckboxGroup);
  Vue.component('TProgress', TProgress);
  Vue.component('TRadio', TRadio);
  Vue.component('TRadioButton', TRadioButton);
  Vue.component('TRadioGroup', TRadioGroup);
  Vue.component('TLoading', TLoading);
  Vue.component('TSwitch', TSwitch);
  Vue.component('TTag', TTag);
};
const initWindowState = () => {
  window.__IS_MONITOR_COMPONENT__ = true;
  window.__IS_MONITOR_TRACE__ = true;
  window.__IS_MONITOR_APM__ = false;
  // 为嵌入运行时注册 workerManager / __BKLOG_WORKERS__ 诊断 API。
  performanceMonitorService.init();
};
const Vue2 = Vue;
export { MonitorTraceLog, logStore, i18n, Vue2, initMonitorState, initWindowState, initGlobalComponents };
