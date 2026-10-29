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
import { getPlatformConfig, setShortcutIcon, setDocumentTitle } from '@blueking/platform-config';
import { defineStore } from 'pinia';
import { applicationPinia } from '../pinia';



interface II18nData {
  name?: string;
}

export interface IPlatformConfig {
  favicon?: string;
  appLogo?: string;
  name?: string;
  nameEn?: string;
  brandName?: string;
  brandNameEn?: string;
  i18n?: II18nData;
}

export const initialConfig = {
  name: '日志平台',
  nameEn: 'Log',
  brandName: '蓝鲸智云',
  brandNameEn: 'Tencent BlueKing',
  version: window.VERSION,
};

export const usePlatformConfigStore = defineStore('bklog.platform-config', {
  state: (): { publicConfig: IPlatformConfig } => ({ publicConfig: {} }),
  actions: {
    updatePlatformConfig(data: IPlatformConfig) {
      this.publicConfig = data;
    },
    async fetchConfig() {
      const bkRepoUrl = window.BK_SHARED_RES_URL;
      const repoUrl = bkRepoUrl && (bkRepoUrl.endsWith('/') ? bkRepoUrl : `${bkRepoUrl}/`);
      const configData = await (repoUrl
        ? getPlatformConfig(`${repoUrl}/bk_log_search/base.js`, initialConfig)
        : getPlatformConfig(initialConfig));
      setShortcutIcon(configData.favicon);
      setDocumentTitle(configData.i18n);
      this.updatePlatformConfig(configData);
    },
  },
});
export default usePlatformConfigStore(applicationPinia);
