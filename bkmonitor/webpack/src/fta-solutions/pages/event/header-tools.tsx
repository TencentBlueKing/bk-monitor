/*
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
 */
import { Component, Emit, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import MonitorDateRange from 'monitor-pc/components/monitor-date-range/monitor-date-range.vue';
import DropDownMenu from 'monitor-pc/components/monitor-dropdown/dropdown-menu.vue';

/*
 * @Date: 2021-06-09 17:02:37
 * @LastEditTime: 2021-06-10 17:09:38
 * @Description: 告警中心头部组件
 */
import type { TranslateResult } from 'vue-i18n';

import './header-tools.scss';

interface IHeadToolEvent {
  onRefreshChange: number;
  onTimeRangeChange: number;
  onImmediateRefresh: () => void;
}
interface IHeadToolProps {
  refreshInterval: number;
  timeRange: number | string | string[];
}
interface IRefreshItem {
  id: number | string;
  name: string | TranslateResult;
}

interface ITimeRangeItem {
  name: string | TranslateResult;
  value: number | string;
}
@Component
export default class HeaderTool extends tsc<IHeadToolProps, IHeadToolEvent> {
  @Prop({ default: 1 * 60 * 60 * 1000, type: [Number, Array, String] }) timeRange: number | string | string[];
  @Prop({ default: -1 }) refreshInterval: number;
  timerangeList: ITimeRangeItem[] = [];
  refreshList: IRefreshItem[] = [];
  timeRangeValue: number = 1 * 60 * 60 * 1000;
  refreshIntervalValue = -1;

  @Watch('timeRange', { immediate: true })
  onTimeRangeChange(v) {
    this.timeRangeValue = v;
  }
  @Watch('refreshInterval', { immediate: true })
  onRefreshIntervalChange(v) {
    this.refreshIntervalValue = v;
  }
  created() {
    this.timerangeList = [
      {
        name: `${this.$t('近{n}分钟', { n: 5 })}`,
        value: 5 * 60 * 1000,
      },
      {
        name: `${this.$t('近{n}分钟', { n: 15 })}`,
        value: 15 * 60 * 1000,
      },
      {
        name: `${this.$t('近{n}分钟', { n: 30 })}`,
        value: 30 * 60 * 1000,
      },
      {
        name: `${this.$t('近{n}小时', { n: 1 })}`,
        value: 1 * 60 * 60 * 1000,
      },
      {
        name: `${this.$t('近{n}小时', { n: 3 })}`,
        value: 3 * 60 * 60 * 1000,
      },
      {
        name: `${this.$t('近{n}小时', { n: 6 })}`,
        value: 6 * 60 * 60 * 1000,
      },
      {
        name: `${this.$t('近{n}小时', { n: 12 })}`,
        value: 12 * 60 * 60 * 1000,
      },
      {
        name: `${this.$t('近{n}小时', { n: 24 })}`,
        value: 24 * 60 * 60 * 1000,
      },
      {
        name: `${this.$t('近 {n} 天', { n: 2 })}`,
        value: 2 * 24 * 60 * 60 * 1000,
      },
      {
        name: `${this.$t('近 {n} 天', { n: 7 })}`,
        value: 7 * 24 * 60 * 60 * 1000,
      },
      {
        name: `${this.$t('近 {n} 天', { n: 30 })}`,
        value: 30 * 24 * 60 * 60 * 1000,
      },
      {
        name: `${this.$t('今天')}`,
        value: 'today',
      },
      {
        name: `${this.$t('昨天')}`,
        value: 'yesterday',
      },
      {
        name: `${this.$t('前天')}`,
        value: 'beforeYesterday',
      },
      {
        name: `${this.$t('本周')}`,
        value: 'thisWeek',
      },
    ];
    this.refreshList = [
      // 刷新间隔列表
      {
        name: 'off',
        id: -1,
      },
      {
        name: '1m',
        id: 60 * 1000,
      },
      {
        name: '5m',
        id: 5 * 60 * 1000,
      },
      {
        name: '15m',
        id: 15 * 60 * 1000,
      },
      {
        name: '30m',
        id: 30 * 60 * 1000,
      },
      {
        name: '1h',
        id: 60 * 60 * 1000,
      },
      {
        name: '2h',
        id: 60 * 2 * 60 * 1000,
      },
      {
        name: '1d',
        id: 60 * 24 * 60 * 1000,
      },
    ];
  }
  @Emit('timeRangeChange')
  handleTimeRangeChange() {
    return this.timeRangeValue;
  }
  @Emit('refreshChange')
  handleRefreshChange() {
    return this.refreshIntervalValue;
  }
  handleAddOption(item) {
    this.timerangeList.push(item);
  }
  render() {
    return (
      <div class='header-tools'>
        <MonitorDateRange
          class='header-date'
          v-model={this.timeRangeValue}
          dropdown-width={100}
          icon='icon-mc-time-shift'
          options={this.timerangeList}
          z-index={2500}
          on-add-option={this.handleAddOption}
          on-change={this.handleTimeRangeChange}
        />
        <DropDownMenu
          class='time-interval'
          v-model={this.refreshIntervalValue}
          icon={'icon-zidongshuaxin'}
          is-refresh-interval={true}
          list={this.refreshList}
          text-active={this.refreshInterval !== -1}
          on-change={this.handleRefreshChange}
          on-on-icon-click={() => this.$emit('immediateRefresh')}
        />
      </div>
    );
  }
}
