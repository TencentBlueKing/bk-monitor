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
window.__IS_MONITOR_COMPONENT__ = true;
window.__IS_MONITOR_TRACE__ = process.env.MONITOR_APP === 'trace';
window.__IS_MONITOR_APM__ = process.env.MONITOR_APP === 'apm';
import Vue from 'vue';

import LogButton from '@/components/log-button';
import JsonFormatWrapper from '@/global/json-format-wrapper.vue';
import useStore from '@/hooks/use-store';
import i18n from '@/language/i18n';

import MonitorRetrieve from './monitor.vue';

import '../../../static/style.css';
const logStore = useStore();
const initMonitorState = payload => {
  logStore.commit('initMonitorState', payload);
};
const initGlobalComponents = () => {
  Vue.component('JsonFormatWrapper', JsonFormatWrapper);
  Vue.component('LogButton', LogButton);
};
export { MonitorRetrieve, logStore, i18n, initMonitorState, initGlobalComponents };
