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
import { Component, Emit, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { metaConfigInfo, pushUrl, queryBkDataToken } from 'monitor-api/modules/apm_meta';
import { copyText } from 'monitor-common/utils/utils';

import ServiceAddSideItem from './service-add-side-item';

import './service-add-side.scss';

type IEvent = {
  onSidesliderShow: (v: boolean) => void;
};

interface IProps {
  applicationId: number | string;
  appName: string;
  isShow: boolean;
}

@Component
export default class ServiceAddSide extends tsc<IProps, IEvent> {
  // 显示接入服务抽屉
  @Prop({ default: false, type: Boolean }) isShow: boolean;
  // 查询上报token必须参数
  @Prop({ default: '', type: [String, Number] }) applicationId: number | string;
  // Quick Start跳转携带参数
  @Prop({ default: '', type: String }) appName: string;

  // 上报token
  token = '';
  // 上报地址
  pushUrlVal = '';
  // 上报地址下拉数据
  pushUrlList = [];
  // 更多地址(上报地址)
  morePushUrl = '';
  // 上报指引地址
  reportGuideUrl = '';

  @Watch('isShow')
  showSideslider(show) {
    this.resetData();
    if (show) {
      this.getToken();
      this.getPushUrl();
      this.getLinkData();
    }
  }

  @Emit('sidesliderShow')
  handleSidesliderShow(v) {
    return v;
  }

  // 重置数据
  resetData() {
    this.token = '';
    this.pushUrlVal = '';
    this.pushUrlList = [];
    this.morePushUrl = '';
    this.reportGuideUrl = '';
  }

  // 获取上报token
  async getToken() {
    this.token = await queryBkDataToken(this.applicationId)
      .then(res => res)
      .catch(() => '');
  }

  // 获取上报地址下拉数据 默认选中第一个地址
  async getPushUrl() {
    const data = await pushUrl({
      format_type: 'simple',
    })
      .then(res => res)
      .catch(() => []);

    // 与接入服务页面拼接保持一致
    // src\apm\pages\service\data-guide.tsx
    this.pushUrlList = data.map(item => ({
      id: item.push_url,
      name: `${item.bk_cloud_alias || this.$t('管控区域')} ${item.push_url}`,
    }));
    this.pushUrlVal = this.pushUrlList[0]?.id || '';
  }

  // 获取更多地址(上报地址)/上报指引地址
  async getLinkData() {
    const data = await metaConfigInfo()
      .then(res => res)
      .catch(() => '');
    if (data.setup) {
      const { access_url = '', data_push_url_all = '' } = data.setup?.guide_url || {};
      this.morePushUrl = data_push_url_all; // 更多地址（上报地址）
      this.reportGuideUrl = access_url; // 上报指引地址
    }
  }

  /**
   * @param urlStr
   * 上报地址的更多地址/上报指引/Quick Start 跳转
   * Quick Start和apm列表首页的接入服务按钮跳转到的页面一致
   * apm列表首页的接入服务按钮有权限控制
   * 而用户能到首次新建应用页面表示已经有权限，所以这里不进行权限判断(已和后端确认)
   * 首次新建应用页面：src\monitor-pc\components\guide-page\guide-page.tsx 118行
   * (2025-09-15)
   */
  handleGoToLink(urlStr: string) {
    if (urlStr === 'Quick') {
      // 首次新建应用成功后，服务相关的动态路由 可能未加载，故直接使用拼接方式跳转
      const hash = `#${window.__BK_WEWEB_DATA__?.baseroute || '/'}service-add/${this.appName}`;
      const url = location.href.replace(location.hash, hash);
      console.log('url', url);
      window.open(url, '_blank');
      return;
    }
    urlStr?.length && window.open(urlStr, '_blank');
  }

  // 复制上报token/上报地址
  handleCopy(text) {
    if (!text) return;
    copyText(text, msg => {
      this.$bkMessage({
        message: msg,
        theme: 'error',
      });
      return;
    });
    this.$bkMessage({
      message: this.$t('复制成功'),
      theme: 'success',
    });
  }

  render() {
    return (
      <bk-sideslider
        class='service-add-side'
        isShow={this.isShow}
        quickClose={true}
        showMask={true}
        {...{ on: { 'update:isShow': this.handleSidesliderShow } }}
        width={640}
      >
        <div slot='header'>{this.$t('接入服务')}</div>
        <div
          class='service-add-side__content'
          slot='content'
        >
          <ServiceAddSideItem
            disabledStyle={true}
            title={this.$t('上报token') as string}
            onCopy={() => this.handleCopy(this.token)}
          >
            {this.token}
          </ServiceAddSideItem>
          <ServiceAddSideItem
            title={this.$t('上报地址') as string}
            onCopy={() => this.handleCopy(this.pushUrlVal)}
          >
            <bk-select
              key='select'
              v-model={this.pushUrlVal}
              clearable={false}
            >
              {this.pushUrlList.map(item => (
                <bk-option
                  id={item.id}
                  key={item.id}
                  name={item.name}
                />
              ))}
            </bk-select>
            <span
              class='more-link'
              slot='btm'
              onClick={() => this.handleGoToLink(this.morePushUrl)}
            >
              {this.$t('更多地址')}
            </span>
          </ServiceAddSideItem>
          <div class='service-add-side__item'>
            <div
              class='service-add-side__block'
              onClick={() => this.handleGoToLink(this.reportGuideUrl)}
            >
              <i class='icon-monitor icon-mc-detail' />
              {this.$t('上报指引')}
            </div>
            <div
              class='service-add-side__block'
              onClick={() => this.handleGoToLink('Quick')}
            >
              <i class='icon-monitor icon-auto-decode' />
              Quick Start
            </div>
          </div>
        </div>
      </bk-sideslider>
    );
  }
}
