/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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
import { computed, defineComponent, onMounted, ref } from 'vue';
import { RouterView, useRoute, useRouter } from 'vue-router';
import { ConfigProvider, Navigation } from 'bkui-vue';
import { en, zhCn } from 'bkui-vue/lib/locale';
import { getLinkMapping } from 'monitor-api/modules/commons';
import { LANGUAGE_COOKIE_KEY } from 'monitor-common/utils';
import { docCookies, getUrlParam } from 'monitor-common/utils/utils';

import AuthorityModal from '../components/authority-modal/authority-modal';
import { createRouteConfig } from '../router/router-config';
import { useAppStore } from '../store/modules/app';

import { useAppReadonlyProvider } from './provider';

import './app.scss';

export default defineComponent({
  setup() {
    const routeList = createRouteConfig();
    const router = useRouter();
    const store = useAppStore();
    const route = useRoute();
    const bizId = computed(() => store.bizId);
    const needMenu = ref(!window.__POWERED_BY_BK_WEWEB__);
    useAppReadonlyProvider(!!window.__BK_WEWEB_DATA__?.readonly || !!getUrlParam('readonly'));
    /** 国际化语言设置 */
    const locale = computed(() => {
      const currentLang = docCookies.getItem(LANGUAGE_COOKIE_KEY);
      return {
        lang: currentLang === 'en' ? 'enUS' : 'zhCN',
        ...(currentLang === 'en' ? en : zhCn)
      };
    });
    const navActive = computed(() => {
      let routeId = bizId.value || 'home';
      const {
        options: { routes }
      } = router;
      const parentId = (routes.find(item => routeId === item.name)?.meta?.route as any)?.parent;
      routeId = parentId || routeId;
      return routeList.find(
        item =>
          item.route === routeId ||
          item.id === routeId ||
          item?.children?.some(child => child.children.some((set: { id: string | number }) => set.id === routeId))
      )?.id;
    });
    onMounted(() => {
      getDocsLinkMapping();
    });
    /** 获取文档链接 */
    const getDocsLinkMapping = async () => {
      const data = await getLinkMapping().catch(() => {});
      store.updateExtraDocLinkMap(data);
    };
    const handleHeaderMenuClick = (id: string, routeName: string) => {
      if (route.name !== routeName) {
        router.push({ name: routeName });
      }
    };
    return {
      needMenu,
      routeList,
      navActive,
      handleHeaderMenuClick,
      locale
    };
  },
  render() {
    return (
      <ConfigProvider locale={this.locale}>
        <div class={{ 'trace-wrap': true, 'is-micro-app': !this.needMenu }}>
          <Navigation
            navigationType='top-bottom'
            needMenu={false}
            side-title='Trace'
          >
            {{
              header: () =>
                this.needMenu && (
                  <div class='trace-wrap-header'>
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
                ),
              default: () => <RouterView />
            }}
          </Navigation>
          <AuthorityModal />
        </div>
      </ConfigProvider>
    );
  }
});
