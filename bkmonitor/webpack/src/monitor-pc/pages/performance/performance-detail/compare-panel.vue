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
  <div :class="['compare-panel', { 'has-favorites-list': hasFavoritesList }]">
    <slot name="pre" />
    <div
      ref="panelWrap"
      class="panel-wrap"
    >
      <div
        v-if="!compareHide"
        v-en-style="'width: 150px'"
        class="panel-wrap-left"
      >
        <drop-down-menu
          v-model="compare.type"
          :list="compareList"
          @change="handleChangeType"
        />
      </div>
      <div :class="['panel-wrap-center', { 'no-compare': compareHide }]">
        <div
          v-if="compare.type === 'target' && curHost && curHost.ip"
          class="center-maintag"
        >
          <span
            class="tag"
            :title="curHost.ip"
          >
            {{ curHost.ip }}
          </span>
        </div>
        <slot
          name="content"
          v-bind="{ compare }"
        >
          <!-- 目标对比 -->
          <div
            v-if="compare.type === 'target' && needTarget"
            class="target-select"
          >
            <bk-select
              ref="targetSelect"
              v-model="compare.value"
              :clearable="false"
              :placeholder="$t('选择目标')"
              :popover-width="200"
              display-tag
              multiple
              searchable
              @change="handleValueChange('compare')"
              @toggle="handleSelectToggle"
            >
              <bk-option
                v-for="option in targetList"
                :id="option.id"
                :key="option.id"
                :name="option.name"
              />
              <div
                v-if="refTargetSelect && showClearBtn"
                class="target-select-clear"
              >
                <span
                  class="clear-btn"
                  @click="deleteSelected"
                >
                  {{ $t('清空') }}
                </span>
              </div>
            </bk-select>
          </div>
          <!-- 时间对比 -->
          <bk-select
            v-else-if="compare.type === 'time'"
            ref="timeSelect"
            class="time-select"
            v-model="compare.value"
            v-en-class="'en-lang'"
            :clearable="false"
            multiple
            @change="handleValueChange('compare')"
            @toggle="handleSelectToggle"
          >
            <bk-option
              v-for="item in timeshiftList"
              :id="item.id"
              :key="item.id + item.name"
              :name="item.name"
            />
            <div>
              <div
                class="time-select-custom"
                @click.prevent.stop="handleCustomClick"
              >
                <span
                  v-if="!custom.show"
                  class="custom-text"
                >
                  {{ $t('自定义') }}
                </span>
                <bk-input
                  v-else
                  v-model.trim="custom.value"
                  size="small"
                  @keydown.enter.native="handleAddCustomTime"
                />
                <span
                  v-if="custom.show"
                  class="help-icon icon-monitor icon-mc-help-fill"
                  v-bk-tooltips.top="$t('自定义输入格式: 如 1w 代表一周 m 分钟 h 小时 d 天 w 周 M 月 y 年')"
                />
              </div>
            </div>
          </bk-select>
          <!-- 不对比: 视图拆分 -->
          <div
            v-else-if="needSplit && compare.type === 'none'"
            class="split-btn-wrapper"
          >
            <i
              :class="['icon-monitor', compare.value ? 'icon-hebing' : 'icon-chaifen icon-active']"
              @click="handleSplit"
            />
          </div>
          <favorites-list
            v-if="hasFavoritesList"
            class="favorites-list"
            :checked-value="favCheckedValue"
            :value="favoritesList"
            @deleteFav="handleDeleteFav"
            @selectFav="emitSelectFav"
          />
          <span class="margin-left-auto" />
          <div
            v-if="needSearchSelect"
            class="search-selector-wrapper search-select-active"
          >
            <slot name="search">
              <div class="search-select">
                <search-select
                  :data="searchSelectList"
                  :placeholder="$t('搜索')"
                  :value="tools.searchValue"
                  @change="handleSearchSelectChange"
                >
                  <i
                    class="bk-icon icon-search"
                    slot="prepend"
                  />
                </search-select>
              </div>
            </slot>
          </div>
          <div class="time-shift">
            <time-range
              :value="tools.timeRange"
              @change="handleTimeRangeChange"
            />
            <!-- <monitor-date-range
              :key="dateRangeKey"
              icon="icon-mc-time-shift"
              class="time-shift-select"
              @add-option="handleAddOption"
              dropdown-width="96"
              v-model="tools.timeRange"
              @change="handleTimeRangeChange"
              :options="timerangeList"
              :style="{ minWidth: showText ? '100px' : '40px' }"
              :show-name="showText"
              :z-index="2500"
            >
            </monitor-date-range> -->
          </div>
          <drop-down-menu
            class="time-interval"
            v-model="tools.refreshInterval"
            :is-refresh-interval="true"
            :list="refreshList"
            :show-name="showText"
            :text-active="tools.refreshInterval !== -1"
            icon="icon-zidongshuaxin"
            @change="handleValueChange('interval')"
            @on-icon-click="$emit('on-immediate-refresh')"
          />
        </slot>
      </div>
      <div
        v-if="hasViewChangeIcon"
        class="panel-wrap-right"
      >
        <span
          class="tool-icon"
          @click="handleViewChange"
        >
          <i
            class="icon-monitor"
            :class="iconList[chartType]"
          />
        </span>
      </div>
    </div>
    <slot name="append" />
  </div>
</template>
<script lang="ts">
import { Component, Emit, Prop, Ref, Vue, Watch } from 'vue-property-decorator';

import { addListener, removeListener } from '@blueking/fork-resize-detector';
import SearchSelect from '@blueking/search-select-v3/vue2';

import { DEFAULT_REFLESH_LIST } from '../../../common/constant';
import MonitorDateRange from '../../../components/monitor-date-range/monitor-date-range.vue';
import DropDownMenu from '../../../components/monitor-dropdown/dropdown-menu.vue';
import TimeRange, { type TimeRangeType } from '../../../components/time-range/time-range';
import { PERFORMANCE_CHART_TYPE } from '../../../constant/constant';
import { getRandomId } from '../../../utils';
import FavoritesList from '../../data-retrieval/favorites-list/favorites-list';

import type { IDataRetrieval, IFavList } from '../../data-retrieval/typings';
import type {
  ChartType,
  ICompareChangeType,
  ICompareOption,
  IOption,
  ISearchSelectList,
  IToolsOption,
} from '../performance-type';

import '@blueking/search-select-v3/vue2/vue2.css';

const DEAULT_TIME_RANGE = [
  {
    name: window.i18n.t('1 小时'),
    value: 1 * 60 * 60 * 1000,
  },
  {
    name: window.i18n.t('1 天'),
    value: 24 * 60 * 60 * 1000,
  },
  {
    name: window.i18n.t('7 天'),
    value: 168 * 60 * 60 * 1000,
  },
  {
    name: window.i18n.t('1 个月'),
    value: 720 * 60 * 60 * 1000,
  },
];
@Component({
  name: 'compare-panel',
  components: {
    DropDownMenu,
    MonitorDateRange,
    FavoritesList,
    TimeRange,
    SearchSelect,
  },
})
export default class ComparePanel extends Vue {
  @Ref('panelWrap') refPanelWrap: HTMLDivElement;
  @Ref('timeSelect') refTimeSelect: Vue;
  @Ref('targetSelect') refTargetSelect: Vue;
  @Prop({ default: 1 }) readonly chartType: ChartType;
  @Prop({ default: true }) readonly hasViewChangeIcon: boolean;
  // 维度列表
  @Prop({
    default: () => [
      {
        id: 'none',
        name: window.i18n.t('不对比'),
      },
      {
        id: 'target',
        name: window.i18n.t('目标对比'),
      },
      {
        id: 'time',
        name: window.i18n.t('时间对比'),
      },
    ],
    type: Array,
  })
  readonly compareList: IOption[];
  // 对比时间list
  @Prop({
    default: () => [
      {
        id: '1h',
        name: window.i18n.t('1 小时前'),
      },
      {
        id: '1d',
        name: window.i18n.t('昨天'),
      },
      {
        id: '1w',
        name: window.i18n.t('上周'),
      },
      {
        id: '1M',
        name: window.i18n.t('一月前'),
      },
    ],
    type: Array,
  })
  readonly timeshiftList: IOption[];
  // 目标对比 ip列表
  @Prop({
    default() {
      return [];
    },
  })
  readonly targetList: IOption[];
  // 工具栏时间间隔列表
  @Prop({
    default() {
      return DEAULT_TIME_RANGE;
    },
  })
  readonly timerangeList: IOption[];

  // 工具栏刷新时间间隔列表
  @Prop({
    default() {
      return DEFAULT_REFLESH_LIST;
    },
  })
  readonly refreshList: IOption[];
  // 是否需要拆分视图
  @Prop({ default: true }) needSplit: boolean;

  @Prop({ required: true }) value: { compare: ICompareOption; tools: IToolsOption };

  // 是否需要目标选择输入
  @Prop({ default: true }) needTarget;
  @Prop({ default: false, type: Boolean }) needSearchSelect: boolean;
  @Prop({ default: () => [], type: Array }) searchSelectList: ISearchSelectList;
  @Prop({ type: Object }) readonly curHost;
  @Prop({ type: Array, default: () => [] }) favoritesList: IFavList.favList[];
  @Prop({ type: Object, default: () => ({}) }) favCheckedValue: IFavList.favList;
  // 隐藏选项
  @Prop({ type: Boolean, default: false }) compareHide: boolean;

  // 对比数据
  compare: ICompareOption = { type: 'none', value: '' };
  // 工具数据
  tools: IToolsOption = { timeRange: 1 * 60 * 60 * 1000, refreshInterval: -1, searchValue: [] };
  resizeHandler: Function = null;
  showText = false;
  iconList = ['icon-mc-one-column', 'icon-mc-two-column', 'icon-mc-three-column'];
  custom = {
    show: false,
    value: '',
  };

  get dateRangeKey() {
    let key = 'dateRangeKey';
    if (this.tools.timeRange && this.timeshiftList) {
      key = getRandomId();
    }
    return key;
  }

  get handleSelectorActive() {
    let flag = false;
    if (this.tools.searchValue.length) {
      flag = true;
    }
    return flag;
  }

  get showClearBtn() {
    return this.refTargetSelect.unmatchedCount !== this.targetList.length;
  }
  get hasFavoritesList() {
    return !!this.favoritesList.length;
  }

  @Watch('curHost', { deep: true })
  handleCurHost(v) {
    if (v !== null) {
      // 默认为主机
      let id = `${v.cloudId}-${v.ip}`;
      if (v.type && v.type === 'SERVICE') {
        // 实例
        id = v.value;
      } else if (v.type && v.type === 'custom') {
        // 自定义指标
        id = v.ip;
      }
      const index = this.compare.value?.indexOf?.(id);
      if (Array.isArray(this.compare.value) && index !== -1) {
        this.compare.value.splice(index, 1);
      }
    }
  }

  @Watch('value', { immediate: true, deep: true })
  onValueChange(v) {
    this.compare = { ...v.compare };
    this.tools = { ...v.tools };
  }

  mounted() {
    this.resizeHandler = () => {
      const rect = this.refPanelWrap.getBoundingClientRect();
      this.showText = rect.width > 750;
    };
    this.resizeHandler();
    addListener(this.refPanelWrap, this.resizeHandler as any);
  }
  beforeDestroy() {
    removeListener(this.refPanelWrap, this.resizeHandler as any);
  }
  @Emit('change')
  handleValueChange(type: ICompareChangeType) {
    return {
      compare: { ...this.compare },
      tools: { ...this.tools },
      type,
    };
  }
  @Emit('chart-change')
  handleViewChange() {
    // if (this.chartTypeReadonly) return 0;
    localStorage.setItem(PERFORMANCE_CHART_TYPE, String((this.chartType + 1) % 3));
    return (this.chartType + 1) % 3;
  }

  handleAddCustomTime() {
    const regular = /^[1-9][0-9]*(?:m|h|d|w|M|y)$/;
    if (regular.test(this.custom.value.trim())) {
      (this.compare.value as string[]).push(this.custom.value);
      this.handleValueChange('compare');
      this.custom.show = false;
      this.handleAddCustomTimeEmit();
    } else {
      this.$bkMessage({
        theme: 'warning',
        message: this.$t('按照提示输入'),
        offsetY: 40,
      });
    }
  }

  @Emit('add-timeshift-option')
  handleAddCustomTimeEmit() {
    return this.custom.value;
  }
  @Emit('delete-fav')
  handleDeleteFav(id: number) {
    return id;
  }
  @Emit('select-fav')
  emitSelectFav(data: IDataRetrieval.ILocalValue) {
    return data;
  }
  // 选择时间间隔触发
  handleTimeRangeChange(timeRange: TimeRangeType) {
    this.tools.timeRange = timeRange;
    this.handleValueChange('timeRange');
  }
  handleSelectToggle(v: boolean) {
    if (v) {
      this.refTimeSelect?.$refs?.selectDropdown?.instance?.set({ zIndex: 9999 });
      this.refTargetSelect?.$refs?.selectDropdown?.instance?.set({ zIndex: 9999 });
    }
  }
  // 设置自定义时间间隔触发
  handleAddOption(params) {
    this.$emit('add-timerange-option', params);
    this.tools.timeRange = params.value;
    this.handleValueChange('timeRange');
  }
  async handleChangeType(type) {
    if (type === 'none') this.compare.value = this.needSplit;
    else if (type === 'time') {
      this.compare.value = ['1h'];
    } else if (type === 'target') this.compare.value = '';
    this.handleValueChange('compare');
  }
  handleSplit() {
    this.compare.value = !this.compare.value;
    this.handleValueChange('compare');
  }
  handleCustomClick() {
    this.custom.show = true;
    this.custom.value = '';
  }

  handleSearchSelectChange(val) {
    this.tools.searchValue = val;
    this.handleValueChange('search');
  }

  deleteSelected() {
    this.$set(this.compare, 'value', []);
  }
}
</script>
<style lang="scss" scoped>
/* stylelint-disable declaration-no-important */

.target-select {
  &-clear {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: flex-end;
    padding: 0 16px;

    &:before {
      width: 100%;
      height: 1px;
      padding: 0 8px;
      margin-top: 4px;
      content: '';
      background: #f0f1f5;
    }

    .clear-btn {
      color: #3a84ff;
      cursor: pointer;
    }
  }
}

.time-select {
  &-custom {
    position: relative;
    display: flex;
    align-items: center;
    height: 32px;
    padding: 0 16px;
    margin-bottom: 6px;

    :deep(.bk-input-small) {
      display: flex;
      align-items: center;
    }

    :deep(.bk-tooltip-ref) {
      margin-left: -20px;
    }

    &:hover {
      cursor: pointer;
    }

    & .custom-text:hover,
    :deep(.bk-tooltip-ref:hover) {
      color: #3a84ff;
    }

    .help-icon {
      position: absolute;
      right: 20px;
      display: flex;
      align-items: center;
      justify-content: center;
      width: 14px;
      height: 14px;
      font-size: 12px;
    }

    :deep(.tippy-active) {
      color: #3a84ff;
    }
  }
}

.compare-panel {
  display: flex;
  height: 42px;
  // box-shadow: 0px 1px 2px 0px rgba(0,0,0,.1);
  background: #fff;
  border-bottom: 1px solid #f0f1f5;

  .panel-wrap {
    display: flex;
    flex: 1;
    height: 100%;

    :deep(.dropdown-trigger) {
      height: 42px;
    }

    :deep(.bk-dropdown-content) {
      top: 0 !important;
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
    }

    &-left {
      flex-basis: 100px;
      width: 100px;
    }

    &-center {
      position: relative;
      display: flex;
      flex: 1;
      padding-left: 6px;
      border-left: 1px solid #f0f1f5;

      .split-btn-wrapper {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 48px;
        height: 100%;
        margin-left: -6px;
        border-right: 1px solid #f0f1f5;

        .icon-monitor {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 24px;
          height: 24px;
          font-size: 17px;
          cursor: pointer;
          border-radius: 2px;
        }

        .icon-active {
          color: #3a84ff;
          background-color: #e1ecff;
        }
      }

      .time-select {
        flex: 1;
        max-width: 150px;
        height: 32px;
        margin: 4px 5px 0 0;

        &.en-lang {
          :deep(.is-unselected:before) {
            left: 26px !important;
          }
        }

        &-custom {
          display: flex;
          align-items: center;
          height: 32px;
        }
      }

      .target-select {
        z-index: 99;
        min-width: 110px;
        margin: 4px 5px 0 0;
        background: white;

        :deep(.bk-select) {
          border: 0;

          &.is-focus {
            box-shadow: none;
          }

          .bk-tooltip-ref {
            background-color: #fff;
          }

          .bk-icon,
          &::before {
            z-index: 9;
          }
        }

        :deep(.bk-select-tag-container) {
          .bk-select-tag {
            max-width: none;
          }
        }
      }

      .margin-left-auto {
        margin-left: auto;
      }

      .search-selector-wrapper {
        display: flex;
        align-items: center;
        min-width: 78px;
        padding-right: 11px;
        border-left: 1px solid #f0f1f5;

        :deep(.search-select) {
          flex: 1;
        }
      }

      .search-select-active {
        width: 240px;
      }

      .time-shift {
        display: flex;
        flex-shrink: 0;
        align-items: center;
        height: 42px;
        padding: 0 12px;
        // min-width: 100px;
        // margin-left: auto;
        border-left: 1px solid #f0f1f5;

        &-select {
          width: 100%;
        }

        :deep(.date) {
          border: 0;

          &.is-focus {
            box-shadow: none;
          }
        }
      }

      .time-interval {
        display: flex;
        align-items: center;
        height: 41px !important;
        padding-right: 8px;
        border-left: 1px solid #f0f1f5;
      }

      .center-maintag {
        display: flex;
        align-items: center;
        justify-content: center;
        min-width: 74px;
        height: 22px;
        padding: 0 5px;
        margin-top: 8px;
        font-weight: 700;
        color: #63656e;
        background: #f0f1f5;
        border-radius: 2px;

        .tag {
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
      }
    }

    .panel-wrap-right {
      &.readonly {
        .tool-icon {
          cursor: not-allowed;
        }
      }
    }
  }

  &.has-favorites-list {
    height: 48px;

    .panel-wrap-left {
      :deep(.dropdown-trigger) {
        height: 48px;
      }
    }

    .panel-wrap-center {
      border-left: 0;

      &.no-compare {
        padding-left: 0;
      }

      .favorites-list {
        flex: 1;
      }

      .time-select {
        margin-top: 8px;
      }

      .time-shift {
        height: 48px;
        border-left: 0;
      }

      :deep(.dropdown-trigger) {
        height: 48px;
      }
    }

    .panel-wrap-right {
      /* stylelint-disable-next-line no-descending-specificity */
      .tool-icon {
        height: 48px;
      }
    }
  }

  :deep(.bk-dropdown-menu) {
    width: 100%;
  }
}
</style>
