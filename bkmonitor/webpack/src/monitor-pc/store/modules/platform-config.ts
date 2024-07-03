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
import { Action, Mutation, getModule, Module, VuexModule } from 'vuex-module-decorators';

import store from '../store';

interface II18nData {
  name: string;
  footerInfoHTML: string;
}

interface IPlatformConfig {
  appLogo?: string;
  name?: string;
  nameEn?: string;
  favicon?: string;
  footerCopyrightContent?: string;
  i18n?: II18nData;
  version?: string;
}

export const initialConfig = {
  name: '监控平台',
  nameEn: 'BK MONITOR',
  brandName: '腾讯蓝鲸智云',
  brandNameEn: 'BlueKing',
  favIcon: '/static/monitor/img/monitor-64.png',
  version: window.footer_version,
};

@Module({ name: 'platform-config', dynamic: true, namespaced: true, store })
class PlatformConfigStore extends VuexModule {
  public publicConfig: IPlatformConfig = {};

  @Action
  public async fetchConfig() {
    let configPromise;
    const bkRepoUrl = window.bk_shared_res_url;

    if (bkRepoUrl) {
      const repoUrl = bkRepoUrl.endsWith('/') ? bkRepoUrl : `${bkRepoUrl}/`;
      configPromise = getPlatformConfig(`${repoUrl}bk_monitorv3/base.js`, initialConfig);
    } else {
      configPromise = getPlatformConfig(initialConfig);
    }

    const configData = await configPromise;
    setShortcutIcon(configData.favIcon);
    setDocumentTitle(configData.i18n);
    this.updatePlatformConfig(configData);
  }

  @Mutation
  public updatePlatformConfig(data: IPlatformConfig) {
    this.publicConfig = data;
  }
}

export default getModule(PlatformConfigStore);
