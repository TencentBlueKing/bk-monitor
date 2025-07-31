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

import './apm-common-nav-bar.scss';

export interface INavItem {
  class?: string;
  id: string;
  /** 展示名称 */
  name: string;
  // 不需要文本点击跳转功能
  notLink?: boolean;
  query?: Record<string, any>;
  subName?: string;
  /** 下拉配置 */
  selectOption?: {
    loading?: boolean;
    /** 下拉列表 */
    selectList: ISelectItem[];
    /** 下拉选择的值 */
    value: string;
  };
}

// nav 导航栏设置数据item
export interface IRouteBackItem {
  id?: string;
  isBack?: boolean;
  name?: string;
  query?: Record<string, any>;
}

export interface ISelectItem {
  [key: string]: any;
  id: any;
  name: string;
}

export type NavBarMode = 'copy' | 'display' | 'share';

interface ICommonNavBarEvents {
  onNavSelect: (item: ISelectItem, routeId: string) => void;
}

interface ICommonNavBarProps {
  backGotoItem?: IRouteBackItem;
  navMode?: NavBarMode;
  needBack?: boolean;
  needCopyLink?: boolean;
  needShadow?: boolean;
  positionText?: string;
  routeList?: INavItem[];
  callbackRouterBack?: () => void;
}

@Component({
  name: 'ApmCommonNavBar',
  components: {
    TemporaryShare: () =>
      import(/* webpackChunkName: "TemporaryShare" */ 'monitor-pc/components/temporary-share/temporary-share') as any,
  },
})
export default class ApmCommonNavBar extends tsc<ICommonNavBarProps, ICommonNavBarEvents> {
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
  get navList(): INavItem[] {
    // 临时分享模式下可能没有title 需要从父级应用下传入获取
    if (window.__POWERED_BY_BK_WEWEB__ && window.token) {
      return window.__BK_WEWEB_DATA__.navList || this.routeList || [];
    }
    return this.routeList;
  }

  navSelectShow = {};

  // goto page by name
  handleGotoPage(item: INavItem) {
    if (this.readonly || item.notLink) return;
    const targetRoute = this.$router.resolve({
      name: item.id,
      query: {
        ...item.query,
        from: this.$route.query?.from || undefined,
        to: this.$route.query?.to || undefined,
        dashboardId: this.$route.query.dashboardId,
      },
    });
    /** 防止出现跳转当前地址导致报错 */
    if (targetRoute.resolved.fullPath !== this.$route.fullPath) {
      this.$router.push({
        name: item.id,
        query: {
          ...item.query,
          from: this.$route.query?.from || undefined,
          to: this.$route.query?.to || undefined,
          dashboardId: this.$route.query.dashboardId,
        },
      });
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

  handleNavSelectShow(item: INavItem) {
    this.$set(this.navSelectShow, item.id, !this.navSelectShow[item.id]);
  }

  handleNavSelect(selectItem: string, routeItem: INavItem) {
    this.$emit(
      'navSelect',
      routeItem.selectOption.selectList.find(item => item.id === selectItem),
      routeItem.id
    );
  }

  sortSelectList(selectOption: INavItem['selectOption']) {
    const selectList: ISelectItem[] = JSON.parse(JSON.stringify(selectOption.selectList));
    const index = selectList.findIndex(item => item.id === selectOption.value);
    const selectItem = selectList.splice(index, 1);
    selectList.sort((a, b) => (a.id >= b.id ? 1 : -1));
    selectList.unshift(...selectItem);
    return selectList;
  }

  render() {
    const len = this.routeList.length;
    return (
      <div
        key='navigationBar'
        class={`navigation-bar common-nav-bar ${this.needShadow ? 'detail-bar' : ''}`}
        slot='title'
      >
        {!this.readonly && (this.needBack || ((this.needBack ?? true) && len > 1)) && (
          <span
            class='icon-monitor icon-back-left navigation-bar-back'
            onClick={() => this.handleBackGotoPage()}
          />
        )}
        <ul class='navigation-bar-list'>
          {this.navList.map((item, index) => (
            <li
              key={index}
              class='bar-item'
            >
              {index > 0 ? <span class='item-split'>/</span> : undefined}
              {!item.selectOption?.loading ? (
                [
                  (!item.selectOption || (index < len - 1 && !item.notLink)) && (
                    <span
                      key='1'
                      class={{
                        'item-name': true,
                        'parent-nav': !!item.id && index < len - 1 && !item.notLink,
                        'only-title': len === 1,
                        [item.class]: !!item.class,
                      }}
                      onClick={() => item.id && index < len - 1 && this.handleGotoPage(item)}
                    >
                      <span class='item-name-text'>{item.name}</span>
                      {!!item.subName && (
                        <span class='item-sub-name'>
                          {item.name ? '-' : ''}&nbsp;{item.subName}
                        </span>
                      )}
                    </span>
                  ),
                  item.selectOption && (
                    <bk-select
                      popover-options={{
                        placement: 'bottom',
                      }}
                      allow-enter={false}
                      ext-popover-cls='nav-bar-select-popover'
                      popover-width={240}
                      value={item.selectOption.value}
                      searchable
                      onChange={val => this.handleNavSelect(val, item)}
                      onToggle={() => this.handleNavSelectShow(item)}
                    >
                      <div
                        class={{ 'select-trigger': true, active: this.navSelectShow[item.id] }}
                        slot='trigger'
                      >
                        {(index === len - 1 || item.notLink) && (
                          <span
                            class={{
                              'item-name': true,
                              [item.class]: !!item.class,
                            }}
                          >
                            <span class='item-name-text'>{item.name}</span>
                            {!!item.subName && (
                              <span class='item-sub-name'>
                                {item.name ? '-' : ''}&nbsp;{item.subName}
                              </span>
                            )}
                          </span>
                        )}
                        <div class='arrow-wrap'>
                          <i class='icon-monitor icon-mc-arrow-down' />
                        </div>
                      </div>

                      {this.sortSelectList(item.selectOption).map((selectItem, index) => (
                        <bk-option
                          id={selectItem.id}
                          key={`${selectItem.id}_${index}`}
                          class={{ item: true, active: selectItem.id === item.selectOption.value }}
                          name={selectItem.name}
                        >
                          <div
                            class='name'
                            v-bk-overflow-tips
                          >
                            {selectItem.name}
                          </div>
                        </bk-option>
                      ))}
                    </bk-select>
                  ),
                ]
              ) : (
                <div class='skeleton-element' />
              )}
            </li>
          ))}
        </ul>
        {!(this.readonly && !this.positionText?.length) && this.needCopyLink ? (
          <temporary-share
            navList={this.routeList}
            navMode={this.navMode}
            positionText={this.positionText}
            onlyCopy={this.navMode === 'copy'}
          />
        ) : undefined}
        {!!this.$slots.append && <span class='nav-append-wrap'>{this.$slots.append}</span>}
      </div>
    );
  }
}
