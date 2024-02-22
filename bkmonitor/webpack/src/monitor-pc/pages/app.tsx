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
// eslint-disable-next-line simple-import-sort/imports
import { Component, ProvideReactive, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import BkPaasLogin from '@blueking/paas-login';
import { addListener, removeListener } from '@blueking/fork-resize-detector';

import { loginRefreshIntercept } from '../common/login-refresh-intercept';
import { getFooter, listStickySpaces } from '../../monitor-api/modules/commons';
import { APP_NAV_COLORS, LANGUAGE_COOKIE_KEY } from '../../monitor-common/utils';
import debounce from '../../monitor-common/utils/debounce-decorator';
import bus from '../../monitor-common/utils/event-bus';
import { docCookies, getUrlParam, random } from '../../monitor-common/utils/utils';
import AuthorityModal from '../../monitor-ui/authority-modal';
import UserConfigMixin from '../mixins/userStoreConfig';
import { GLOAB_FEATURE_LIST, IRouteConfigItem, getRouteConfig } from '../router/router-config';
import { SET_NAV_ROUTE_LIST } from '../store/modules/app';
import { ISpaceItem } from '../types';

import DashboardContainer from './grafana/dashboard-container/dashboard-container';
import CommonNavBar from './monitor-k8s/components/common-nav-bar';
import { useCheckVersion } from './check-version';
import NavTools from './nav-tools';

// #if APP !== 'external'
import BizSelect from '../components/biz-select/biz-select';
import NoticeGuide, { IStepItem } from '../components/novice-guide/notice-guide';
import AiWhale, { AI_WHALE_EXCLUED_ROUTES } from '../components/ai-whale/ai-whale';
import HeaderSettingModal from './header-setting-modal';
// #endif

import './app.scss';
import introduce from '../common/introduce';
import { isAuthority } from '../router/router';
import { getDashboardCache } from './grafana/utils';
import { getDashboardList } from '../../monitor-api/modules/grafana';
import NoticeComponent from '@blueking/notice-component-vue2';
import '@blueking/notice-component-vue2/dist/style.css';

const changeNoticeRouteList = [
  'strategy-config-add',
  'strategy-config-edit',
  'strategy-config-target',
  'alarm-shield-add',
  'alarm-shield-edit',
  'plugin-add',
  'plugin-edit'
];
const microRouteNameList = ['alarm-shield'];
const userConfigModal = new UserConfigMixin();
const NEW_UER_GUDE_KEY = 'NEW_UER_GUDE_KEY';
const STORE_USER_MENU_KEY = 'USER_STORE_MENU_KEY';
export const WATCH_SPACE_STICKY_LIST = 'WATCH_SPACE_STICKY_LIST'; /** 监听空间置顶列表数据事件key */
const currentLang = docCookies.getItem(LANGUAGE_COOKIE_KEY) || 'zhCN';
let WIDTH_LIST = [100, 72, 86, 100, 100, 100, 72, 72];
let SPACE_WIDTH = 0;
if (currentLang === 'en') {
  WIDTH_LIST = [118, 82, 120, 92, 88, 127, 126, 118];
  SPACE_WIDTH = 263;
}
@Component
export default class App extends tsc<{}> {
  @Ref('menuSearchInput') menuSearchInputRef: any;
  @Ref('navHeader') navHeaderRef: HTMLDivElement;
  @Ref('headerDrowdownMenu') headerDrowdownMenuRef: any;
  routeList = getRouteConfig();
  showBizList = false;
  keyword = '';
  localMenuList = [];
  footerHtml = '';
  needMenu = false;
  menuToggle = false;
  noticeStepList: IStepItem[] = [];
  needNewUserGuide = false;
  showNav = false;
  needCopyLink = false;
  needBack = false;
  headerNav = 'home';
  headerNavChange = true;
  menuStore = '';
  hideNavCount = 0;
  spacestickyList: string[] = []; /** 置顶的空间列表 */
  headerSettingShow = false;
  userStoreRoutes: IRouteConfigItem[] = [];
  showAlert = false; // 是否展示跑马灯
  // 全局设置弹窗
  globalSettingShow = false;
  @ProvideReactive('toggleSet') toggleSet: boolean = localStorage.getItem('navigationToogle') === 'true';
  @ProvideReactive('readonly') readonly: boolean = !!window.__BK_WEWEB_DATA__?.readonly || !!getUrlParam('readonly');
  routeViewKey = random(10);
  get bizId() {
    return this.$store.getters.bizId;
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
        item?.children?.some(child => child.id === routeId) ||
        item?.children?.some(child => child?.children?.some(set => set.id === routeId))
    )?.id;
  }
  get routeId() {
    return this.$store.getters.navId;
  }
  get menuList() {
    let list = [];
    if (this.$route.path.includes('exception/403')) this.headerNav = this.$route.query.parentRoute as string;
    if (!this.navActive) {
      list = this.routeList.find(item => item.id === this.headerNav)?.children || [];
      // ai 设置 enable_aiops为true 则ai设置不展示 fasle 则ai设置页面展示
      list = list.filter(item => !(item.id === 'ai' && !window.enable_aiops));
      return list;
    }
    list = this.routeList.find(item => item.id === this.navActive)?.children || [];
    // ai 设置 enable_aiops为true 则ai设置不展示 fasle 则ai设置页面展示
    list = list.filter(item => !(item.id === 'ai' && !window.enable_aiops));
    return list;
  }
  get navRouteList() {
    return this.$store.getters.navRouteList;
  }
  /** 业务列表 */
  get bizIdList(): ISpaceItem[] {
    return this.$store.getters.bizList;
  }
  get hasBusinessAuth() {
    return this.$store.getters.bizList.some(item => +item.id === +this.bizId);
  }
  // 业务列表
  get bizList() {
    return this.$store.getters.bizList.filter(
      item =>
        item.text.includes(this.keyword) ||
        String(item.id).includes(this.keyword) ||
        item.py_text.includes(this.keyword)
    );
  }
  get bizName() {
    return this.$store.getters.bizList.find(item => +item.id === +this.bizId)?.text;
  }

  // 当前是否全屏
  get isFullScreen() {
    return this.$store.getters.isFullScreen;
  }
  // route loading
  get routeChangeLoading() {
    return this.$store.getters.routeChangeLoading;
  }

  /** 仪表盘下的所有子路由页面 */
  get isDashboard() {
    const excludesKey = ['grafana', 'email-subscriptions'];
    return excludesKey.some(key => this.$route.path?.indexOf?.(key) > -1);
  }
  @Watch('$route.name', { immediate: true })
  async handlerRouteChange(v: string) {
    if (v === 'home' && !this.footerHtml) {
      this.footerHtml = await getFooter().catch(() => '');
    }
    this.handleSowNav();
    this.headerNav = this.navActive;
  }

  created() {
    this.handleSetNeedMenu();
    this.menuToggle = localStorage.getItem('navigationToogle') === 'true';
    this.noticeStepList = [
      {
        target: '#head-nav-performance',
        title: this.$tc('观测场景'),
        content: this.$tc('各种监控场景能力，当前有主机监控、服务拨测、Kubernetes监控，还可以自定义观测场景')
      },
      {
        target: '#head-nav-strategy-config',
        title: this.$tc('配置管理'),
        content: this.$tc('告警策略配置、处理套餐、告警组、屏蔽等各种配置管理操作')
      },
      {
        target: '#head-nav-plugin-manager',
        title: this.$tc('route-集成'),
        content: this.$tc('可以制作插件、批量导出导入配置、可自定义数据采集')
      },
      {
        target: '#nav-search-bar',
        title: this.$tc('全站搜索'),
        content: this.$tc('全站搜索，可以跨业务直接搜索任意资源')
      }
    ];
  }
  async handleGetNewUserGuide() {
    if (this.readonly || /^#\/share\//.test(location.hash)) return;
    const value = await userConfigModal.handleGetUserConfig<string[]>(NEW_UER_GUDE_KEY);
    this.needNewUserGuide = !value;
  }
  mounted() {
    this.handleGetNewUserGuide();
    window.LoginModal = this.$refs.login;
    loginRefreshIntercept();
    this.needMenu && this.handleNavHeaderResize();
    this.needMenu && addListener(this.navHeaderRef, this.handleNavHeaderResize);
    addListener(this.navHeaderRef, this.handleNavHeaderResize);
    this.handleFetchStickyList();
    bus.$on(WATCH_SPACE_STICKY_LIST, this.handleWatchSpaceStickyList);
    process.env.NODE_ENV === 'production' && process.env.APP === 'pc' && useCheckVersion();
  }
  beforeDestroy() {
    this.needMenu && removeListener(this.navHeaderRef, this.handleNavHeaderResize);
    bus.$off(WATCH_SPACE_STICKY_LIST);
  }
  // 一级导航宽度变化时触发自动计算收缩
  handleNavHeaderResize() {
    if (!(this.$refs.NavTools as any)?.$el) return;
    const minWidth = 772 + (this.$refs.NavTools as any).$el.clientWidth + 2;
    if (this.navHeaderRef?.clientWidth >= minWidth + SPACE_WIDTH) {
      this.hideNavCount = 0;
      return;
    }
    let width = minWidth + 1 + SPACE_WIDTH - this.navHeaderRef?.clientWidth + 60;
    let index = 0;
    while (width >= 0 && index < 8) {
      width -= WIDTH_LIST[7 - index] + 10;
      index += 1;
    }
    this.hideNavCount = index;
  }
  /**
   * 接收空间uid
   * @param list 空间uid
   */
  handleWatchSpaceStickyList(list: string[]) {
    this.spacestickyList = list;
  }
  /**
   * 获取置顶列表
   */
  async handleFetchStickyList() {
    const params = {
      username: this.$store.getters.userName
    };
    const res = await listStickySpaces(params).catch(() => []);
    this.spacestickyList = res;
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
        const parentRoute = routes.find(item => item.name === meta?.route?.parent);
        parentRoute && routeList.unshift({ name: parentRoute?.meta?.title, id: parentRoute.name });
        if (parentRoute?.meta?.route?.parent) {
          getRouteItem(parentRoute?.meta);
        }
      };
      getRouteItem(meta);
    }
    /** 设置默认的路由 */
    this.$store.commit(`app/${SET_NAV_ROUTE_LIST}`, routeList);
  }
  // 设置是否需要menu
  handleSetNeedMenu() {
    const needMenu = getUrlParam('needMenu');
    this.readonly = !!window.__BK_WEWEB_DATA__?.readonly || !!getUrlParam('readonly');
    this.needMenu = `${needMenu}` !== 'false' && this.$route?.name !== 'share' && !window.__BK_WEWEB_DATA__?.readonly;
  }
  handleGotoPage(name: string) {
    this.$router.push({ name });
  }
  /**
   * @description: 点击左下收缩menu触发
   * @param {boolean} v
   * @return {*}
   */
  handleToggle(v: boolean) {
    this.menuToggle = v;
  }
  handleHeaderMenuClick(id: string, route: string) {
    if (this.$route.name !== route) {
      this.$router.push({ name: route });
    }
  }
  getUserStoreMenu() {
    const storeRoute = localStorage.getItem(STORE_USER_MENU_KEY);
    if (!storeRoute) return null;
    try {
      return JSON.parse(storeRoute);
    } catch {
      return null;
    }
  }
  setUserStoreMenu(newMenu: Record<string, { name: string } | { path: string }>) {
    const storeMenu = this.getUserStoreMenu() || {};
    localStorage.setItem(
      STORE_USER_MENU_KEY,
      JSON.stringify({
        ...storeMenu,
        ...newMenu
      })
    );
  }
  /**
   * @description: 点击menu 触发
   * @param {*} item
   * @return {*}
   */
  async handleMenuItemClick(item) {
    let hasRouteChange = this.$route.path !== item.path;
    const isMicroApp = microRouteNameList.includes(item.id);
    // const isPeddingMicroApp = microRouteNameList.includes((this.$router as any).history?.pending?.name);
    // 屏蔽是微应用 需特殊处理
    if (isMicroApp) {
      hasRouteChange = location.hash !== item.href;
    }
    if (hasRouteChange && !!item.href) {
      await this.$nextTick();
      if (!(this.$router as any).history.pending) {
        const route = item.usePath ? { path: item.path } : { name: item.id };
        !item.noCache &&
          this.setUserStoreMenu({
            [this.headerNav]: route
          });
        if (isMicroApp) {
          location.hash = item.href;
        } else this.$router.push(route);
      }
      setTimeout(() => {
        (this.$router as any).history.pending = null;
      }, 2000);
    }
  }
  /**
   * @description: 路由切换前出发
   * @param {*} newId
   * @param {*} oldId
   * @return {*}
   */
  handleBeforeNavChange(newId: string, oldId: string) {
    this.handleHeaderSettingShowChange(false);
    if (changeNoticeRouteList.includes(this.$route.name)) {
      if (newId !== oldId) {
        this.$router.push({
          name: newId
        });
      }
      return false;
    }
    (this.$router as any).history.pending = null;
    return true;
  }
  // 切换业务
  async handleBizChange(v: number) {
    this.handleHeaderSettingShowChange(false);
    // 切换全局业务配置
    window.cc_biz_id = +v;
    window.bk_biz_id = +v;
    window.space_uid = this.bizIdList.find(item => item.bk_biz_id === +v)?.space_uid;
    this.showBizList = false;
    this.$store.commit('app/SET_BIZ_ID', +v);
    this.$store.commit('app/SET_ROUTE_CHANGE_LOADNG', true);
    const { navId } = this.$route.meta;
    // 处理页面引导页信息
    introduce.clear();
    let promise = null;
    if (navId in introduce.data) {
      promise = introduce.getIntroduce(this.$route.meta.navId);
    }
    // 跳转
    if (navId === 'grafana') {
      const dashboardCache = getDashboardCache();
      const dashboardId = dashboardCache[v];
      let path = 'grafana/home';
      if (dashboardId) {
        const list = await getDashboardList().catch(() => []);
        const hasDashboard = list.some(item => item.uid === dashboardId);
        path = hasDashboard ? `grafana/d/${dashboardId}` : 'grafana/home';
      }
      this.$store.commit('app/SET_BIZ_CHANGE_PEDDING', path);
      await this.handleUpdateRoute({ bizId: `${v}` }, promise, path).then(async hasAuth => {
        if (hasAuth) {
          this.routeViewKey = random(10);
        }
      });
      setTimeout(() => {
        this.$store.commit('app/SET_BIZ_CHANGE_PEDDING', '');
      }, 32);
    } else if (navId !== this.$route.name) {
      // 所有页面的子路由在切换业务的时候都统一返回到父级页面
      const parentRoute = this.$router.options.routes.find(item => item.name === navId);
      if (parentRoute) {
        this.$store.commit('app/SET_BIZ_CHANGE_PEDDING', parentRoute.name);
        const hasAuth = await this.handleUpdateRoute({ bizId: `${v}` }, promise);
        hasAuth &&
          this.$router.push({ name: parentRoute.name, params: { bizId: `${v}` } }, () => {
            this.$store.commit('app/SET_BIZ_CHANGE_PEDDING', '');
          });
        if (!hasAuth) {
          this.$store.commit('app/SET_BIZ_CHANGE_PEDDING', '');
        }
        return;
      }
      await this.handleUpdateRoute({ bizId: `${v}` }, promise).then(hasAuth => {
        hasAuth && (this.routeViewKey = random(10));
      });
    } else {
      await this.handleUpdateRoute({ bizId: `${v}` }, promise).then(hasAuth => {
        hasAuth && (this.routeViewKey = random(10));
      });
    }
    window.requestIdleCallback(() => introduce.initIntroduce(this.$route));
    this.$store.commit('app/SET_ROUTE_CHANGE_LOADNG', false);
  }
  // 刷新页面
  async handleUpdateRoute(params: Record<string, any>, promise = () => false, path?: string) {
    const promiseList = [];
    promiseList.push(promise);
    const { authority } = this.$route.meta;
    const serachParams = new URLSearchParams(params);
    const newUrl = `${window.location.pathname}?${serachParams.toString()}#${path || this.$route.path}`;
    history.replaceState({}, '', newUrl);
    // 判断页面权限
    let hasAuthority = false;
    if (authority?.page) {
      promiseList.push(
        isAuthority(authority?.page)
          .catch(() => false)
          .finally(() => {
            setTimeout(() => this.$store.commit('app/SET_ROUTE_CHANGE_LOADNG', false), 20);
          })
      );
      [, hasAuthority] = await Promise.all(promiseList);
      if (!hasAuthority) {
        this.$router.push({
          path: `/exception/403/${random(10)}`,
          query: {
            actionId: authority.page || '',
            fromUrl: (path || this.$route.path).replace(/^\//, ''),
            parentRoute: this.$route.meta.route.parent
          },
          params: {
            title: '无权限'
          }
        });
        return false;
      }
    }
    await Promise.all(promiseList);
    return true;
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
    this.toggleSet = v;
    localStorage.setItem('navigationToogle', String(v));
  }
  handleNoticeDone() {
    // NEW_UER_GUDE_KEY新手指引字段存储到后台
    userConfigModal.handleSetUserConfig(NEW_UER_GUDE_KEY, JSON.stringify(['done']));
  }
  handleHeaderNavClick(id: string) {
    this.headerNavChange = this.$route.name === 'event-center-detail' ? true : this.headerNav !== id;
    this.headerNav = id;
  }
  /**
   * @description: 点击头部menu
   * @param event
   * @param name
   * @return {*}
   */
  handleClickHeaderMenu(e: MouseEvent, name: string, id?: string) {
    this.handleHeaderSettingShowChange(false);
    this.headerDrowdownMenuRef?.hide?.();
    if (e.ctrlKey || e.metaKey) {
      return;
    }
    this.headerSettingShow = false;
    this.globalSettingShow = false;
    e.preventDefault();
    if (!this.headerNavChange) return;
    id && (this.headerNav = id);
    const { route } = this.$router.resolve({ name }, this.$route, false);
    let storeVal: any = this.getUserStoreMenu();
    if (storeVal) {
      try {
        const storeRoute = storeVal?.[this.headerNav];
        if (storeRoute) {
          // 如果缓存是应用监控路由且当前业务非应用监控白名单 则跳转到默认路由
          if (storeRoute?.name === 'apm-home' && !window.enable_apm) {
            this.setUserStoreMenu({ [this.headerNav]: route });
            this.$router.push(route);
            return;
          }
          const navList = this.routeList.find(item => item.id === this.headerNav).children;
          if (navList?.length) {
            const storeRoute = storeVal[this.headerNav];
            const hasRoute = navList.find(
              item => item.id === storeRoute?.name || item?.children?.some(set => set.id === storeRoute?.name)
            );
            this.$router.push(hasRoute ? storeRoute : route);
            if (!hasRoute) {
              this.setUserStoreMenu({ [this.headerNav]: route });
            }
            return;
          }
          this.$router.push(route);
          return;
        }
      } catch {
        storeVal = null;
      }
    }
    this.$router.push(route);
  }
  handleGoStoreRoute(item: IRouteConfigItem) {
    const globalSetting = GLOAB_FEATURE_LIST.find(set => set.id === item.id);
    (this.$refs.commonHeaderDrop as any)?.hide();
    if (globalSetting) {
      this.handleHeaderSettingShowChange(false);
      (this.$refs.NavTools as any).handleSet(globalSetting);
    } else if (this.$route.name !== item.id) {
      this.handleHeaderSettingShowChange(false);
      const route = item.usePath
        ? {
            path: item.path
          }
        : { name: item.id };
      !item.noCache &&
        this.setUserStoreMenu({
          [this.headerNav]: route
        });
      this.$router.push({
        ...route,
        query: {
          ...item.query
        }
      });
    }
  }
  handleOpenSpace() {
    this.handleHeaderSettingShowChange(false);
    (this.$refs.NavTools as any).handleSet({
      id: 'space-manage',
      name: window.i18n.tc('空间管理').toString()
    });
  }
  handleGlobSettingsShowChange(v: boolean) {
    this.globalSettingShow = v;
    this.headerSettingShow = false;
  }
  commonHeader() {
    return (
      <bk-dropdown-menu
        position-fixed={true}
        ref='commonHeaderDrop'
      >
        <div
          slot='dropdown-trigger'
          class='header-list-item no-border'
        >
          {this.$t('route-常用')}
          <i class='bk-icon icon-down-shape' />
        </div>
        ;
        <ul
          class='common-list'
          slot='dropdown-content'
        >
          {this.userStoreRoutes
            ?.filter(item => item.id)
            .map(item => (
              <li
                class='common-list-item'
                key={item.id}
                onClick={() => this.handleGoStoreRoute(item)}
              >
                <i class={`${item.icon} list-item-icon`} />
                {this.$t(item.name.startsWith('route-') ? item.name : `route-${item.name}`)}
              </li>
            ))}
        </ul>
        <div
          class='list-append'
          slot='dropdown-content'
          onClick={() => this.handleHeaderSettingShowChange(!this.headerSettingShow)}
        >
          <i class='bk-icon icon-cog' />
          {this.$t('管理')}
        </div>
      </bk-dropdown-menu>
    );
  }
  handleHeaderSettingShowChange(v: boolean) {
    this.headerSettingShow = v;
    (this.$refs.commonHeaderDrop as any)?.hide();
  }
  showAlertChange(v: boolean) {
    this.showAlert = v;
  }
  render() {
    /** 页面内容部分 */
    const pageMain = [
      this.showNav && (
        <CommonNavBar
          class='common-nav-bar-single'
          routeList={this.navRouteList}
          needCopyLink={this.needCopyLink}
          needBack={this.needBack}
        ></CommonNavBar>
      ),
      <div
        key={this.routeViewKey}
        v-monitor-loading={{ isLoading: this.routeChangeLoading }}
        class={['page-container', { 'no-overflow': !!this.$route.meta?.customTitle }, this.$route.meta?.pageCls]}
        style={{ height: this.showNav ? 'calc(100% - 52px - var(--notice-alert-height))' : '100%' }}
      >
        <keep-alive>
          <router-view class='page-wrapper'></router-view>
        </keep-alive>
        <router-view
          class='page-wrapper'
          key='noCache'
          name='noCache'
        ></router-view>
        {this.$route.name === 'home' && this.footerHtml ? (
          <div
            class='monitor-footer'
            domPropsInnerHTML={this.footerHtml}
          ></div>
        ) : undefined}
      </div>
    ];
    return (
      <div
        class='bk-monitor'
        style={{
          '--notice-alert-height': this.showAlert ? '40px' : '0px'
        }}
      >
        {process.env.NODE_ENV !== 'development' && (
          <NoticeComponent
            apiUrl='/notice/announcements'
            onShowAlertChange={this.showAlertChange}
          />
        )}
        <bk-navigation
          class={{
            'no-need-menu': !this.needMenu || this.isFullScreen || this.$route.name === 'share'
          }}
          navigation-type='top-bottom'
          on-toggle={this.handleToggle}
          themeColor='#2c354d'
          side-title={this.$t('监控平台')}
          head-height={this.isFullScreen ? 0 : 52}
          need-menu={!!this.menuList?.length && this.needMenu && !this.isFullScreen && this.$route.name !== 'share'}
          default-open={this.menuToggle}
          on-toggle-click={this.handleToggleClick}
        >
          {this.needMenu && !this.isFullScreen && this.$route.name !== 'share' && (
            <div
              class='bk-monitor-header'
              ref='navHeader'
              slot='header'
            >
              <div class='header-list'>
                {process.env.APP !== 'external' && this.commonHeader()}
                {this.routeList.map(
                  ({ id, route, name }, index) =>
                    this.routeList.length - index > this.hideNavCount && (
                      <a
                        key={id}
                        class={[
                          'header-list-item',
                          { 'item-active': !this.globalSettingShow && id === this.headerNav }
                        ]}
                        onMousedown={() => this.handleHeaderNavClick(id)}
                        id={`head-nav-${route}`}
                        // style={{ width }}
                        onClick={e => this.handleClickHeaderMenu(e, route, id)}
                        href={`${this.$router.resolve({ name: route }, this.$route, false).href}`}
                      >
                        {this.$t(name.startsWith('route-') ? name : `route-${name}`)}
                      </a>
                    )
                )}
                {this.hideNavCount > 0 && (
                  <bk-dropdown-menu
                    ref='headerDrowdownMenu'
                    class='header-more-dropdown'
                    position-fixed
                    style='height: inherit'
                  >
                    <span
                      slot='dropdown-trigger'
                      class='header-more'
                    >
                      <i class='bk-icon icon-ellipsis' />
                    </span>
                    <ul
                      class='header-more-list'
                      slot='dropdown-content'
                    >
                      {this.routeList.map(
                        ({ id, route, name }, index) =>
                          this.routeList.length - index <= this.hideNavCount && (
                            <a
                              key={id}
                              class={['list-item', { 'item-active': id === this.headerNav }]}
                              onMousedown={() => this.handleHeaderNavClick(id)}
                              id={`head-nav-${route}`}
                              onClick={e => this.handleClickHeaderMenu(e, route)}
                              href={`${this.$router.resolve({ name: route }, this.$route, false).href}`}
                            >
                              {this.$t(name.startsWith('route-') ? name : `route-${name}`)}
                            </a>
                          )
                      )}
                    </ul>
                  </bk-dropdown-menu>
                )}
              </div>
              {(this.needMenu || (this.$route.name && this.$route.name !== 'share')) && (
                <NavTools
                  ref='NavTools'
                  show={this.globalSettingShow}
                  onChange={this.handleGlobSettingsShowChange}
                />
              )}
            </div>
          )}
          {
            // #if APP !== 'external'
            this.menuList?.length ? (
              <div
                class='fta-menu'
                key='menu'
                slot='menu'
              >
                <div class='biz-select'>
                  <BizSelect
                    value={+this.bizId}
                    bizList={this.bizIdList}
                    isShrink={!this.menuToggle}
                    theme='dark'
                    minWidth={380}
                    stickyList={this.spacestickyList}
                    onOpenSpaceManager={this.handleOpenSpace}
                    onChange={this.handleBizChange}
                  />
                </div>
                <bk-navigation-menu
                  style={{ marginTop: this.headerNav === 'data' ? '8px' : '0px' }}
                  toggle-active={this.menuToggle}
                  default-active={this.routeId}
                  before-nav-change={this.handleBeforeNavChange}
                  {...{ props: APP_NAV_COLORS }}
                >
                  {this.menuList
                    .filter(item => !item.hidden)
                    .map(item =>
                      item?.children?.length ? (
                        <bk-navigation-menu-group
                          key={item.id}
                          group-name={this.menuToggle ? this.$t(item.name) : this.$t(item.shortName)}
                        >
                          {item.children
                            .filter(child => !child.hidden)
                            .map(child => (
                              <bk-navigation-menu-item
                                onClick={() => this.handleMenuItemClick(child)}
                                key={child.id}
                                href={child.href}
                                has-child={child.children && !!child.children.length}
                                scopedSlots={{
                                  child: () =>
                                    child?.children?.map(set => (
                                      <bk-navigation-menu-item
                                        class={{ 'disabled-event': !set.href && !set.path }}
                                        onClick={() => this.handleMenuItemClick(set)}
                                        key={set.id}
                                        href={set.href}
                                        {...{ props: set }}
                                      >
                                        {this.$t(set.name)}
                                      </bk-navigation-menu-item>
                                    ))
                                }}
                                {...{ props: child }}
                              >
                                <span class='nav-menu-item'>
                                  {this.$t(`route-${child.name}`)}
                                  {child.isBeta && <span class='nav-menu-item-beta'>BETA</span>}
                                  {child.navIcon && <i class={child.navIcon} />}
                                </span>
                              </bk-navigation-menu-item>
                            ))}
                        </bk-navigation-menu-group>
                      ) : (
                        <bk-navigation-menu-item
                          onClick={() => this.handleMenuItemClick(item)}
                          key={item.id}
                          href={item.href}
                          has-child={false}
                          {...{ props: item }}
                        >
                          <span class='nav-menu-item'>
                            {this.$t(`route-${item.name}`)}
                            {item.isBeta && <span class='nav-menu-item-beta'>BETA</span>}
                            {item.navIcon && <i class={item.navIcon} />}
                          </span>
                        </bk-navigation-menu-item>
                      )
                    )}
                </bk-navigation-menu>
              </div>
            ) : undefined
            // #endif
          }
          {!this.menuList?.length && this.isDashboard ? (
            <DashboardContainer
              key={this.routeViewKey}
              bizIdList={this.bizIdList}
              onBizChange={this.handleBizChange}
              onOpenSpaceManager={this.handleOpenSpace}
            >
              <template slot='main'>{pageMain}</template>
            </DashboardContainer>
          ) : (
            pageMain
          )}
          <AuthorityModal />
          <BkPaasLogin ref='login' />
          {
            // #if APP !== 'external'
            !this.readonly && this.$route.name && this.$route.name !== 'share' && (
              <HeaderSettingModal
                show={this.headerSettingShow}
                onStoreRoutesChange={v => (this.userStoreRoutes = v)}
                onChange={this.handleHeaderSettingShowChange}
              />
            )
            // #endif
          }
          {
            // #if APP !== 'external'
            this.hasBusinessAuth && this.needNewUserGuide && (
              <NoticeGuide
                stepList={this.noticeStepList}
                onDone={this.handleNoticeDone}
              />
            )
            // #endif
          }
          <div
            class='monitor-logo'
            slot='side-icon'
          />
        </bk-navigation>
        {
          // #if APP !== 'external'
          !(this.readonly || window.__POWERED_BY_BK_WEWEB__) &&
            this.$route.name &&
            !AI_WHALE_EXCLUED_ROUTES.includes(this.$route.name) &&
            this.hasBusinessAuth && <AiWhale></AiWhale>
          // #endif
        }
      </div>
    );
  }
}
