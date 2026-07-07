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
import { computed, defineComponent, onMounted, shallowRef } from 'vue';

import { Tab } from 'bkui-vue';
import { useI18n } from 'vue-i18n';
import { useRoute, useRouter } from 'vue-router';

import SDKReport from '../components/sdk-report/sdk-report';
import { RUM_APP_CONFIG_TAB_ENUM, RUM_APP_CONFIG_TAB_MAP } from '../constants';
import AppBasicInfo from './components/app-basic-info';
import BasicConfig from './components/basic-config';
import DataState from './components/data-state/data-state';
import StorageStatus from './components/storage-status';
import { getAppConfigByAppName, getEsClusterList } from './services/app-config';
import NavBar from '@/components/nav-bar/nav-bar';

import type { ApplicationOperationType, IRumAppConfig, RumAppConfigTabType } from '../typings';

import './rum-app-config.scss';

export default defineComponent({
  name: 'RumAppConfigPage',
  setup() {
    const { t } = useI18n();
    const route = useRoute();
    const router = useRouter();

    /* 路由面包屑数据 */
    const navList = computed(() => {
      return [{ name: t('应用配置'), id: '' }];
    });

    /**
     * 返回上一页
     */
    const handleBackPage = () => {
      router.push({
        name: 'rum',
      });
    };

    /**
     * 应用基本信息数据
     */
    const appInfo = shallowRef<IRumAppConfig>(undefined);

    /** 当前选中的 Tab 面板 */
    const currentPanel = shallowRef<RumAppConfigTabType>(RUM_APP_CONFIG_TAB_ENUM.BASIC_CONFIG);

    /** 是否展示 SDK 接入指引侧栏 */
    const sdkGuideShow = shallowRef(false);

    /** ES 集群列表 */
    const clusterList = shallowRef([]);

    /** 切换 Tab 面板 */
    const handleCurrentPanelChange = (v: RumAppConfigTabType) => {
      currentPanel.value = v;
    };

    /** 获取应用配置信息 */
    const getRumAppConfig = async () => {
      appInfo.value = await getAppConfigByAppName(decodeURIComponent(route.params.appName as string));
    };

    /**
     * @desc 获取es集群列表
     */
    const getEsCluster = async () => {
      clusterList.value = await getEsClusterList();
    };

    /** 处理应用信息变更，合并更新后的字段 */
    const handleAppInfoChange = (info: Partial<IRumAppConfig>) => {
      appInfo.value = { ...appInfo.value, ...info };
    };

    /** 处理应用操作（启用/停用/删除） */
    const handleAppOperation = (type: ApplicationOperationType) => {
      // 删除返回列表页
      if (type === 'delete') {
        router.replace({
          name: 'rum',
        });
      } else {
        // 修改应用配置禁用状态即可
        appInfo.value = { ...appInfo.value, is_enabled: type === 'start' };
      }
    };

    /** 展示/隐藏 SDK 接入指引侧栏 */
    const handleShowSdkGuide = (show: boolean) => {
      sdkGuideShow.value = show;
    };

    onMounted(() => {
      getRumAppConfig();
      getEsCluster();
    });

    /** 根据当前 Tab 获取对应的面板组件 */
    const getPanelComponent = () => {
      switch (currentPanel.value) {
        case RUM_APP_CONFIG_TAB_ENUM.BASIC_CONFIG:
          return (
            <BasicConfig
              detail={appInfo.value}
              onApplicationInfoChange={handleAppInfoChange}
            />
          );
        case RUM_APP_CONFIG_TAB_ENUM.STORAGE_STATUS:
          return (
            <StorageStatus
              clusterList={clusterList.value}
              detail={appInfo.value}
            />
          );
        case RUM_APP_CONFIG_TAB_ENUM.DATA_STATUS:
          return <DataState detail={appInfo.value} />;
      }
    };

    return {
      navList,
      appInfo,
      currentPanel,
      sdkGuideShow,
      handleCurrentPanelChange,
      handleBackPage,
      getPanelComponent,
      handleAppOperation,
      handleAppInfoChange,
      handleShowSdkGuide,
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
          <AppBasicInfo
            data={this.appInfo}
            onApplicationInfoChange={this.handleAppInfoChange}
            onApplicationOperation={this.handleAppOperation}
            onShowSdkGuide={() => this.handleShowSdkGuide(true)}
          />
        </div>

        <div class='rum-app-config-page__body'>
          <Tab
            class='panel-tab'
            active={this.currentPanel}
            type='card-grid'
            onUpdate:active={this.handleCurrentPanelChange}
          >
            {RUM_APP_CONFIG_TAB_MAP?.map(item => (
              <Tab.TabPanel
                key={item.id}
                label={item.name}
                name={item.id}
              />
            ))}
          </Tab>
          <div class='panel-tab-body'>{this.getPanelComponent()}</div>
        </div>
        <SDKReport
          appInfo={this.appInfo}
          mode='guide'
          show={this.sdkGuideShow}
          onShowChange={this.handleShowSdkGuide}
        />
      </div>
    );
  },
});
