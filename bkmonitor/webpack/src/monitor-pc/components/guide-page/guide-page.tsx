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
import { Component, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { getDocLink } from 'monitor-api/modules/commons';

import AddAppSide from '../../../apm/pages/home/add-app/add-app-side';
import ServiceAddSide from '../../../apm/pages/service/service-add-side';

import type { IBtnAndLinkItem, ISPaceIntroduceData, SpaceIntroduceKeys } from '../../types/common/common';
import type { Route } from 'vue-router';

import './guide-page.scss';

const SPACE_DEMO_NAME = 'DEMO';
interface IGuidePageProps {
  guideData?: ISPaceIntroduceData;
  guideId?: string;
  marginless?: boolean;
}
Component.registerHooks(['beforeRouteEnter']);
@Component
export default class GuidePage extends tsc<IGuidePageProps> {
  @Prop({ default: false, type: Boolean }) marginless: boolean;
  @Prop({ required: false, type: String }) guideId: string;
  @Prop({ required: false, type: Object }) guideData: ISPaceIntroduceData;

  navId: '' | SpaceIntroduceKeys = '';

  // 展开新建应用抽屉
  isShowAppAdd = false;

  // 展开接入服务抽屉
  isShowServiceAdd = false;

  // 用于查询接入服务抽屉上报token
  appId = '';
  // 用于接入服务抽屉Quick Start跳转携带参数
  appName = '';

  /** 业务id */
  get bizId() {
    return this.$store.getters.bizId;
  }
  get bizList() {
    return this.$store.getters.bizList;
  }
  /** DEMO业务 */
  get demoBiz() {
    return this.bizList.find(item => item.is_demo);
  }
  get introduceData(): ISPaceIntroduceData {
    return this.guideData;
  }
  created() {
    this.navId = this.$route.meta?.navId;
  }
  activated() {
    this.navId = this.$route.meta?.navId;
  }
  beforeRouteEnter(to: Route, _from: Route, next) {
    next((vm: GuidePage) => {
      const { navId } = to.meta;
      vm.navId = navId;
    });
  }
  /**
   * 快捷链接跳转
   * @param item 链接数据
   */
  handleGotoLink(item: IBtnAndLinkItem) {
    if (item.url?.match?.(/^https?:\/\//)) {
      window.open(item.url, '_blank');
      return;
    }
    getDocLink({ md_path: item.url })
      .then(data => {
        window.open(data, '_blank');
      })
      .catch(() => false);
  }
  handleBtnClick(item: IBtnAndLinkItem) {
    if (item.name === SPACE_DEMO_NAME) {
      if (this.demoBiz?.bk_biz_id) {
        if (+this.$store.getters.bizId === +this.demoBiz?.bk_biz_id) {
          location.reload();
        } else {
          location.href = location.href.replace(`bizId=${this.bizId}`, `bizId=${this.demoBiz?.bk_biz_id}`);
        }
      }
    } else if (this.introduceData.is_no_source) {
      this.$bkInfo({
        title: this.$t('当前未关联任何资源'),
        subTitle: this.$t('该功能暂不可用'),
      });
    } else if (item.url.match(/^#\//)) {
      // 新建apm改为抽屉方式
      if (item.url.includes('apm/application/add')) {
        this.handleToggleAppAdd(true);
        return;
      }
      location.href = location.href.replace(location.hash, item.url);
      // this.$router.push({ path: item.url.replace('#/', '') });
    } else if (item.url) {
      window.open(item.url, '_blank');
    }
  }

  // 新建应用抽屉显示状态
  handleToggleAppAdd(v: boolean) {
    this.isShowAppAdd = v;
  }

  // 新建应用成功
  handleAddAppSuccess(appName: string, appId: string) {
    this.appId = appId;
    this.appName = appName;
    // 打开接入服务抽屉
    this.isShowServiceAdd = true;
  }

  // 接入服务抽屉显隐
  handleServiceAddSideShow(v) {
    this.isShowServiceAdd = v;
  }

  render() {
    if (!this.introduceData) return undefined;
    const { title = '', subTitle = '', introduce = [], buttons = [], links = [] } = this.introduceData?.data || {};
    return (
      <div class={['guide-page-wrap', { 'margin-less': this.marginless }]}>
        <div class='guide-page-main'>
          <div class='guide-left'>
            <div class='guide-title'>{this.$t(title)}</div>
            {subTitle && <div class='guide-subtitle'>{this.$t(subTitle)}</div>}
            <ul class='guide-tips'>
              {introduce.map((item, index) => (
                <li
                  key={index}
                  class='guide-tips-item'
                >
                  {index + 1}. {this.$t(item)}
                </li>
              ))}
            </ul>
            <div class='guide-btn-group'>
              {buttons.map(item =>
                !(item.name === SPACE_DEMO_NAME && !this.demoBiz) ? (
                  <bk-button
                    key={item.name}
                    theme={item.name === SPACE_DEMO_NAME ? 'default' : 'primary'}
                    onClick={() => this.handleBtnClick(item)}
                  >
                    {this.$t(item.name)}
                  </bk-button>
                ) : undefined
              )}
            </div>
            {links?.length > 0 && (
              <div class='guide-link'>
                <div class='link-title'>{this.$t('文档链接')}</div>
                <div class='link-list'>
                  {links.map(item =>
                    item.url ? (
                      <span
                        key={item.name}
                        class='link-item'
                        onClick={() => this.handleGotoLink(item)}
                      >
                        {this.$t(item.name)}
                      </span>
                    ) : undefined
                  )}
                </div>
              </div>
            )}
          </div>
          <div class='guide-right'>
            <div class={`guide-img-wrap img-${this.guideId ?? this.navId}`} />
          </div>
        </div>
        {this.$route.name === 'apm-home' && [
          <AddAppSide
            key='add-app-side'
            isShow={this.isShowAppAdd}
            onShowChange={v => this.handleToggleAppAdd(v)}
            onSuccess={this.handleAddAppSuccess}
          />,
          <ServiceAddSide
            key='service-add-side'
            applicationId={this.appId}
            appName={this.appName}
            isShow={this.isShowServiceAdd}
            onSidesliderShow={v => this.handleServiceAddSideShow(v)}
          />,
        ]}
      </div>
    );
  }
}
