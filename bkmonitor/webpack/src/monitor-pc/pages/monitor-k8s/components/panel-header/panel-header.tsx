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

// import MonitorDateRange from '../../../../components/monitor-date-range';
import DropDownMenu from '../../../../components/monitor-dropdown';
import TimeRange, { type TimeRangeType } from '../../../../components/time-range/time-range';
import { DEFAULT_TIME_RANGE } from '../../../../components/time-range/utils';
import { PANEL_INTERVAL_LIST } from '../../../../constant/constant';
import {
  type OptionsItem,
  type PanelHeaderType,
  REFLESH_DEFAULT_LIST,
  TIME_RANGE_DEFAULT_LIST,
} from '../../typings/panel-tools';
import FavoritesList, { type IFavList } from './favorites-list/favorites-list';

import type { IRefleshItem } from '../dashboard-tools';

import './panel-header.scss';

@Component
export default class PanelHeader extends tsc<PanelHeaderType.IProps, PanelHeaderType.IEvents> {
  @Prop({ default: () => DEFAULT_TIME_RANGE, type: Array }) timeRange: TimeRangeType;
  @Prop({ default: -1, type: Number }) refleshInterval: number;
  @Prop({ type: String }) timezone: string;
  /** 工具栏时间间隔列表 */
  @Prop({ default: () => TIME_RANGE_DEFAULT_LIST }) readonly timeRangeList: OptionsItem[];
  /** 工具栏刷新时间间隔列表 */
  @Prop({ default: () => REFLESH_DEFAULT_LIST }) readonly refleshList: OptionsItem[];

  /** 收藏数据 */
  @Prop({ type: Array, default: () => [] }) favoritesList: IFavList.favList[];
  @Prop({ type: Object, default: () => ({}) }) favCheckedValue: IFavList.favList;
  @Prop({ type: String, default: 'auto' }) downSampleRange: string;
  @Prop({ type: Boolean, default: false }) showDownSample: boolean;
  // 事件检索图表框选范围需更新到此组件
  @Prop({ default: () => DEFAULT_TIME_RANGE, type: Array }) eventSelectTimeRange: TimeRangeType;

  /** 收藏的展示状态 */
  shwoFav = false;

  /** 时间范围展示状态 */
  showText = true;

  /** 刷新间隔 */
  localRefleshInterval = -1;
  /** 时间范围 */
  localTimeRange: TimeRangeType = DEFAULT_TIME_RANGE;

  downSampleRangeList: IRefleshItem[] = [];
  downSampleRangeValue = 'auto';
  created() {
    this.downSampleRangeList = PANEL_INTERVAL_LIST;
  }
  @Watch('timeRange', { immediate: true })
  timeRangeChange() {
    this.localTimeRange = this.timeRange;
  }
  @Watch('refleshInterval', { immediate: true })
  refleshIntervalChange() {
    this.localRefleshInterval = this.refleshInterval;
  }
  @Watch('downSampleRange', { immediate: true })
  onDownSampleRangeChange() {
    this.downSampleRangeValue = this.downSampleRange;
  }
  @Watch('eventSelectTimeRange')
  handleEventSelectTimeRange(v) {
    this.localTimeRange = JSON.parse(JSON.stringify(v));
  }
  /** 立即刷新 */
  @Emit('immediateReflesh')
  handleImmediateReflesh() {}

  /** 刷新间隔更新 */
  @Emit('refleshIntervalChange')
  handleRefleshChange() {
    return this.localRefleshInterval;
  }

  /** 时间范围值更新 */
  @Emit('timeRangeChange')
  handleTimeRangeChange(val: PanelHeaderType.TimeRangeValue): PanelHeaderType.TimeRangeValue {
    return val;
  }

  @Emit('timezoneChange')
  handleTimezoneChange(val: string) {
    return val;
  }

  /** 选择收藏 */
  @Emit('selectFav')
  handleSelectFav(data) {
    return data;
  }

  /** 删除收藏 */
  @Emit('deleteFav')
  handleDeleteFav(id) {
    return id;
  }
  @Emit('downSampleChange')
  handleIntervalChange() {
    return this.downSampleRangeValue;
  }
  render() {
    return (
      <div class={['panel-header-wrap', { 'has-pre': !!this.$slots.pre }]}>
        <span>{this.$slots.pre}</span>
        {!!this.favoritesList.length && (
          <FavoritesList
            class='panel-header-favlist'
            checkedValue={this.favCheckedValue}
            value={this.favoritesList}
            onDeleteFav={this.handleDeleteFav}
            onSelectFav={this.handleSelectFav}
            onShowChange={val => (this.shwoFav = val)}
          />
        )}
        <span class='panel-header-center' />
        <span class='panel-header-right'>
          {this.showDownSample && (
            <DropDownMenu
              class='tools-interval'
              v-model={this.downSampleRangeValue}
              icon={'icon-lidu'}
              iconTitle={window.i18n.tc('粒度')}
              list={this.downSampleRangeList}
              readonly
              on-change={this.handleIntervalChange}
            />
          )}
          <TimeRange
            timezone={this.timezone}
            value={this.localTimeRange}
            onChange={this.handleTimeRangeChange}
            onTimezoneChange={this.handleTimezoneChange}
          />
          {/* <MonitorDateRange
            icon="icon-mc-time-shift"
            class={['time-shift-select', { 'right-item': !this.shwoFav }]}
            dropdown-width="96"
            v-model={this.localTimeRange}
            options={this.timeRangeListFormatter}
            show-name={this.showText}
            z-index={2500}
            onChange={this.handleTimeRangeChange}/> */}
          <DropDownMenu
            class='time-interval right-item'
            v-model={this.localRefleshInterval}
            icon={'icon-zidongshuaxin'}
            isRefleshInterval={true}
            list={this.refleshList}
            text-active={this.localRefleshInterval !== -1}
            on-on-icon-click={this.handleImmediateReflesh}
            onChange={this.handleRefleshChange}
          />
        </span>
      </div>
    );
  }
}
