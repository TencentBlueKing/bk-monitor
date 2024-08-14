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
import { Component, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import dayjs from 'dayjs';

import './bar-alarm-chart.scss';

interface IProps {
  itemHeight?: number;
  activeItemHeight?: number;
  showXAxis?: boolean;
  showHeader?: boolean;
  isAdaption?: boolean;
}

enum EAlarmType {
  blue = 3,
  gray = 'no_data',
  green = 'no_alarm',
  red = 1,
  yellow = 2,
}

const alarmColorMap = {
  [EAlarmType.blue]: '#699DF4',
  [EAlarmType.gray]: '#EAEBF0',
  [EAlarmType.green]: '#2DCB56',
  [EAlarmType.red]: '#FF5656',
  [EAlarmType.yellow]: '#FFB848',
};

interface IDataItem {
  type: EAlarmType;
  time: number;
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

  localData: IDataItem[] = [
    {
      type: EAlarmType.green,
      time: 1723006950000,
    },
    {
      type: EAlarmType.green,
      time: 1723007100000,
    },
    {
      type: EAlarmType.green,
      time: 1723007250000,
    },
    {
      type: EAlarmType.yellow,
      time: 1723007400000,
    },
    {
      type: EAlarmType.yellow,
      time: 1723007550000,
    },
    {
      type: EAlarmType.yellow,
      time: 1723007700000,
    },
    {
      type: EAlarmType.red,
      time: 1723007850000,
    },
    {
      type: EAlarmType.red,
      time: 1723008000000,
    },
    {
      type: EAlarmType.red,
      time: 1723008150000,
    },
    {
      type: EAlarmType.blue,
      time: 1723008300000,
    },
    {
      type: EAlarmType.blue,
      time: 1723008450000,
    },
    {
      type: EAlarmType.blue,
      time: 1723008600000,
    },
    {
      type: EAlarmType.gray,
      time: 1723008750000,
    },
    {
      type: EAlarmType.gray,
      time: 1723008900000,
    },
    {
      type: EAlarmType.gray,
      time: 1723009050000,
    },
    {
      type: EAlarmType.green,
      time: 1723009200000,
    },
    {
      type: EAlarmType.green,
      time: 1723009350000,
    },
    {
      type: EAlarmType.green,
      time: 1723009500000,
    },
    {
      type: EAlarmType.green,
      time: 1723009650000,
    },
    {
      type: EAlarmType.green,
      time: 1723009800000,
    },
    {
      type: EAlarmType.green,
      time: 1723009950000,
    },
    {
      type: EAlarmType.green,
      time: 1723010100000,
    },
    {
      type: EAlarmType.green,
      time: 1723010250000,
    },
    {
      type: EAlarmType.green,
      time: 1723010400000,
    },
  ];

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
  statusList = [
    { color: '#FF9C01', text: '错误率 < 10%' },
    { color: '#3A84FF', text: '发布事件：K8SEvents  45' },
  ];
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

  created() {
    const len = this.localData.length;
    const start = this.localData[0].time;
    const end = this.localData[len - 1].time;
    const center = this.localData[Math.floor(len / 2)].time;
    this.xAxis = [dayjs(start).format('HH:mm'), dayjs(center).format('HH:mm'), dayjs(end).format('HH:mm')];
  }

  /**
   * @description 鼠标移入事件
   * @param event
   * @param item
   * @returns
   */
  handleMouseEnter(event: Event, item: IDataItem) {
    if (item.type === EAlarmType.gray) {
      return;
    }
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
  handleClick(item: IDataItem) {
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
      w += itemWidth;
      if (!startTime && w - 2 > startX) {
        startTime = item.time;
      }
      if (!endTime && w > endX) {
        endTime = item.time;
        break;
      }
    }
    this.timeRange = [startTime, endTime];
  }

  handleTimeRangeReset() {
    this.timeRange = [];
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
          {this.localData.map(item => (
            <div
              key={item.time}
              style={{
                height: `${
                  (this.curHover === item.time && item.type !== EAlarmType.gray) || this.curActive === item.time
                    ? this.activeItemHeight
                    : this.itemHeight
                }px`,
                background: `${alarmColorMap[item.type]}`,
                cursor: item.type !== EAlarmType.gray ? 'pointer' : 'default',
              }}
              class={['time-cube', { 'adaptive-width': this.isAdaption }]}
              onClick={() => this.handleClick(item)}
              onMouseenter={event => this.handleMouseEnter(event, item)}
              onMouseleave={() => this.handleMouseLeave()}
            />
          ))}
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
            <div class='time-text'>2024-04-08 17:58:00</div>
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
