<!-- eslint-disable vue/no-deprecated-slot-attribute -->
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
  <nav class="log-search-nav">
    <div class="nav-left fl">
      <div
        class="log-logo-container"
        @click.stop="jumpToHome"
      >
        <img
          class="logo-image"
          :src="platformData.logo"
          alt="logo"
        />
        <span class="logo-text">{{ platformData.name }}</span>
      </div>
      <div class="nav-separator">|</div>
      <BizMenuSelect class="head-navi-left"></BizMenuSelect>
    </div>
    <div
      class="nav-center fl"
      data-test-id="topNav_div_topNavBox"
    >
      <ul>
        <li
          v-for="menu in menuList"
          :class="['menu-item', { active: navMenu.activeTopMenu.id === menu.id }]"
          :data-test-id="`topNavBox_li_${menu.id}`"
          :id="`${menu.id}MenuGuide`"
          :key="menu.id"
          @click="routerHandler(menu)"
        >
          <template>
            {{ menu.name }}
          </template>
        </li>
      </ul>
    </div>
    <div
      class="nav-right fr"
      v-show="usernameRequested"
    >
      <!-- 全局设置 -->
      <bk-dropdown-menu
        v-if="isShowGlobalSetIcon"
        align="center"
        @hide="isShowGlobalDropdown = false"
        @show="isShowGlobalDropdown = true"
      >
        <template #dropdown-trigger>
          <div class="icon-language-container">
            <span
              :class="{
                'setting bk-icon icon-cog-shape icon-language-container': true,
                active: isShowGlobalDialog || isShowGlobalDropdown,
              }"
            ></span>
          </div>
        </template>
        <template #dropdown-content>
          <ul class="bk-dropdown-list">
            <li
              v-for="item in globalSettingList"
              class="language-btn"
              :key="item.id"
            >
              <a
                href="javascript:;"
                @click="handleClickGlobalDialog(item.id)"
              >
                {{ item.name }}
              </a>
            </li>
          </ul>
        </template>
      </bk-dropdown-menu>
      <!-- 语言 -->
      <bk-dropdown-menu
        align="center"
        @hide="isShowLanguageDropdown = false"
        @show="isShowLanguageDropdown = true"
      >
        <template #dropdown-trigger>
          <div class="icon-language-container">
            <div class="icon-circle-container">
              <div
                :class="[
                  'icon-language',
                  {
                    active: isShowLanguageDropdown,
                  },
                  language === 'en' ? 'bk-icon icon-english' : 'bk-icon icon-chinese',
                ]"
              />
            </div>
          </div>
        </template>
        <template #dropdown-content>
          <ul class="bk-dropdown-list">
            <li
              v-for="item in languageList"
              class="language-btn"
              :key="item.id"
            >
              <a
                :class="{ active: language === item.id }"
                href="javascript:;"
                @click="changeLanguage(item.id)"
              >
                <span :class="['icon-language', getLanguageClass(item.id)]" />
                {{ item.name }}
              </a>
            </li>
          </ul>
        </template>
      </bk-dropdown-menu>
      <!-- 版本日志和产品文档 -->
      <bk-dropdown-menu
        ref="dropdownHelp"
        align="center"
        @hide="isShowHelpDropdown = false"
        @show="isShowHelpDropdown = true"
      >
        <template #dropdown-trigger>
          <div
            class="icon-language-container"
            :class="isShowHelpDropdown && 'active'"
          >
            <div class="icon-circle-container">
              <span
                class="icon bklog-icon bklog-help"
                slot="dropdown-trigger"
              ></span>
            </div>
          </div>
        </template>
        <template #dropdown-content>
          <ul class="bk-dropdown-list">
            <li>
              <a
                href="javascript:;"
                @click.stop="dropdownHelpTriggerHandler('docCenter')"
              >
                {{ $t('产品文档') }}
              </a>
              <a
                v-if="!isExternal"
                href="javascript:;"
                @click.stop="dropdownHelpTriggerHandler('logVersion')"
              >
                {{ $t('版本日志') }}
              </a>
              <a
                href="javascript:;"
                @click.stop="dropdownHelpTriggerHandler('feedback')"
              >
                {{ $t('问题反馈') }}
              </a>
            </li>
          </ul>
        </template>
      </bk-dropdown-menu>
      <log-version :dialog-show.sync="showLogVersion" />
      <bk-dropdown-menu
        align="center"
        @hide="isShowLogoutDropdown = false"
        @show="isShowLogoutDropdown = true"
      >
        <template #dropdown-trigger>
          <div
            class="icon-language-container"
            :class="isShowLogoutDropdown && 'active'"
          >
            <span
              v-if="username"
              class="username"
            >
              {{ username }}
              <i class="bk-icon icon-down-shape"></i>
            </span>
          </div>
        </template>
        <template #dropdown-content>
          <ul class="bk-dropdown-list">
            <li>
              <a
                href="javascript:;"
                @click="handleGoToMyApplication"
              >
                {{ $t('我申请的') }}
              </a>
            </li>
            <li>
              <a
                href="javascript:;"
                @click="handleGoToMyReport"
              >
                {{ $t('我的订阅') }}
              </a>
            </li>
            <li>
              <a
                href="javascript:;"
                @click="handleQuit"
              >
                {{ $t('退出登录') }}
              </a>
            </li>
          </ul>
        </template>
      </bk-dropdown-menu>
    </div>

    <GlobalDialog
      v-model="showGlobalDialog"
      :title="globalDialogTitle"
    >
      <iframe
        style="width: 100%; height: 100%; border: none"
        :src="targetSrc"
      ></iframe>
    </GlobalDialog>
  </nav>
</template>

<script>
  import { useJSONP } from '@/common/jsonp';
  import GlobalDialog from '@/components/global-dialog';
  import logoImg from '@/images/log-logo.png';
  import { useNavMenu } from '@/hooks/use-nav-menu';
  import platformConfigStore from '@/store/modules/platform-config';
  import jsCookie from 'js-cookie';
  import { mapState, mapGetters } from 'vuex';

  import { menuArr } from './complete-menu';
  import LogVersion from './log-version';
  import BizMenuSelect from '@/global/bk-space-choice/index'

  export default {
    name: 'HeaderNav',
    components: {
      LogVersion,
      GlobalDialog,
      BizMenuSelect,
    },
    props: {
      welcomeData: {
        type: Object,
        default: null,
      },
    },
    data() {
      return {
        navMenu: null,
        isFirstLoad: true,
        isOpenVersion: window.RUN_VER.indexOf('open') !== -1,
        username: '',
        usernameRequested: false,
        isShowLanguageDropdown: false,
        isShowGlobalDropdown: false,
        isShowHelpDropdown: false,
        isShowLogoutDropdown: false,
        showLogVersion: false,
        language: 'zh-cn',
        languageList: [
          { id: 'zh-cn', name: '中文' },
          { id: 'en', name: 'English' },
        ],
        showGlobalDialog: false,
        globalDialogTitle: '',
        targetSrc: '',
      };
    },
    computed: {
      ...mapState({
        currentMenu: state => state.currentMenu,
        errorPage: state => state.errorPage,
        asIframe: state => state.asIframe,
        iframeQuery: state => state.iframeQuery,
        isExternal: state => state.isExternal,
        isShowGlobalDialog: state => state.isShowGlobalDialog,
        globalSettingList: state => state.globalSettingList,
      }),
      ...mapGetters('globals', ['globalsData']),
      platformData() {
        const { appLogo, i18n } = platformConfigStore.publicConfig;
        const bkRepoUrl = window.BK_SHARED_RES_URL;
        const publicConfigName = i18n?.name ?? this.$t('日志平台');
        return {
          name: !!bkRepoUrl ? publicConfigName : this.$t('日志平台'),
          logo: appLogo || logoImg,
        };
      },
      envConfig() {
        const { paas_api_host: host, bk_domain: bkDomain } = this.globalsData;
        return {
          host,
          bkDomain,
        };
      },
      dropDownActive() {
        let current;
        if (this.currentMenu.dropDown && this.currentMenu.children) {
          const routeName = this.$route.name;
          current = this.navMenu.activeTopMenu(this.currentMenu.children, routeName);
        }
        return current || {};
      },
      isDisableSelectBiz() {
        return Boolean(this.$route.name === 'trace' && this.$route.query.traceId);
      },
      menuList() {
        const list = this.navMenu.topMenu.filter(menu => {
          return menu.feature === 'on' && (this.isExternal ? this.externalMenu.includes(menu.id) : true);
        });
        // #if MONITOR_APP === 'apm'
        if (process.env.NODE_ENV === 'development' && process.env.MONITOR_APP === 'apm' && list?.length) {
          return [...list, { id: 'monitor-apm-log', name: 'APM Log检索' }];
        }
        // #elif MONITOR_APP === 'trace'
        if (process.env.NODE_ENV === 'development' && process.env.MONITOR_APP === 'trace' && list?.length) {
          return [...list, { id: 'monitor-trace-log', name: 'Trace Log检索' }];
        }
        // #else
        return list;
        // #endif
      },
      isShowGlobalSetIcon() {
        return !this.welcomeData && !this.isExternal;
      },
    },
    watch: {
      $route() {
        /** 当路由改变时应该把 dialog 关闭掉 */
        this.showGlobalDialog = false;
      },
    },
    async created() {
      this.language = jsCookie.get('blueking_language') || 'zh-cn';
      this.$store.commit('updateMenuList', menuArr);

      // 初始化 navMenu 并保存到组件数据
      this.navMenu = useNavMenu({
        t: $t,
        bkInfo: window.$bkInfo,
        http: window.$http,
        emit: window.$emit
      });

      this.navMenu.requestMySpaceList();
      
      this.getGlobalsData();
      this.getUserInfo();
      window.bus.$on('showGlobalDialog', this.handleGoToMyReport);
    },
    beforeUnmount() {
      window.bus.$off('showGlobalDialog', this.handleGoToMyReport);
    },

    methods: {
      async getUserInfo() {
        try {
          const res = this.$store.state.userMeta;
          this.username = res.username;
          // this.$store.commit('updateUserMeta', res.data);
          if (window.__aegisInstance) {
            window.__aegisInstance.setConfig({
              uin: res.username,
            });
          }
        } catch (e) {
          console.warn(e);
        } finally {
          this.usernameRequested = true;
        }
      },
      // 获取全局数据和 判断是否可以保存 已有的日志聚类
      getGlobalsData() {
        // if (Object.keys(this.globalsData).length) return;
        // this.$http
        //   .request('collect/globals')
        //   .then(res => {
        //     this.$store.commit('globals/setGlobalsData', res.data);
        //   })
        //   .catch(e => {
        //     console.warn(e);
        //   });
      },
      jumpToHome() {
        this.$store.commit('updateIsShowGlobalDialog', false);

        if (window.IS_EXTERNAL) {
          this.$router.push({
            name: 'manage',
            query: {
              spaceUid: this.$store.state.spaceUid,
              bizId: this.$store.state.bizId,
            },
          });

          return;
        }
        this.$router.push({
          name: 'retrieve',
          query: {
            spaceUid: this.$store.state.spaceUid,
          },
        });
        setTimeout(() => {
          this.$emit('reload-router');
        });
      },
      routerHandler(menu) {
        // 关闭全局设置弹窗
        this.$store.commit('updateIsShowGlobalDialog', false);
        if (menu.id === this.navMenu.activeTopMenu.id) {
          if (menu.id === 'retrieve') {
            this.$router.push({
              name: menu.id,
              query: {
                spaceUid: this.$store.state.spaceUid,
              },
            });
            this.$emit('reload-router');
            return;
          }
          if (menu.id === 'extract') {
            if (this.$route.query.create) {
              this.$router.push({
                name: 'extract',
                query: {
                  spaceUid: this.$store.state.spaceUid,
                },
              });
            } else {
              this.$emit('reload-router');
            }
            return;
          }
          if (menu.id === 'trace') {
            if (this.$route.name === 'trace-detail') {
              this.$router.push({
                name: 'trace-list',
                query: {
                  spaceUid: this.$store.state.spaceUid,
                },
              });
            } else {
              this.$emit('reload-router');
            }
            return;
          }
          if (menu.id === 'dashboard') {
            // if (this.$route.query.manageAction) {
            //   const newQuery = { ...this.$route.query };
            //   delete newQuery.manageAction;
            //   this.$router.push({
            //     name: 'dashboard',
            //     query: newQuery,
            //   });
            // }
            // this.$emit('reload-router');
            // return;
            this.$router.push({
              name: menu.id,
              query: {
                spaceUid: this.$store.state.spaceUid,
              },
            });
            this.$emit('reload-router');
            return;
          }
          if (menu.id === 'manage') {
            if (this.$route.name !== 'collection-item') {
              this.$router.push({
                name: 'manage',
                query: {
                  spaceUid: this.$store.state.spaceUid,
                },
              });
            } else {
              this.$emit('reload-router');
            }
            return;
          }
          this.$emit('reload-router');
          return;
        }
        if (menu.id === 'monitor') {
          window.open(`${window.MONITOR_URL}/?bizId=${this.bkBizId}#/strategy-config`, '_blank');
        } else if (menu.id === 'trace') {
          this.$router.push({
            name: 'trace-list',
            query: {
              spaceUid: this.$store.state.spaceUid,
            },
          });
        } else {
          this.$router.push({
            name: menu.id,
            query: {
              spaceUid: this.$store.state.spaceUid,
            },
          });
        }
      },
      async changeLanguage(value) {
        jsCookie.remove('blueking_language', { path: '' });
        jsCookie.set('blueking_language', value, {
          expires: 3600,
          domain:
            this.envConfig.bkDomain || location.host.split('.').slice(-2).join('.').replace(`:${location.port}`, ''),
        });
        if (this.envConfig.host) {
          try {
            useJSONP(
              `${this.envConfig.host
                .replace(/\/$/, '')
                .replace(/^http:/, location.protocol)}/api/c/compapi/v2/usermanage/fe_update_user_language`,
              {
                data: {
                  language: value,
                },
              },
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
      },

      dropdownHelpTriggerHandler(type) {
        this.$refs.dropdownHelp.hide();
        if (type === 'logVersion') {
          this.showLogVersion = true;
        } else if (type === 'docCenter') {
          // window.open(window.BK_DOC_URL);
          this.handleGotoLink('docCenter');
        } else if (type === 'feedback') {
          window.open(window.BK_FAQ_URL);
        }
      },
      /** 前往 我申请的 */
      handleGoToMyApplication() {
        this.showGlobalDialog = false;
        this.$nextTick(() => {
          const bizId = this.$store.state.bkBizId;
          const host =
            process.env.NODE_ENV === 'development' ? `http://${process.env.devHost}:7001` : window.MONITOR_URL;
          const targetSrc = `${host}/?bizId=${bizId}&needMenu=false#/trace/report/my-applied-report`;
          this.globalDialogTitle = this.$t('我申请的');
          this.showGlobalDialog = true;
          this.targetSrc = targetSrc;
        });
      },
      /** 前往 我的订阅 */
      handleGoToMyReport() {
        this.showGlobalDialog = false;
        this.$nextTick(() => {
          const bizId = this.$store.state.bkBizId;
          const host =
            process.env.NODE_ENV === 'development' ? `http://${process.env.devHost}:7001` : window.MONITOR_URL;
          const targetSrc = `${host}/?bizId=${bizId}&needMenu=false#/trace/report/my-report`;
          this.globalDialogTitle = this.$t('我的订阅');
          this.showGlobalDialog = true;
          this.targetSrc = targetSrc;
        });
      },
      /** 退出登录 */
      handleQuit() {
        location.href = `${window.BK_PLAT_HOST}/console/accounts/logout/`;
      },
      handleClickGlobalDialog(id) {
        // 打开全局设置弹窗
        this.$store.commit('updateGlobalActiveLabel', id);
        this.$store.commit('updateIsShowGlobalDialog', true);
      },
      getLanguageClass(language) {
        return language === 'en' ? 'bk-icon icon-english' : 'bk-icon icon-chinese';
      },
    },
  };
</script>

<style lang="scss">
  @import '../../scss/mixins/clearfix';
  @import '../../scss/conf';
  @import '../../scss/mixins/flex';

  .log-search-nav {
    height: 52px;
    color: #fff;
    background: #182132;

    @include clearfix;

    .nav-left {
      display: flex;
      align-items: center;
      min-width: max-content;
      max-width: 180px;
      height: 100%;
      padding-left: 16px;
      margin-right: 315px;
      font-size: 18px;

      .log-logo-container {
        display: flex;
        align-items: center;
        height: 100%;
        color: #96a2b9;
        cursor: pointer;

        .logo-text {
          font-size: 16px;
          font-weight: 700;
          color: #96a2b9;
        }

        .logo-image {
          width: 40px;
          height: 40px;
          margin-right: 10px;
        }
      }

      .nav-separator {
        margin: 0px 2px 0 18px;
        font-size: 20px;
        color: #5f616b;
      }

      .head-navi-left {
        &.biz-menu-select {
          .menu-select {
            background-color: #182132;
          }

          .menu-select-list {
            top: 52px;
            left: 138px;
          }
        }
      }
    }

    .nav-center {
      font-size: 14px;

      ul {
        @include clearfix;
      }

      .menu-item {
        position: relative;
        float: left;
        height: 50px;
        padding: 0 20px;
        line-height: 50px;
        color: #979ba5;
        cursor: pointer;
        transition: color 0.3s linear;

        &.active {
          color: #fff;
          background: #0c1423;
          transition: all 0.3s linear;
        }

        &:hover {
          color: #fff;
          transition: color 0.3s linear;
        }

        &.guide-highlight {
          background: #000;
        }
      }

      .bk-dropdown-content {
        z-index: 2105;
        min-width: 112px;
        line-height: normal;

        /* stylelint-disable-next-line declaration-no-important */
        text-align: center !important;
      }

      .drop-menu-item > .active {
        color: #3a84ff;
      }
    }

    .nav-right {
      display: flex;
      align-items: center;
      height: 100%;
      color: #768197;

      @include clearfix;

      .setting {
        position: relative;
        font-size: 15px;
        cursor: pointer;

        &::before {
          position: relative;
          z-index: 2;
        }

        &.active,
        &:hover {
          color: #d3d9e4;
        }

        &.active::after,
        &:hover::after {
          position: absolute;
          left: 50%;
          z-index: 1;
          width: 30px;
          height: 30px;
          content: '';
          background: linear-gradient(270deg, #253047, #263247);
          border-radius: 50%;
          transform: translateX(-50%);
        }
      }

      .select-business {
        margin-right: 22px;
        color: #979ba5;
        border-color: #445060;
      }

      .icon-language-container {
        height: 50px;
        margin: 4px;
        cursor: pointer;

        @include flex-center;

        .username {
          margin: 0 28px 0 6px;
          font-size: 12px;
          line-height: 20px;
          color: #63656e;

          &:hover {
            color: #d3d9e4;
            cursor: pointer;
          }
        }

        &.active {
          .username {
            color: #d3d9e4;
          }
        }

        .icon-circle-container {
          width: 32px;
          height: 32px;
          border-radius: 16px;
          transition: all 0.2s;

          @include flex-center;

          .icon-language {
            font-size: 18px;

            &.active,
            &:hover {
              color: #d3d9e4;
            }
          }

          .log-icon {
            font-size: 16px;
            transition: all 0.2s;
          }
        }

        &:hover,
        &.active {
          .icon-circle-container {
            background: linear-gradient(270deg, #253047, #263247);
            transition: all 0.2s;

            .bklog-icon {
              color: #d3d9e4;
              transition: all 0.2s;
            }
          }
        }
      }

      .icon-icon-help-document-fill {
        font-size: 16px;
        cursor: pointer;
      }

      .bk-dropdown-list {
        .language-btn {
          a {
            display: flex;
            align-items: center;
          }
        }

        .active {
          color: #3c96ff;
        }
      }
    }

    .icon-chinese::before {
      content: '\e206';
    }

    .icon-english::before {
      content: '\e207';
    }
  }

  .select-business-dropdown-content {
    /* stylelint-disable-next-line declaration-no-important */
    border: none !important;

    .bk-select-search-wrapper {
      border: 1px solid #dcdee5;
      border-bottom: none;
      border-top-left-radius: 2px;
      border-top-right-radius: 2px;
    }

    .bk-options-wrapper {
      border-right: 1px solid #dcdee5;
      border-left: 1px solid #dcdee5;
    }

    .bk-select-extension {
      padding: 0;
      border: none;

      &:hover {
        background: #fafbfd;
      }

      .select-business-extension {
        display: flex;
        cursor: pointer;

        .extension-item {
          flex-grow: 1;
          width: 50%;
          text-align: center;
          border: 1px solid #dcdee5;

          &:nth-child(2) {
            margin-left: -1px;
            border-left-color: #dcdee5;
          }

          &:first-child {
            border-bottom-left-radius: 2px;
          }

          &:last-child {
            border-bottom-right-radius: 2px;
          }

          &:hover {
            z-index: 1;
            color: #3a84ff;
            background: #f0f5ff;
            border-color: #3a84ff;
          }
        }
      }
    }
  }
</style>
