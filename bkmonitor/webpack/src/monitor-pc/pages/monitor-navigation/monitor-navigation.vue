<!-- eslint-disable vue/no-v-html -->
<!--
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
-->
<template>
  <div
    class="monitor-navigation"
    v-bkloading="{ isLoading: loading }"
    :class="$route.meta.navClass"
  >
    <bk-navigation
      :class="{
        'no-need-menu': !header.needMenu,
        'custom-content': customContent
      }"
      @toggle="handleToggle"
      :need-menu="header.needMenu"
      :side-title="nav.title"
      @toggle-click="handleToggleClick"
      :default-open="nav.toggle"
    >
      <div
        slot="header"
        class="monitor-navigation-header"
      >
        <div class="header-title">
          <span
            v-if="$route.meta.needBack"
            @click="handleBack"
            class="header-title-back icon-monitor icon-back-left"
          />
          {{ navTitle && $t('route-' + navTitle).replace('route-', '') }}
          <i
            v-if="showCopyBtn"
            v-bk-tooltips="{ content: $t('复制链接') }"
            class="icon-monitor icon-copy-link monitor-copy-link"
            @click="handleCopyLink"
          />
          <template v-if="$route.name === 'grafana'">
            <set-menu
              ref="setMenu"
              @click="!hasDashboardAuth && handleUnDashboardAuth()"
              :has-auth="hasDashboardAuth"
              :menu-list="grafanaMenuList"
              @item-click="handleGrafanaMenuClick"
            />
          </template>
        </div>
        <bk-select
          ref="headerSelect"
          search-with-pinyin
          class="header-select"
          v-model="header.select.value"
          @change="handleBizChange"
          searchable
          :clearable="false"
        >
          <bk-option
            v-for="(option, index) in header.select.list"
            :key="index"
            :id="option.id"
            :name="option.text"
          />
          <div
            slot="extension"
            class="select-extension"
          >
            <span
              class="select-extension-btn has-border"
              @click="handleGetBizAuth"
            >{{ $t('申请业务权限') }}</span>
            <span
              class="select-extension-btn"
              @click="handleGotoDemo"
              v-if="hasDemoBiz"
            >{{ $t('DEMO') }}</span>
          </div>
        </bk-select>
        <bk-popover
          theme="light navigation-message"
          :arrow="false"
          offset="-20, 6"
          placement="bottom-start"
          :tippy-options="{ hideOnClick: false }"
        >
          <div class="header-help is-left">
            <span class="help-icon icon-monitor icon-mc-help-fill" />
          </div>
          <template slot="content">
            <ul class="monitor-navigation-help">
              <li
                class="nav-item"
                v-for="(item, index) in help.list"
                :key="index"
                @click="handleHelp(item)"
              >
                {{ item.name }}
              </li>
            </ul>
          </template>
        </bk-popover>
        <bk-popover
          theme="light navigation-message"
          :arrow="false"
          offset="-20, 10"
          placement="bottom-start"
          :tippy-options="{ hideOnClick: false }"
        >
          <div class="header-user is-left">
            {{ userName }}
            <i class="bk-icon icon-down-shape" />
          </div>
        </bk-popover>
      </div>
      <div
        class="monitor-logo"
        slot="side-icon"
      >
        <img
          class="monitor-logo-icon"
          src="../../static/images/svg/monitor-logo.svg"
          alt=''
        >
      </div>
      <div
        slot="menu"
        class="monitor-menu"
      >
        <bk-navigation-menu
          ref="menu"
          :default-active="defaultRouteId"
          :toggle-active="nav.toggle"
          :before-nav-change="handleBeforeNavChange"
        >
          <template v-for="item in nav.list">
            <bk-navigation-menu-group
              v-if="item.children && !!item.children.length"
              :group-name="nav.toggle ? $t(item.navName || item.name) : $t(item.shortName)"
              :key="item.name"
            >
              <template v-for="child in item.children">
                <bk-navigation-menu-item
                  :key="child.id"
                  v-bind="child"
                  v-if="!child.hidden"
                  :href="getNavHref(child)"
                  @click="handleNavItemClick(child)"
                  :default-active="child.active"
                >
                  <span>{{ $t('route-' + (child.navName || child.name)) }}</span>
                </bk-navigation-menu-item>
              </template>
            </bk-navigation-menu-group>
            <bk-navigation-menu-item
              :key="item.id"
              v-bind="item"
              v-else
              :href="getNavHref(item)"
              @click="handleNavItemClick(item)"
              :default-active="item.active"
            >
              <span>{{ $t('route-' + (item.navName || item.name)) }}</span>
            </bk-navigation-menu-item>
          </template>
        </bk-navigation-menu>
      </div>
      <!-- eslint-disable-next-line vue/no-v-html-->
      <div
        slot="footer"
        style="width: 100%"
        v-if="$route.name === 'home'"
        v-html="footer.html"
      />
      <div
        v-bkloading="{ isLoading: mcMainLoading }"
        class="monitor-main-loading"
        v-show="mcMainLoading"
      />
      <template>
        <keep-alive>
          <router-view
            :toggle-set="nav.toggleSet"
            v-bind="Object.assign({}, $route.params, { title: '' })"
          />
        </keep-alive>
        <router-view
          key="noCache"
          v-bind="Object.assign({}, $route.params, { title: '' })"
          name="noCache"
          :toggle-set="nav.toggleSet"
        />
        <authority-modal />
      </template>
    </bk-navigation>
    <log-version :dialog-show.sync="log.show" />
    <bk-paas-login ref="login" />
  </div>
</template>

<script>
import Vue from 'vue';
import { createNamespacedHelpers } from 'vuex';
import BkPaasLogin from '@blueking/paas-login';

import { getFooter } from '../../../monitor-api/modules/commons';
import { copyText, deleteCookie, getUrlParam, LOCAL_BIZ_STORE_KEY } from '../../../monitor-common/utils/utils';
import AuthorityModal from '../../../monitor-ui/authority-modal/index';
import LogVersion from '../../components/log-version/log-version';
import LogVersionMixin from '../../components/log-version/log-version-mixin';
import documentLinkMixin from '../../mixins/documentLinkMixin.ts';
import { createRouteConfig } from '../../router/router-config';
import { SET_BIZ_ID } from '../../store/modules/app';
import authorityStore from '../../store/modules/authority';
import PerformanceModule from '../../store/modules/performance';
import { MANAGE_AUTH as GRAFANA_MANAGE_AUTH } from '../grafana/authority-map';

import SetMenu from './set-menu/set-menu';

const { mapMutations } = createNamespacedHelpers('app');
const routerList = createRouteConfig();
export default {
  name: 'MonitorNavigation',
  components: {
    LogVersion,
    AuthorityModal,
    SetMenu,
    BkPaasLogin
  },
  mixins: [LogVersionMixin, documentLinkMixin],
  data() {
    return {
      nav: {
        list: routerList,
        id: 'home',
        toggle: false,
        submenuActive: false,
        title: this.$t('监控平台'),
        toggleSet: false
      },
      header: {
        select: {
          list: [],
          value: 0
        },
        needMenu: true,
        setDashboard: false
      },
      user: {
        list: [this.$t('项目管理'), this.$t('权限中心'), this.$t('退出')]
      },
      loading: false,
      // 帮助列表
      help: {
        list: [
          {
            id: 'DOCS',
            name: this.$t('产品文档'),
            href: ''
          },
          {
            id: 'VERSION',
            name: this.$t('版本日志')
          },
          {
            id: 'FAQ',
            name: this.$t('问题反馈'),
            href: window.ce_url
          }
        ]
      },
      // 显示版本日志
      log: {
        show: false
      },
      footer: {
        html: ''
      },
      grafanaMenuList: [
        {
          id: 'create',
          name: this.$t('新建仪表盘')
        },
        {
          id: 'folder',
          name: this.$t('新建目录')
        },
        {
          id: 'import',
          name: this.$t('导入仪表盘')
        }
      ]
    };
  },
  computed: {
    defaultRouteId() {
      return this.$store.getters.navId;
    },
    userName() {
      return this.$store.getters.userName || window.uin;
    },
    navTitle() {
      return this.$store.getters.navTitle || this.$route.meta.title || '';
    },
    mcMainLoading() {
      return this.$store.getters.mcMainLoading;
    },
    showCopyBtn() {
      return [
        'performance',
        'performance-detail',
        'event-center-detail',
        'event-center-action-detail',
        'strategy-config-detail',
        'collect-config-view'
      ].includes(this.$route.name);
    },
    siteUrl() {
      return this.$store.getters.siteUrl || window.site_url || '/';
    },
    enableGrafana() {
      return !!window.enable_grafana;
    },
    setDashboardButtonStatus() {
      return this.$store.getters['grafana/setDashboardButtonStatus'];
    },
    customContent() {
      return this.$route.meta.customContent;
    },
    hasDemoBiz() {
      return this.$store.getters.bizList.some(item => item.is_demo);
    },
    hasDashboardAuth() {
      return this.$store.getters['grafana/hasManageAuth'];
    }
  },
  watch: {
    '$route.name': {
      async handler(v) {
        if (v === 'home' && !this.footer.html) {
          this.footer.html = await getFooter().catch(() => '');
        }
      },
      imediadate: true
    }
  },
  beforeCreate() {
    const siteUrl = window.site_url || window.siteUrl;
    siteUrl && siteUrl.length > 10 && deleteCookie('bk_biz_id', siteUrl.slice(0, siteUrl.length - 1));
  },
  async created() {
    this.handleGlobalBiz();
    this.handleSetNeedMenu();
    this.nav.toggle = localStorage.getItem('navigationToogle') === 'true';
    this.nav.toggleSet = this.nav.toggle;
    Vue.prototype.$authorityStore = authorityStore;
  },
  mounted() {
    window.addEventListener('blur', this.handleWindowBlur);
    window.LoginModal = this.$refs.login;
  },
  beforeDestroy() {
    window.removeEventListener('blur', this.handleWindowBlur);
  },
  methods: {
    ...mapMutations([SET_BIZ_ID]),
    // 设置是否需要menu
    handleSetNeedMenu() {
      const needMenu = getUrlParam('needMenu');
      this.header.needMenu = `${needMenu}` !== 'false';
    },
    // 设置全局业务
    handleGlobalBiz() {
      const bizId = +getUrlParam('bizId')?.replace(/\//gmi, '') || +window.cc_biz_id;
      this.header.select.value = bizId;
      this.header.select.list = this.$store.getters.bizList;
    },
    getNavHref(item) {
      if (item.href) {
        return `${this.siteUrl}?bizId=${this.$store.getters.bizId}${item.href}`;
      }
      return '';
    },
    async handleNavItemClick(item) {
      // const { bizList, bizId } = this.$store.getters
      // if ((+bizId === - 1 || !(bizList || []).some(item => +item.id === +bizId))) {
      //   return
      // }
      if (this.$route.name !== item.id) {
        await this.$nextTick();
        if (!this.$router.history.pending) {
          this.$router.push({
            name: item.id
          });
        }
      }
    },
    handleCopyLink() {
      const str = `${window.location.origin + window.location.pathname}`;
      const url = `${str}?bizId=${this.$store.getters.bizId}${location.hash}${PerformanceModule.urlQuery}`;
      copyText(url, (err) => {
        this.$bkMessage('error', err);
      });
      this.$bkMessage({ theme: 'success', message: this.$t('链接复制成功') });
    },
    handleToggle(v) {
      this.nav.toggle = v;
    },
    handleToggleClick(v) {
      this.nav.toggleSet = v;
      localStorage.setItem('navigationToogle', v);
      this.$store.commit('app/setNavToggle', v);
    },
    handleBizChange(v) {
      window.cc_biz_id = +v;
      window.bk_biz_id = +v;
      localStorage.setItem(LOCAL_BIZ_STORE_KEY, +v);
      this.$store.commit('app/SET_BIZ_ID', +v);
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
    },
    handleGotoDemo() {
      const demo = this.$store.getters.bizList.find(item => item.is_demo);
      if (demo?.id) {
        if (+this.$store.getters.bizId === +demo.id) {
          location.reload();
        } else {
          this.handleBizChange(demo.id);
        }
      }
    },
    handleReload() {
      const { needClearQuery } = this.$route.meta;
      // 清空query查询条件
      if (needClearQuery) {
        location.href = `${location.origin}${location.pathname}?bizId=${window.cc_biz_id}#${this.$route.path}`;
      } else {
        location.search = `?bizId=${window.cc_biz_id}`;
      }
    },
    handleBack() {
      this.$router.back();
    },
    handleBeforeNavChange(newId, oldId) {
      if (
        [
          'strategy-config-add',
          'strategy-config-edit',
          'strategy-config-target',
          'alarm-shield-add',
          'alarm-shield-edit',
          'plugin-add',
          'plugin-edit'
        ].includes(this.$route.name)
      ) {
        if (newId !== oldId) {
          this.$router.push({
            name: newId
          });
        }
        return false;
      }
      return true;
    },
    /**
     * 当前window失去焦点的时候触发
     * 解决 popover不能捕获到iframe的点击事件的问题
     */
    handleWindowBlur() {
      const { headerSelect, setMenu } = this.$refs;
      if (headerSelect?.$refs.selectDropdown?.instance) {
        headerSelect.$refs.selectDropdown.instance.hide();
      }
      if (setMenu?.instance) {
        setMenu.instance.hide();
      }
    },
    /**
     * 帮助列表
     */
    handleHelp(item) {
      switch (item.id) {
        case 'DOCS':
          this.handleGotoLink('homeLink');
          break;
        case 'FAQ':
          item.href && window.open(item.href);
          break;
        case 'VERSION':
          this.log.show = true;
          break;
      }
    },
    async handleSetDefaultDashboardId() {
      this.header.setDashboard = true;
      const success = await this.$store.dispatch('grafana/setDefaultDashboard');
      success
        && this.$bkMessage({
          message: this.$t('设置成功'),
          theme: 'success'
        });
      this.header.setDashboard = false;
    },
    async handleGetBizAuth() {
      const data = await authorityStore.handleGetAuthDetail('view_business_v2');
      if (!data.apply_url) return;
      try {
        if (self === top) {
          window.open(data.apply_url, '__blank');
        } else {
          top.BLUEKING.api.open_app_by_other('bk_iam', data.apply_url);
        }
      } catch (_) {
        // 防止跨域问题
        window.open(data.apply_url, '__blank');
      }
    },
    handleGrafanaMenuClick({ id }) {
      this.$store.commit('grafana/setDashboardCheck', `${id}-${Date.now()}`);
    },
    // 无grafana管理权限时触发
    handleUnDashboardAuth() {
      authorityStore.getAuthorityDetail(GRAFANA_MANAGE_AUTH);
    }
  }
};
</script>

<style lang="scss" scoped>
@mixin defualt-icon-mixin($color: #768197) {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  margin-right: 8px;
  font-size: 16px;
  color: $color;
}

@mixin is-left-mixin($needBgColor: true) {
  color: #63656e;

  &:hover {
    color: #3a84ff;

    @if $needBgColor {
      background: #f0f1f5;
    }
  }
}

@mixin icon-hover-mixin {
  color: #d3d9e4;
  cursor: pointer;
  background: linear-gradient(270deg, rgba(37, 48, 71, 1) 0%, rgba(38, 50, 71, 1) 100%);
  border-radius: 100%;
}

@mixin popover-panel-mxin($width: 150px, $itemHoverColor: #3a84ff) {
  display: flex;
  flex-direction: column;
  width: $width;
  padding: 6px 0;
  margin: 0;
  color: #63656e;
  background: #fff;
  border: 1px solid #e2e2e2;
  box-shadow: 0px 3px 4px 0px rgba(64, 112, 203, .06);

  .nav-item {
    display: flex;
    flex: 0 0 32px;
    align-items: center;
    padding: 0 20px;
    list-style: none;

    &:hover {
      color: $itemHoverColor;
      cursor: pointer;
      background-color: #f0f1f5;
    }
  }
}

.monitor-navigation {
  :deep(.navigation-nav) {
    z-index: 9999;
  }

  .custom-content {
    :deep(.container-content) {
      padding: 0;
    }
  }

  .no-need-menu {
    :deep(.container-header) {
      /* stylelint-disable-next-line declaration-no-important */
      display: none !important;
    }

    :deep(.navigation-container) {
      /* stylelint-disable-next-line declaration-no-important */
      max-width: 100vw !important;
    }

    :deep(.container-content) {
      /* stylelint-disable-next-line declaration-no-important */
      max-height: 100vh !important;
    }
  }

  :deep(.navigation-bar-nav) {
    z-index: 1001;
  }

  &.event-center-nav {
    :deep(.container-content) {
      // overflow: hidden;
      padding: 0;
    }
  }

  &.plugin-detail-nav,
  &.uptime-check-nav {
    :deep(.container-header) {
      border-bottom: 0;
      box-shadow: none;
    }
  }

  &.data-retrieval-nav {
    :deep(.container-content) {
      padding: 0;
    }
  }

  &.escalation-content {
    :deep(.container-content) {
      overflow: hidden;
    }

    :deep(.container-header) {
      border-bottom: 0;
      box-shadow: none;
    }
  }

  .monitor-copy-link {
    margin-left: 10px;
    cursor: pointer;

    &:hover {
      color: #3a84ff;
    }
  }

  .set-default {
    margin-left: 20px;
  }

  .monitor-logo {
    width: 32px;
    height: 32px;
  }

  .monitor-menu {
    :deep(.menu-icon) {
      font-size: 18px;
    }
  }

  .monitor-main-loading {
    /* stylelint-disable-next-line declaration-no-important */
    position: absolute !important;
    width: 100%;
    height: calc(100vh - 52px - var(--notice-alert-height));
    margin-top: -20px;
    margin-left: -24px;
  }

  .help-icon {
    height: 16px;
  }

  &-header {
    display: flex;
    flex: 1;
    align-items: center;
    height: 100%;
    font-size: 14px;

    .header-title {
      display: flex;
      align-items: center;
      height: 21px;
      margin-right: auto;
      font-size: 16px;
      line-height: 21px;
      color: #313238;

      &-back {
        margin-left: -7px;
        font-size: 28px;
        color: #3a84ff;
        cursor: pointer;
      }

      &-grafana {
        display: flex;
        align-items: center;
        width: 152px;
        padding: 0 12px;
        margin: 0 24px;
        font-size: 12px;
        line-height: 26px;
        color: #63656e;
        border: 1px solid #c4c6cc;
        border-radius: 2px;

        .grafana-label {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 32px;
          height: 14px;
          margin-right: 8px;
          color: white;
          background-color: #c4c6cc;
          border-top-left-radius: 7px;
          border-top-right-radius: 7px;
          border-bottom-left-radius: 7px;

          &-font {
            line-height: 10px;
            transform: scale(.75);
          }
        }

        &:hover {
          color: #3a84ff;
          cursor: pointer;
          border-color: #3a84ff;

          .grafana-label {
            background-color: #3a84ff;
          }
        }
      }
    }

    .header-select {
      width: 240px;
      margin-right: 34px;
      margin-left: auto;
      color: #63656e;
      background: #f0f1f5;
      border: 0;
      box-shadow: none;

      :deep(.bk-select-dropdown) {
        /* stylelint-disable-next-line declaration-no-important */
        background-color: inherit !important;
      }
    }

    .header-mind {
      @include defualt-icon-mixin;

      &.is-left {
        @include is-left-mixin;
      }

      &-mark {
        position: absolute;
        top: 8px;
        right: 8px;
        width: 7px;
        height: 7px;
        background-color: #ea3636;
        border: 1px solid #27334c;
        border-radius: 100%;

        &.is-left {
          border-color: #f0f1f5;
        }
      }

      &:hover {
        @include icon-hover-mixin;
      }
    }

    .header-help {
      @include defualt-icon-mixin;

      &.is-left {
        @include is-left-mixin;
      }

      &:hover {
        @include icon-hover-mixin;
      }
    }

    .header-user {
      display: flex;
      align-items: center;
      justify-content: center;
      height: 100%;
      margin-left: 8px;
      color: #96a2b9;

      .bk-icon {
        margin-left: 5px;
        font-size: 12px;
      }

      &.is-left {
        @include is-left-mixin(false);
      }

      &:hover {
        color: #d3d9e4;
        cursor: pointer;
      }
    }
  }

  &-help {
    @include popover-panel-mxin(170px #63656e);
  }

  &-admin {
    @include popover-panel-mxin(170px #63656e);
  }

  :deep(.monitor-navigation-footer) {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    width: 100%;
    height: 52px;
    margin: 32px 0 0;
    font-size: 12px;
    color: #63656e;
    border-top: 1px solid #dcdee5;

    .footer-link {
      margin-bottom: 6px;
      color: #3480fe;

      a {
        margin: 0 2px;
        color: #3480fe;
        cursor: pointer;
      }
    }
  }
}

.select-extension {
  display: flex;
  align-items: center;
  height: 32px;
  margin: 0 -16px;

  &:hover {
    /* stylelint-disable-next-line declaration-no-important */
    background: white !important;
  }

  &-btn {
    display: flex;
    flex: 1;
    align-items: center;
    justify-content: center;

    &.has-border {
      border-right: 1px solid #eff5ff;
    }

    &:hover {
      color: #3a84ff;
      cursor: pointer;
      background: #eff5ff;
    }
  }
}
</style>
