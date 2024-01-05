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
import { Component, InjectReactive, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

// import TemporaryShare from '../../../components/temporary-share/temporary-share';
import { INavItem, IRouteBackItem } from '../typings';

import './common-nav-bar.scss';

interface ICommonNavBarProps {
  routeList?: INavItem[];
  needBack?: boolean;
  needShadow?: boolean;
  needCopyLink?: boolean;
  positionText?: string;
  backGotoItem?: IRouteBackItem;
  navMode?: NavBarMode;
  callbackRouterBack?: () => void;
}
export type NavBarMode = 'copy' | 'share' | 'display';

@Component({
  name: 'CommonNavBar',
  components: {
    TemporaryShare: () =>
      import(/* webpackChunkName: "TemporaryShare" */ '../../../components/temporary-share/temporary-share') as any
  }
})
export default class CommonNavBar extends tsc<ICommonNavBarProps> {
  @Prop({ type: Array, default: () => [] }) routeList: INavItem[];
  @Prop({ type: Boolean, default: undefined }) needBack: boolean;
  @Prop({ type: Boolean, default: false }) needShadow: boolean;
  @Prop({ type: Boolean, default: false }) needCopyLink: boolean;
  @Prop({ type: String, default: 'share' }) navMode: NavBarMode;
  @Prop({ type: String, default: '' }) positionText: string;
  @Prop({ type: Object, default: () => ({ isBack: false }) }) backGotoItem: IRouteBackItem;
  /** 面包屑返回按钮回调方法 */
  @Prop({ type: Function }) callbackRouterBack: () => void;
  @InjectReactive('readonly') readonly readonly: boolean;
  get navList() {
    // 临时分享模式下可能没有title 需要从父级应用下传入获取
    if (window.__POWERED_BY_BK_WEWEB__ && window.token) {
      return window.__BK_WEWEB_DATA__.navList || this.routeList || [];
    }
    return this.routeList;
  }
  // goto page by name
  handleGotoPage(item: INavItem) {
    if (this.readonly) return;
    const targetRoute = this.$router.resolve({ name: item.id, query: item.query || {} });
    /** 防止出现跳转当前地址导致报错 */
    if (targetRoute.resolved.fullPath !== this.$route.fullPath) {
      this.$router.push({ name: item.id, query: item.query || {} });
    }
  }
  handleBackGotoPage() {
    if (this.callbackRouterBack) {
      return this.callbackRouterBack();
    }
    if (this.backGotoItem?.id && !this.backGotoItem?.isBack) {
      this.$router.push({ name: this.backGotoItem.id, query: this.backGotoItem.query || {} });
      return;
    }
    // 如果新窗口打开页面，点返回上一级跳转到策略列表
    if (window.history.length <= 1) {
      if (this.$route.name.includes('strategy-config')) {
        this.$router.push({ path: '/strategy-config' });
      }
    } else {
      this.$router.back();
    }
  }
  render() {
    const len = this.routeList.length;
    return (
      <div
        class={`navigation-bar common-nav-bar ${this.needShadow ? 'detail-bar' : ''}`}
        slot='title'
        key='navigationBar'
      >
        {!this.readonly && (this.needBack || ((this.needBack ?? true) && len > 1)) && (
          <span
            class='icon-monitor icon-back-left navigation-bar-back'
            onClick={() => this.handleBackGotoPage()}
          ></span>
        )}
        {!!this.$slots.custom ? (
          <div class='navigation-bar-list'>{this.$slots.custom}</div>
        ) : (
          <ul class='navigation-bar-list'>
            {this.navList.map((item, index) => (
              <li
                key={index}
                class='bar-item'
              >
                {/* {index > 0 ? <span class="item-split icon-monitor icon-arrow-right"></span> : undefined} */}
                {index > 0 ? <span class='item-split'>/</span> : undefined}
                <span
                  class={`item-name ${!!item.id && index < len - 1 ? 'parent-nav' : ''} ${
                    len === 1 ? 'only-title' : ''
                  }`}
                  onClick={() => item.id && index < len - 1 && this.handleGotoPage(item)}
                >
                  <span class='item-name-text'>{item.name}</span>
                  {!!item.subName && (
                    <span class='item-sub-name'>
                      {item.name ? '-' : ''}&nbsp;{item.subName}
                    </span>
                  )}
                </span>
              </li>
            ))}
          </ul>
        )}
        {/* {
        !!this.positionText ? <PositionLink positionText={this.positionText} /> : undefined
      } */}
        {
          !(this.readonly && !this.positionText?.length) && this.needCopyLink ? (
            <TemporaryShare
              positionText={this.positionText}
              navList={this.routeList}
              navMode={this.navMode}
              onlyCopy={this.navMode === 'copy'}
            />
          ) : undefined
          // this.needCopyLink ? <CopyText style="margin-left: 16px;" tipsText={this.$t('复制链接')} /> : undefined
        }
        {!!this.$slots.append && <span class='nav-append-wrap'>{this.$slots.append}</span>}
      </div>
    );
  }
}
