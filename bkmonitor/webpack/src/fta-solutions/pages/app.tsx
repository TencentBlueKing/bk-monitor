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

import { Component, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { listStickySpaces } from 'monitor-api/modules/commons';
import { APP_NAV_COLORS } from 'monitor-common/utils';
import bus from 'monitor-common/utils/event-bus';
import { globalUrlFeatureMap } from 'monitor-common/utils/global-feature-map';
import BizSelect from 'monitor-pc/components/biz-select/biz-select';
import CommonNavBar from 'monitor-pc/pages/monitor-k8s/components/common-nav-bar';
import NavTools from 'monitor-pc/pages/nav-tools';
import AuthorityModal from 'monitor-ui/authority-modal/index';
import {} from 'vue-router';

import debounce from '../common/debounce-decorator';
import { createRouteConfig } from '../router/router-config';
import { SET_NAV_ROUTE_LIST } from '../store/modules/app';
import authorityStore from '../store/modules/authority';

import type { ISpaceItem } from '../typings';

import './app.scss';

const WATCH_SPACE_STICKY_LIST = 'WATCH_SPACE_STICKY_LIST'; /** 监听空间置顶列表数据事件key */

@Component
export default class App extends tsc<object> {
  @Ref('menuSearchInput') menuSearchInputRef: any;
  private routeList = createRouteConfig();
  private menuToggle = false;
  private bizId = window.cc_biz_id;
  private showBizList = false;
  private keyword = '';
  private showNav = false;
  private needCopyLink = false;
  private needBack = false;
  private needMenu = !window.__POWERED_BY_BK_WEWEB__;
  private spaceStickyList: string[] = []; /** 置顶的空间列表 */

  private globalSettingShow = false;
  get navActive() {
    let routeId = this.routeId || 'home';
    const {
      options: { routes },
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
  get navRouteList() {
    return this.$store.getters.navRouteList;
  }
  /** 业务列表 */
  get bizIdList(): ISpaceItem[] {
    return this.$store.getters.bizList;
  }
  // 当前是否全屏
  get isFullScreen() {
    return this.$store.getters.isFullScreen;
  }
  @Watch('$route.name', { immediate: true })
  routeChange() {
    this.handleSowNav();
  }
  created() {
    this.needMenu && this.handleSetNeedMenu();
    this.bizId = this.$store.getters.bizId;
    this.menuToggle = localStorage.getItem('navigationToggle') === 'true';
    Vue.prototype.$authorityStore = authorityStore;
  }
  mounted() {
    this.handleFetchStickyList();
    bus.$on(WATCH_SPACE_STICKY_LIST, this.handleWatchSpaceStickyList);
  }
  // 设置是否需要menu
  handleSetNeedMenu() {
    this.needMenu = globalUrlFeatureMap.NEED_MENU;
  }

  /**
   * 接收空间uid
   * @param list 空间uid
   */
  handleWatchSpaceStickyList(list: string[]) {
    this.spaceStickyList = list;
  }
  /**
   * 获取置顶列表
   */
  async handleFetchStickyList() {
    const params = {
      username: this.$store.getters.userName,
    };
    const res = await listStickySpaces(params).catch(() => []);
    this.spaceStickyList = res;
  }
  /**
   * 处理路由面包屑数据
   */
  handleSowNav() {
    const routeList = [];
    const {
      options: { routes },
    } = this.$router;
    const { meta, name } = this.$route;
    this.showNav = !meta.noNavBar && !!name;
    if (this.showNav) {
      this.needCopyLink = meta.needCopyLink ?? false;
      this.needBack = meta.needBack ?? false;
      routeList.unshift({ name: this.$t(meta.title), id: name });
      const getRouteItem = (meta: any) => {
        const parentRoute = routes.find(item => item.name === meta?.route?.parent);
        parentRoute && routeList.unshift({ name: this.$t(parentRoute?.meta?.title), id: parentRoute.name });
        if (parentRoute?.meta?.route?.parent) {
          getRouteItem(parentRoute?.meta);
        }
      };
      getRouteItem(meta);
    }
    /** 设置默认的路由 */
    this.$store.commit(`app/${SET_NAV_ROUTE_LIST}`, routeList);
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
      if (!(this.$router as any).history.pending) {
        this.$router.push({
          name: id,
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
          name: newId,
        });
      }
      return false;
    }
    return true;
  }
  handleOpenSpace() {
    (this.$refs.NavTools as any).handleSet({
      id: 'space-manage',
      name: window.i18n.tc('空间管理').toString(),
    });
  }
  handleGlobSettingsShowChange(v: boolean) {
    this.globalSettingShow = v;
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
    localStorage.setItem('navigationToggle', String(v));
  }
  // 左侧栏业务列表选择
  menuSelect() {
    return (
      <div class='menu-select'>
        <span
          class='menu-select-name'
          tabindex={0}
          on-mousedown={this.handleClickBizSelect}
        >
          {this.bizName}
          <i
            style={{ transform: `rotate(${!this.showBizList ? '0deg' : '-180deg'})` }}
            class='bk-select-angle bk-icon icon-angle-down select-icon'
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
            placeholder={this.$t('搜索')}
            right-icon='bk-icon icon-search'
            value={this.keyword}
            on-blur={() => (this.showBizList = false)}
            on-change={this.handleBizSearch}
            on-clear={() => this.handleBizSearch('')}
          />
          {this.bizList.length ? (
            this.bizList.map((item: ISpaceItem) => (
              <li
                key={item.id}
                class={['list-item', { 'is-select': item.id === this.bizId }]}
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
      <div class={{ 'fta-solution': true, 'is-micro-app': !this.needMenu }}>
        <bk-navigation
          class={{
            'no-need-menu': !this.needMenu || this.isFullScreen || this.$route.name === 'share',
          }}
          default-open={this.menuToggle}
          navigation-type='top-bottom'
          need-menu={!!this.menuList && this.needMenu}
          side-title={this.$t('故障自愈')}
          themeColor='#242b3b'
          on-toggle={this.handleToggle}
          on-toggle-click={this.handleToggleClick}
        >
          {this.needMenu && (
            <div
              class='fta-solution-header'
              slot='header'
            >
              <ul class='header-list'>
                {this.routeList.map(({ id, route, name }) => (
                  <li
                    key={id}
                    class={['header-list-item', { 'item-active': id === this.navActive }]}
                    onClick={() => this.handleHeaderMenuClick(id, route)}
                  >
                    {this.$t(`route-${name}`)}
                  </li>
                ))}
              </ul>
              {(this.needMenu || (this.$route.name && this.$route.name !== 'share')) && (
                <NavTools
                  ref='NavTools'
                  show={this.globalSettingShow}
                  onChange={this.handleGlobSettingsShowChange}
                />
              )}
            </div>
          )}
          <span
            class='app-logo'
            slot='side-icon'
          />
          {this.menuList?.length ? (
            <div
              key='menu'
              class='fta-menu'
              slot='menu'
            >
              <div class='biz-select'>
                <BizSelect
                  bizList={this.bizIdList}
                  isShrink={!this.menuToggle}
                  minWidth={380}
                  stickyList={this.spaceStickyList}
                  theme='dark'
                  value={+this.bizId}
                  onChange={this.handleBizChange}
                  onOpenSpaceManager={this.handleOpenSpace}
                />
              </div>
              <bk-navigation-menu
                before-nav-change={this.handleBeforeNavChange}
                default-active={this.routeId}
                toggle-active={this.menuToggle}
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
                          key={child.id}
                          href={child.href}
                          onClick={() => this.handleMenuItemClick(child.id)}
                          {...{ props: child }}
                        >
                          <span>{this.$t(`route-${child.name}`)}</span>
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
              navMode={'copy'}
              needBack={this.needBack}
              needCopyLink={this.needCopyLink}
              routeList={this.navRouteList}
            />
          )}
          <div class='page-container'>
            <keep-alive>
              <router-view class='page-wrapper' />
            </keep-alive>
            <router-view
              key='noCache'
              class='page-wrapper'
              name='noCache'
            />
            <AuthorityModal />
          </div>
        </bk-navigation>
      </div>
    );
  }
}
