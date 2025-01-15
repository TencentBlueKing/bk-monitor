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
    v-bkloading="{ isLoading: loading || inLoading }"
    class="alarm-shield-config"
  >
    <div class="header">
      <common-nav-bar
        :route-list="navRouteList"
        :need-back="true"
      />
      <bk-tab
        :active="tab.active"
        type="unborder-card"
        class="tab-wrap"
        @tab-change="handleTabChange"
      >
        <bk-tab-panel
          v-for="(item, index) in tab.list
            .filter(item =>
              ['alarm-shield-clone', 'alarm-shield-edit'].includes($route.name)
                ? item.componentName === curComponent
                : item.componentName !== 'alarm-shield-event'
            )
            .map(item => ({
              name: item.id,
              label: item.name,
            }))"
          v-bind="item"
          :key="index"
        />
      </bk-tab>
    </div>
    <div class="container">
      <!-- <ul class="tab-list">
        <li
          class="tab-list-item"
          v-for="(item, index) in tab.list"
          :class="{ 'tab-active': index === tab.active }"
          :key="item.name"
          v-show="
            $route.name === 'alarm-shield-edit'
              ? item.componentName === curComponent
              : item.componentName !== 'alarm-shield-event'
          "
          @click="handleTabChange(index, item.componentName)"
        >
          <span class="tab-name">{{ item.name }}</span>
        </li>
        <li class="tab-list-blank"></li>
      </ul> -->
      <div class="set-config-wrapper">
        <keep-alive>
          <component
            :is="curComponent"
            v-model="commonDateData"
            :shield-data="shieldData"
            :loading.sync="loading"
            :edit="edit"
          />
        </keep-alive>
      </div>
    </div>
  </div>
</template>
<script>
import { frontendCloneInfo, frontendShieldDetail } from 'monitor-api/modules/shield';

import { SET_NAV_ROUTE_LIST } from '../../../store/modules/app';
import CommonNavBar from '../../monitor-k8s/components/common-nav-bar.tsx';
import AlarmShieldDimension from './alarm-shield-dimension.tsx';
import AlarmShieldEvent from './alarm-shield-event';
import AlarmShieldScope from './alarm-shield-scope/alarm-shield-scope';
import AlarmShieldStrategy from './alarm-shield-strategy';

export default {
  name: 'AlarmShieldSet',
  components: {
    AlarmShieldScope,
    AlarmShieldStrategy,
    AlarmShieldEvent,
    AlarmShieldDimension,
    CommonNavBar,
  },
  // beforeRouteEnter(to, from, next) {
  //   next((vm) => {
  //     if (to.name === 'alarm-shield-edit') {
  //       vm.handleGetShieldDetail()
  //       vm.curComponent = vm.typeMap[to.params.type]
  //       const index = vm.tab.list.findIndex(item => item.componentName === vm.curComponent)
  //       vm.tab.active = vm.tab.list[index].id
  //     } else {
  //       vm.curComponent = 'alarm-shield-scope'
  //     }
  //   })
  // },
  async beforeRouteLeave(to, from, next) {
    if (!to.params.refresh) {
      const needNext = await this.handleCancel(false);
      next(needNext);
    } else {
      next();
    }
  },
  data() {
    return {
      commonDateData: {
        shieldCycle: {
          list: [
            { label: this.$t('单次'), value: 'single' },
            { label: this.$t('每天'), value: 'day' },
            { label: this.$t('每周'), value: 'week' },
            { label: this.$t('每月'), value: 'month' },
          ],
          value: 'single',
        },
        noticeDate: {
          single: {
            list: [],
            range: [],
          },
          day: {
            list: [],
            range: ['00:00:00', '23:59:59'],
          },
          week: {
            list: [],
            range: ['00:00:00', '23:59:59'],
          },
          month: {
            list: [],
            range: ['00:00:00', '23:59:59'],
          },
        },
        hasTimeRange: true,
        hasDateRange: true,
        hasWeekList: true,
        hasMonthList: true,
        dateRange: [],
      },
      inLoading: false,
      loading: false,
      tab: {
        active: 0,
        list: [
          { name: this.$t('基于范围进行屏蔽'), id: 0, componentName: 'alarm-shield-scope' },
          { name: this.$t('基于策略进行屏蔽'), id: 1, componentName: 'alarm-shield-strategy' },
          { name: this.$t('基于告警事件进行屏蔽'), id: 2, componentName: 'alarm-shield-event' },
          { name: this.$t('基于维度进行屏蔽'), id: 3, componentName: 'alarm-shield-dimension' },
        ],
      },
      curComponent: '',
      typeMap: {
        scope: 'alarm-shield-scope',
        strategy: 'alarm-shield-strategy',
        event: 'alarm-shield-event',
        alert: 'alarm-shield-event',
        dimension: 'alarm-shield-dimension',
      },
      shieldData: {},
      edit: false,
    };
  },
  computed: {
    navRouteList() {
      return this.$store.getters.navRouteList;
    },
  },
  created() {
    // if (this.$route.name === 'alarm-shield-edit') {
    //   this.handleGetShieldDetail();
    //   this.curComponent = this.typeMap[this.$route.params.type];
    //   this.tab.active = this.tab.list.find((item) => item.componentName === this.curComponent).id;
    //   // this.tab.active = this.tab.list[index].id;
    // } else {
    //   this.updateNavData(this.$tc('新建屏蔽'));
    //   this.curComponent = 'alarm-shield-scope';
    // }

    // 跳转后根据操作类型处理对应逻辑
    this.handleGetShieldDetail(this.$route.name);
    if (this.$route.name === 'alarm-shield-edit') {
      this.updateNavData(this.$t('route-编辑屏蔽'));
    } else {
      this.updateNavData(this.$t('route-新建屏蔽'));
    }
  },
  methods: {
    handleTabChange(active) {
      if (this.tab.active !== active) {
        this.tab.active = active;
        this.curComponent = this.tab.list.find(item => item.id === active).componentName;
      }
    },
    handleCancel(needBack = true) {
      return new Promise(resolve => {
        this.$bkInfo({
          title: this.$t('是否放弃本次操作？'),
          confirmFn: () => {
            needBack && this.$router.back();
            resolve(true);
          },
          cancelFn: () => resolve(false),
        });
      });
    },

    // 判断是否处理详情数据
    handleGetShieldDetail(actionType) {
      let actionTitle = '新建屏蔽';
      this.loading = true;

      if (['alarm-shield-edit', 'alarm-shield-clone'].includes(actionType)) {
        this.curComponent = this.typeMap[this.$route.params.type];
        this.tab.active = this.tab.list.find(item => item.componentName === this.curComponent).id;
      }

      switch (actionType) {
        case 'alarm-shield-edit':
          this.edit = true;
          actionTitle = `${this.$t('编辑')} #${this.$route.params.id}`;
          frontendShieldDetail({ id: this.$route.params.id })
            .then(data => {
              this.shieldData = data;
            })
            .finally(() => {
              this.loading = false;
            });
          break;
        case 'alarm-shield-clone':
          actionTitle = `${this.$t('克隆')} #${this.$route.params.id}`;
          frontendCloneInfo({ id: this.$route.params.id })
            .then(data => {
              this.shieldData = data;
            })
            .finally(() => {
              this.loading = false;
            });
          break;
        default:
          this.loading = false;
          this.curComponent = 'alarm-shield-scope';
          break;
      }

      this.updateNavData(actionTitle);
    },

    /** 更新面包屑 */
    updateNavData(name = '') {
      if (!name) return;
      const routeList = [];
      routeList.push({
        name,
        id: '',
      });
      this.$store.commit(`app/${SET_NAV_ROUTE_LIST}`, routeList);
    },
  },
};
</script>
<style lang="scss" scoped>
.alarm-shield-config {
  // border: 1px solid #dcdee5;
  // background: #fff;
  // min-height: calc(100vh - 140px);
  // margin: 20px;
  .header {
    width: 100%;
    height: 88px;
    padding: 0 27px;
    background: #fff;
    box-shadow: 0 3px 4px 0 rgba(64, 112, 203, 0.06);

    .common-nav-bar {
      box-shadow: none;
    }

    .tab-wrap {
      margin-top: -13px;
    }
  }

  .container {
    min-height: calc(100vh - 140px);
    max-height: calc(100vh - 140px);
    padding: 20px;
    overflow-y: auto;

    .set-config-wrapper {
      background: #fff;
      border: 1px solid #dcdee5;
    }
  }
  // .tab-list {
  //   display: flex;
  //   flex-direction: row;
  //   justify-content: flex-start;
  //   align-items: center;
  //   line-height: 42px;
  //   background: #fafbfd;
  //   padding: 0;
  //   margin: 0;
  //   font-size: 14px;
  //   &-item {
  //     flex: 0 0 213px;
  //     border-right: 1px solid #dcdee5;
  //     border-bottom: 1px solid #dcdee5;
  //     text-align: center;
  //     color: #63656e;
  //     font-weight: bold;
  //     &.tab-active {
  //       color: #3a84ff;
  //       background: #fff;
  //       border-bottom-color: transparent;
  //       font-weight: bold;
  //     }
  //     &:hover {
  //       cursor: pointer;
  //       color: #3a84ff;
  //       font-weight: bold;
  //     }
  //   }
  //   &-blank {
  //     flex: 1 1 auto;
  //     height: 42px;
  //     border-bottom: 1px solid #dcdee5;
  //   }
  // }
}
</style>
