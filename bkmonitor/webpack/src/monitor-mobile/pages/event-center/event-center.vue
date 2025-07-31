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
  <div class="event-center">
    <event-tab
      v-model="curTab"
      class="tab-list"
      :tab-list="tabList"
      @change="changeTab"
    />
    <van-list
      ref="vanList"
      v-model="loading"
      class="card-list"
      :finished="finished"
      :finished-text="noDataText"
      :immediate-check="false"
      :offset="10"
      @load="getData"
    >
      <div class="event-center-content">
        <van-row
          v-show="curTab !== 'target'"
          gutter="11"
        >
          <van-col
            v-for="(item, index) in typeList"
            :key="index"
            span="8"
          >
            <select-button
              :active="curType.includes(item.type)"
              :icon="item.icon"
              :text="item.text"
              @click="changeType(item.type)"
            />
          </van-col>
        </van-row>
        <div
          v-if="listData.length"
          :class="['event-center-list', { 'event-center-not-pt': curTab === 'target' }]"
        >
          <event-list-item
            v-for="(item, index) in listData"
            :key="item.strategyId + '-' + index"
            :item-data="item"
          />
        </div>
      </div>
    </van-list>
  </div>
</template>
<script lang="ts">
import { Component, Prop, Vue, Watch } from 'vue-property-decorator';

import { Col, List, Row } from 'vant';

import SelectButton from '../../components/select-button/select-button.vue';
import EventCenterModule from '../../store/modules/event-center';
import EventListItem from './event-list-item.vue';
import EventTab from './event-tab.vue';

export interface IListItem {
  level: string;
  name: string;
  strategyId: number;
  events: {
    dimensionMessage: string;
    duration: string;
    eventId: number;
    target: string;
  }[];
}
export interface ITabItem {
  count: number;
  shortTitle?: string;
  title: string;
  value: number | string;
}
interface IEventCenterData {
  curTab: string;
  curType: string;
  loading: boolean;
  tabList: ITabItem[];
  typeList: ITypeList[];
}
interface ITypeList {
  icon: string;
  text: string;
  type: string;
  value: number;
}

@Component({
  name: 'event-center',
  components: {
    EventTab,
    SelectButton,
    EventListItem,
    [List.name]: List,
    [Col.name]: Col,
    [Row.name]: Row,
  },
})
export default class EventCenter extends Vue implements IEventCenterData {
  // loading
  loading = false;
  // 当前tab
  curTab = 'strategy';
  // 当前类型
  curType = '';
  // tab配置
  tabList = [];
  // 类型选项配置
  typeList = [];
  timer = null;
  @Prop() readonly routeKey: string;

  created() {
    this.getList();
    this.tabList = [
      {
        title: this.$tc('未恢复事件'),
        shortTitle: this.$tc('未恢复'),
        value: 'strategy',
        count: 0,
      },
      {
        title: this.$tc('异常目标'),
        shortTitle: this.$tc('异常目标'),
        value: 'target',
        count: 0,
      },
      {
        title: this.$tc('已屏蔽事件'),
        shortTitle: this.$tc('已屏蔽'),
        value: 'shield',
        count: 0,
      },
    ];
    this.typeList = [
      {
        type: '1',
        text: this.$tc('致命'),
        icon: 'icon-danger',
        value: 1,
      },
      {
        type: '2',
        text: this.$tc('预警'),
        icon: 'icon-mind-fill',
        value: 2,
      },
      {
        type: '3',
        text: this.$tc('提醒'),
        icon: 'icon-tips',
        value: 3,
      },
      // {
      //     type: 'me',
      //     text: this.$tc('我的'),
      //     icon: 'icon-user',
      //     value: 4
      // }
    ];
  }

  // 无数据提示
  get noDataText() {
    return this.listData.length ? this.$tc('没有更多了') : this.$tc('查无数据');
  }

  // 页面显示的list数据
  get listData() {
    return EventCenterModule.viewList;
  }

  // 统计数据
  get count() {
    return EventCenterModule.count;
  }

  // 数据加载完成状态
  get finished() {
    return EventCenterModule.finished;
  }

  @Watch('routeKey')
  onRouteKeyChange() {
    this.getList();
  }

  // 改变告警类型
  changeType(type: string) {
    this.timer && clearTimeout(this.timer);
    this.curType = type === this.curType ? '' : type;
    EventCenterModule.getFilterLIst(this.curType);
    EventCenterModule.setListData({
      viewList: [],
      finished: false,
      page: 1,
    });
    EventCenterModule.addPage();
  }

  // 获取数据
  async getList() {
    await EventCenterModule.getAllList({ type: this.curTab });
    this.tabList.forEach(item => {
      item.count = this.count[item.value];
    });
    EventCenterModule.setListData({
      page: 1,
      finished: false,
    });
    EventCenterModule.addPage();
  }

  // 改变tab
  changeTab() {
    this.timer && clearTimeout(this.timer);
    EventCenterModule.setListData({
      allList: [],
      filterList: [],
      page: 1,
      viewList: [],
      finished: false,
    });
    this.loading = false;
    this.curType = '';
    this.getList();
  }

  // 加载数据
  async getData() {
    if (!this.listData.length) return (this.loading = false);
    this.loading = true;
    EventCenterModule.setListData({
      page: EventCenterModule.page + 1,
    });
    EventCenterModule.addPage();
    this.loading = false;
  }
}
</script>
<style lang="scss" scoped>
@import '../../static/scss/variate';

.event-center {
  box-sizing: border-box;
  height: 100vh;
  padding-top: 48px;
  padding-bottom: 53px;
  overflow: auto;
  background-color: #efefef;
  -webkit-overflow-scrolling: touch;

  .tab-list {
    position: fixed;
    top: 0;
    left: 0;
    z-index: 1;
    width: 100%;
  }

  &-content {
    padding: 16px 16px 0;
  }

  &-list {
    padding-top: 10px;
  }

  &-not-pt {
    padding-top: 0;
  }
}
</style>
