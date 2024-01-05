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
// import Vue from 'vue';
import { TranslateResult } from 'vue-i18n';
import { Component, Emit, InjectReactive, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

//
// import MonitorDateRange from '../../../components/monitor-date-range';
import MonitorDropdown from '../../../components/monitor-dropdown';
import TimeRange, { TimeRangeType } from '../../../components/time-range/time-range';
import { DEFAULT_TIME_RANGE, getTimeDisplay } from '../../../components/time-range/utils';
import { PANEL_INTERVAL_LIST } from '../../../constant/constant';
import { COMMON_SETTINGS_LIST, IMenuItem } from '../typings';

import ListMenu from './list-menu';

import './dashboard-tools.scss';

// Vue.use(DatePicker);
// Vue.use(DropdownMenu);
interface ITimeRangeItem {
  // 数据间隔别名 如 1h 1d
  name: TranslateResult | string;
  // 间隔值 如 60 * 60 * 1000 = 1h
  value: number | string;
}
export interface IRefleshItem {
  // 刷新间隔名称
  name: TranslateResult | string;
  // 自动刷新间隔值
  id: number | string;
}
interface IHeadToolProps {
  // 数据间隔
  timeRange?: TimeRangeType;
  // 时区
  timezone?: string;
  // 自动刷新数据间隔
  refleshInterval?: number;
  // 是否显示分屏功能
  isSplitPanel: boolean;
  // 是否展示列表功能
  showListMenu?: boolean;
  // 是否显示timerange 功能
  showTimeRange?: boolean;
  // 是否显示分屏功能
  showSplitPanel?: boolean;
  // menu list
  menuList?: IMenuItem[];
  // 粒度
  downSampleRange?: number | string;
  interval?: number | string;
  // 是否显示粒度
  showDownSampleRange?: boolean;
  showInterval?: boolean;
}

interface IHeadToolEvent {
  // 数据间隔修改触发
  onTimeRangeChange: TimeRangeType;
  // 自动刷新数据间隔修改触发
  onRefleshChange: number;
  // 触发立即刷新
  onImmediateReflesh: () => void;
  // 点击全屏功能触发
  onFullscreenChange: (v: boolean) => void;
  // 点击分屏功能触发
  onSplitPanelChange: (v: boolean) => void;
  // 选择menu触发
  onSelectedMenu: (v: IMenuItem) => void;
  // 选择粒度
  onDownSampleRangeChange?: (v: string | number) => void;
  onIntervalChange?: (v: string | number) => void;
  // 选择时区
  onTimezoneChange?: (v: string) => void;
}
@Component
export default class DashboardTools extends tsc<IHeadToolProps, IHeadToolEvent> {
  @InjectReactive('readonly') readonly readonly: boolean; // 是否只读
  // 数据间隔
  @Prop({ default: () => DEFAULT_TIME_RANGE, type: Array }) timeRange: TimeRangeType;
  // 时区
  @Prop({ type: String }) timezone: string;
  // 自动刷新数据间隔
  @Prop({ default: -1 }) readonly refleshInterval: number;
  // 是否显示分屏功能
  @Prop({ default: false }) readonly isSplitPanel: boolean;
  // 是否展示列表功能
  @Prop({ default: true, type: Boolean }) showListMenu: boolean;
  // 是否显示timerange 功能
  @Prop({ default: true, type: Boolean }) showTimeRange: boolean;
  // 是否显示分屏功能
  @Prop({ default: false, type: Boolean }) showSplitPanel: boolean;
  // menu list
  @Prop({ default: () => COMMON_SETTINGS_LIST }) menuList: IMenuItem[];
  // 粒度
  @Prop({ default: 'auto' }) readonly downSampleRange: number | string;
  @Prop({ default: 'auto' }) readonly interval: number | string;
  // 是否显粒度
  @Prop({ default: false }) showDownSampleRange: boolean;
  @Prop({ default: false }) showInterval: boolean;

  timeRangeList: ITimeRangeItem[] = [];
  refleshList: IRefleshItem[] = [];
  timeRangeValue: any = DEFAULT_TIME_RANGE;
  refleshIntervalValue = -1;
  isFullscreen = false;
  isSettings = false;
  curTimeRange: TimeRangeType = DEFAULT_TIME_RANGE;
  /* 粒度 */
  downSampleRangeList: IRefleshItem[] = [];
  downSampleRangeValue = 'auto';

  intervalList: IRefleshItem[] = [];
  intervalValue = 'auto';

  @Watch('timeRange', { immediate: true })
  onTimeRangeChange(v: TimeRangeType) {
    this.curTimeRange = v;
  }
  @Watch('refleshInterval', { immediate: true })
  onRefleshIntervalChange(v) {
    this.refleshIntervalValue = v;
  }
  @Watch('downSampleRange', { immediate: true })
  onGrainSizeValue(v) {
    this.downSampleRangeValue = v;
  }
  @Watch('interval', { immediate: true })
  onIntervalChange(v) {
    this.intervalValue = v;
  }

  // 监听全屏和取消全屏事件
  handleFullscreenChange() {
    let store = this.$store;
    if (window.__BK_WEWEB_DATA__?.$baseStore) {
      store = window.__BK_WEWEB_DATA__.$baseStore;
    }
    if (document.fullscreenElement != null) {
      store.commit('app/SET_FULL_SCREEN', true);
    } else {
      store.commit('app/SET_FULL_SCREEN', false);
    }
  }
  // 处理快捷键操作全屏
  handleHotkeyActionFullscreen(e) {
    // 组合键Ctrl + m 可以开关全屏
    if (e.ctrlKey && e.code === 'KeyM') this.handleFullScreen();
    // 拦截f11进入全屏，用自己的全屏方法
    if (e.code === 'F11') {
      e.preventDefault();
      this.handleFullScreen();
    }
  }
  created() {
    // 初始化数据间隔列表
    this.timeRangeList = [
      {
        name: `${this.$t('近{n}分钟', { n: 5 })}`,
        value: 5 * 60 * 1000
      },
      {
        name: `${this.$t('近{n}分钟', { n: 15 })}`,
        value: 15 * 60 * 1000
      },
      {
        name: `${this.$t('近{n}分钟', { n: 30 })}`,
        value: 30 * 60 * 1000
      },
      {
        name: `${this.$t('近{n}小时', { n: 1 })}`,
        value: 1 * 60 * 60 * 1000
      },
      {
        name: `${this.$t('近{n}小时', { n: 3 })}`,
        value: 3 * 60 * 60 * 1000
      },
      {
        name: `${this.$t('近{n}小时', { n: 6 })}`,
        value: 6 * 60 * 60 * 1000
      },
      {
        name: `${this.$t('近{n}小时', { n: 12 })}`,
        value: 12 * 60 * 60 * 1000
      },
      {
        name: `${this.$t('近{n}小时', { n: 24 })}`,
        value: 24 * 60 * 60 * 1000
      },
      {
        name: `${this.$t('近 {n} 天', { n: 2 })}`,
        value: 2 * 24 * 60 * 60 * 1000
      },
      {
        name: `${this.$t('近 {n} 天', { n: 7 })}`,
        value: 7 * 24 * 60 * 60 * 1000
      },
      {
        name: `${this.$t('近 {n} 天', { n: 30 })}`,
        value: 30 * 24 * 60 * 60 * 1000
      },
      {
        name: `${this.$t('今天')}`,
        value: 'today'
      },
      {
        name: `${this.$t('昨天')}`,
        value: 'yesterday'
      },
      {
        name: `${this.$t('前天')}`,
        value: 'beforeYesterday'
      },
      {
        name: `${this.$t('本周')}`,
        value: 'thisWeek'
      }
    ];
    // 初始化自动刷新间隔列表
    this.refleshList = [
      // 刷新间隔列表
      {
        name: 'off',
        id: -1
      },
      {
        name: '1m',
        id: 60 * 1000
      },
      {
        name: '5m',
        id: 5 * 60 * 1000
      },
      {
        name: '15m',
        id: 15 * 60 * 1000
      },
      {
        name: '30m',
        id: 30 * 60 * 1000
      },
      {
        name: '1h',
        id: 60 * 60 * 1000
      },
      {
        name: '2h',
        id: 60 * 2 * 60 * 1000
      },
      {
        name: '1d',
        id: 60 * 24 * 60 * 1000
      }
    ];
    this.downSampleRangeList = [
      {
        name: this.$t('自动'),
        id: 'auto'
      },
      {
        name: this.$t('原始'),
        id: 'raw'
      },
      {
        name: this.$t('10 秒'),
        id: '10s'
      },
      {
        name: this.$t('20 秒'),
        id: '20s'
      },
      {
        name: this.$t('30 秒'),
        id: '30s'
      },
      {
        name: this.$t('1 分钟'),
        id: '1m'
      },
      {
        name: this.$t('5 分钟'),
        id: '5m'
      },
      {
        name: this.$t('30 分钟'),
        id: '30m'
      },
      {
        name: this.$t('1 小时'),
        id: '1h'
      },
      {
        name: this.$t('12 小时'),
        id: '12h'
      },
      {
        name: this.$t('1 天'),
        id: '1d'
      }
    ];
    this.intervalList = PANEL_INTERVAL_LIST;
  }
  mounted() {
    // 初始化全屏事件
    document.addEventListener('fullscreenchange', this.handleFullscreenChange);
    document.addEventListener('keydown', this.handleHotkeyActionFullscreen);
  }
  beforeDestroy() {
    // 销毁全屏事件
    document.removeEventListener('fullscreenchange', this.handleFullscreenChange);
    document.removeEventListener('keydown', this.handleHotkeyActionFullscreen);
  }

  @Emit('timeRangeChange')
  handleTimeRangeChange(val: TimeRangeType) {
    this.curTimeRange = [...val];
    return [...this.curTimeRange];
  }
  @Emit('refleshChange')
  handleRefleshChange() {
    return this.refleshIntervalValue;
  }
  @Emit('fullscreenChange')
  // 处理全屏操作
  handleFullScreen() {
    let store = this.$store;
    if (window.__BK_WEWEB_DATA__?.$baseStore) {
      store = window.__BK_WEWEB_DATA__.$baseStore;
    }
    if (!document.fullscreenElement) {
      store.commit('app/SET_FULL_SCREEN', true);
      document.body.requestFullscreen();
    } else if (document.exitFullscreen) {
      store.commit('app/SET_FULL_SCREEN', false);
      document.exitFullscreen();
    }
    return !this.isFullscreen;
  }
  handleAddOption(item) {
    this.timeRangeList.push(item);
  }
  @Emit('splitPanelChange')
  handleSplitPanel() {
    return !this.isSplitPanel;
  }
  handleSetSettings() {
    this.isSettings = !this.isSettings;
  }

  /**
   * @description: 选择菜单
   * @param {IMenuItem} item
   * @return {*}
   */
  @Emit('selectedMenu')
  handleSettingsMenuSelect(item: IMenuItem) {
    return item;
  }
  @Emit('downSampleRangeChange')
  handlDownSampleRangeChange() {
    return this.downSampleRangeValue;
  }
  @Emit('intervalChange')
  handleIntervalChange() {
    return this.intervalValue;
  }
  @Emit('timezoneChange')
  handleTimezoneChange(v) {
    return v;
  }
  render() {
    return (
      <div class='dashboard-tools'>
        {this.showInterval && (
          <MonitorDropdown
            icon={'icon-lidu'}
            class='dashboard-tools-interval'
            v-model={this.intervalValue}
            list={this.intervalList}
            iconTitle={window.i18n.tc('汇聚周期')}
            on-change={this.handleIntervalChange}
          />
        )}
        {this.showDownSampleRange && (
          <MonitorDropdown
            icon={'icon-lidu'}
            class='dashboard-tools-interval'
            v-model={this.downSampleRangeValue}
            list={this.downSampleRangeList}
            iconTitle={window.i18n.tc('粒度')}
            readonly={true}
            on-change={this.handlDownSampleRangeChange}
          />
        )}
        {this.showTimeRange &&
          (window.__BK_WEWEB_DATA__?.lockTimeRange ? (
            <span class='dashboard-tools-timerange'>{getTimeDisplay(this.curTimeRange)}</span>
          ) : (
            <TimeRange
              class='dashboard-tools-timerange'
              value={this.curTimeRange}
              timezone={this.timezone}
              onTimezoneChange={this.handleTimezoneChange}
              onChange={this.handleTimeRangeChange}
            />
          ))}
        {<span></span>}
        <MonitorDropdown
          icon='icon-zidongshuaxin'
          class={`dashboard-tools-interval ${this.readonly ? 'is-readonly' : ''}`}
          v-model={this.refleshIntervalValue}
          text-active={this.refleshInterval !== -1}
          on-on-icon-click={() => this.$emit('immediateReflesh')}
          on-change={this.handleRefleshChange}
          isRefleshInterval={true}
          list={this.refleshList}
        />
        <span class='dashboard-tools-more'>
          {this.showSplitPanel && (
            <i
              class={`icon-monitor icon-mc-split-panel ${this.isSplitPanel ? 'icon-active' : ''}`}
              v-bk-tooltips={{ content: this.$t('分屏'), delay: 200, boundary: 'window', placement: 'bottom' }}
              onClick={this.handleSplitPanel}
            />
          )}
          <i
            class={`icon-monitor ${this.isFullscreen ? 'icon-mc-unfull-screen icon-active' : 'icon-mc-full-screen'}`}
            v-bk-tooltips={{ content: this.$t('全屏 ctrl + m'), delay: 200, boundary: 'window', placement: 'bottom' }}
            onClick={this.handleFullScreen}
          />
          {this.$slots.default}
          {this.showListMenu && !!this.menuList?.length && (
            <ListMenu
              list={this.menuList}
              onMenuSelect={this.handleSettingsMenuSelect}
              onHidden={this.handleSetSettings}
              onShow={this.handleSetSettings}
            >
              <div class='more-button'>
                <i class='icon-monitor icon-mc-more-tool' />
              </div>
            </ListMenu>
          )}
        </span>
      </div>
    );
  }
}
