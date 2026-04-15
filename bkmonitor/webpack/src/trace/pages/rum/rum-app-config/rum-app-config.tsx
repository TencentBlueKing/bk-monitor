/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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
import { computed, defineComponent, reactive } from 'vue';

import { useI18n } from 'vue-i18n';
import { useRouter } from 'vue-router';

import AppBasicInfo, { type IAppBasicInfo } from './components/app-basic-info';
import NavBar from '@/components/nav-bar/nav-bar';

import './rum-app-config.scss';

export default defineComponent({
  name: 'RumAppConfigPage',
  setup() {
    const { t } = useI18n();
    const router = useRouter();

    /* 路由面包屑数据 */
    const navList = computed(() => {
      return [{ name: t('应用配置'), id: '' }];
    });

    /**
     * 返回上一页
     */
    const handleBackPage = () => {
      router.back();
    };

    /**
     * 应用基本信息数据
     */
    const appBasicInfo = reactive<IAppBasicInfo>({
      domain: 'www.example.com',
      status: '启用中',
      token: '**** 2323423',
      alias: 'Web 端口官网',
      desc: '这是蓝鲸作业平台的 RUM 应用',
    });

    return {
      navList,
      appBasicInfo,
      handleBackPage,
    };
  },

  render() {
    return (
      <div class='rum-app-config-page'>
        {/* 导航栏 */}
        <NavBar
          callbackRouterBack={this.handleBackPage}
          needBack={true}
          routeList={this.navList}
        />
        {/* 应用基本信息头部区域 */}
        <div class='rum-app-config-page__header'>
          <AppBasicInfo data={this.appBasicInfo} />
        </div>
      </div>
    );
  },
});
