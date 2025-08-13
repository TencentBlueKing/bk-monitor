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
  <div class="tool-panel">
    <div
      ref="panelWrap"
      class="panel-wrap"
    >
      <div class="panel-wrap-left">
        {{ $t('数据预览') }}
      </div>
      <div class="panel-wrap-center">
        <slot name="content">
          <span class="margin-left-auto" />
          <div class="time-shift">
            <time-range
              :value="timeRange"
              :timezone="timezone"
              @timezoneChange="handleTimezoneChange"
              @change="handleSelectTimeRangeChange"
            />
            <!-- <monitor-date-range
              icon="icon-mc-time-shift"
              class="time-shift-select"
              @add-option="handleAddOption"
              dropdown-width="96"
              v-model="timeRange"
              :options="timerangeList"
              :style="{ minWidth: showText ? '100px' : '40px' }"
              :show-name="showText"
              @change="handleValueChange('timeRange')"
            > -->
            <!-- </monitor-date-range> -->
          </div>
          <drop-down-menu
            v-model="refreshInterval"
            :show-name="showText"
            :icon="'icon-zidongshuaxin'"
            class="time-interval"
            :text-active="refreshInterval !== -1"
            :is-refresh-interval="true"
            :list="refreshList"
            @on-icon-click="$emit('on-immediate-refresh')"
            @change="handleValueChange('interval')"
          />
        </slot>
      </div>
    </div>
  </div>
</template>
<script lang="ts">
import { Component, Emit, Prop, Ref, Vue, Watch } from 'vue-property-decorator';

// import MonitorDateRange from '../../../../components/monitor-date-range/monitor-date-range.vue';
import { addListener, removeListener } from '@blueking/fork-resize-detector';

import { DEFAULT_REFLESH_LIST } from '../../../../common/constant';
import DropDownMenu from '../../../../components/monitor-dropdown/dropdown-menu.vue';
import TimeRange, { type TimeRangeType } from '../../../../components/time-range/time-range';
import { DEFAULT_TIME_RANGE } from '../../../../components/time-range/utils';
import { getDefaultTimezone, updateTimezone } from '../../../../i18n/dayjs';

import type { ICompareChangeType, IOption } from '../../../performance/performance-type';

@Component({
  name: 'tool-panel',
  components: {
    DropDownMenu,
    // MonitorDateRange,
    TimeRange,
  },
})
export default class ToolPanel extends Vue {
  @Ref('panelWrap') refPanelWrap: HTMLDivElement;
  // 工具栏时间间隔列表
  @Prop({
    default() {
      return [
        {
          name: this.$t('1 小时'),
          value: 1 * 60 * 60 * 1000,
        },
        {
          name: this.$t('1 天'),
          value: 24 * 60 * 60 * 1000,
        },
        {
          name: this.$t('7 天'),
          value: 168 * 60 * 60 * 1000,
        },
        {
          name: this.$t('1 个月'),
          value: 720 * 60 * 60 * 1000,
        },
      ];
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

  showText = false;
  timeRange: TimeRangeType = DEFAULT_TIME_RANGE;
  timezone: string = getDefaultTimezone();
  refreshInterval = 5 * 60 * 1000;
  resizeHandler: Function = null;

  @Watch('timeRange')
  handleTimeRangeChange(range) {
    // 自定义时间默认不开启刷新，语义时间默认刷新时间为 1 分钟
    if (Array.isArray(range)) {
      this.refreshInterval = -1;
      this.handleValueChange('interval');
    } else if (this.refreshInterval === -1) {
      this.refreshInterval = 5 * 60 * 1000;
      this.handleValueChange('interval');
    }
  }

  @Emit('change')
  handleValueChange(type: ICompareChangeType) {
    return {
      type,
      tools: {
        timeRange: this.timeRange,
        refreshInterval: this.refreshInterval,
      },
    };
  }

  @Emit('timezoneChange')
  handleTimezoneChange(v: string) {
    this.timezone = v;
    return v;
  }

  handleSelectTimeRangeChange(val: TimeRangeType) {
    this.timeRange = val;
    updateTimezone(this.timezone);
    this.handleValueChange('timeRange');
  }

  mounted() {
    this.resizeHandler = () => {
      const rect = this.refPanelWrap.getBoundingClientRect();
      this.showText = rect.width > 500;
    };
    this.resizeHandler();
    addListener(this.refPanelWrap, this.resizeHandler);
    this.timezone = getDefaultTimezone();
  }

  beforeDestroy() {
    removeListener(this.refPanelWrap, this.resizeHandler);
  }

  // 设置自定义时间间隔触发
  handleAddOption(params) {
    this.$emit('add-timerange-option', params);
    this.timeRange = params.value;
    this.handleValueChange('timeRange');
  }

  // handleSetTimeRange(range: TimeRangeType) {
  //   this.timeRange = range;
  // }
}
</script>
<style lang="scss" scoped>
.tool-panel {
  display: flex;
  height: 42px;
  // box-shadow: 0px 1px 2px 0px rgba(0,0,0,.1);
  background: #fff;
  // border-bottom: 1px solid #f0f1f5;

  :deep(.bk-dropdown-menu) {
    width: 100%;
  }

  .panel-wrap {
    display: flex;
    flex: 1;
    height: 100%;

    &-left {
      flex-basis: 124px;
      width: 124px;
      padding-left: 15px;
      font-size: 14px;
      font-weight: 700;
      line-height: 42px;
      color: #313238;
    }

    &-center {
      position: relative;
      display: flex;
      flex: 1;
      align-items: center;
      padding-left: 6px;

      .margin-left-auto {
        margin-left: auto;
      }

      .time-shift {
        display: flex;
        flex-shrink: 0;
        align-items: center;
        height: 42px;
        padding: 0 12px;
        // min-width: 100px;
        // margin-left: auto;
        // border-left: 1px solid #f0f1f5;

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
        // border-left: 1px solid #f0f1f5;
        position: relative;

        /* stylelint-disable-next-line declaration-no-important */
        height: 22px !important;
        padding: 0 8px;

        &:before {
          position: absolute;
          top: 50%;
          left: 0px;
          width: 1px;
          height: 14px;
          content: '';
          background: #dcdee5;
          transform: translateY(-50%);
        }
      }
    }
  }
}
</style>
