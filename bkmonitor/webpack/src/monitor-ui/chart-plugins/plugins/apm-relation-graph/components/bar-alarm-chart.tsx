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
import { Component, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import dayjs from 'dayjs';

import { EAlarmType, type IAlarmDataItem, type EDataType, alarmColorMap, getAlarmItemStatusTips } from './utils';

import './bar-alarm-chart.scss';

type TGetData = (set: (v: IAlarmDataItem[]) => void) => void;
interface IProps {
  itemHeight?: number;
  activeItemHeight?: number;
  showXAxis?: boolean;
  showHeader?: boolean;
  isAdaption?: boolean;
  dataType: EDataType;
  getData?: TGetData;
  onDataZoom: () => void;
}

@Component
export default class BarAlarmChart extends tsc<IProps> {
  @Ref('tips') tipsRef: HTMLDivElement;
  /* 当前item的高度 */
  @Prop({ type: Number, default: 24 }) itemHeight: number;
  /* 当前选中的item的高度 */
  @Prop({ type: Number, default: 32 }) activeItemHeight: number;
  /* 是否展示x轴 */
  @Prop({ type: Boolean, default: false }) showXAxis: boolean;
  /* 是否展示头部内容 */
  @Prop({ type: Boolean, default: false }) showHeader: boolean;
  /* 是否自适应宽度 */
  @Prop({ type: Boolean, default: false }) isAdaption: boolean;
  /* 数据类型，上层参数 */
  @Prop({ type: String, default: '' }) dataType: EDataType;
  @Prop({ type: Function, default: null }) getData: TGetData;

  loading = false;

  localData: readonly IAlarmDataItem[] = [];

  // 当前悬停的时间戳
  curHover = -1;
  // 当前选中的时间戳
  curActive = -1;
  // x轴刻度
  xAxis = [];

  /* tooltip 实例 */
  popInstance = null;
  timer = null;
  /* tooltip 内容状态 */
  statusList = [{ color: '#FF9C01', text: '错误率 < 10%' }];
  /*  */
  boxSelector: {
    [key: string]: any;
    boundingClientRect: DOMRect;
  } = {
    downClientX: -1,
    moveClientX: -1,
    isMouseDown: false,
    start: false,
    boundingClientRect: null,
    top: -1,
    left: -1,
    width: 0,
  };

  timeRange = [];
  selectedTimeRange = [];

  initData() {
    if (this.getData) {
      this.loading = true;
      this.getData(data => {
        this.loading = false;
        this.localData = Object.freeze(data);
        if (this.localData.length) {
          const len = this.localData.length;
          const start = this.localData[0].time;
          const end = this.localData[len - 1].time;
          const center = this.localData[Math.floor(len / 2)].time;
          this.xAxis = [dayjs(start).format('HH:mm'), dayjs(center).format('HH:mm'), dayjs(end).format('HH:mm')];
        } else {
          this.xAxis = [];
        }
      });
    }
  }

  @Watch('getData', { immediate: true })
  handleGetData() {
    this.loading = true;
    this.initData();
  }

  getTips(item) {
    const statusItem = getAlarmItemStatusTips(this.dataType, item);
    this.statusList = [statusItem];
  }

  /**
   * @description 鼠标移入事件
   * @param event
   * @param item
   * @returns
   */
  handleMouseEnter(event: Event, item: IAlarmDataItem) {
    if (item.type === EAlarmType.gray) {
      return;
    }
    this.getTips(item);
    this.curHover = item.time;
    this.timer = setTimeout(() => {
      this.popInstance = this.$bkPopover(event.target, {
        content: this.tipsRef,
        placement: 'top',
        boundary: 'window',
        arrow: true,
        trigger: 'click',
        theme: 'bar-alarm-chart-tooltip-theme',
      });
      this.popInstance.show();
    }, 200);
  }
  /**
   * @description 鼠标离开事件
   */
  handleMouseLeave() {
    this.curHover = -1;
    clearTimeout(this.timer);
    this.popInstance?.hide?.(0);
    this.popInstance?.destroy?.();
    this.popInstance = null;
  }
  /**
   * @description 点击事件
   * @param item
   * @returns
   */
  handleClick(item: IAlarmDataItem) {
    if (item.type === EAlarmType.gray) {
      return;
    }
    if (this.curActive === item.time) {
      this.curActive = -1;
      this.curHover = -1;
    } else {
      this.curActive = item.time;
    }
  }

  /**
   * @description 鼠标按下事件
   * @param event
   */
  handleMouseDown(event: MouseEvent) {
    if (this.loading) {
      return;
    }
    const target: HTMLDivElement = this.$el.querySelector('.alarm-chart-wrap');
    this.boxSelector = {
      ...this.boxSelector,
      isMouseDown: true,
      downClientX: event.clientX,
      boundingClientRect: target.getBoundingClientRect(),
      top: target.offsetTop - 7,
    };
    document.addEventListener('mousemove', this.handleMouseMove);
    document.addEventListener('mouseup', this.handleMouseUp);
  }

  /**
   * @description 鼠标移动事件
   * @param event
   * @returns
   */
  handleMouseMove(event: MouseEvent) {
    const diffX = event.clientX - this.boxSelector.downClientX;
    const downX = this.boxSelector.downClientX - this.boxSelector.boundingClientRect.left;
    const moveX = event.clientX - this.boxSelector.boundingClientRect.left;
    const computedLeft = (downX, moveX_) => {
      if (moveX_ < downX) {
        return moveX_;
      }
      return downX;
    };
    if (this.boxSelector.start) {
      const left = (() => {
        let left = 0;
        if (moveX < 0) {
          left = computedLeft(0, downX);
        } else if (moveX > this.boxSelector.boundingClientRect.width) {
          left = computedLeft(this.boxSelector.boundingClientRect.width, downX);
        } else {
          left = computedLeft(moveX, downX);
        }
        return left;
      })();
      const width = (() => {
        const diffXAbs = Math.abs(diffX);
        const residualWidth = this.boxSelector.boundingClientRect.width - left;
        if (event.clientX < this.boxSelector.boundingClientRect.left) {
          return downX;
        }
        if (diffXAbs > residualWidth) {
          return residualWidth;
        }
        return diffXAbs;
      })();
      this.boxSelector = {
        ...this.boxSelector,
        left,
        width,
        moveClientX: event.clientX,
      };
      return;
    }
    if (this.boxSelector.isMouseDown && Math.abs(diffX) > 6) {
      this.boxSelector.start = true;
    }
  }
  /**
   * @description 鼠标抬起事件
   */
  handleMouseUp() {
    if (this.boxSelector.start) {
      this.timeRangeChange();
      this.boxSelector = {
        downClientX: -1,
        moveClientX: -1,
        isMouseDown: false,
        start: false,
        boundingClientRect: null,
        top: -1,
        left: -1,
        width: 0,
      };
      document.removeEventListener('mousemove', this.handleMouseMove);
      document.removeEventListener('mouseup', this.handleMouseUp);
    } else {
      this.boxSelector.isMouseDown = false;
    }
  }

  /**
   * @description 时间范围变化
   */
  timeRangeChange() {
    let w = 0;
    const startX = this.boxSelector.left;
    const endX = this.boxSelector.left + this.boxSelector.width;
    let startTime = 0;
    let endTime = 0;
    const target: HTMLDivElement = this.$el.querySelector('.alarm-chart-wrap');
    const itemWidth = target?.children?.[0]?.clientWidth || 6;
    for (const item of this.localData) {
      w += itemWidth + 2;
      if (!startTime && w - 2 > startX) {
        startTime = item.time;
      }
      if (!endTime && w > endX) {
        console.log(w, endX);
        endTime = item.time;
        break;
      }
    }
    this.selectedTimeRange = [startTime, endTime];
    const timeFrom = dayjs(+startTime.toFixed(0)).format('YYYY-MM-DD HH:mm:ss');
    const timeTo = dayjs(+endTime.toFixed(0)).format('YYYY-MM-DD HH:mm:ss');
    this.$emit('dataZoom', timeFrom, timeTo);
  }

  handleTimeRangeReset() {
    this.selectedTimeRange = [];
  }

  alarmListRender(item) {
    const isSelected = this.curActive === item.time;
    const isHover = this.curHover === item.time && item.type !== EAlarmType.gray;
    let color = alarmColorMap.default[item.type];
    if (isHover) {
      color = alarmColorMap.hover[item.type];
    }
    if (isSelected) {
      color = alarmColorMap.selected[item.type];
    }
    return (
      <div
        key={item.time}
        style={{
          height: `${isSelected || isHover ? this.activeItemHeight : this.itemHeight}px`,
          background: `${color}`,
          cursor: item.type !== EAlarmType.gray ? 'pointer' : 'default',
        }}
        class={['time-cube', { 'adaptive-width': this.isAdaption }]}
        onClick={() => this.handleClick(item)}
        onMouseenter={event => this.handleMouseEnter(event, item)}
        onMouseleave={() => this.handleMouseLeave()}
      />
    );
  }

  render() {
    return (
      <div
        style={{
          width: this.isAdaption ? '100%' : `${this.localData.length * 8 - 2}px`,
        }}
        class='bar-alarm-chart'
      >
        {this.showHeader && (
          <div class='alarm-header-wrap'>
            <div class='header-left'>{this.$slots?.title || ''}</div>
            {!!this.timeRange.length && (
              <div
                class='header-center'
                onClick={() => this.handleTimeRangeReset()}
              >
                {this.$t('复位')}
              </div>
            )}
            <div class='header-right'>{this.$slots?.more || ''}</div>
          </div>
        )}
        <div
          style={{
            height: `${this.activeItemHeight}px`,
          }}
          class='alarm-chart-wrap'
          onMousedown={this.handleMouseDown}
        >
          {this.loading ? (
            <div class='skeleton-element bar-loading' />
          ) : (
            this.localData.map(item => this.alarmListRender(item))
          )}
        </div>
        {this.showXAxis && (
          <div class='alarm-footer-wrap'>
            {this.xAxis.map(item => (
              <div
                key={item}
                class='x-axis-item'
              >
                {item}
              </div>
            ))}
          </div>
        )}
        <div
          style={{
            display: 'none',
          }}
        >
          <div
            ref='tips'
            class='bar-alarm-chart-tooltip'
          >
            <div class='time-text'>{dayjs(this.curHover).format('YYYY-MM-DD HH:mm:ss')}</div>
            {this.statusList.map((item, index) => (
              <div
                key={index}
                class='status-wrap'
              >
                <div
                  style={{
                    background: item.color,
                  }}
                  class='status-color'
                />
                <div class='status-text'>{item.text}</div>
              </div>
            ))}
          </div>
        </div>
        <div
          style={{
            height: `${this.activeItemHeight + 14}px`,
            width: `${this.boxSelector.width}px`,
            top: `${this.boxSelector.top}px`,
            left: `${this.boxSelector.left}px`,
            display: this.boxSelector.start ? 'block' : 'none',
          }}
          class='box-selector'
        />
      </div>
    );
  }
}
