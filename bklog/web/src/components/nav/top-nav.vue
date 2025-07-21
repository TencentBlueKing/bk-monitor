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
  <section class="log-search-top-nav">
    <div class="top-nav-content">
      <div
        v-if="title"
        class="top-nav-title fl"
      >
        <div
          v-if="title === $t('数据采样')"
          class="skip"
        >
          <span @click="clickSkip('collectAccess')">{{ $t('采集接入') }} / </span>
          <span @click="clickSkip('allocation')">{{ $t('采集状态') }} / </span>
          {{ title }}
        </div>
        <div
          v-else
          style="display: flex; align-items: center"
        >
          <i
            class="bk-icon icon-arrows-left title-btn-back"
            @click.stop="goBack"
          ></i>
          {{ title }}
        </div>
      </div>
      <div
        v-else
        class="top-nav-title title-roll fl"
      >
        {{ menu.name }}
      </div>
      <ul
        v-if="!title && menu.children"
        class="top-nav-list fl"
      >
        <li
          v-for="item in menu.children"
          :class="{ active: routerName === item.id, 'text-disabled': item.id === 'esAccess' && !collectProject }"
          :key="item.id"
          @click="routerHandler(item)"
        >
          {{ item.name }}
        </li>
      </ul>
    </div>
  </section>
</template>

<script>
import { projectManage } from '@/common/util';
import { mapState } from 'vuex';

export default {
  name: 'TopNav',
  components: {},
  props: {
    title: {
      type: String,
      default: '',
    },
    menu: {
      type: Object,
      default() {
        return {};
      },
    },
    goBack: {
      type: Function,
      default() {
        this.getParentRoute(this.currentMenu, null);
        if (this.parentRoute) {
          this.$router.replace({
            name: this.parentRoute,
            query: {
              spaceUid: this.$store.state.spaceUid,
            },
          });
        }
      },
    },
  },
  data() {
    return {
      parentRoute: '',
    };
  },
  computed: {
    ...mapState({
      currentMenu: state => state.currentMenu,
      menuProject: state => state.menuProject,
    }),
    routerName() {
      return this.$route.name;
    },
    collectProject() {
      return projectManage(this.menuProject, 'manage', 'manage');
    },
  },
  methods: {
    routerHandler(menu) {
      if (menu.id === 'esAccess' && !this.collectProject) return;
      if (menu.id !== this.routerName) {
        this.$router.push({
          name: menu.id,
          query: {
            spaceUid: this.$store.state.spaceUid,
          },
        });
      }
    },
    getParentRoute(routeMenu, parent) {
      if (routeMenu.id === this.routerName) {
        this.parentRoute = parent ? parent.id : routeMenu.id;
        return false;
      }
      if (routeMenu.children) {
        routeMenu.children.forEach(child => {
          this.getParentRoute(child, routeMenu);
        });
      }
    },
    clickSkip(val) {
      this.$router.push({
        name: val,
        hash: '#hisitory',
        query: {
          spaceUid: this.$store.state.spaceUid,
        },
      });
    },
  },
};
</script>

<style lang="scss">
  @import '../../scss/mixins/clearfix';
  @import '../../scss/conf';

  .log-search-top-nav {
    padding: 0 60px;
    font-size: 14px;

    @include clearfix;

    .top-nav-content {
      height: 60px;
      padding: 20px 0;
      line-height: 20px;
      border-bottom: 1px solid $borderWeightColor;

      @include clearfix;
    }

    .top-nav-title {
      padding: 0 28px 0 10px;
      font-weight: 600;

      &.title-roll {
        border-left: 2px solid #a3c5fd;
      }

      .title-btn-back {
        font-size: 20px;
        font-weight: 600;
        color: #3a84ff;
        cursor: pointer;
      }
    }

    .top-nav-list {
      color: #313238;
      border-left: 1px solid $borderWeightColor;

      @include clearfix;

      li {
        float: left;
        margin-left: 26px;
        cursor: pointer;

        &.active {
          color: #3a84ff;
        }
      }

      span {
        float: left;
        margin-left: 26px;
        cursor: pointer;
      }

      .nav-col {
        color: #3a84ff;
      }
    }

    .skip {
      /* stylelint-disable-next-line declaration-no-important */
      font-weight: normal !important;
      color: #64656e;

      span {
        color: #979ba5;
        cursor: pointer;
      }

      span:hover {
        color: #64656e;
      }
    }

    .text-disabled {
      color: #c4c6cc;
    }

    .text-disabled:hover {
      color: #c4c6cc;
      cursor: not-allowed;
    }
  }
</style>
