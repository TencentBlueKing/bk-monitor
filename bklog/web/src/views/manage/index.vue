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
      }
    },
    watch: {
      '$route.query.spaceUid'(newSpaceUid, oldSpaceUid) {
        if (newSpaceUid !== oldSpaceUid) {
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
      }
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
</style>
