/* eslint-disable perfectionist/sort-imports */
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
import { Component, Prop, Watch } from 'vue-property-decorator';
import { ofType } from 'vue-tsx-support';

import { useJSONP } from 'monitor-api/jsonp';
import { LANGUAGE_COOKIE_KEY } from 'monitor-common/utils/constant';
import bus from 'monitor-common/utils/event-bus';
import { docCookies } from 'monitor-common/utils/utils';

import LogVersion from '../components/log-version/intex';
import LogVersionMixin from '../components/log-version/log-version-mixin';
import DocumentLinkMixin from '../mixins/documentLinkMixin';
import { GLOBAL_FEATURE_LIST, setLocalStoreRoute } from '../router/router-config';
import enIcon from '../static/images/svg/en.svg';
import zhIcon from '../static/images/svg/zh.svg';
import type { IMenuItem } from '../types';

// #if APP !== 'external'
// import GlobalSearchModal from './global-search-modal-new';
import HomeSelect from 'monitor-pc/pages/home/new-home/components/home-select';
import SettingModal from './setting-modal';
// #endif

import './nav-tools.scss';
import { getCmdShortcutKey } from 'monitor-common/utils/navigator';

export const HANDLE_SHOW_SETTING = 'HANDLE_SHOW_SETTING';
export const HANDLE_HIDDEN_SETTING = 'HANDLE_HIDDEN_SETTING';
export const HANDLE_MENU_CHANGE = 'HANDLE_MENU_CHANGE';
interface INavToolsProps {
  show: boolean;
}
interface INavToolsEvents {
  onChange: boolean;
}
@Component({
  mixins: [LogVersionMixin],
  // #if APP !== 'external'
  components: {
    GlobalConfig: () => import(/* webpackChunkName: "global-config" */ '../pages/global-config') as any,
    HealthZ: () => import(/* webpackChunkName: "healthz" */ '../pages/healthz-new/healthz-alarm') as any,
    MigrateDashboard: () =>
      import(/* webpackChunkName: 'MigrateDashboard' */ '../pages/migrate-dashboard/migrate-dashboard.vue') as any,
    ResourceRegister: () =>
      import(/* webpackChunkName: 'ResourceRegister' */ '../pages/resource-register/resource-register') as any,
    DataPipeline: () => import(/* webpackChunkName: 'DataPipeline' */ '../pages/data-pipeline/data-pipeline') as any,
    SpaceManage: () => import(/* webpackChunkName: 'SpaceManage' */ './space-manage/space-manage') as any,
    GlobalCalendar: () => import(/* webpackChunkName: 'calendar' */ './calendar/calendar') as any,
    MyApply: () => import(/* webpackChunkName: 'MyApply' */ './my-apply/my-apply') as any,
    MySubscription: () => import(/* webpackChunkName: 'MySubscription' */ './my-subscription/my-subscription') as any,
  },
  // #endif
} as any)
class NavTools extends DocumentLinkMixin {
  @Prop({ default: false, type: Boolean }) show: boolean;
  // 帮助列表
  helpList: IMenuItem[] = [];
  setList: IMenuItem[] = [];
  languageList: IMenuItem[] = [];
  logShow = false;
  globalSearchShow = false;
  activeSetting = '';
  settingTitle = '';
  defaultSearchPlaceholder = `${this.$t('全站搜索')}`;
  globalSearchPlaceholder = this.defaultSearchPlaceholder;
  isShowMyApplyModal = false;
  isShowMyReportModal = false;

  get isHomePage() {
    return this.$route.name && this.$route.name === 'home';
  }

  // 全局弹窗在路由变化时需要退出
  @Watch('$route.name')
  async handler() {
    this.$emit('change', false);
    this.globalSearchShow = false;
    this.isShowMyReportModal = false;
    this.isShowMyApplyModal = false;
  }

  /** 20231226 暂不使用 */
  /** vue-router 加载时间过长，导致没法直接在 mounted 中判断，故通过监听的方式去控制 我的订阅 弹窗是否打开 */
  @Watch('$route.query')
  handleQueryChange() {
    // 从 日志平台 跳转过来时会通过 url 参数开启 我的订阅 弹窗。
    if (this.$route.query.isShowMyReport) {
      this.isShowMyReportModal = this.$route.query.isShowMyReport === 'true';
    }
  }

  created() {
    this.helpList = [
      {
        id: 'DOCS',
        name: this.$t('产品文档').toString(),
        href: '',
      },
      {
        id: 'VERSION',
        name: this.$t('版本日志').toString(),
      },
      {
        id: 'FAQ',
        name: this.$t('问题反馈').toString(),
        href: window.ce_url,
      },
    ];
    this.setList = GLOBAL_FEATURE_LIST.map(({ name, ...args }) => ({
      name: `route-${name}`,
      ...args,
    }));
    this.languageList = [
      {
        id: 'zh-cn',
        name: '中文',
      },
      {
        id: 'en',
        name: 'English',
      },
    ];
  }
  mounted() {
    document.addEventListener('keydown', this.handleKeyupSearch);
    bus.$on(HANDLE_SHOW_SETTING, this.handleShowSetting);
    bus.$on('handle-keyup-search', this.handleKeyupSearch);
    bus.$on(HANDLE_MENU_CHANGE, this.handleSet);
    window.addEventListener('blur', this.hidePopoverSetOrHelp);
  }
  beforeDestroy() {
    document.removeEventListener('keydown', this.handleKeyupSearch);
    bus.$off('handle-keyup-search', this.handleKeyupSearch);
    bus.$off(HANDLE_MENU_CHANGE, this.handleSet);
    window.removeEventListener('blur', this.hidePopoverSetOrHelp);
  }

  handleShowSetting(key: string) {
    const item = this.setList.find(item => item.id === key);
    if (item) {
      this.handleSet(item);
    }
  }
  /**
   * @description: ctrl+k 打开全站搜索弹窗
   * @param { * } event
   */
  handleKeyupSearch(event: KeyboardEvent) {
    if (this.globalSearchShow) return;
    if ((event.ctrlKey || event.metaKey) && event.key === '/') {
      if (this.isHomePage) {
        bus.$emit('handle-keyup-nav', event);
      } else {
        event.preventDefault();
        this.handleGlobalSearch();
        this.handleGlobalSearchShowChange(true);
      }
    }
  }
  /**
   * @description: 全局搜索
   * @param {*}
   * @return {*}
   */
  handleGlobalSearch() {
    this.globalSearchShow = !this.globalSearchShow;
    /** 展示在顶部导航栏的时候的自动聚焦 */
    setTimeout(() => (this.$refs.homeSelectModal as any)?.handleInputFocus(), 10);
  }
  /**
   * @description: 帮助列表
   * @param {*}
   * @return {*}
   */
  handleHelp(item) {
    this.hidePopoverSetOrHelp();
    switch (item.id) {
      case 'DOCS':
        this.handleGotoLink('homeLink');
        break;
      case 'FAQ':
        item.href && window.open(item.href);
        break;
      case 'VERSION':
        this.logShow = true;
        break;
    }
  }
  /**
   * @description: 全局设置
   * @param {IMenuItem} item
   * @return {*}
   */
  handleSet(item: IMenuItem) {
    setLocalStoreRoute(item.id);
    this.hidePopoverSetOrHelp();
    this.activeSetting = item.id;
    this.settingTitle = item.name;
    this.handleSettingShowChange(true);
  }
  /* 隐藏弹出层 */
  hidePopoverSetOrHelp() {
    (this.$refs.popoverset as any)?.hideHandler();
    (this.$refs.popoverhelp as any)?.hideHandler();
    (this.$refs.popoverlanguage as any)?.hideHandler();
    (this.$refs.popoveruser as any)?.hideHandler();
  }
  /**
   * @description: 设置显示
   * @param {boolean} v
   * @return {*}
   */
  handleSettingShowChange(v: boolean) {
    this.$emit('change', v);
    !v && bus.$emit(HANDLE_HIDDEN_SETTING, this.activeSetting);
  }
  /* 切换语言 */
  async handleLanguageChange(item: IMenuItem) {
    if (item.id === docCookies.getItem(LANGUAGE_COOKIE_KEY)) {
      return;
    }
    docCookies.removeItem(LANGUAGE_COOKIE_KEY);
    docCookies.setItem(
      LANGUAGE_COOKIE_KEY,
      item.id,
      undefined,
      '/',
      `${window.bk_domain && location.hostname.includes(window.bk_domain) ? window.bk_domain : location.hostname}`
    );
    if (window.bk_component_api_url) {
      useJSONP(
        `${window.bk_component_api_url
          .replace(/\/$/, '')
          .replace(/^http:/, location.protocol)}/api/c/compapi/v2/usermanage/fe_update_user_language`,
        {
          data: {
            language: item.id,
          },
        }
      ).finally(() => {
        location.reload();
      });
      return;
    }
    location.reload();
  }
  handleMenuChange(item: IMenuItem) {
    this.activeSetting = item.id;
    this.settingTitle = item.name;
  }
  createAsyncComponent() {
    if (this.activeSetting === 'global-config') {
      return <global-config />;
    }
    if (this.activeSetting === 'migrate-dashboard') {
      return <migrate-dashboard class='migrate-dashboard' />;
    }
    if (this.activeSetting === 'calendar') {
      return <global-calendar />;
    }
    if (this.activeSetting === 'space-manage') {
      return <space-manage />;
    }
    if (this.activeSetting === 'resource-register') {
      return <resource-register />;
    }
    if (this.activeSetting === 'data-pipeline') {
      return <data-pipeline />;
    }
    return <health-z />;
  }
  /**
   * @description: 全局搜索显示
   * @param {boolean} v
   * @return {*}
   */
  handleGlobalSearchShowChange(v: boolean, searchKey?: string) {
    this.globalSearchShow = v;
    // 关闭弹窗时若存在已输入但未搜索的关键字
    if (searchKey?.length) {
      this.globalSearchPlaceholder = searchKey;
    } else {
      this.globalSearchPlaceholder = this.defaultSearchPlaceholder;
    }
  }
  /**
   * 退出登录
   * 跳转到paas-host登录页面会自动清除登录cookie
   */
  handleQuit() {
    location.href = `${location.origin}/logout`;
  }
  render() {
    return (
      <div class='nav-tools'>
        {
          // #if APP !== 'external'
          /** 新版首页无需展示右侧的全站搜索框 */
          !this.isHomePage && (
            <div
              id='nav-search-bar'
              class='search-bar'
              onClick={this.handleGlobalSearch}
            >
              <span class='search-text'>{this.globalSearchPlaceholder}</span>
              {/* <span class='bk-icon icon-search' /> */}
              <span class='search-bar-keyword'>
                {this.$t('快捷键')} {getCmdShortcutKey()} + /
              </span>
            </div>
          )
          // #endif
        }
        {
          // #if APP !== 'external'
          <bk-popover
            ref='popoverset'
            tippy-options={{
              trigger: 'click',
            }}
            arrow={false}
            offset='-10, 4'
            placement='bottom-start'
            theme='light common-monitor'
          >
            <div class='header-help'>
              <span class='help-icon icon-monitor icon-menu-setting' />
            </div>
            <template slot='content'>
              <ul class='monitor-navigation-help'>
                {this.setList.map((item, index) => (
                  <li
                    key={index}
                    class='nav-item'
                    onClick={() => this.handleSet(item)}
                  >
                    {this.$t(item.name)}
                  </li>
                ))}
              </ul>
            </template>
          </bk-popover>
          // #endif
        }
        <bk-popover
          ref='popoverlanguage'
          tippy-options={{
            trigger: 'click',
          }}
          arrow={false}
          offset='-10, 4'
          placement='bottom-start'
          theme='light common-monitor'
        >
          <div class='header-language'>
            {this.$store.getters.lang === 'en' ? (
              <img
                class='language-icon'
                alt='english'
                src={enIcon}
              />
            ) : (
              <img
                class='language-icon'
                alt='中文'
                src={zhIcon}
              />
            )}
          </div>
          <template slot='content'>
            <ul class='monitor-navigation-help'>
              {this.languageList.map((item, index) => (
                <li
                  key={index}
                  class={`nav-item ${item.id === this.$store.getters.lang ? 'nav-item-active' : ''}`}
                  onClick={() => this.handleLanguageChange(item)}
                >
                  <span class={`bk-icon ${item.id === 'en' ? 'icon-english' : 'icon-chinese'} language-icon`} />
                  {item.name}
                </li>
              ))}
            </ul>
          </template>
        </bk-popover>
        {
          // #if APP !== 'external'
          <bk-popover
            ref='popoverhelp'
            tippy-options={{
              trigger: 'click',
            }}
            arrow={false}
            offset='-10, 4'
            placement='bottom-start'
            theme='light common-monitor'
          >
            <div class='header-help'>
              <svg
                style='width: 1em; height: 1em;vertical-align: middle;fill: currentColor;overflow: hidden;'
                class='bk-icon'
                version='1.1'
                viewBox='0 0 64 64'
                xmlns='http://www.w3.org/2000/svg'
              >
                <path d='M32,4C16.5,4,4,16.5,4,32c0,3.6,0.7,7.1,2,10.4V56c0,1.1,0.9,2,2,2h13.6C36,63.7,52.3,56.8,58,42.4S56.8,11.7,42.4,6C39.1,4.7,35.6,4,32,4z M31.3,45.1c-1.7,0-3-1.3-3-3s1.3-3,3-3c1.7,0,3,1.3,3,3S33,45.1,31.3,45.1z M36.7,31.7c-2.3,1.3-3,2.2-3,3.9v0.9H29v-1c-0.2-2.8,0.7-4.4,3.2-5.8c2.3-1.4,3-2.2,3-3.8s-1.3-2.8-3.3-2.8c-1.8-0.1-3.3,1.2-3.5,3c0,0.1,0,0.1,0,0.2h-4.8c0.1-4.4,3.1-7.4,8.5-7.4c5,0,8.3,2.8,8.3,6.9C40.5,28.4,39.2,30.3,36.7,31.7z' />
              </svg>
            </div>
            <template slot='content'>
              <ul class='monitor-navigation-help'>
                {this.helpList.map((item, index) => (
                  <li
                    key={index}
                    class='nav-item'
                    onClick={() => this.handleHelp(item)}
                  >
                    {item.name}
                  </li>
                ))}
              </ul>
            </template>
          </bk-popover>
          // #endif
        }
        <div
          class={{
            'header-user is-left': true,
            'is-external': process.env.APP === 'external',
          }}
        >
          <bk-popover
            ref='popoveruser'
            tippy-options={{
              trigger: 'click',
            }}
            arrow={false}
            disabled={process.env.APP === 'external'}
            offset='0, 4'
            placement='bottom'
            theme='light common-monitor'
          >
            <bk-user-display-name
              class='header-user-text'
              user-id={window.user_name || window.username}
            />
            <i class='bk-icon icon-down-shape' />
            <div slot='content'>
              {process.env.APP !== 'external' && (
                <ul class='monitor-navigation-help'>
                  {/* <li
                    class='nav-item'
                    onClick={() => {
                      this.isShowMyReportModal = false;
                      this.isShowMyApplyModal = true;
                      this.$nextTick(() => {
                        (this.$refs.popoveruser as any)?.hideHandler?.();
                      });
                    }}
                  >
                    {this.$t('我申请的')}
                  </li>
                  <li
                    class='nav-item'
                    onClick={() => {
                      this.isShowMyApplyModal = false;
                      this.isShowMyReportModal = true;
                      this.$nextTick(() => {
                        (this.$refs.popoveruser as any)?.hideHandler?.();
                      });
                    }}
                  >
                    {this.$t('我的订阅')}
                  </li> */}
                  <li
                    class='nav-item'
                    onClick={this.handleQuit}
                  >
                    {this.$t('退出登录')}
                  </li>
                </ul>
              )}
            </div>
          </bk-popover>
        </div>
        <LogVersion
          dialogShow={this.logShow}
          on={{ 'update:dialogShow': v => (this.logShow = v) }}
        />
        {
          // #if APP !== 'external'
          [
            <SettingModal
              key='setting-modal'
              activeMenu={this.activeSetting}
              menuList={this.setList}
              show={this.show}
              title={this.settingTitle}
              zIndex={2000}
              onChange={this.handleSettingShowChange}
              onMenuChange={this.handleMenuChange}
            >
              {this.show && this.createAsyncComponent()}
            </SettingModal>,
            <keep-alive key='keep-alive'>
              {this.globalSearchShow && (
                <HomeSelect
                  ref='homeSelectModal'
                  isBarToolShow={true}
                  show={this.globalSearchShow}
                  onChange={this.handleGlobalSearchShowChange}
                />
                // <GlobalSearchModal
                //   ref='globalSearchModal'
                //   show={this.globalSearchShow}
                //   onChange={this.handleGlobalSearchShowChange}
                // />
              )}
            </keep-alive>,
          ]
          // #endif
        }

        {this.isShowMyApplyModal && (
          <SettingModal
            show={this.isShowMyApplyModal}
            title={this.$t('我申请的').toString()}
            zIndex={2000}
            onChange={v => {
              this.isShowMyApplyModal = v;
            }}
          >
            <my-apply />
          </SettingModal>
        )}

        {this.isShowMyReportModal && (
          <SettingModal
            show={this.isShowMyReportModal}
            title={this.$t('我的订阅').toString()}
            zIndex={2000}
            onChange={v => {
              this.isShowMyReportModal = v;
            }}
          >
            <my-subscription />
          </SettingModal>
        )}
      </div>
    );
  }
}
export default ofType<INavToolsProps, INavToolsEvents>().convert(NavTools);
