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

import { useJSONP } from '../../monitor-api/jsonp';
import { LANGUAGE_COOKIE_KEY } from '../../monitor-common/utils/constant';
import bus from '../../monitor-common/utils/event-bus';
import { docCookies } from '../../monitor-common/utils/utils';
import LogVersion from '../components/log-version/intex';
import LogVersionMixin from '../components/log-version/log-version-mixin';
import DocumentLinkMixin from '../mixins/documentLinkMixin';
import { GLOAB_FEATURE_LIST, setLocalStoreRoute } from '../router/router-config';
import enIcon from '../static/images/svg/en.svg';
import zhIcon from '../static/images/svg/zh.svg';
import { IMenuItem } from '../types';

// #if APP !== 'external'
import GlobalSearchModal from './global-search-modal-new';
import SettingModal from './setting-modal';

// #endif
import './nav-tools.scss';

export const HANDLE_SHOW_SETTING = 'HANDLE_SHOW_SETTING';
export const HANDLE_HIDDEN_SETTING = 'HANDLE_HIDDEN_SETTING';
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
    HealthZ: () => import(/* webpackChunkName: "healthz" */ '../pages/healthz/healthz.vue') as any,
    MigrateDashboard: () =>
      import(/* webpackChunkName: 'MigrateDashboard' */ '../pages/migrate-dashboard/migrate-dashboard.vue') as any,
    ResourceRegister: () =>
      import(/* webpackChunkName: 'ResourceRegister' */ '../pages/resource-register/resource-register') as any,
    DataPipeline: () => import(/* webpackChunkName: 'DataPipeline' */ '../pages/data-pipeline/data-pipeline') as any,
    SpaceManage: () => import(/* webpackChunkName: 'SpaceManage' */ './space-manage/space-manage') as any,
    GlobalCalendar: () => import(/* webpackChunkName: 'calendar' */ './calendar/calendar') as any
  }
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
  defauleSearchPlaceholder = `${this.$t('全站搜索')} Ctrl + k`;
  globalSearchPlaceholder = this.defauleSearchPlaceholder;

  // 全局弹窗在路由变化时需要退出
  @Watch('$route.name')
  async handler() {
    this.$emit('change', false);
    this.globalSearchShow = false;
  }

  created() {
    this.helpList = [
      {
        id: 'DOCS',
        name: this.$t('产品文档').toString(),
        href: ''
      },
      {
        id: 'VERSION',
        name: this.$t('版本日志').toString()
      },
      {
        id: 'FAQ',
        name: this.$t('问题反馈').toString(),
        href: window.ce_url
      }
    ];
    this.setList = GLOAB_FEATURE_LIST.map(({ name, ...args }) => ({
      name: `route-${name}`,
      ...args
    }));
    this.languageList = [
      {
        id: 'zh-cn',
        name: '中文'
      },
      {
        id: 'en',
        name: 'English'
      }
    ];
  }
  mounted() {
    document.addEventListener('keydown', this.handleKeyupSearch);
    bus.$on(HANDLE_SHOW_SETTING, this.handleShowSetting);
    bus.$on('handle-keyup-search', this.handleKeyupSearch);
    window.addEventListener('blur', this.hidePopoverSetOrHelp);
  }
  beforeDestroy() {
    document.removeEventListener('keydown', this.handleKeyupSearch);
    bus.$off('handle-keyup-search', this.handleKeyupSearch);
    window.removeEventListener('blur', this.hidePopoverSetOrHelp);
  }

  handleShowSetting(key: string) {
    const item = this.setList.find(item => item.id === key);
    if (!!item) {
      this.handleSet(item);
    }
  }
  /**
   * @description: ctrl+k 打开全站搜索弹窗
   * @param { * } event
   */
  handleKeyupSearch(event) {
    if (this.globalSearchShow) return;
    if (event.ctrlKey && event.keyCode === 75) {
      event.preventDefault();
      this.handleGlobalSearchShowChange(true);
    }
  }
  /**
   * @description: 全局搜索
   * @param {*}
   * @return {*}
   */
  handleGlobalSearch() {
    this.globalSearchShow = !this.globalSearchShow;
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
      `${window.bk_domain || location.host.split('.').slice(-2).join('.').replace(`:${location.port}`, '')}`
    );
    if (window.bk_component_api_url) {
      useJSONP(
        `${window.bk_component_api_url}/api/c/compapi/v2/usermanage/fe_update_user_language`.replace(/\/\//, '/'),
        {
          data: {
            language: item.id
          }
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
      return <global-calendar></global-calendar>;
    }
    if (this.activeSetting === 'space-manage') {
      return <space-manage></space-manage>;
    }
    if (this.activeSetting === 'resource-register') {
      return <resource-register></resource-register>;
    }
    if (this.activeSetting === 'data-pipeline') {
      return <data-pipeline></data-pipeline>;
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
    if (searchKey.length) {
      this.globalSearchPlaceholder = searchKey;
    } else {
      this.globalSearchPlaceholder = this.defauleSearchPlaceholder;
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
          <div
            id='nav-search-bar'
            class='search-bar'
            onClick={this.handleGlobalSearch}
          >
            <span class='search-text'>{this.globalSearchPlaceholder}</span>
            <span class='bk-icon icon-search'></span>
          </div>
          // #endif
        }
        {
          // #if APP !== 'external'
          <bk-popover
            ref='popoverset'
            theme='light common-monitor'
            arrow={false}
            offset='-10, 4'
            placement='bottom-start'
            tippy-options={{
              trigger: 'click'
            }}
          >
            <div class='header-help'>
              <span class='help-icon icon-monitor icon-menu-setting'></span>
            </div>
            <template slot='content'>
              <ul class='monitor-navigation-help'>
                {this.setList.map((item, index) => (
                  <li
                    class='nav-item'
                    key={index}
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
          theme='light common-monitor'
          arrow={false}
          offset='-10, 4'
          placement='bottom-start'
          tippy-options={{
            trigger: 'click'
          }}
        >
          <div class='header-language'>
            {this.$store.getters.lang === 'en' ? (
              <img
                class='language-icon'
                alt='english'
                src={enIcon}
              ></img>
            ) : (
              <img
                class='language-icon'
                src={zhIcon}
                alt='中文'
              ></img>
            )}
          </div>
          <template slot='content'>
            <ul class='monitor-navigation-help'>
              {this.languageList.map((item, index) => (
                <li
                  class='nav-item'
                  key={index}
                  onClick={() => this.handleLanguageChange(item)}
                >
                  <img
                    class='language-icon'
                    src={item.id === 'en' ? enIcon : zhIcon}
                    alt='language'
                  ></img>
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
            theme='light common-monitor'
            arrow={false}
            offset='-10, 4'
            placement='bottom-start'
            tippy-options={{
              trigger: 'click'
            }}
          >
            <div class='header-help'>
              <span class='help-icon icon-monitor icon-mc-help-fill'></span>
            </div>
            <template slot='content'>
              <ul class='monitor-navigation-help'>
                {this.helpList.map((item, index) => (
                  <li
                    class='nav-item'
                    key={index}
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
            'is-external': process.env.APP === 'external'
          }}
        >
          <bk-popover
            ref='popoveruser'
            theme='light common-monitor'
            arrow={false}
            offset='0, 4'
            placement='bottom'
            disabled={process.env.APP === 'external'}
            tippy-options={{
              trigger: 'click'
            }}
          >
            <span class='header-user-text'>{window.user_name || window.username}</span>
            <i class='bk-icon icon-down-shape'></i>
            <div slot='content'>
              {process.env.APP !== 'external' && (
                <ul class='monitor-navigation-help'>
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
        ></LogVersion>
        {
          // #if APP !== 'external'
          [
            <SettingModal
              title={this.settingTitle}
              show={this.show}
              menuList={this.setList}
              activeMenu={this.activeSetting}
              zIndex={2000}
              onChange={this.handleSettingShowChange}
              onMenuChange={this.handleMenuChange}
            >
              {this.show && this.createAsyncComponent()}
            </SettingModal>,
            <keep-alive>
              {this.globalSearchShow && (
                <GlobalSearchModal
                  ref='globalSearchModal'
                  show={this.globalSearchShow}
                  onChange={this.handleGlobalSearchShowChange}
                ></GlobalSearchModal>
              )}
            </keep-alive>
          ]
          // #endif
        }
      </div>
    );
  }
}
export default ofType<INavToolsProps, INavToolsEvents>().convert(NavTools);
