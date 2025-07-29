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
import { getPlatformConfig, setDocumentTitle, setShortcutIcon } from '@blueking/platform-config';
import { Action, getModule, Module, Mutation, VuexModule } from 'vuex-module-decorators';

import store from '../store';

interface IPlatformConfig {
  appLogo: string; // 站点logo
  bkAppCode: string; // app code
  brandImg: string;
  brandImgEn: string;
  brandName: string; // 品牌名，会用于拼接在站点名称后面显示在网页title中
  brandNameEn: string; // 品牌名-英文
  favicon: string; // 站点favicon
  footerCopyright: string; // 版本信息，包含 version 变量，展示在页脚内容下方
  footerCopyrightContent: string; // 替换完变量之后的版本信息，可以直接用于在页面中展示
  footerInfo: string; // 页脚的内容，仅支持 a 的 markdown 内容格式
  footerInfoEn: string; // 页脚的内容-英文
  footerInfoHTML: string; // 转换为HTML的页脚内容，已处理 xss，可以直接用于在页面中展示
  footerInfoHTMLEn: string; // 转换为HTML的页脚内容-英文
  helperLink: string; // 超链接或IM协议地址
  helperText: string;
  helperTextEn: string;
  name: string; // 站点的名称，通常显示在页面左上角，也会出现在网页title中
  nameEn: string; // 站点的名称-英文

  // 需要国际化的字段，根据当前语言cookie自动匹配，页面中应该优先使用这里的字段
  i18n: {
    brandImg: string;
    brandName: string;
    footerInfoHTML: string;
    helperText: string;
    name: string; // 国际化对应的内容：某某平台 或 AAA
  };
}
@Module({ name: 'platform-config', dynamic: true, namespaced: true, store })
class PlatformConfigStore extends VuexModule {
  public publicConfig: Partial<IPlatformConfig> = {};

  @Action
  public async fetchConfig() {
    let configPromise: Promise<IPlatformConfig>;
    const initialConfig = {
      name: '监控平台',
      nameEn: 'Monitor',
      brandName: '蓝鲸智云',
      brandNameEn: 'Tencent BlueKing',
      favIcon: '/static/monitor/img/monitor-64.png',
      version: window.footer_version,
    };
    if (window.bk_shared_res_url) {
      configPromise = getPlatformConfig(
        `${window.bk_shared_res_url.replace(/\/$/, '')}/bk_monitorv3/base.js`,
        initialConfig
      );
    } else {
      configPromise = getPlatformConfig(initialConfig);
    }

    const configData = await configPromise;
    setShortcutIcon(configData.favicon);
    setDocumentTitle(configData.i18n);
    this.updatePlatformConfig(configData);
  }

  @Mutation
  public updatePlatformConfig(data: IPlatformConfig) {
    this.publicConfig = data;
  }
}

export default getModule(PlatformConfigStore);
