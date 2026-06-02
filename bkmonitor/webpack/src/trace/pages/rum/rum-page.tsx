/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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

import { defineComponent, shallowRef } from 'vue';

import GuidePage from 'trace/components/guide-page/guide-page';

import CreateApp from './components/create-app/create-app';
import SDKReport from './components/sdk-report/sdk-report';
import RumPage from './rum';

import type { IRumAppConfig } from './typings/rum-app-config';

/** 创建应用页面的 URL 路径，用于 GuidePage 拦截跳转并转为侧栏弹窗 */
const addUrl = '/rum/application/add';

export default defineComponent({
  name: 'RumPage',
  setup() {
    /** 是否显示引导页（无数据或无数据源时展示） */
    const showGuidePage = shallowRef(!!window.__BK_WEWEB_DATA__?.setIntroduceData);
    /** 引导页所需的数据（包含 is_no_data / is_no_source 等状态） */
    const introduceData = shallowRef(null);
    /** 通过 WeWeb 桥接获取外部传入的引导数据 */
    window.__BK_WEWEB_DATA__?.setIntroduceData?.(data => {
      introduceData.value = data;
      // 无应用数据或无数据源时展示引导页
      showGuidePage.value = !!(data?.is_no_data || data?.is_no_source);
    });

    /** 是否显示创建应用侧栏 */
    const showCreateApp = shallowRef(false);
    /** 是否显示 SDK 上报指引侧栏 */
    const showSdkReport = shallowRef(false);
    /** SDK 上报所需的已创建应用信息（创建成功后由 CreateApp 回传） */
    const sdkReportAppInfo = shallowRef<Partial<IRumAppConfig>>(null);

    /**
     * 处理 GuidePage 中的链接点击
     * 当点击"创建应用"相关链接时，拦截并打开创建应用侧栏而非页面跳转
     */
    const handleOpenUrl = (url: string) => {
      if (url.includes(addUrl)) {
        handleCreateApp();
      }
    };

    /** 打开创建应用侧栏 */
    const handleCreateApp = () => {
      handleCreateAppShowChange(true);
    };

    /** 切换创建应用侧栏显隐状态 */
    const handleCreateAppShowChange = (show: boolean) => {
      showCreateApp.value = show;
    };

    /**
     * 创建应用成功后的回调：
     * 1. 保存应用信息用于后续 SDK 接入
     * 2. 关闭创建应用侧栏
     * 3. 打开 SDK 上报指引侧栏（形成两步引导流）
     */
    const handleCreateAppSuccess = params => {
      sdkReportAppInfo.value = params;
      handleCreateAppShowChange(false);
      handleSdkReportShowChange(true);
    };

    /** 切换 SDK 上报指引侧栏显隐状态 */
    const handleSdkReportShowChange = (show: boolean) => {
      showSdkReport.value = show;
    };

    return {
      showGuidePage,
      introduceData,
      sdkReportAppInfo,
      showSdkReport,
      showCreateApp,
      handleOpenUrl,
      handleCreateAppShowChange,
      handleCreateAppSuccess,
      handleSdkReportShowChange,
    };
  },
  render() {
    return (
      <>
        {this.showGuidePage ? (
          <GuidePage
            customEventUrls={[addUrl]}
            guideId={'rum'}
            introduceData={this.introduceData}
            onUrl={this.handleOpenUrl}
          />
        ) : (
          <RumPage />
        )}
        <CreateApp
          show={this.showCreateApp}
          onShowChange={this.handleCreateAppShowChange}
          onSuccess={this.handleCreateAppSuccess}
        />
        <SDKReport
          appInfo={this.sdkReportAppInfo}
          show={this.showSdkReport}
          onShowChange={this.handleSdkReportShowChange}
        />
      </>
    );
  },
});
