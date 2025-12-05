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
  <bk-navigation class="bk-log-navigation" :theme-color="navThemeColor" head-height="0" header-title=""
    navigation-type="left-right" default-open @toggle="handleToggle">
    <template #menu>
      <bk-navigation-menu :default-active="activeManageNav.id" :item-default-bg-color="navThemeColor">
        <template v-for="groupItem in menuList">
          <bk-navigation-menu-group v-if="groupItem.children.length"
            :group-name="isExpand ? groupItem.name : groupItem.keyword" :key="groupItem.id">
            <template>
              <a v-for="navItem in getGroupChildren(groupItem.children)" class="nav-item"
                :href="getRouteHref(navItem.id)" :key="navItem.id">
                <bk-navigation-menu-item :data-test-id="`navBox_nav_${navItem.id}`" :icon="getMenuIcon(navItem)"
                  v-if="shouldShowMenuItem(navItem.id)"
                  :id="navItem.id" @click="handleClickNavItem(navItem.id)">
                  <span>{{ isExpand ? navItem.name : '' }}</span>
                </bk-navigation-menu-item>
              </a>
            </template>
          </bk-navigation-menu-group>
        </template>
      </bk-navigation-menu>
    </template>

    <!-- 灰度控制：如果是灰度业务且不在白名单，显示提醒组件 -->
    <div v-if="showGrayReleaseReminder" class="navigation-content gray-release-content">
      <bk-exception
        class="exception-wrap-item"
        type="403"
        scene="part">
        <span>{{ $t('灰度业务') }}</span>
        <div class="text-subtitle">{{ $t('本功能为灰度业务，请联系管理员开通') }}</div>
      </bk-exception>
    </div>

    <!-- 正常内容 -->
    <div v-else class="navigation-content">
      <auth-container-page v-if="authPageInfo" :info="authPageInfo"></auth-container-page>
      <div class="manage-container">
        <div class="manage-main">
          <sub-nav :sub-nav-list="menuList"></sub-nav>
          <router-view class="manage-content" :key="refreshKey"></router-view>
        </div>
      </div>
    </div>
  </bk-navigation>

</template>

<script>
  import SubNav from '@/components/nav/manage-nav';
import { mapGetters, mapState } from 'vuex';

  export default {
    name: 'ManageIndex',
    components: {
      SubNav,
    },
    data() {
      return {
        navThemeColor: '#2c354d',
        isExpand: true,
        refreshKey: ''
      };
    },

    computed: {
      ...mapState(['topMenu', 'spaceUid', 'bkBizId', 'isExternal', 'globals']),
      ...mapGetters({
        authPageInfo: 'globals/authContainerInfo',
      }),
      manageNavList() {
        return this.topMenu.find(item => item.id === 'manage')?.children || [];
      },
      menuList() {
        const list = this.manageNavList;
        if (this.isExternal) {
          // 外部版只保留【日志提取】菜单
          return list.filter(menu => menu.id === 'manage-extract-strategy');
        }
        return list ?? [];
      },
      activeManageNav() {
        const childList = this.menuList.map(m => m.children).flat(2);
        return childList.find(t => t.id === this.$route.meta.navId) ?? {};
      },
      // 判断是否显示灰度提醒页面
      showGrayReleaseReminder() {
        // 首先检查是否在 tgpa-task 相关路由
        const isTgpaTaskRoute = this.checkIfTgpaTaskRoute();

        if (isTgpaTaskRoute) {
          // 检查是否为灰度业务
          return this.isGrayReleaseBusiness();
        }

        return false;
      }
    },
    watch: {
      '$route.query.spaceUid'(newSpaceUid, oldSpaceUid) {
        if (newSpaceUid !== oldSpaceUid) {
          // 检查当前是否在 tgpa-task 相关路由
          const isTgpaTaskRoute = this.checkIfTgpaTaskRoute();

          if (isTgpaTaskRoute) {
            // 检查权限
            const hasPermission = this.checkTgpaTaskFeatureToggle();
            if (!hasPermission) {
              // 没有权限，跳转到管理页面第一个菜单项
              this.redirectToFirstMenuItem();
              return;
            }
          }

          // 获取最外层路径
          const topLevelRoute = this.getTopLevelRoute();

          this.$router.replace({
            name: topLevelRoute,
            query: {
              ...this.$route.query,
              spaceUid: this.spaceUid,
              bizId: this.bkBizId,
            },
          }).then(() => {
            this.refreshKey = `${this.$router.name}_${this.$route.query.spaceUid}`
          });
        }
      },
    },
    methods: {
      getMenuIcon(item) {
        if (item.icon) {
          return `bklog-icon bklog-${item.icon}`;
        }
        return 'bk-icon icon-home-shape';
      },
      handleClickNavItem(id) {
        this.$router.push({
          name: id,
          query: {
            spaceUid: this.$store.state.spaceUid,
          },
        });
      },
      handleToggle(data) {
        this.isExpand = data;
      },
      // 获取当前路由的最外层路径，用于切换业务时跳转到菜单栏目录项
      getTopLevelRoute() {
        const currentPath = this.$route.path;
        const match = currentPath.match(/^\/manage\/([^\/]+)/);  // 匹配 /manage/xxx 的模式

        if (match) return match[1]; // 返回紧跟 /manage 的路径段

        return 'manage';
      },
      getGroupChildren(list) {
        if (this.isExternal) {
          // 外部版只保留【日志提取任务】
          return list.filter(menu => menu.id === 'log-extract-task');
        }
        return list;
      },
      getRouteHref(pageName) {
        const newUrl = this.$router.resolve({
          name: pageName,
          query: {
            spaceUid: this.$store.state.spaceUid,
          },
        });
        return newUrl.href;
      },
      // 判断是否应该显示菜单项
      shouldShowMenuItem(menuId) {
        // 如果是 tgpa-task 菜单项，需要检查功能开关
        if (menuId === 'tgpa-task') {
          return this.checkTgpaTaskFeatureToggle();
        }

        // 其他菜单项默认显示
        return true;
      },
      // 检查 tgpa_task 功能开关
      checkTgpaTaskFeatureToggle() {
        const featureToggle = window.FEATURE_TOGGLE?.tgpa_task;

        // 如果功能开关为 'on' 或不存在，显示菜单
        if (featureToggle === 'on' || !featureToggle) {
          return true;
        }

        // 如果功能开关为 'off'，隐藏菜单
        if (featureToggle === 'off') {
          return false;
        }

        // 如果功能开关为 'debug'，检查白名单
        if (featureToggle === 'debug') {
          const whiteList = window.FEATURE_TOGGLE_WHITE_LIST?.tgpa_task ?? [];
          const bizId = this.$store.state.bkBizId;
          const spaceUid = this.$store.state.spaceUid;

          // 如果是 100269 业务，跳过白名单检查，返回 true（显示菜单项）
          if (spaceUid === 'bkcc__100269' || String(bizId) === '100269') {
            return true;
          }

          // 其他业务进行正常的白名单检查
          const normalizedWhiteList = whiteList.map(id => String(id));
          return normalizedWhiteList.includes(String(bizId))
            || normalizedWhiteList.includes(String(spaceUid));
        }

        // 默认不显示
        return false;
      },
      // 检查当前路由是否为 tgpa-task 相关路由
      checkIfTgpaTaskRoute() {
        return this.$route.meta?.navId === 'tgpa-task';
      },
      // 跳转到manage首页
      redirectToFirstMenuItem() {
        // 根据是否为外部版决定跳转目标
        if (this.isExternal) {
          // 外部版跳转到日志提取任务
          this.$router.replace({
            name: 'log-extract-task',
            query: {
              spaceUid: this.spaceUid,
              bizId: this.bkBizId,
            },
          });
        } else {
          // 直接跳转到 manage 路由，让路由的 redirect 逻辑自动处理
          this.$router.replace({
            name: 'manage',
            query: {
              spaceUid: this.spaceUid,
              bizId: this.bkBizId,
            },
          });
        }
      },
      // 检查是否为灰度业务
      isGrayReleaseBusiness() {
        // 首先检查功能开关状态
        const featureToggle = window.FEATURE_TOGGLE?.tgpa_task;

        // 只有在功能开关为 'debug' 时才可能有灰度业务
        if (featureToggle !== 'debug') {
          return false;
        }

        // 检查当前业务是否为灰度发布业务
        const currentSpaceUid = this.spaceUid;
        const currentBizId = this.bkBizId;

        // 如果是特定的 spaceUid 或 bizId，检查是否在灰度白名单中
        if (currentSpaceUid === 'bkcc__100269' || String(currentBizId) === '100269') {
          const whiteList = window.FEATURE_TOGGLE_WHITE_LIST?.tgpa_task ?? [];
          const normalizedWhiteList = whiteList.map(id => String(id));

          // 如果不在白名单中，说明是灰度业务
          return !normalizedWhiteList.includes(String(currentSpaceUid))
            && !normalizedWhiteList.includes(String(currentBizId));
        }

        // 其他业务不是灰度业务
        return false;
      },

    },
    mounted() {
      const bkBizId = this.$store.state.bkBizId;
      const spaceUid = this.$store.state.spaceUid;

      this.$router.replace({
        query: {
          bizId: bkBizId,
          spaceUid: spaceUid,
          ...this.$route.query,
        },
      }).then(() => {
        this.refreshKey = `${this.$router.name}_${this.$route.query.spaceUid}`
      });
    },
  };
</script>

<style lang="scss" scoped>
  @import '../../scss/mixins/scroller.scss';

  .manage-container {
    height: 100%;

    .manage-content {
      // height: 100%;
      position: relative;
      top: 48px;
      height: calc(100% - 52px);
      overflow: auto;

      @include scroller($backgroundColor: #c4c6cc, $width: 4px);
    }

    .manage-main {
      height: 100%;
    }

    :deep(.bk-table) {
      background: #fff;

      .cell {
        display: block;
      }

      .bk-table-pagination-wrapper {
        background: #fafbfd;
      }
    }
  }

    .gray-release-content {
      display: flex;
      align-items: center;
      justify-content: center;
      height: 100%;

      .exception-wrap-item {
        span {
          font-size: 24px;
          color: #63656e;
        }

        .text-subtitle {
          margin-top: 14px;
          font-size: 14px;
          color: #979ba5;
          text-align: center;
        }
      }
    }
</style>
