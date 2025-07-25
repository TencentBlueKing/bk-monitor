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
import { Component } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { activated, deactivated, loadApp } from '@blueking/bk-weweb';
import EventDetailSlider from 'fta-solutions/pages/event/event-detail/event-detail-slider';

import introduce from '../../common/introduce';
import GuidePage from '../../components/guide-page/guide-page';

import './apm.scss';

Component.registerHooks(['beforeRouteLeave']);
@Component
export default class ApmPage extends tsc<object> {
  loading = false;
  appkey = 'apm';
  // 侧栏详情信息
  detailInfo: { bizId: number; id: string; isShow: boolean; type: 'eventDetail' } = {
    isShow: false,
    id: '',
    type: 'eventDetail',
    bizId: +window.bk_biz_id,
  };
  get apmHost() {
    return process.env.NODE_ENV === 'development' ? `http://${process.env.devHost}:7002` : location.origin;
  }
  get apmUrl() {
    return process.env.NODE_ENV === 'development'
      ? this.apmHost
      : `${location.origin}${window.site_url}apm/?bizId=${this.$store.getters.bizId}`;
  }
  get apmData() {
    return JSON.stringify({
      host: this.apmHost,
      baseroute: '/apm/',
    });
  }
  // 是否显示引导页
  get showGuidePage() {
    if (this.$route.name === 'application-add') return false;
    return introduce.getShowGuidePageByRoute(this.$route.meta?.navId);
  }
  created() {
    /** 如果在当前页面切换业务 切换后业务未配置应用监控白名单 则跳回首页 */
    if (!window.enable_apm) {
      location.href = `${location.origin}${location.pathname}?bizId=${this.$store.getters.bizId}#/`;
    }
  }
  async mounted() {
    if (this.showGuidePage) return;
    this.loading = true;
    await loadApp({
      url: this.apmUrl,
      id: this.appkey,
      container: this.$refs.apmPageWrap as HTMLElement,
      showSourceCode: false,
      scopeCss: true,
      scopeJs: true,
      scopeLocation: false,
      setShodowDom: false,
      keepAlive: false,
      data: {
        host: this.apmHost,
        baseroute: '/apm/',
        $baseStore: this.$store,
        showDetailSlider: this.handleShowDetail,
      },
    });
    activated(this.appkey, this.$refs.apmPageWrap as HTMLElement);
    window.requestIdleCallback(() => (this.loading = false));
  }
  beforeRouteLeave(to, from, next) {
    next();
  }
  async activated() {
    if (this.showGuidePage || this.loading) return;
    activated(this.appkey, this.$refs.apmPageWrap as HTMLElement);
  }
  beforeDestroy() {
    if (this.showGuidePage) return;
    this.$route.name !== 'application-add' && deactivated(this.appkey);
  }
  deactivate() {
    this.$route.name !== 'application-add' && deactivated(this.appkey);
  }
  /**
   * @description: 显示详情数据
   */
  handleShowDetail(id: string) {
    this.detailInfo.id = id;
    this.detailInfo.isShow = true;
    this.detailInfo.bizId = +window.bk_biz_id;
  }
  render() {
    if (this.showGuidePage) return <GuidePage guideData={introduce.data['apm-home'].introduce} />;
    return (
      <div class='apm-wrap'>
        <div
          ref='apmPageWrap'
          class='apm-wrap-iframe'
        />
        <EventDetailSlider
          bizId={this.detailInfo.bizId}
          eventId={this.detailInfo.id}
          isShow={this.detailInfo.isShow}
          type={this.detailInfo.type}
          onShowChange={v => (this.detailInfo.isShow = v)}
        />
      </div>
    );
  }
}
