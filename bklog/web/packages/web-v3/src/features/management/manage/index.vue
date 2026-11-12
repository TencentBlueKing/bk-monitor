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
  <router-view v-if="isHeadless" :key="refreshKey" class="manage-content manage-content-headless"></router-view>
  <div v-else class="bk-log-navigation">
    <aside class="manage-sidebar" :class="{ 'is-fixed': isFixed }">
      <div
        class="manage-sidebar-slider"
        :class="{ 'is-expanded': isExpand }"
        @mouseenter="handleMouseEnter"
        @mouseleave="handleMouseLeave"
      >
        <t-menu :value="activeManageNav.id || ''" :collapsed="!isExpand" :width="['260px', '60px']" theme="dark">
          <template v-for="groupItem in menuList" :key="groupItem.id">
            <t-menu-group
              v-if="getGroupChildren(groupItem.children).length"
              :title="isExpand ? groupItem.name : groupItem.keyword"
            >
              <template v-for="navItem in getGroupChildren(groupItem.children)" :key="navItem.id">
                <a
                  v-if="shouldShowMenuItem(navItem.id)"
                  class="nav-item"
                  :data-test-id="`navBox_nav_${navItem.id}`"
                  :href="getRouteHref(navItem.id)"
                  @click="handleMenuAnchorClick($event, navItem.id)"
                >
                  <t-menu-item :value="navItem.id">
                    <template #icon><i :class="getMenuIcon(navItem)"></i></template>
                    <span v-show="isExpand">{{ navItem.name }}</span>
                  </t-menu-item>
                </a>
              </template>
            </t-menu-group>
          </template>
        </t-menu>
        <div class="nav-slider-footer">
          <div class="footer-icon is-left" @click.stop="handleFix">
            <span class="footer-icon-svg" :style="{ transform: isFixed ? 'rotate(180deg)' : 'rotate(0deg)' }">
              <svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg">
                <path d="M31,13.5l-4.77,4.77,9.54,9.55H4v6.36H35.76l-9.53,9.55L31,48.5,48.47,31Zm22.65,0v35H60v-35Z" />
              </svg>
            </span>
          </div>
        </div>
      </div>
    </aside>
    <div class="navigation-content">
      <auth-container-page v-if="authPageInfo" :info="authPageInfo"></auth-container-page>
      <div class="manage-container">
        <div class="manage-main">
          <sub-nav :sub-nav-list="menuList" :show-sub-nav="showSubNav"></sub-nav>
          <router-view :key="refreshKey" class="manage-content"></router-view>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { Menu as TMenu, MenuGroup as TMenuGroup, MenuItem as TMenuItem } from 'tdesign-vue-next';
import SubNav from '@/features/navigation/manage-nav';
import AuthContainerPage from '@/shared/ui/common/auth-container-page.vue';
import { mapState } from '@/app/state/map-helpers';
import { isFeatureToggleOn } from '@/app/state/helper';

export default {
  name: 'ManageIndex',
  components: {
    SubNav,
    AuthContainerPage,
    TMenu,
    TMenuGroup,
    TMenuItem,
  },
  props: {
    showSubNav: {
      type: Boolean,
      default: true,
    },
  },
  data() {
    return {
      navThemeColor: '#2c354d',
      isExpand: false,
      isFixed: false,
      hoverEnterTimer: null,
      refreshKey: '',
    };
  },
  computed: {
    ...mapState(['topMenu', 'spaceUid', 'bkBizId', 'isExternal', 'globals']),
    authPageInfo() {
      return this.isHeadless ? null : this.$store.getters['globals/authContainerInfo'];
    },
    manageNavList() {
      if (this.isHeadless) {
        return [];
      }
      return (this.topMenu || []).find((item) => item.id === 'manage')?.children || [];
    },
    menuList() {
      const list = (this.manageNavList || []).filter(Boolean).map((menu) => ({
        ...menu,
        children: menu.children || [],
      }));
      if (this.isExternal) {
        // 外部版只保留【日志提取】菜单
        return list.filter((menu) => menu.id === 'manage-extract-strategy');
      }
      return list;
    },
    activeManageNav() {
      if (this.isHeadless) {
        return {};
      }
      const childList = this.menuList
        .map((m) => m.children || [])
        .flat(2)
        .filter(Boolean);
      return childList.find((t) => t.id === this.$route.meta?.navId) ?? {};
    },
    isHeadless() {
      return this.$route.query.hl === '1';
    },
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

        // 检查当前是否在 log_manage_v2 需要隐藏的路由
        const isV2HiddenRoute = this.checkIfV2HiddenRoute();
        if (isV2HiddenRoute && this.checkLogManageV2()) {
          this.redirectToFirstMenuItem();
          return;
        }

        // 获取最外层路径
        const topLevelRoute = this.getTopLevelRoute();

        this.$router
          .replace({
            name: topLevelRoute,
            query: {
              ...this.$route.query,
              spaceUid: this.spaceUid,
              bizId: this.bkBizId,
            },
          })
          .then(() => {
            this.updateRefreshKey();
          });
      }
    },
  },
  created() {
    this.refreshKey = this.buildRefreshKey();
  },
  mounted() {
    const bkBizId = this.$store.state.bkBizId;
    const spaceUid = this.$store.state.spaceUid;

    this.$router
      .replace({
        query: {
          bizId: bkBizId,
          spaceUid,
          ...this.$route.query,
        },
      })
      .then(() => {
        this.updateRefreshKey();
      });
    if (!this.isHeadless) {
      setTimeout(() => {
        if (!this.isFixed) this.handleToggle(false);
      }, 10);
    }
  },
  beforeUnmount() {
    this.clearHoverTimer();
  },
  methods: {
    buildRefreshKey() {
      return `${this.$router.name}_${this.$route.query.spaceUid ?? ''}`;
    },
    updateRefreshKey() {
      const nextKey = this.buildRefreshKey();
      if (nextKey !== this.refreshKey) {
        this.refreshKey = nextKey;
      }
    },
    getMenuIcon(item) {
      if (item.icon) {
        return `bklog-icon bklog-${item.icon}`;
      }
      return 'bk-icon icon-home-shape';
    },
    handleMenuAnchorClick(event, id) {
      // Preserve native new-tab/copy-link behavior for modified anchor clicks.
      if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || event.button !== 0) return;
      event.preventDefault();
      this.handleClickNavItem(id);
    },
    handleClickNavItem(id) {
      if (!this.isValidRouteName(id)) return;
      this.$router.push({
        name: id,
        query: {
          spaceUid: this.$store.state.spaceUid,
        },
      });
    },
    clearHoverTimer() {
      if (this.hoverEnterTimer) {
        clearTimeout(this.hoverEnterTimer);
        this.hoverEnterTimer = null;
      }
    },
    handleMouseEnter() {
      if (this.isFixed) return;
      this.clearHoverTimer();
      this.hoverEnterTimer = setTimeout(() => {
        this.isExpand = true;
        this.hoverEnterTimer = null;
      }, 100);
    },
    handleMouseLeave() {
      if (this.isFixed) return;
      this.clearHoverTimer();
      this.isExpand = false;
    },
    handleFix() {
      this.clearHoverTimer();
      this.isFixed = !this.isFixed;
      this.isExpand = this.isFixed;
    },
    handleToggle(data) {
      if (typeof data === 'boolean') {
        this.isExpand = data;
      }
    },
    // 获取当前路由的最外层路径，用于切换业务时跳转到菜单栏目录项
    getTopLevelRoute() {
      const currentPath = this.$route.path;
      const match = currentPath.match(/^\/manage\/([^/]+)/); // 匹配 /manage/xxx 的模式

      if (match) return match[1]; // 返回紧跟 /manage 的路径段

      return 'manage';
    },
    isValidRouteName(name) {
      if (!name) return false;
      return this.$router.getRoutes().some((route) => route.name === name);
    },
    getGroupChildren(list = []) {
      const safeList = (list || []).filter(Boolean);
      if (this.isExternal) {
        // 外部版只保留【日志提取任务】
        return safeList.filter((menu) => menu.id === 'log-extract-task' && this.isValidRouteName(menu.id));
      }
      // 仅展示已注册的路由项，过滤 collectAccess / addIndexSet 等权限元数据菜单
      return safeList.filter((menu) => this.isValidRouteName(menu.id));
    },
    getRouteHref(pageName) {
      if (!this.isValidRouteName(pageName)) {
        return '#';
      }
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
      if (!this.isValidRouteName(menuId)) {
        return false;
      }
      // 如果是 tgpa-task 菜单项，需要检查功能开关
      if (menuId === 'tgpa-task') {
        return this.checkTgpaTaskFeatureToggle();
      }

      // 如果是新版采集(log_manage_v2)启用，则隐藏计算平台、第三方ES、自定义上报
      const v2HiddenMenus = ['bk-data-collection', 'es-collection', 'custom-report'];
      if (v2HiddenMenus.includes(menuId)) {
        return !this.checkLogManageV2();
      }

      // 其他菜单项默认显示
      return true;
    },
    // 检查 tgpa_task 功能开关
    checkTgpaTaskFeatureToggle() {
      const bizId = this.$store.state.bkBizId;
      const spaceUid = this.$store.state.spaceUid;
      return isFeatureToggleOn('tgpa_task', [String(bizId), String(spaceUid)], { defaultEnabled: true });
    },
    // 检查当前路由是否为 tgpa-task 相关路由
    checkIfTgpaTaskRoute() {
      return this.$route.meta?.navId === 'tgpa-task';
    },
    // 检查当前路由是否为 log_manage_v2 启用后需要隐藏的路由
    checkIfV2HiddenRoute() {
      const hiddenNavIds = ['bk-data-collection', 'es-collection', 'custom-report'];
      return hiddenNavIds.includes(this.$route.meta?.navId);
    },
    // 检查 log_manage_v2 功能开关（是否启用新版采集）
    checkLogManageV2() {
      return isFeatureToggleOn('log_manage_v2', [String(this.bkBizId), String(this.spaceUid)]);
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
  },
};
</script>

<style lang="scss" scoped>
@use '../../../shared/styles/mixins/scroller.scss' as *;
.bk-log-navigation {
  display: flex;
  width: 100%;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

.manage-sidebar {
  position: relative;
  z-index: var(--bklog-z-nav-top);
  flex: 0 0 60px;
  width: 60px;
  min-width: 0;
  height: 100%;
  overflow: visible;
  transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1);

  &.is-fixed {
    flex-basis: 260px;
    width: 260px;
  }
}

.manage-sidebar-slider {
  display: flex;
  flex-direction: column;
  width: 60px;
  height: 100%;
  overflow: hidden;
  background: #2c354d;
  transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1);

  &.is-expanded {
    width: 260px;
  }

  :deep(.t-default-menu) {
    flex: 1;
    min-height: 0;
    height: auto;
    --td-gray-color-13: #2c354d;
    --td-gray-color-10: #3b4660;
  }

  // V2 navigation metrics: list gutter 12px, group headings 40/48px,
  // and 40px menu rows with 2px vertical space on each side.
  :deep(.t-default-menu .t-menu) {
    padding: 12px 0 4px;
  }

  :deep(.t-default-menu .t-menu-group__title) {
    display: block;
    padding: 26px 18px 6px;
    margin: 0;
    font-size: 12px;
    font-weight: 400;
    line-height: 16px;
    color: #66748f;
    white-space: nowrap;
  }

  :deep(.t-default-menu .t-menu-group:first-child .t-menu-group__title) {
    padding-top: 18px;
  }

  :deep(.t-default-menu.t-is-collapsed .t-menu-group:first-child .t-menu-group__title) {
    display: block;
  }

  :deep(.t-default-menu.t-is-collapsed .t-menu-group__title::after) {
    display: none;
  }

  :deep(.t-default-menu .t-menu .t-menu-group > .nav-item) {
    height: 44px;
    padding: 2px 0;
    margin: 0;
  }

  :deep(.t-default-menu .t-menu .t-menu__item) {
    justify-content: flex-start;
    height: 40px;
    min-height: 40px;
    padding: 0 12px 0 22px;
    margin: 0;
    font-size: 14px;
    border-radius: 0;

    > i {
      flex: 0 0 16px;
      width: 16px;
      margin-right: 22px;
      font-size: 16px;
    }
  }

  .nav-item {
    display: block;
    color: inherit;
    text-decoration: none;
  }

  &:not(.is-expanded) {
    :deep(.t-menu__item) {
      justify-content: center;
      overflow: hidden;
      white-space: nowrap;
    }

    :deep(.t-menu__content) {
      display: none;
    }
  }
}

.nav-slider-footer {
  display: flex;
  flex: 0 0 56px;
  align-items: center;
  justify-content: flex-start;
  padding-left: 14px;

  .footer-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    color: #96a2b9;
    border-radius: 100%;
    cursor: pointer;

    &:hover {
      color: #d3d9e4;
      background: linear-gradient(270deg, #253047, #263247);
    }
  }

  .footer-icon-svg {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 16px;
    height: 16px;
    font-size: 16px;
    transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);

    svg {
      width: 1em;
      height: 1em;
      fill: currentcolor;
    }
  }
}

.navigation-content {
  flex: 1;
  min-width: 0;
  height: 100%;
  overflow: hidden;
}

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
    position: relative;
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
</style>
