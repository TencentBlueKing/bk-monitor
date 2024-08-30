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
import { formatTimeUnitAndValue } from '../../../utils/utils';

import dayjs from 'dayjs';

import { type MonitorEchartOptions, echarts } from '../../../typings/index';

import './mini-chart.scss';

export enum EPointType {
  compare = 'compare',
  end = 'end',
  refer = 'refer',
}
export enum EDropType {
  compare = 'compare',
  end = 'end',
  refer = 'refer',
}

interface IProps {
  data?: number[]; // todo: 待补充
  chartStyle?: {
    lineMaxHeight: number;
    chartWarpHeight: number;
  };
  groupId?: string;
  compareX?: number;
  referX?: number;
  pointType?: EPointType;
  dropType?: EDropType;
  disableHover?: boolean;
  valueTitle?: string;
  unit?: string;
  onPointTypeChange?: (type: EPointType) => void;
  onCompareXChange?: (x: number) => void;
  onReferXChange?: (x: number) => void;
}

@Component
export default class MiniChart extends tsc<IProps> {
  @Ref('chartInstance') chartRef: HTMLDivElement;
  /* 图表样式微调 （缩略图高度非常小仅24px, echarts无法渲染完全，在渲染时实际高度需尽可能占满容器） */
  @Prop({ type: Object, default: () => ({ lineMaxHeight: 24, chartWarpHeight: 50 }) }) chartStyle: IProps['chartStyle'];
  /* groupId */
  @Prop({ type: String, default: '' }) groupId: string;
  /* 对比点 */
  @Prop({ type: Number, default: 0 }) compareX: number;
  /* 参照点 */
  @Prop({ type: Number, default: 0 }) referX: number;
  /* 当前标记点类型 */
  @Prop({ type: String, default: EPointType.compare }) pointType: EPointType;
  /* 拖拽标记点时的状态 */
  @Prop({ type: String, default: EDropType.end }) dropType: EDropType;
  /* 禁止hover tooltip及标记点 */
  @Prop({ type: Boolean, default: false }) disableHover: boolean;
  @Prop({ type: Array, default: () => [] }) data: number[];
  /* tips显示值标题 */
  @Prop({ type: String, default: '数量' }) valueTitle: string;
  @Prop({ type: String, default: '' }) unit: string;

  /* 对比点 */
  localComparePoint = {
    x: 0,
    y: 0,
  };
  /* 参照点 */
  localReferPoint = {
    x: 0,
    y: 0,
  };

  localPointType: EPointType = EPointType.compare;

  options: MonitorEchartOptions = {
    grid: {
      left: 6,
    },
    xAxis: {
      show: false,
      type: 'value',
      max: 'dataMax',
      min: 'dataMin',
    },
    yAxis: {
      show: false,
      type: 'value',
    },
    tooltip: {
      show: true,
      trigger: 'axis',
      appendToBody: true,
      padding: [6, 8, 6, 12],
      transitionDuration: 0,
    },
    series: [
      {
        type: 'line',
        cursor: 'auto',
        silent: false,
        emphasis: {
          disabled: true,
        },
        triggerLineEvent: true,
        data: [],
      },
    ],
  };

  // 当前视图是否hover
  isMouseOver = false;
  /* 当前hover的标记点信息 */
  hoverPoint = {
    isHover: false,
    type: EPointType.end,
    position: {
      x: 0,
      y: 0,
    },
    isMouseDown: false,
  };
  /* 是否开始拖拽 */
  isDrop = false;

  @Watch('disableHover')
  handleWatchDisableHover(disableHover) {
    if (disableHover) {
      this.localPointType = EPointType.compare;
      this.setMarkPointData();
    }
  }

  @Watch('pointType')
  handleWatchPointType(type: EPointType) {
    if (this.localPointType !== type) {
      this.localPointType = type;
      let comparePointY = null;
      let referPointY = null;
      for (const value of this.options.series[0].data) {
        if (this.compareX === value.value[0]) {
          comparePointY = value.value[1];
        }
        if (this.referX === value.value[0]) {
          referPointY = value.value[1];
        }
        if (comparePointY !== null && referPointY !== null) {
          break;
        }
      }
      if (comparePointY !== null)
        this.localComparePoint = {
          x: this.compareX,
          y: comparePointY,
        };
      if (referPointY !== null) {
        this.localReferPoint = JSON.parse(
          JSON.stringify({
            x: this.referX,
            y: referPointY,
          })
        );
      }
      this.setMarkPointData();
    }
  }
  @Watch('compareX')
  handleWatchComparePoint(compareX) {
    if (compareX !== this.localComparePoint.x) {
      let comparePointY = null;
      for (const value of this.options.series[0].data) {
        if (compareX === value.value[0]) {
          comparePointY = value.value[1];
        }
        if (comparePointY !== null) {
          this.localComparePoint = {
            x: this.compareX,
            y: comparePointY,
          };
          this.setMarkPointData();
          break;
        }
      }
    }
  }
  @Watch('referX')
  handleWatchReferPoint(referX) {
    if (referX !== this.localReferPoint.x) {
      let referPointY = null;
      for (const value of this.options.series[0].data) {
        if (referX === value.value[0]) {
          referPointY = value.value[1];
        }
        if (referPointY !== null) {
          this.localReferPoint = {
            x: referX,
            y: referPointY,
          };
          this.setMarkPointData();
          break;
        }
      }
    }
  }

  mounted() {
    this.initChart();
  }

  destroyed() {
    (this as any).instance?.dispose?.();
    (this as any).instance = null;
    this.isMouseOver = false;
  }

  initChart() {
    if (!(this as any).instance) {
      setTimeout(() => {
        if (!this.chartRef) return;
        this.options = {
          ...this.options,
          yAxis: {
            ...this.options.yAxis,
            max: v => {
              return v.max + ((v.max * this.chartStyle.chartWarpHeight) / this.chartStyle.lineMaxHeight - v.max);
            },
            min: v => {
              return 0 - ((v.max * this.chartStyle.chartWarpHeight) / this.chartStyle.lineMaxHeight - v.max) / 1.5;
            },
          },
          tooltip: {
            ...this.options.tooltip,
            className: 'details-side-mini-chart-tooltip',
            formatter: params => {
              if (this.isMouseOver && !this.disableHover) {
                const time = params[0].value[0];
                const value = params[0].value[1] || 0;
                this.hoverPoint.position = {
                  x: time,
                  y: value,
                };
                if (this.localPointType === EPointType.compare) {
                  this.localComparePoint.x = time;
                  this.localComparePoint.y = value;
                }
                if (this.localPointType === EPointType.refer) {
                  this.localReferPoint.x = time;
                  this.localReferPoint.y = value;
                }
                let timeTitle = '';
                const compareTitleText = this.$tc('对比时间');
                const referTitleText = this.$tc('参照时间');
                const isSelectEnd = this.localPointType === EPointType.end;
                if (this.localPointType === EPointType.compare) {
                  timeTitle = compareTitleText;
                } else if (this.localPointType === EPointType.refer) {
                  timeTitle = referTitleText;
                }
                /* 是否选择完对比点及参照点 */
                if (isSelectEnd) {
                  if (this.hoverPoint.type === EPointType.compare) {
                    timeTitle = compareTitleText;
                  } else if (this.hoverPoint.type === EPointType.refer) {
                    timeTitle = referTitleText;
                  } else {
                    return undefined;
                  }
                }
                const valueText = formatTimeUnitAndValue(value, this.unit);
                return `
              <div class="left-compare-type" style="background: ${timeTitle === compareTitleText ? '#7B29FF' : '#FFB848'};"></div>
              <div>
                <div>${timeTitle}：${dayjs(time).format('YYYY-MM-DD HH:mm:ss')}</div>
                <div>${this.valueTitle}：${valueText.value}${valueText.unit}</div>
              </div>`;
              }
              if (this.isMouseOver) {
                const valueText = formatTimeUnitAndValue(params[0].value[1] || 0, this.unit);
                return `<div>
                <div>${dayjs(params[0].value[0]).format('YYYY-MM-DD HH:mm:ss')}</div>
                <div>${this.valueTitle}：${valueText.value}${valueText.unit}</div>
              </div>`;
              }
              return undefined;
            },
          },
          series: [
            {
              ...this.options.series[0],
              ...this.getSymbolItemStyle(),
              ...this.getSeriesStyle(),
              data: this.data.map(item => ({
                value: [item[1], item[0] || 0],
              })),
            },
          ],
        };
        (this as any).instance = echarts.init(this.chartRef);
        (this as any).instance.setOption(this.options);
        for (const event of ['mousemove', 'click']) {
          (this as any).instance.on(event, params => {
            if (event === 'mousemove') {
              if (this.localPointType === EPointType.end && !this.hoverPoint.isMouseDown) {
                this.hoverPoint.isHover = params.componentType === 'markPoint';
                const { x: hoverX } = this.hoverPoint.position;
                if (hoverX === this.compareX) {
                  this.hoverPoint.type = EPointType.compare;
                } else if (hoverX === this.referX) {
                  this.hoverPoint.type = EPointType.refer;
                } else {
                  this.hoverPoint.type = EPointType.end;
                }
                this.setMarkPointData();
              }
            }
          });
        }
        this.handleWatchPointType(this.pointType);
        if (this.groupId) {
          (this as any).instance.group = this.groupId;
        }
      }, 100);
    }
  }

  /**
   * @description 获取鼠标悬停标记点样式
   * @returns
   */
  getSymbolItemStyle() {
    if (this.hoverPoint.isMouseDown) {
      return {
        symbol: 'circle',
        symbolSize: 12,
        showSymbol: false,
        itemStyle: {
          color: this.hoverPoint.type === EPointType.compare ? '#7B29FF' : '#FF9C01',
          borderColor: this.hoverPoint.type === EPointType.compare ? '#DBC5FF' : '#FFD695',
          borderWidth: 1,
        },
      };
    }
    return {
      symbol: this.localPointType === EPointType.end || this.disableHover || !this.isMouseOver ? 'none' : 'circle',
      symbolSize: 8,
      showSymbol: false,
      itemStyle: {
        color: this.localPointType === EPointType.compare ? '#7B29FF' : '#FF9C01',
        borderColor: this.localPointType === EPointType.compare ? '#DBC5FF' : '#FFD695',
        borderWidth: 1,
      },
    };
  }

  /**
   * @description 获取折线与面积样式
   * @returns
   */
  getSeriesStyle() {
    return {
      lineStyle: {
        color: this.localPointType === EPointType.end ? '#C4C6CC' : '#3A84FF',
        width: 1,
      },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          {
            offset: 0,
            color: this.localPointType === EPointType.end ? '#D5D6D9' : '#A4C6FD',
          },
          {
            offset: 1,
            color: '#FFFFFF',
          },
        ]),
      },
    };
  }

  /**
   * @description 点击图表
   * @returns
   */
  handleClick() {
    if (this.localPointType === EPointType.end || this.disableHover) {
      return;
    }
    if (this.localPointType === EPointType.compare) {
      this.localPointType = EPointType.refer;
      this.compareXChange(this.localComparePoint.x);
    } else if (this.localPointType === EPointType.refer) {
      this.localPointType = EPointType.end;
      this.referXChange(this.localReferPoint.x);
    }
    this.pointTypeChange(this.localPointType);
    this.setMarkPointData();
  }

  /**
   * @description 设置标记点数据
   */
  setMarkPointData() {
    const markPointData = [];
    if ([EPointType.refer, EPointType.end].includes(this.localPointType)) {
      const isMouseDown = this.hoverPoint.isMouseDown && this.hoverPoint.type === EPointType.compare;
      markPointData.push({
        coord: [this.localComparePoint.x, this.localComparePoint.y],
        symbol: isMouseDown ? 'none' : 'circle',
        symbolSize: this.hoverPoint.isHover && this.hoverPoint.type === EPointType.compare ? 12 : 8,
        itemStyle: {
          color: '#7B29FF',
          borderColor: '#DBC5FF',
          borderWidth: 1,
        },
      });
    }
    if (this.localPointType === EPointType.end) {
      const isMouseDown = this.hoverPoint.isMouseDown && this.hoverPoint.type === EPointType.refer;
      markPointData.push({
        coord: [this.localReferPoint.x, this.localReferPoint.y],
        symbol: isMouseDown ? 'none' : 'circle',
        symbolSize: this.hoverPoint.isHover && this.hoverPoint.type === EPointType.refer ? 12 : 8,
        itemStyle: {
          color: '#FF9C01',
          borderColor: '#FFD695',
          borderWidth: 1,
        },
      });
    }
    this.options = {
      ...this.options,
      series: [
        {
          ...this.options.series[0],
          ...this.getSymbolItemStyle(),
          ...this.getSeriesStyle(),
          markPoint: {
            animation: false,
            data: markPointData,
          },
        },
      ],
    };
    (this as any).instance?.setOption(this.options);
  }

  pointTypeChange(type: EPointType) {
    this.$emit('pointTypeChange', type);
  }
  compareXChange(x: number) {
    this.$emit('compareXChange', x);
  }
  referXChange(x: number) {
    this.$emit('referXChange', x);
  }

  /**
   * @description 鼠标移入图表
   */
  handleMouseover() {
    this.isMouseOver = true;
    this.setMarkPointData();
  }
  /**
   * @description 鼠标移出图表
   */
  handleMouseleave() {
    this.isMouseOver = false;
    this.dropEnd();
  }
  /**
   * @description 鼠标按下
   */
  handleMouseDown() {
    if (this.hoverPoint.type !== EPointType.end && this.hoverPoint.isHover) {
      this.hoverPoint.isMouseDown = true;
    }
  }
  /**
   * @description 鼠标松开
   */
  handleMouseUp() {
    this.dropEnd();
  }
  /**
   * @description 拖拽开始
   */
  handleMouseMove() {
    if (this.hoverPoint.isMouseDown && !this.isDrop) {
      this.isDrop = true;
      this.setMarkPointData();
    }
  }
  /**
   * @description 拖拽结束/hover结束
   */
  dropEnd() {
    if (this.hoverPoint.isMouseDown) {
      if (this.hoverPoint.type === EPointType.compare) {
        this.localComparePoint = JSON.parse(JSON.stringify(this.hoverPoint.position));
        this.compareXChange(this.localComparePoint.x);
      } else if (this.hoverPoint.type === EPointType.refer) {
        this.localReferPoint = JSON.parse(JSON.stringify(this.hoverPoint.position));
        this.referXChange(this.localReferPoint.x);
      }
      this.hoverPoint = {
        ...this.hoverPoint,
        isMouseDown: false,
        isHover: false,
        type: EPointType.end,
      };
      this.isDrop = false;
    }
    this.hoverPoint.isHover = false;
    this.setMarkPointData();
  }

  render() {
    return (
      <div
        ref='chartInstance'
        style={{
          height: `${this.chartStyle.chartWarpHeight}px`,
        }}
        class={['details-side-mini-chart', { 'is-hover-point': this.hoverPoint.isHover }]}
        onClick={this.handleClick}
        onMousedown={this.handleMouseDown}
        onMouseleave={this.handleMouseleave}
        onMousemove={this.handleMouseMove}
        onMouseover={this.handleMouseover}
        onMouseup={this.handleMouseUp}
      />
    );
  }
}
