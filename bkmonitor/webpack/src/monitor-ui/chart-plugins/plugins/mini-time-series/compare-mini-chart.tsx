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
import { Component, Prop, Watch } from 'vue-property-decorator';

import dayjs from 'dayjs';

import { getValueFormat } from '../../../monitor-echarts/valueFormats/valueFormats';
import { echarts } from '../../typings/index';
import MiniTimeSeries from './mini-time-series';

export enum EDropType {
  compare = 'compare',
  end = 'end',
  refer = 'refer',
}
export enum EPointType {
  compare = 'compare',
  end = 'end',
  refer = 'refer',
}

/* 用于两点对比 */
@Component
export default class CompareMiniChart extends MiniTimeSeries {
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

  /**
   * @description tooltip 配置
   * @returns
   */
  getTooltipParams() {
    return {
      ...this.options.tooltip,
      className: 'mini-time-series-chart-tooltip',
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
          const valueText = getValueFormat(this.unit)(value, this.unitDecimal);
          return `
        <div class="left-compare-type" style="background: ${timeTitle === compareTitleText ? '#7B29FF' : '#FFB848'};"></div>
        <div>
          <div>${timeTitle}：${dayjs.tz(time).format('YYYY-MM-DD HH:mm:ss')}</div>
          <div>${this.valueTitle}：${valueText.text}${valueText.suffix}</div>
        </div>`;
        }
        if (this.isMouseOver) {
          const valueText = getValueFormat(this.unit)(params[0].value[1] || 0, this.unitDecimal);
          return `<div>
          <div>${dayjs.tz(params[0].value[0]).format('YYYY-MM-DD HH:mm:ss')}</div>
          <div>${this.valueTitle}：${valueText.text}${valueText.suffix}</div>
        </div>`;
        }
        return undefined;
      },
    };
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
   * @description 设置标记点数据
   * @param needSetOption
   */
  setMarkPointData(needSetOption = true) {
    const markPointData = [];
    const seriesData = this.options.series[0].data || [];
    if (this.showLastMarkPoint && seriesData.length) {
      const lastItem = seriesData[seriesData.length - 1];
      const valueItem = getValueFormat(this.unit)(lastItem.value[1], this.unitDecimal);
      this.lastValue = `${valueItem.text}${valueItem.suffix}`;
      markPointData.push({
        coord: [lastItem.value[0], lastItem.value[1]],
        symbol: 'circle',
        symbolSize: 6,
        itemStyle: {
          color: '#fff',
          borderColor: '#699DF4',
          borderWidth: 2,
        },
      });
    }
    /* compare */
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
    if (needSetOption) {
      (this as any).instance?.setOption(this.options);
    }
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
   * @description 图表事件
   */
  seriesHandleEvents() {
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
  }

  otherInitFn() {
    this.handleWatchPointType(this.pointType);
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
}
