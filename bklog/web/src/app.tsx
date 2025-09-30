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
import { computed, defineComponent, onMounted, type Ref, ref } from 'vue';

import(/* webpackChunkName: 'appload-import' */ './common/appload-import');
import(/* webpackChunkName: 'demand-import' */ './common/demand-import');

import AuthDialog from '@/components/common/auth-dialog.vue';
import GlobalSettingDialog from '@/components/global-setting/index';
import HeadNav from '@/components/nav/head-nav.vue';
import NoticeComponent from '@blueking/notice-component-vue2';
import { bkNavigation, bkNavigationMenu, bkNavigationMenuItem, bkNavigationMenuGroup } from 'bk-magic-vue';
import jsCookie from 'js-cookie';
import { useRoute } from 'vue-router/composables';

import useLocale from './hooks/use-locale';
import useStore from './hooks/use-store';

import './app.scss';
import '@blueking/notice-component-vue2/dist/style.css';

export default defineComponent({
  components: {
    bkNavigation,
    bkNavigationMenu,
    bkNavigationMenuItem,
    bkNavigationMenuGroup,
  },
  setup() {
    const route = useRoute();
    const store = useStore();
    const { $t } = useLocale();

    const noticeComponentHeight = ref(0);
    const refNoticeComponent: Ref<any | null> = ref(null);
    const welcomePageData = ref(null);

    const rootClass = computed(() => ({ 'clear-min-height': route.name === 'retrieve' }));

    const noticeComponentStyle = computed(() => ({
      '--notice-component-height': `${noticeComponentHeight.value}px`,
    }));

    const isAsIframe = computed(() => route.query.from === 'monitor');
    const showAlert = computed(() => store.state.showAlert);

    const isShowGlobalDialog = computed(() => store.state.isShowGlobalDialog);
    const globalActiveLabel = computed(() => store.state.globalActiveLabel);
    const globalSettingList = computed(() => store.state.globalSettingList);

    const appBodyClassName = computed(() => [
      'log-search-container',
      isAsIframe.value && 'as-iframe',
      { 'is-show-notice': showAlert.value },
    ]);

    /** 初始化脱敏灰度相关的数据 */
    const initMaskingToggle = () => {
      const { log_desensitize: logDesensitize } = window.FEATURE_TOGGLE;
      let toggleList = window.FEATURE_TOGGLE_WHITE_LIST?.log_desensitize || [];
      switch (logDesensitize) {
        case 'on':
          toggleList = [];
          break;
        case 'off': {
          toggleList = [];
          store.commit('updateState', {'globalSettingList' : []});
          break;
        }
        default:
          break;
      }
      store.commit('updateState', {'maskingToggle': {
        toggleString: logDesensitize,
        toggleList,
      }});

      // 更新全局操作列表
      const isShowSettingList = logDesensitize !== 'off';
      store.commit(
        'updateState', {
          'globalSettingList': isShowSettingList ? [{ id: 'masking-setting', name: $t('全局脱敏') }] : []
        }
      );
    };

    /**
     * 公告状态变化
     * @param v
     */
    const showAlertChange = (v: boolean) => {
      store.commit('updateState', {'showAlert': v});

      if (refNoticeComponent.value) {
        noticeComponentHeight.value = refNoticeComponent.value.$el.offsetHeight;
      }
    };

    /**
     * 渲染公告组件
     */
    const renderNoticeComponent = () => {
      if (!isAsIframe.value) {
        return (
          <NoticeComponent
            ref='refNoticeComponent'
            api-url='/notice/announcements/'
            on-show-alert-change={showAlertChange}
          />
        );
      }
    };

    /**
     * 处理欢迎页数据
     * @param args
     */
    const handleWelcome = (args: any) => {
      welcomePageData.value = args;
    };

    /**
     * 渲染头部组件
     */
    const renderHeadComponent = () => {
      if (!isAsIframe.value && route.path !== '/') {
        return (
          <HeadNav
            welcome-data={welcomePageData.value}
            on-welcome={handleWelcome}
          />
        );
      }
    };

    /**
     * 获取欢迎页
     */
    const getWelcomePage = () => {
      if (welcomePageData.value) {
        return <welcome-page data={welcomePageData.value} />;
      }

      return null;
    };

    /**
     * 渲染路由视图
     */
    const renderRouterView = () => {
      return <router-view class='manage-content' />;
    };

    /**
     * 渲染授权弹窗
     * @returns
     */
    const renderAuthDialog = () => {
      return <AuthDialog />;
    };

    /**
     * 更新全局弹窗的选项
     */
    const handleChangeMenu = (item: any) => {
      store.commit('updateState', {'globalActiveLabel': item.id});
    };

    /**
     * 渲染全局设置弹窗
     */
    const renderGlobalSettingDialog = () => {
      return (
        <GlobalSettingDialog
          active-menu={globalActiveLabel.value}
          menu-list={globalSettingList.value}
          value={isShowGlobalDialog.value}
          on-menu-change={handleChangeMenu}
        />
      );
    };

    /**
     * 渲染应用主体
     */
    const renderAppBody = () => {
      return (
        <div class={appBodyClassName.value}>
          {getWelcomePage()}
          {renderRouterView()}
          {renderAuthDialog()}
          {renderGlobalSettingDialog()}
        </div>
      );
    };

    onMounted(() => {
      const platform = window.navigator.platform.toLowerCase();
      const fontFamily =
        platform.indexOf('win') === 0
          ? 'Microsoft Yahei, pingFang-SC-Regular, Helvetica, Aria, sans-serif'
          : 'pingFang-SC-Regular, Microsoft Yahei, Helvetica, Aria, sans-serif';
      document.body.style['font-family'] = fontFamily;
      store.commit('updateState', {'runVersion': window.RUN_VER || ''});

      const isEnLanguage = (jsCookie.get('blueking_language') || 'zh-cn') === 'en';
      store.commit('updateState', {'isEnLanguage': isEnLanguage});
      const languageClassName = isEnLanguage ? 'language-en' : 'language-zh';
      document.body.classList.add(languageClassName);
      // 初始化脱敏灰度相关的代码
      initMaskingToggle();
      store.state.isExternal = window.IS_EXTERNAL ? JSON.parse(`${window.IS_EXTERNAL}`) : false;
    });

    return () => (
      <div
        id='app'
        style={noticeComponentStyle.value}
        class={rootClass.value}
      >
        {renderNoticeComponent()}
        {renderHeadComponent()}
        {renderAppBody()}
      </div>
    );
  },
});
