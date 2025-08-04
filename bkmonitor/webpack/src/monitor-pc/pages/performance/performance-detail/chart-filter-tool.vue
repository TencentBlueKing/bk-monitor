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
  <div class="chart-tool">
    <compare-panel
      :value="value"
      :chart-type="chartType"
      :compare-list="compareList"
      :target-list="targetList"
      :timeshift-list="timeshiftList"
      :timerange-list="timerangeList"
      :need-split="needSplit"
      :need-search-select="true"
      :cur-host="curNode"
      @change="handleToolChange"
      @chart-change="handleChartChange"
      @add-timerange-option="handleAddTimeRangeOption"
      @add-timeshift-option="handleAddTimeshifOption"
      @on-immediate-refresh="handleImmediateRefresh"
    >
      <template #pre>
        <span
          v-show="!listVisible"
          class="tool-icon right"
          @click="handleShowList"
        >
          <i class="arrow-right icon-monitor icon-double-up" />
        </span>
        <div class="chart-tool-left bk-button-group">
          <bk-button
            :class="{ 'is-selected': viewType === 'host' }"
            @click="handleViewChange('host')"
          >
            {{ $t('button-主机') }}
          </bk-button>
          <bk-button
            :class="{ 'is-selected': viewType === 'process' }"
            @click="handleViewChange('process')"
          >
            {{ $t('进程') }}
          </bk-button>
        </div>
        <div
          v-if="curNode.type === 'node'"
          class="chart-tool-agg"
        >
          <span class="label">{{ $t('汇聚') }}：</span>
          <drop-down-menu
            v-model="method"
            class="content"
            :list="aggMethods"
            @change="handleAggMethodChange"
          />
        </div>
      </template>
      <template #search>
        <div class="tool-search">
          <i class="bk-icon icon-search tool-search-icon" />
          <input
            v-model="search.value"
            :style="{ width: search.focus || search.value ? '140px' : '40px' }"
            class="tool-search-input"
            :placeholder="$t('搜索')"
            @focus="search.focus = true"
            @blur="search.focus = false"
            @input="searchFn"
          />
        </div>
      </template>
      <template #append>
        <div class="chart-tool-right">
          <span
            v-if="groupsData.length"
            v-authority="{ active: !authority.MANAGE_AUTH }"
            class="tool-icon"
            @click="authority.MANAGE_AUTH ? handleSettingChart() : handleShowAuthorityDetail(authorityMap.MANAGE_AUTH)"
          >
            <i class="icon-monitor icon-setting" />
          </span>
          <span
            v-show="!detailVisible"
            class="tool-icon"
            @click="handleShowDetail"
          >
            <i class="arrow-left icon-monitor icon-double-up" />
          </span>
        </div>
      </template>
    </compare-panel>
    <sort-panel
      v-if="groupsData.length"
      v-model="showSetting"
      :groups-data="groupsData"
      :loading="sortLoading"
      :need-group="viewType === 'host'"
      @save="handleSortChange"
      @undo="handleUndo"
    />
  </div>
</template>
<script lang="ts">
import { Component, Emit, Inject, Prop, Vue } from 'vue-property-decorator';

import { debounce } from 'throttle-debounce';

import { DEFAULT_TIME_RANGE_LIST, DEFAULT_TIMESHIFT_LIST } from '../../../common/constant';
import DropDownMenu from '../../../components/monitor-dropdown/dropdown-menu.vue';
import PerformanceModule, { type ICurNode } from '../../../store/modules/performance';
import ComparePanel from './compare-panel.vue';
import SortPanel from './sort-panel.vue';

import type { ICompareOption, IHostGroup, IOption, IToolsOption, ViewType } from '../performance-type';

@Component({
  name: 'chart-filter-tool',
  components: {
    SortPanel,
    ComparePanel,
    DropDownMenu,
  },
})
export default class ChartFilterTool extends Vue {
  @Prop({ default: () => [], type: Array }) readonly groupsData: IHostGroup[];
  @Prop({ default: true }) readonly listVisible: boolean;
  @Prop({ default: true }) readonly detailVisible: boolean;
  @Prop({ default: false }) readonly needSplit: boolean;
  @Prop({ default: 0 }) readonly chartType: 0 | 1 | 2;
  @Prop({ required: true }) readonly viewType: ViewType;
  @Prop({ required: true }) readonly value: { compare: ICompareOption; tools: IToolsOption };
  @Prop({ required: true }) readonly curNode: ICurNode;
  @Prop({ type: String, default: '' }) readonly defaultMethod!: string;

  @Inject('authority') authority;
  @Inject('handleShowAuthorityDetail') handleShowAuthorityDetail;
  @Inject('authorityMap') authorityMap;
  private showSetting = false;
  private sortLoading = false;
  // private compareList: IOption[] = []
  private timeshiftList: IOption[] = [];
  private timerangeList: IOption[] = [];
  private search: { focus: false; value: string } = { focus: false, value: '' };
  private searchFn: Function = null;
  private aggMethods: IOption[] = [
    {
      id: 'AVG',
      name: 'AVG',
    },
    {
      id: 'SUM',
      name: 'SUM',
    },
    {
      id: 'MIN',
      name: 'MIN',
    },
    {
      id: 'MAX',
      name: 'MAX',
    },
  ];
  private method = this.defaultMethod;
  // 主机IP列表
  get targetList() {
    if (this.curNode.type === 'node') return [];

    return PerformanceModule.hosts
      .map(item => ({ id: `${item.bk_cloud_id}-${item.bk_host_innerip}`, name: item.bk_host_innerip }))
      .filter(item => item.id !== `${this.curNode.cloudId}-${this.curNode.ip}`);
  }
  created() {
    this.timerangeList = DEFAULT_TIME_RANGE_LIST;
    this.timeshiftList = DEFAULT_TIMESHIFT_LIST;
    this.searchFn = debounce(300, this.handleSearchValueChange);
  }
  get compareList(): IOption[] {
    const list = [
      {
        id: 'none',
        name: this.$t('不对比'),
      },
      {
        id: 'time',
        name: this.$t('时间对比'),
      },
    ];

    if (this.curNode?.type === 'host') {
      list.push({
        id: 'target',
        name: this.$t('目标对比'),
      });
    }
    // if (this.viewType === 'host') {
    //   list.push({
    //     id: 'target',
    //     name: this.$t('目标对比')
    //   })
    // }
    return list;
  }
  @Emit('view-change')
  handleViewChange(v) {
    return v;
  }

  @Emit('tool-change')
  handleToolChange(params) {
    return params;
  }

  // 图表设置
  handleSettingChart() {
    this.showSetting = true;
  }
  // 显示左侧主机列表
  @Emit('show-list')
  handleShowList() {
    return true;
  }

  @Emit('show-detail')
  handleShowDetail() {
    return true;
  }

  @Emit('sort-change')
  async handleSortChange(data: IHostGroup[]) {
    this.sortLoading = true;
    const success = await PerformanceModule.saveDashboardOrder({
      order: data,
      id: this.viewType,
    });
    this.sortLoading = false;
    if (success) {
      this.showSetting = false;
    }
  }

  @Emit('sort-change')
  async handleUndo() {
    this.sortLoading = true;
    const success = await PerformanceModule.deletePanelOrder(this.viewType);
    this.sortLoading = false;
    if (success) {
      this.showSetting = false;
    }
  }
  // 图表类型转换
  @Emit('chart-change')
  handleChartChange(type: number) {
    return type;
  }
  // 添加自定义时间对比
  handleAddTimeshifOption(v: string) {
    v.trim().length &&
      !this.timeshiftList.some(item => item.id === v) &&
      this.timeshiftList.push({
        id: v,
        name: v,
      });
  }
  handleAddTimeRangeOption(option: IOption) {
    this.timerangeList.push(option);
  }
  // 刷新数据
  @Emit('immediate-reflesh')
  handleImmediateRefresh() {
    return this.viewType;
  }
  @Emit('search-change')
  handleSearchValueChange() {
    return this.search.value;
  }
  @Emit('method-change')
  handleAggMethodChange() {
    return this.method;
  }
}
</script>
<style lang="scss" scoped>
@mixin icon-arrow($rotate: 0) {
  font-size: 24px;
  color: #979ba5;
  cursor: pointer;
  transform: rotate($rotate);
}

.chart-tool {
  height: 42px;
  background: #fff;

  &-agg {
    display: flex;
    align-items: center;
    width: 120px;
    border-right: 1px solid #f0f1f5;

    .label {
      padding-left: 10px;
    }

    .content {
      position: relative;
      top: 1px;
      flex: 1;

      :deep(.dropdown-trigger) {
        padding: 0 10px 0 5px;
      }
    }
  }

  .arrow-right {
    @include icon-arrow(90deg);
  }

  .arrow-left {
    @include icon-arrow(-90deg);
  }

  .tool-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 48px;
    height: 42px;
    font-size: 14px;
    color: #979ba5;
    cursor: pointer;
    border-left: 1px solid #f0f1f5;

    &.right {
      border-right: 1px solid #f0f1f5;
    }
  }

  &-left {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0 14px;
    border-right: 1px solid #f0f1f5;

    :deep(.bk-button) {
      font-size: 12px;
    }
  }

  &-right {
    display: flex;
  }

  .tool-search {
    display: flex;
    align-items: center;
    min-width: 78px;
    height: 32px;
    padding-left: 18px;
    font-size: 12px;
    color: #63656e;

    &-icon {
      margin-right: 5px;
      font-size: 14px;
      color: #737987;
    }

    &-input {
      width: 40px;
      border: 0;
    }
  }
}
</style>
