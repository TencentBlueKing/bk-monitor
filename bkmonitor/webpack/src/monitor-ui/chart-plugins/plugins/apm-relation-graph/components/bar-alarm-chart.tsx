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
import { Component, Inject, InjectReactive, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import dayjs from 'dayjs';
import { random } from 'monitor-common/utils';

import { type EDataType, type IAlarmDataItem, alarmColorMap, EAlarmType, getAlarmItemStatusTips } from './utils';

import type { CustomChartConnector } from '../../../utils/utils';
import type { TimeRangeType } from 'monitor-pc/components/time-range/time-range';

import './bar-alarm-chart.scss';

export const getSliceTimeRange = (datas: IAlarmDataItem[], timePoint: number) => {
  let intervalTime = 60 * 1000;
  if (datas.length >= 2) {
    intervalTime = datas[1].time - datas[0].time;
  }
  let sliceStartTime = 0;
  for (const item of datas) {
    if (item.time === timePoint) {
      sliceStartTime = item.time;
      break;
    }
  }
  return [sliceStartTime, sliceStartTime + intervalTime];
};

interface IProps {
  activeItemHeight?: number;
  dataType?: EDataType;
  enableSelect?: boolean;
  enableZoom?: boolean;
  getData?: TGetData;
  groupId?: string;
  isAdaption?: boolean;
  itemHeight?: number;
  needRestoreEvent?: boolean;
  showHeader?: boolean;
  showXAxis?: boolean;
  showXAxisNum?: number;
  sliceTimeRange?: number[];
  xAxisFormat?: string;
  onDataZoom?: () => void;
  onSliceTimeRangeChange?: (v: number[]) => void;
}
type TGetData = (set: (v: IAlarmDataItem[], sliceTimeRange?: number[]) => void) => void;

@Component
export default class BarAlarmChart extends tsc<IProps> {
  @Ref('tips') tipsRef: HTMLDivElement;
  /* 当前item的高度 */
  @Prop({ type: Number, default: 24 }) itemHeight: number;
  /* 当前选中的item的高度 */
  @Prop({ type: Number, default: 32 }) activeItemHeight: number;
  /* 是否展示x轴 */
  @Prop({ type: Boolean, default: false }) showXAxis: boolean;
  /* 是否展示x轴 */
  @Prop({ type: Number, default: 3 }) showXAxisNum: number;
  /* 是否展示头部内容 */
  @Prop({ type: Boolean, default: false }) showHeader: boolean;
  /* 是否自适应宽度 */
  @Prop({ type: Boolean, default: false }) isAdaption: boolean;
  /* 数据类型，上层参数 */
  @Prop({ type: String, default: '' }) dataType: EDataType;
  @Prop({ type: Array, default: () => [] }) sliceTimeRange: number[];
  @Prop({ type: Boolean, default: false }) enableSelect: boolean;
  @Prop({ type: Function, default: null }) getData: TGetData;
  @Prop({ type: Boolean, default: false }) needRestoreEvent: boolean;
  @Prop({ type: Boolean, default: false }) enableZoom: boolean;
  @Prop({ type: String, default: '' }) groupId: string;
  /* x轴label格式 */
  @Prop({ type: String, default: 'HH:mm' }) xAxisFormat: string;

  // 图表的数据时间间隔
  @InjectReactive('timeRange') readonly timeRange!: TimeRangeType;
  // 框选事件范围后需应用到所有图表(包含三个数据 框选方法 是否展示复位  复位方法)
  @Inject({ from: 'handleChartDataZoom', default: () => null }) readonly handleChartDataZoom: (value: any) => void;
  @Inject({ from: 'handleRestoreEvent', default: () => null }) readonly handleRestoreEvent: () => void;
  @InjectReactive({ from: 'showRestore', default: false }) readonly showRestoreInject: boolean;

  @InjectReactive({ from: 'customChartConnector', default: () => null }) customChartConnector: CustomChartConnector;

  loading = false;

  localData: readonly IAlarmDataItem[] = [];

  // 当前悬停的时间戳
  curHover = -1;
  // 当前选中的时间戳
  curActive = -1;
  // x轴刻度
  xAxis = [];
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

  selectedTimeRange = [];

  chartInstance = null;
  chartId = random(8);

  intersectionObserver: IntersectionObserver;
  isIntersecting = true;

  tipsInfo = {
    left: 0,
    top: 0,
    show: false,
  };

  created() {
    this.chartInstance = {
      dispatchAction: this.dispatchAction,
    };
  }

  mounted() {
    setTimeout(this.registerObserver, 20);
    document.addEventListener('wheel', this.tipsHide);
  }

  beforeDestroy() {
    this.unregisterObserver();
    document.removeEventListener('wheel', this.tipsHide);
  }

  registerObserver() {
    if (this.intersectionObserver) {
      this.unregisterObserver();
    }
    this.intersectionObserver = new IntersectionObserver(entries => {
      for (const entry of entries) {
        this.isIntersecting = !!entry.isIntersecting;
        if (!this.isIntersecting) {
          this.tipsHide();
        }
      }
    });
    this.intersectionObserver.observe(this.$el);
  }

  unregisterObserver() {
    if (this.intersectionObserver) {
      this.intersectionObserver.unobserve(this.$el);
      this.intersectionObserver.disconnect();
      this.intersectionObserver = null;
    }
  }

  /* 联动操作 */
  dispatchAction(obj) {
    if (!this.isIntersecting) {
      return;
    }
    if (obj.type === 'showTip') {
      const time = obj.x || -1;
      const item = this.localData.find(v => v.time === time);
      const target = this?.$el?.querySelector?.(`.time-cube______${time}`);
      if (item && target) {
        this.getTips(item);
        this.curHover = item.time;
        this.tipsShow();
      } else {
        this.curHover = -1;
        this.tipsHide();
      }
    }
  }

  @Watch('timeRange')
  handleWatchTimeRange() {
    if (this.needRestoreEvent) {
      this.initData();
    }
  }

  @Watch('sliceTimeRange')
  handleWatchSliceTimeRange(sliceTimeRange: number[]) {
    this.curActive = -1;
    if (this.enableSelect) {
      if (sliceTimeRange?.every?.(v => !!v)) {
        const [sliceStartTime] = sliceTimeRange;
        for (const item of this.localData) {
          if (item.time >= sliceStartTime) {
            this.curActive = item.time;
            break;
          }
        }
      }
    }
  }

  initData() {
    if (this.getData) {
      this.loading = true;
      this.getData((data, sliceTimeRange?) => {
        this.loading = false;
        this.localData = Object.freeze(data);
        this.curActive = -1;
        if (this.customChartConnector?.groupId === this.groupId) {
          this.customChartConnector.setCustomChartInstance(this.chartId, this.chartInstance);
        }
        if (this.localData.length) {
          if (this.showXAxisNum === 3) {
            const len = this.localData.length;
            const start = this.localData[0].time;
            const end = this.localData[len - 1].time;
            const center = this.localData[Math.floor(len / 2)].time;
            this.xAxis = [
              dayjs(start).format(this.xAxisFormat),
              dayjs(center).format(this.xAxisFormat),
              dayjs(end).format(this.xAxisFormat),
            ];
          } else if (this.showXAxisNum === 2) {
            const len = this.localData.length;
            const start = this.localData[0].time;
            const end = this.localData[len - 1].time;
            this.xAxis = [dayjs(start).format(this.xAxisFormat), dayjs(end).format(this.xAxisFormat)];
          }

          if (this.enableSelect) {
            if (sliceTimeRange?.every?.(v => !!v)) {
              const [sliceStartTime] = sliceTimeRange;
              for (const item of this.localData) {
                if (item.time >= sliceStartTime) {
                  this.curActive = item.time;
                  break;
                }
              }
            }
            /* if (this.curActive <= 0) {
              this.curActive = this.localData[this.localData.length - 1].time;
            } */
          }
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
    // if (item.type === EAlarmType.gray) {
    //   return;
    // }
    this.getTips(item);
    this.curHover = item.time;
    if (this.customChartConnector?.groupId === this.groupId) {
      this.customChartConnector.updateCustomAxisPointer(this.chartId, item.time);
    }
    this.tipsShow();
  }
  /**
   * @description 鼠标离开事件
   */
  handleMouseLeave() {
    this.curHover = -1;
    this.tipsHide();
    if (this.customChartConnector?.groupId === this.groupId) {
      this.customChartConnector.updateCustomAxisPointer(this.chartId, 0);
    }
  }
  /**
   * @description 点击事件
   * @param item
   * @returns
   */
  handleClick(item: IAlarmDataItem) {
    if (item.type === EAlarmType.gray || !this.enableSelect) {
      return;
    }
    if (this.curActive === item.time) {
      this.curActive = -1;
      // this.curActive = this.localData[this.localData.length - 1].time;
      this.$emit('sliceTimeRangeChange', [0, 0]);
    } else {
      this.curActive = item.time;
      this.$emit('sliceTimeRangeChange', getSliceTimeRange(this.localData as any, item.time));
    }
  }

  /**
   * @description 鼠标按下事件
   * @param event
   */
  handleMouseDown(event: MouseEvent) {
    if (this.loading || !this.localData.length || !this.enableZoom) {
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
        endTime = item.time;
        break;
      }
    }
    this.selectedTimeRange = [startTime, endTime];
    const timeFrom = dayjs(+startTime.toFixed(0)).format('YYYY-MM-DD HH:mm:ss');
    const timeTo = dayjs(+endTime.toFixed(0)).format('YYYY-MM-DD HH:mm:ss');
    if (this.needRestoreEvent) {
      this.handleChartDataZoom([startTime, endTime]);
    } else {
      this.$emit('dataZoom', timeFrom, timeTo);
    }
  }

  handleTimeRangeReset() {
    this.selectedTimeRange = [];
    this.handleRestoreEvent();
  }

  alarmChartWrap() {
    if (this.loading) {
      return <div class='skeleton-element bar-loading' />;
    }
    if (!this.localData.length) {
      return <div class='no-data'>{this.$t('暂无数据')}</div>;
    }
    return this.localData.map(item => this.alarmListRender(item));
  }

  tipsShow() {
    try {
      if (this.curHover <= 0) {
        this.tipsInfo.show = false;
        return;
      }
      const target = this.$el.querySelector(`.time-cube______${this.curHover}`);
      const wrapTarget = this.$el.querySelector('.alarm-chart-wrap');
      if (target && wrapTarget) {
        const tipTarget = this.$el.querySelector('.bar-alarm-chart-tooltip');
        const tipWidth = tipTarget?.clientWidth || 137;
        const { x } = target.getBoundingClientRect();
        const { y } = wrapTarget.getBoundingClientRect();
        const left = x - tipWidth / 2;
        const top = y - 60;
        let tLeft = left;
        const tTop = top;
        const { clientWidth } = document.body;
        if (tLeft >= clientWidth - tipWidth) {
          tLeft = clientWidth - tipWidth;
        } else if (tLeft <= 0) {
          tLeft = 0;
        }
        this.tipsInfo = {
          left: tLeft,
          top: tTop,
          show: true,
        };
      } else {
        this.tipsInfo.show = false;
      }
    } catch (err) {
      console.error(err);
    }
  }
  tipsHide() {
    this.tipsInfo.show = false;
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
    const height = isSelected || isHover ? this.activeItemHeight : this.itemHeight;
    // if (item.value === null) {
    //   height = 0;
    // }
    return (
      <div
        key={item.time}
        style={{
          height: `${height}px`,
          background: `${color}`,
          cursor: item.type !== EAlarmType.gray ? 'pointer' : 'default',
        }}
        class={['time-cube', `time-cube______${item.time}`, { 'adaptive-width': this.isAdaption }]}
        onClick={() => this.handleClick(item)}
        onMouseenter={event => this.handleMouseEnter(event, item)}
        // onMouseleave={() => this.handleMouseLeave()}
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
            {(this.needRestoreEvent ? this.showRestoreInject : this.selectedTimeRange.length) ? (
              <div
                class='header-center'
                onClick={() => this.handleTimeRangeReset()}
              >
                {this.$t('复位')}
              </div>
            ) : undefined}
            <div class='header-right'>{this.$slots?.more || ''}</div>
          </div>
        )}
        <div
          style={{
            height: `${this.activeItemHeight}px`,
          }}
          class='alarm-chart-wrap'
          onMousedown={this.handleMouseDown}
          onMouseleave={() => this.handleMouseLeave()}
        >
          {this.alarmChartWrap()}
        </div>
        {this.showXAxis && (
          <div class='alarm-footer-wrap'>
            {this.xAxis.map((item, index) => (
              <div
                key={`${item}_${index}`}
                class='x-axis-item'
              >
                {item}
              </div>
            ))}
          </div>
        )}
        {/* <div
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
        </div> */}
        <div
          style={{
            display: this.tipsInfo.show ? 'block' : 'none',
          }}
        >
          <div
            style={{
              left: `${this.tipsInfo.left}px`,
              top: `${this.tipsInfo.top}px`,
            }}
            class='bar-alarm-chart-tooltip'
          >
            <div class='time-text'>{dayjs.tz(this.curHover).format('YYYY-MM-DD HH:mm:ss')}</div>
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
