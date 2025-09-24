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

// 顶部导航（TSX重构版）：复用 use-nav-menu 的业务与路由逻辑，保持与 head-nav.vue 一致的交互与样式
import { computed, defineComponent, onBeforeUnmount, onMounted, reactive, ref } from 'vue';

import { useJSONP } from '@/common/jsonp';
// 全局弹窗（受控组件：value/onChange），用于“我申请的 / 我的订阅”内嵌页面
import GlobalDialog from '@/components/global-dialog';
import BizMenuSelect from '@/global/bk-space-choice/index';
// 统一的导航/空间切换逻辑，避免重复代码
import { useNavMenu } from '@/hooks/use-nav-menu';
import useRouter from '@/hooks/use-router';
import useStore from '@/hooks/use-store';
import logoImg from '@/images/log-logo.png';
import platformConfigStore from '@/store/modules/platform-config';
import { bkDropdownMenu } from 'bk-magic-vue';
import jsCookie from 'js-cookie';
import { useRoute } from 'vue-router/composables';

import { MENU_LISTS } from './complete-menu';
import LogVersion from './log-version';

import './index.scss';

export default defineComponent({
  name: 'HeaderNavTsx',
  components: { BizMenuSelect, GlobalDialog, LogVersion, bkDropdownMenu },
  props: {
    welcomeData: {
      type: Object as () => Record<string, any> | null,
      default: null,
    },
  },
  setup(props, { emit }) {
    const store = useStore();
    const router = useRouter();
    const route = useRoute();

    // 初始化菜单配置（使用与 .vue 版一致的静态菜单）
    onMounted(() => {
      store.commit('updateState', { menuList: MENU_LISTS });
    });

    const activeTopMenu = computed(() => {
      const matchedList = route.matched;
      const menuList = store.state.menuList;
      return (
        menuList.find(item => {
          return matchedList.some(record => record.name === item.id);
        }) || {}
      );
    });

    // i18n 函数：优先使用全局 $t，兜底返回原文
    const t = (msg: string) => ((window as any).$t ? (window as any).$t(msg) : msg);

    // 复用组合式导航逻辑（含空间切换、菜单高亮、外部版菜单计算等）
    const navMenu = useNavMenu({
      t,
      bkInfo: (window as any).$bkInfo,
      http: (window as any).$http,
      emit: (event: string, ...args: any[]) => emit(event, ...args),
    });

    // 组件本地状态：仅保存视图 UI 状态，业务状态统一走 store
    const state = reactive({
      isFirstLoad: true,
      username: '',
      usernameRequested: false,
      isShowLanguageDropdown: false,
      isShowGlobalDropdown: false,
      isShowHelpDropdown: false,
      isShowLogoutDropdown: false,
      showLogVersion: false,
      language: 'zh-cn',
      showGlobalDialog: false,
      globalDialogTitle: '',
      targetSrc: '',
    });

    // 初始化用户信息与 bus 事件
    onMounted(() => {
      state.language = jsCookie.get('blueking_language') || 'zh-cn';
      getUserInfo();
      (window as any).bus?.$on('showGlobalDialog', handleGoToMyReport);
    });

    onBeforeUnmount(() => {
      (window as any).bus?.$off('showGlobalDialog', handleGoToMyReport);
    });

    const globalsData = computed(() => store.getters['globals/globalsData']);
    const isExternal = computed(() => store.state.isExternal);

    // 平台展示信息（名称 / logo），支持动态配置
    const platformData = computed(() => {
      const { appLogo, i18n } = platformConfigStore.publicConfig;
      const bkRepoUrl = (window as any).BK_SHARED_RES_URL;
      const publicConfigName = i18n?.name ?? t('日志平台');
      return {
        name: bkRepoUrl ? publicConfigName : t('日志平台'),
        logo: appLogo || (logoImg as any),
      };
    });

    // 语言切换所需配置
    const envConfig = computed(() => {
      const { paas_api_host: host, bk_domain: bkDomain } = globalsData.value || {};
      return { host, bkDomain };
    });

    /**
     * 获取用户信息并注入埋点 UID
     */
    async function getUserInfo() {
      try {
        const res = store.state.userMeta;
        state.username = res?.username || '';
        if ((window as any).__aegisInstance && state.username) {
          (window as any).__aegisInstance.setConfig({ uin: state.username });
        }
      } catch (e) {
        console.warn(e);
      } finally {
        state.usernameRequested = true;
      }
    }

    /**
     * 点击 Logo 返回首页（外部版跳“管理”）
     */
    function jumpToHome() {
      store.commit('updateState', { isShowGlobalDialog: false });
      if ((window as any).IS_EXTERNAL) {
        router.push({
          name: 'manage',
          query: {
            spaceUid: store.state.spaceUid,
            bizId: store.state.bizId,
          },
        });
        return;
      }
      router.push({ name: 'retrieve', query: { spaceUid: store.state.spaceUid } });
      setTimeout(() => emit('reload-router'));
    }

    /**
     * 顶部菜单点击：使用策略映射处理相同菜单二次点击与普通跳转
     */
    function routerHandler(menu: any) {
      store.commit('updateState', { isShowGlobalDialog: false });

      const currentRoute = (router as any).currentRoute.value;
      const spaceUidQuery = { spaceUid: store.state.spaceUid };

      // 相同菜单再次点击时的处理策略
      const sameMenuHandlers: Record<string, () => void> = {
        retrieve: () => {
          router.push({ name: 'retrieve', query: spaceUidQuery });
          emit('reload-router');
        },
        extract: () => {
          if (currentRoute.query.create) {
            router.push({ name: 'extract', query: spaceUidQuery });
          } else {
            emit('reload-router');
          }
        },
        trace: () => {
          if (currentRoute.name === 'trace-detail') {
            router.push({ name: 'trace-list', query: spaceUidQuery });
          } else {
            emit('reload-router');
          }
        },
        dashboard: () => {
          router.push({ name: 'dashboard', query: spaceUidQuery });
          emit('reload-router');
        },
        manage: () => {
          if (currentRoute.name !== 'collection-item') {
            router.push({ name: 'manage', query: spaceUidQuery });
          } else {
            emit('reload-router');
          }
        },
        default: () => emit('reload-router'),
      };

      // 不同菜单跳转时的处理策略
      const navigateHandlers: Record<string, () => void> = {
        monitor: () => {
          const url = `${(window as any).MONITOR_URL}/?bizId=${store.state.bkBizId}#/strategy-config`;
          window.open(url, '_blank');
        },
        trace: () => {
          router.push({ name: 'trace-list', query: spaceUidQuery });
        },
        default: () => {
          router.push({ name: menu.id, query: spaceUidQuery });
        },
      };

      const isSameMenu = menu.id === activeTopMenu.value?.id;
      if (isSameMenu) {
        (sameMenuHandlers[menu.id] || sameMenuHandlers.default)();
        return;
      }
      (navigateHandlers[menu.id] || navigateHandlers.default)();
    }

    /**
     * 获取语言图标 class
     */
    function getLanguageClass(language: string) {
      return language === 'en' ? 'bk-icon icon-english' : 'bk-icon icon-chinese';
    }

    /**
     * 切换语言（兼容跨域：通过 JSONP 调前端网关 API）
     */
    function changeLanguage(value: string) {
      jsCookie.remove('blueking_language', { path: '' });
      jsCookie.set('blueking_language', value, {
        expires: 3600,
        domain:
          envConfig.value.bkDomain || location.host.split('.').slice(-2).join('.').replace(`:${location.port}`, ''),
      });
      if (envConfig.value.host) {
        try {
          useJSONP(
            `${envConfig.value.host.replace(/\/$/, '').replace(/^http:/, location.protocol)}/api/c/compapi/v2/usermanage/fe_update_user_language`,
            { data: { language: value } },
          );
        } catch (error) {
          console.warn(error);
          location.reload();
        } finally {
          location.reload();
        }
        return;
      }
      location.reload();
    }

    /**
     * 帮助下拉触发（版本日志 / 文档中心 / 反馈）
     */
    function dropdownHelpTriggerHandler(type: 'docCenter' | 'feedback' | 'logVersion') {
      (dropdownHelpRef.value as any)?.hide?.();
      if (type === 'logVersion') {
        state.showLogVersion = true;
      } else if (type === 'docCenter') {
        handleGotoLink('docCenter');
      } else if (type === 'feedback') {
        window.open((window as any).BK_FAQ_URL);
      }
    }

    /**
     * 外链跳转
     */
    function handleGotoLink(type: 'docCenter') {
      if (type === 'docCenter') {
        const url = (window as any).BK_DOC_URL;
        url && window.open(url);
      }
    }

    /**
     * 打开“我申请的”弹窗（通过 GlobalDialog 受控显示）
     */
    function handleGoToMyApplication() {
      state.showGlobalDialog = false;
      const bizId = store.state.bkBizId;
      const host =
        process.env.NODE_ENV === 'development'
          ? `http://${(process as any).env.devHost}:7001`
          : (window as any).MONITOR_URL;
      const targetSrc = `${host}/?bizId=${bizId}&needMenu=false#/trace/report/my-applied-report`;
      state.globalDialogTitle = t('我申请的');
      state.showGlobalDialog = true;
      state.targetSrc = targetSrc;
    }

    /**
     * 打开“我的订阅”弹窗
     */
    function handleGoToMyReport() {
      state.showGlobalDialog = false;
      const bizId = store.state.bkBizId;
      const host =
        process.env.NODE_ENV === 'development'
          ? `http://${(process as any).env.devHost}:7001`
          : (window as any).MONITOR_URL;
      const targetSrc = `${host}/?bizId=${bizId}&needMenu=false#/trace/report/my-report`;
      state.globalDialogTitle = t('我的订阅');
      state.showGlobalDialog = true;
      state.targetSrc = targetSrc;
    }

    /**
     * 退出登录
     */
    function handleQuit() {
      location.href = `${(window as any).BK_PLAT_HOST}/console/accounts/logout/`;
    }

    /**
     * 打开全局设置弹窗
     */
    function handleClickGlobalDialog(id: string) {
      store.commit('updateState', { globalActiveLabel: id });
      store.commit('updateState', { isShowGlobalDialog: true });
    }

    const dropdownHelpRef = ref();

    // 计算可见菜单（外部版根据 externalMenu 限制）
    const menuList = computed(() => {
      const list =
        (navMenu.topMenu as any).value?.filter((menu: any) => {
          return menu.feature === 'on' && (isExternal.value ? store.state.externalMenu.includes(menu.id) : true);
        }) || [];
      if (process.env.NODE_ENV === 'development' && (process as any).env.MONITOR_APP === 'apm' && list.length) {
        return [...list, { id: 'monitor-apm-log', name: 'APM Log检索' }];
      }
      if (process.env.NODE_ENV === 'development' && (process as any).env.MONITOR_APP === 'trace' && list.length) {
        return [...list, { id: 'monitor-trace-log', name: 'Trace Log检索' }];
      }
      return list;
    });

    // 是否展示全局设置入口（欢迎页/外部版不展示）
    const isShowGlobalSetIcon = computed(() => !props.welcomeData && !isExternal.value);

    return () => (
      <nav class='log-search-nav'>
        <div class='nav-left fl'>
          <div
            class='log-logo-container'
            onClick={e => (e.stopPropagation(), jumpToHome())}
          >
            <img
              width='40px'
              height='40px'
              class='logo-image'
              alt='logo'
              src={platformData.value.logo}
            />
            <span class='logo-text'>{platformData.value.name}</span>
          </div>
          <div class='nav-separator'>|</div>
          <BizMenuSelect class='head-navi-left' />
        </div>

        <div
          class='nav-center fl'
          data-test-id='topNav_div_topNavBox'
        >
          <ul>
            {menuList.value.map((menu: any) => (
              <li
                id={`${menu.id}MenuGuide`}
                key={menu.id}
                class={['menu-item', { active: (activeTopMenu as any).value?.id === menu.id }]}
                data-test-id={`topNavBox_li_${menu.id}`}
                onClick={() => routerHandler(menu)}
              >
                {menu.name}
              </li>
            ))}
          </ul>
        </div>

        <div
          style={{ display: state.usernameRequested ? '' : 'none' }}
          class='nav-right fr'
        >
          {/* 全局设置 */}
          {isShowGlobalSetIcon.value ? (
            <bkDropdownMenu
              scopedSlots={{
                'dropdown-trigger': () => (
                  <div class='icon-language-container'>
                    <span
                      class={{
                        'setting bk-icon icon-cog-shape icon-language-container': true,
                        active: store.state.isShowGlobalDialog || state.isShowGlobalDropdown,
                      }}
                    ></span>
                  </div>
                ),
                'dropdown-content': () => (
                  <ul class='bk-dropdown-list'>
                    {(store.state.globalSettingList || []).map((item: any) => (
                      <li
                        key={item.id}
                        class='language-btn'
                      >
                        <a
                          href='javascript:;'
                          onClick={() => handleClickGlobalDialog(item.id)}
                        >
                          {item.name}
                        </a>
                      </li>
                    ))}
                  </ul>
                ),
              }}
              align='center'
              onHide={() => (state.isShowGlobalDropdown = false)}
              onShow={() => (state.isShowGlobalDropdown = true)}
            ></bkDropdownMenu>
          ) : null}

          {/* 语言 */}
          <bkDropdownMenu
            scopedSlots={{
              'dropdown-trigger': () => (
                <div class='icon-language-container'>
                  <div class='icon-circle-container'>
                    <div
                      class={[
                        'icon-language',
                        { active: state.isShowLanguageDropdown },
                        state.language === 'en' ? 'bk-icon icon-english' : 'bk-icon icon-chinese',
                      ]}
                    />
                  </div>
                </div>
              ),
              'dropdown-content': () => (
                <ul class='bk-dropdown-list'>
                  {[
                    { id: 'zh-cn', name: '中文' },
                    { id: 'en', name: 'English' },
                  ].map(item => (
                    <li
                      key={item.id}
                      class='language-btn'
                    >
                      <a
                        class={{ active: state.language === item.id }}
                        href='javascript:;'
                        onClick={() => changeLanguage(item.id)}
                      >
                        <span class={['icon-language', getLanguageClass(item.id)]} />
                        {item.name}
                      </a>
                    </li>
                  ))}
                </ul>
              ),
            }}
            align='center'
            onHide={() => (state.isShowLanguageDropdown = false)}
            onShow={() => (state.isShowLanguageDropdown = true)}
          ></bkDropdownMenu>

          {/* 帮助 */}
          <bkDropdownMenu
            ref={dropdownHelpRef as any}
            scopedSlots={{
              'dropdown-trigger': () => (
                <div class={['icon-language-container', state.isShowHelpDropdown && 'active']}>
                  <div class='icon-circle-container'>
                    <span class='icon bklog-icon bklog-help'></span>
                  </div>
                </div>
              ),
              'dropdown-content': () => (
                <ul class='bk-dropdown-list'>
                  <li>
                    <a
                      href='javascript:;'
                      onClick={e => (e.stopPropagation(), dropdownHelpTriggerHandler('docCenter'))}
                    >
                      {t('产品文档')}
                    </a>
                    {!isExternal.value ? (
                      <a
                        href='javascript:;'
                        onClick={e => (e.stopPropagation(), dropdownHelpTriggerHandler('logVersion'))}
                      >
                        {t('版本日志')}
                      </a>
                    ) : null}
                    <a
                      href='javascript:;'
                      onClick={e => (e.stopPropagation(), dropdownHelpTriggerHandler('feedback'))}
                    >
                      {t('问题反馈')}
                    </a>
                  </li>
                </ul>
              ),
            }}
            align='center'
            onHide={() => (state.isShowHelpDropdown = false)}
            onShow={() => (state.isShowHelpDropdown = true)}
          ></bkDropdownMenu>
          <LogVersion
            dialogShow={state.showLogVersion}
            {...{ on: { 'update:dialog-show': (v: boolean) => (state.showLogVersion = v) } }}
          />

          {/* 用户 */}
          <bkDropdownMenu
            scopedSlots={{
              'dropdown-trigger': () => (
                <div class={['icon-language-container', state.isShowLogoutDropdown && 'active']}>
                  {state.username ? (
                    <span class='username'>
                      {state.username}
                      <i class='bk-icon icon-down-shape'></i>
                    </span>
                  ) : null}
                </div>
              ),
              'dropdown-content': () => (
                <ul class='bk-dropdown-list'>
                  <li>
                    <a
                      href='javascript:;'
                      onClick={handleGoToMyApplication}
                    >
                      {t('我申请的')}
                    </a>
                  </li>
                  <li>
                    <a
                      href='javascript:;'
                      onClick={handleGoToMyReport}
                    >
                      {t('我的订阅')}
                    </a>
                  </li>
                  <li>
                    <a
                      href='javascript:;'
                      onClick={handleQuit}
                    >
                      {t('退出登录')}
                    </a>
                  </li>
                </ul>
              ),
            }}
            align='center'
            onHide={() => (state.isShowLogoutDropdown = false)}
            onShow={() => (state.isShowLogoutDropdown = true)}
          ></bkDropdownMenu>
        </div>

        <GlobalDialog
          title={state.globalDialogTitle}
          value={state.showGlobalDialog}
          onChange={(v: boolean) => (state.showGlobalDialog = v)}
        >
          <iframe
            style='width: 100%; height: 100%; border: none'
            src={state.targetSrc}
          ></iframe>
        </GlobalDialog>
      </nav>
    );
  },
});
