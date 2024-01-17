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
import Vue from 'vue';
import { Component, ProvideReactive, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { APP_NAV_COLORS } from '../../monitor-common/utils';
import { getUrlParam } from '../../monitor-common/utils/utils';
import CommonNavBar from '../../monitor-pc/pages/monitor-k8s/components/common-nav-bar';
import AuthorityModal from '../../monitor-ui/authority-modal';
import debounce from '../common/debounce-decorator';
import { createRouteConfig } from '../router/router-config';
import appStoreModule from '../store/modules/app';
import authorityStore from '../store/modules/authority';
import { ISpaceItem } from '../typings';

import './app.scss';

@Component
export default class App extends tsc<{}> {
  @Ref('menuSearchInput') menuSearchInputRef;
  private routeList = createRouteConfig();
  private menuToggle = false;
  private bizId = window.cc_biz_id;
  private showBizList = false;
  private keyword = '';

  private showNav = false;
  private needCopyLink = false;
  private needBack = false;
  private needMenu = !window.__POWERED_BY_BK_WEWEB__;
  // eslint-disable-next-line @typescript-eslint/member-ordering
  @ProvideReactive('readonly') readonly: boolean = !!window.__BK_WEWEB_DATA__?.readonly || !!getUrlParam('readonly');
  get navRouteList() {
    return this.$store.getters.navRouteList;
  }
  get navActive() {
    let routeId = this.routeId || 'home';
    const {
      options: { routes }
    } = this.$router;
    const parentId = routes.find(item => routeId === item.name)?.meta?.route?.parent;
    routeId = parentId || routeId;
    return this.routeList.find(
      item =>
        item.route === routeId ||
        item.id === routeId ||
        item?.children?.some(child => child.children.some(set => set.id === routeId))
    )?.id;
  }
  get routeId() {
    return this.$store.getters.navId;
  }
  get menuList() {
    return this.routeList.find(item => item.id === this.navActive)?.children;
  }
  // 业务列表
  get bizList() {
    return this.$store.getters.bizList.filter(
      item => item.text.includes(this.keyword) || String(item.id).includes(this.keyword)
    );
  }
  get bizName() {
    return this.$store.getters.bizList.find(item => +item.id === +this.bizId)?.text;
  }
  created() {
    this.needMenu && this.handleSetNeedMenu();
    this.bizId = this.$store.getters.bizId;
    this.menuToggle = localStorage.getItem('navigationToogle') === 'true';
    Vue.prototype.$authorityStore = authorityStore;
  }
  // 设置是否需要menu
  handleSetNeedMenu() {
    const needMenu = getUrlParam('needMenu');
    this.readonly = !!window.__BK_WEWEB_DATA__?.readonly || !!getUrlParam('readonly');
    this.needMenu = `${needMenu}` !== 'false' && this.$route.name !== 'share' && !window.__BK_WEWEB_DATA__?.readonly;
  }
  /**
   * 处理路由面包屑数据
   */
  handleSowNav() {
    const routeList = [];
    const {
      options: { routes }
    } = this.$router;
    const { meta, name } = this.$route;
    this.showNav = !meta.noNavBar && !!name;
    if (this.showNav) {
      this.needCopyLink = meta.needCopyLink ?? false;
      this.needBack = meta.needBack ?? false;
      routeList.unshift({ name: meta.title, id: name });
      const getRouteItem = (meta: any) => {
        const parentRoute = routes.find(item => item.name === (meta?.route?.parent ?? null));
        parentRoute && routeList.unshift({ name: parentRoute?.meta?.title, id: parentRoute.name });
        if (parentRoute?.meta?.route?.parent) {
          getRouteItem(parentRoute?.meta);
        }
      };
      getRouteItem(meta);
    }
    /** 设置默认的路由 */
    // const appStoreModule = getModule(AppStore, this.$store);
    appStoreModule.setNavRouterList(routeList);
  }
  @Watch('$route.name')
  routeChange() {
    this.handleSowNav();
  }
  handleGotoPage(name: string) {
    this.$router.push({ name });
  }
  handleToggle(v: boolean) {
    this.menuToggle = v;
  }
  handleHeaderMenuClick(id: string, route: string) {
    this.$route.name !== route && this.$router.push({ name: route });
  }
  async handleMenuItemClick(id: string) {
    if (this.$route.name !== id) {
      await this.$nextTick();
      if (!this.$router.history.pending) {
        this.$router.push({
          name: id
        });
      }
    }
  }
  handleBeforeNavChange(newId, oldId) {
    if (
      ['strategy-config-add', 'strategy-config-edit', 'alarm-shield-add', 'alarm-shield-edit'].includes(
        this.$route.name
      )
    ) {
      if (newId !== oldId) {
        this.$router.push({
          name: newId
        });
      }
      return false;
    }
    return true;
  }
  // 切换业务
  handleBizChange(v: number) {
    window.cc_biz_id = +v;
    window.bk_biz_id = +v;
    this.showBizList = false;
    this.$store.commit('app/SET_APP_STATE', { bizId: +v });
    const { navId } = this.$route.meta;
    // 所有页面的子路由在切换业务的时候都统一返回到父级页面
    if (navId !== this.$route.name) {
      const parentRoute = this.$router.options.routes.find(item => item.name === navId);
      if (parentRoute) {
        location.href = `${location.origin}${location.pathname}?bizId=${window.cc_biz_id}#${parentRoute.path}`;
      } else {
        this.handleReload();
      }
    } else {
      this.handleReload();
    }
  }
  // 刷新页面
  handleReload() {
    const { needClearQuery } = this.$route.meta;
    // 清空query查询条件
    if (needClearQuery) {
      location.href = `${location.origin}${location.pathname}?bizId=${window.cc_biz_id}#${this.$route.path}`;
    } else {
      location.search = `?bizId=${window.cc_biz_id}`;
    }
  }
  handleClickBizSelect() {
    this.showBizList = !this.showBizList;
    setTimeout(() => {
      this.menuSearchInputRef.focus();
    }, 100);
  }
  @debounce(300)
  handleBizSearch(v: string) {
    this.keyword = v;
  }
  handleToggleClick(v: boolean) {
    localStorage.setItem('navigationToogle', String(v));
  }
  // 左侧栏业务列表选择
  menuSelect() {
    return (
      <div class='menu-select'>
        <span
          tabindex={0}
          class='menu-select-name'
          on-mousedown={this.handleClickBizSelect}
        >
          {this.bizName}
          <i
            class='bk-select-angle bk-icon icon-angle-down select-icon'
            style={{ transform: `rotate(${!this.showBizList ? '0deg' : '-180deg'})` }}
          />
        </span>
        <ul
          style={{ display: this.showBizList ? 'flex' : 'none' }}
          class='menu-select-list'
        >
          <bk-input
            ref='menuSearchInput'
            class='menu-select-search'
            clearable={false}
            right-icon='bk-icon icon-search'
            placeholder={this.$t('搜索')}
            value={this.keyword}
            on-clear={() => this.handleBizSearch('')}
            on-change={this.handleBizSearch}
            on-blur={() => (this.showBizList = false)}
          />
          {this.bizList.length ? (
            this.bizList.map((item: ISpaceItem) => (
              <li
                class={['list-item', { 'is-select': item.id === this.bizId }]}
                key={item.id}
                onMousedown={() => this.handleBizChange(item.id)}
              >
                {item.text}
              </li>
            ))
          ) : (
            <li class='list-empty'>{this.$t('无匹配的数据')}</li>
          )}
        </ul>
      </div>
    );
  }
  render() {
    return (
      <div class={{ 'apm-wrap': true, 'is-micro-app': !this.needMenu }}>
        <bk-navigation
          navigation-type='top-bottom'
          on-toggle={this.handleToggle}
          themeColor='#2c354d'
          side-title={'APM'}
          need-menu={!!this.menuList && this.needMenu}
          default-open={this.menuToggle}
          on-toggle-click={this.handleToggleClick}
        >
          {this.needMenu && (
            <div
              class='apm-wrap-header'
              slot='header'
            >
              <ul class='header-list'>
                {this.routeList.map(({ id, route, name }) => (
                  <li
                    key={id}
                    class={['header-list-item', { 'item-active': id === this.navActive }]}
                    onClick={() => this.handleHeaderMenuClick(id, route)}
                  >
                    {this.$t(name)}
                  </li>
                ))}
              </ul>
            </div>
          )}
          <span
            slot='side-icon'
            class='app-logo'
          ></span>
          {this.menuList?.length ? (
            <div
              class='fta-menu'
              key='menu'
              slot='menu'
            >
              <div class='fta-menu-select'>
                {this.menuToggle ? (
                  this.menuSelect()
                ) : (
                  <span class='menu-title'>{this.bizName.split(']')[1][1].toLocaleUpperCase()}</span>
                )}
              </div>
              <bk-navigation-menu
                toggle-active={this.menuToggle}
                default-active={this.routeId}
                before-nav-change={this.handleBeforeNavChange}
                {...{ props: APP_NAV_COLORS }}
              >
                {this.menuList.map(item =>
                  item?.children?.length ? (
                    <bk-navigation-menu-group
                      key={item.id}
                      group-name={this.menuToggle ? this.$t(item.name) : this.$t(item.shortName)}
                    >
                      {item.children.map(child => (
                        <bk-navigation-menu-item
                          onClick={() => this.handleMenuItemClick(child.id)}
                          key={child.id}
                          href={child.href}
                          {...{ props: child }}
                        >
                          <span>{this.$t(child.name)}</span>
                        </bk-navigation-menu-item>
                      ))}
                    </bk-navigation-menu-group>
                  ) : undefined
                )}
              </bk-navigation-menu>
            </div>
          ) : undefined}
          {/* {this.navigationBar} */}
          {this.showNav && (
            <CommonNavBar
              class='common-nav-bar-single'
              routeList={this.navRouteList}
              needCopyLink={this.needCopyLink}
              needBack={this.needBack}
            ></CommonNavBar>
          )}
          <div
            class={[
              'page-container',
              {
                'page-padding': this.$route?.meta?.needPadding,
                'has-nav': !this.$route?.meta?.noNavBar
              }
            ]}
          >
            <keep-alive>
              <router-view class='page-wrapper'></router-view>
            </keep-alive>
            <router-view
              class='page-wrapper'
              key='noCache'
              name='noCache'
            ></router-view>
            <AuthorityModal></AuthorityModal>
          </div>
        </bk-navigation>
      </div>
    );
  }
}
