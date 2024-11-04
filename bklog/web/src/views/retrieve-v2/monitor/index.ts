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
window.__IS_MONITOR_APM__ = true

import LogButton from '@/components/log-button';
import JsonFormatWrapper from '@/global/json-format-wrapper.vue';
import useStore from '@/hooks/use-store';
import i18n from '@/language/i18n';

import http from '../../../api';
import MonitorRetrieve from './monitor.vue';
const logStore = useStore();
const initMonitorState = (payload) => {
  logStore.commit('initMonitorState', payload);
};
const initDevelopmentLog = () => {
  return http.request('meta/getEnvConstant').then(res => {
    const { data } = res;
    Object.keys(data).forEach(key => {
      window[key] = data[key];
    });
    window.FEATURE_TOGGLE = JSON.parse(data.FEATURE_TOGGLE);
    window.FEATURE_TOGGLE_WHITE_LIST = JSON.parse(data.FEATURE_TOGGLE_WHITE_LIST);
    window.SPACE_UID_WHITE_LIST = JSON.parse(data.SPACE_UID_WHITE_LIST);
    window.FIELD_ANALYSIS_CONFIG = JSON.parse(data.FIELD_ANALYSIS_CONFIG);
  })
}
export {
  MonitorRetrieve,
  initMonitorState,
  initDevelopmentLog,
  logStore,
  i18n,
  LogButton,
  JsonFormatWrapper
}
