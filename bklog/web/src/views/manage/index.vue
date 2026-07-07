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
  <router-view
    v-if="isHeadless"
    class="manage-content manage-content-headless"
    :key="refreshKey"
  ></router-view>
  <bk-navigation v-else class="bk-log-navigation" :theme-color="navThemeColor" head-height="0" header-title=""
    navigation-type="left-right" :default-open="false" @toggle="handleToggle">
    <template #menu>
      <bk-navigation-menu :default-active="activeManageNav.id || ''" :item-default-bg-color="navThemeColor">
        <template v-for="groupItem in menuList">
          <bk-navigation-menu-group
            v-if="getGroupChildren(groupItem.children).length"
            :group-name="isExpand ? groupItem.name : groupItem.keyword"
            :key="groupItem.id"
          >
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
    <div class="navigation-content">
      <auth-container-page v-if="authPageInfo" :info="authPageInfo"></auth-container-page>
      <div class="manage-container">
        <div class="manage-main">
          <sub-nav :sub-nav-list="menuList" :show-sub-nav="showSubNav"></sub-nav>
          <router-view class="manage-content" :key="refreshKey"></router-view>
        </div>
      </div>
    </div>
  </bk-navigation>

</template>

<script>
  import SubNav from '@/components/nav/manage-nav';
import { mapState } from 'vuex';
import { isFeatureToggleOn } from '@/store/helper';

  export default {
    name: 'ManageIndex',
    components: {
      SubNav,
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
        isExpand: true,
        refreshKey: '',
      };
    },
    created() {
      this.refreshKey = this.buildRefreshKey();
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
        return (this.topMenu || []).find(item => item.id === 'manage')?.children || [];
      },
      menuList() {
        const list = (this.manageNavList || [])
          .filter(Boolean)
          .map(menu => ({
            ...menu,
            children: menu.children || [],
          }));
        if (this.isExternal) {
          // 外部版只保留【日志提取】菜单
          return list.filter(menu => menu.id === 'manage-extract-strategy');
        }
        return list;
      },
      activeManageNav() {
        if (this.isHeadless) {
          return {};
        }
        const childList = this.menuList
          .map(m => m.children || [])
          .flat(2)
          .filter(Boolean);
        return childList.find(t => t.id === this.$route.meta?.navId) ?? {};
      },
      isHeadless() {
        return this.$route.query.hl === '1';
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

          // 检查当前是否在 log_manage_v2 需要隐藏的路由
          const isV2HiddenRoute = this.checkIfV2HiddenRoute();
          if (isV2HiddenRoute && this.checkLogManageV2()) {
            this.redirectToFirstMenuItem();
            return;
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
            this.updateRefreshKey();
          });
        }
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
        this.updateRefreshKey();
      });
      if (!this.isHeadless) {
        setTimeout(() => {
          this.handleToggle(true);
        }, 10);
      }
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
      handleClickNavItem(id) {
        if (!this.isValidRouteName(id)) return;
        this.$router.push({
          name: id,
          query: {
            spaceUid: this.$store.state.spaceUid,
          },
        });
      },
      handleToggle(data) {
        if (typeof data === 'boolean') {
          this.isExpand = data;
        }
      },
      // 获取当前路由的最外层路径，用于切换业务时跳转到菜单栏目录项
      getTopLevelRoute() {
        const currentPath = this.$route.path;
        const match = currentPath.match(/^\/manage\/([^/]+)/);  // 匹配 /manage/xxx 的模式

        if (match) return match[1]; // 返回紧跟 /manage 的路径段

        return 'manage';
      },
      isValidRouteName(name) {
        if (!name) return false;
        return this.$router.getRoutes().some(route => route.name === name);
      },
      getGroupChildren(list = []) {
        const safeList = (list || []).filter(Boolean);
        if (this.isExternal) {
          // 外部版只保留【日志提取任务】
          return safeList.filter(menu => menu.id === 'log-extract-task' && this.isValidRouteName(menu.id));
        }
        // 仅展示已注册的路由项，过滤 collectAccess / addIndexSet 等权限元数据菜单
        return safeList.filter(menu => this.isValidRouteName(menu.id));
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
</style>
