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
import { Component, Inject, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { cloneDeep } from 'lodash';
import { Debounce } from 'monitor-common/utils/utils';

import { getValueFormat } from '../../../monitor-echarts/valueFormats';
import BaseEchart from '../monitor-base-echart';

import type { MonitorEchartOptions } from '../../typings';
import type { ECharts } from 'echarts';

import './aiops-dimension-point.scss';

interface IChartDataItem {
  anomaly_score: number;
  dimension_details: IDimensionDetails[];
  is_anomaly: boolean;
  is_filled?: boolean;
}

interface IDimensionDetails {
  anomaly_score: number;
  dimension_value: string;
  metric_value: number;
}

interface IInfo {
  median?: number;
  metric_alias?: string;
  unit?: string;
}

interface IProps {
  chartData?: IChartDataItem[];
  info: IInfo;
}

@Component
export default class AiopsDimensionPoint extends tsc<IProps> {
  @Ref() baseChart: InstanceType<typeof BaseEchart> & { instance: ECharts };

  @Prop({ type: Array, default: () => [] }) chartData: IChartDataItem[];
  @Prop({ type: Object, default: () => {} }) info: IInfo;
  @Inject('reportEventLog') reportEventLog: (arg: any) => void;
  /** tips 是否初始化事件 */
  initTipsEvent = false;
  /** tips 参数 */
  tipsParams = { name: ' ' };
  /** 数据点移出时，取消高亮的定时器 */
  outTime = null;
  /** 当前高亮的数据点名称 */
  highlightName = '';
  /** 存储tips dom */
  tipsDom: any = null;
  /** 异常数据点依次大小 */
  dimensionSize = [8, 8, 8, 10, 12, 14, 16, 18, 20, 22, 24];
  /** 数据点异常/正常颜色值 */
  dimensionColor = {
    max: 'rgba(234,54,54,0.20)',
    min: 'rgba(58,132,255,0.20)',
  };
  /** 中位数 */
  get median() {
    return this.info?.median || 0;
  }
  /** 将每个数据集中的前2个点放入到数组中 */
  get formatPoint() {
    return this.chartData.map(point => ({
      anomaly_score: point.anomaly_score,
      points: point.dimension_details?.slice?.(0, 2) || [],
    }));
  }
  /** 接近中位数的点 */
  get nearMedianPoint() {
    const medianPoint = this.formatPoint.filter(item => {
      const medianPoint = item.points.find(item => Math.abs(item.anomaly_score - this.median) < 0.05);
      return !!medianPoint;
    });
    return medianPoint;
  }
  /** 当前点是否接近中位数 */
  handleCheckShowMedianPoint(anomaly_score) {
    const diffResult = this.nearMedianPoint.find(point => point.anomaly_score === anomaly_score);
    return !!diffResult;
  }
  get customOptions(): MonitorEchartOptions {
    return {
      grid: {
        left: 20,
        containLabel: false,
      },
      markLine: {
        z: -100,
      },
      xAxis: {
        show: false,
        type: 'value',
        triggerEvent: true,
        minInterval: 0.1,
        inverse: true,
      },
      yAxis: {
        show: false,
        data: [],
        type: 'category',
      },
      tooltip: {
        trigger: 'item',
        axisPointer: {
          type: 'shadow',
          show: false,
        },
        enterable: true,
        transitionDuration: 0,
        position: this.setPosition.bind(this),
        appendToBody: true,
        hideDelay: 30,
        // backgroundColor: `#000000`,
        padding: 0,
        formatter: this.tipsFormatter,
      },
      series: [
        {
          name: 'DimensionLine',
          type: 'line',
          triggerLineEvent: true,
          symbolSize: 10,
          symbol: 'circle',
          z: 100,
          smooth: true,
          lineStyle: {
            opacity: 0,
          },
          markLine: {
            symbol: 'none',
            z: 2,
            lineStyle: {
              type: 'solid',
              width: 2,
              color: '#979BA5',
            },
            data: [{ xAxis: this.median }],
          },
          data: this.getDimensionsData(),
        },
      ],
    };
  }
  /** 补充数据缺失，使得每次绘制10个数据点  */
  fillMissingObjects(data, key, increment = 0.1): IChartDataItem[] {
    // 生成完整的键值集合，步长为 increment
    const completeKeys = Array.from({ length: Math.round(1 / increment) + 1 }, (_, i) =>
      Number.parseFloat((i * increment).toFixed(1))
    );

    // 创建一个键值对映射，便于查找
    const dataMap = new Map(data.map(item => [item[key], item]));

    // 构建最终的完整数据集
    const completeData = completeKeys.map(value => {
      if (dataMap.has(value)) {
        // 如果原始数据中存在该值，直接使用
        return dataMap.get(value);
      }
      // 否则，创建一个新的补充对象
      return {
        [key]: value,
        dimension_details: [],
        is_anomaly: false,
        is_filled: true, // 补充标识
      };
    });

    return completeData as IChartDataItem[];
  }

  /** 生成数据点
   * is_filled 标识为填充的缺失数据，对于缺失数据只需要占位而不需要展示
   */
  getDimensionsData() {
    const data = [];
    const chartData =
      this.chartData.length > 0 ? this.fillMissingObjects(cloneDeep(this.chartData), 'anomaly_score') : this.chartData;
    chartData.forEach(item => {
      let symbolSize = 0;
      const isDimension = item.is_anomaly;
      if (!item.is_filled) {
        /** 异常的需要根据值来决定档位的显示大小 */
        symbolSize = isDimension ? this.dimensionSize[item.anomaly_score * 10] : 8;
      }
      const options = {
        value: [item.anomaly_score, 0],
        mapData: item.dimension_details,
        anomaly_score: item.anomaly_score,
        is_filled: item.is_filled,
      };
      const point = {
        ...options,
        name: String(item.anomaly_score),
        symbolSize,
        cursor: item.is_filled ? 'default' : 'pointer',
        z: 99,
        symbolOffset: [item.anomaly_score === this.median ? '-15%' : '0%', '25%'],
        emphasis: {
          itemStyle: {
            borderWidth: 1,
            borderColor: isDimension ? '#EA3636' : '#3A84FF',
          },
        },
        itemStyle: {
          opacity: item.is_filled ? 0 : 1,
          shadowColor: '#EA3636',
          color: isDimension ? this.dimensionColor.max : this.dimensionColor.min,
        },
      };
      data.push(point);
      /** 对于非填充数据增加热区 */
      if (!item.is_filled) {
        /** 触发热区 */
        const pointCursor = {
          ...options,
          name: `${item.anomaly_score}_cursor`,
          symbolSize: [40, 100],
          itemStyle: {
            opacity: 0,
          },
        };
        data.push(pointCursor);
      }
    });
    return data;
  }
  /** 取消数据点高亮 */
  handleDownplay(params = this.tipsParams) {
    try {
      const { instance } = this.baseChart;
      this.highlightName = '';
      instance.dispatchAction({ type: 'downplay', name: params.name });
      instance.dispatchAction({ type: 'downplay', name: params.name.replace('_cursor', '') });
    } catch {}
  }
  /** 高亮数据点 */
  handleHighlight(params = this.tipsParams) {
    if (!params.name || this.highlightName === params.name) {
      return;
    }
    this.highlightName = params.name;
    const { instance } = this.baseChart;
    instance.dispatchAction({ type: 'highlight', name: params.name });
    instance.dispatchAction({ type: 'highlight', name: params.name.replace('_cursor', '') });
  }
  /** 修复图例不消失问题 & 位置遮挡*/
  setPosition(point, params, dom) {
    /** 确认当前数据点与中位数是否是相近的点，如果是需要一起展示中位数 */
    const medianPoint = this.handleCheckShowMedianPoint(params?.data?.anomaly_score);
    this.tipsParams = params;
    this.tipsDom = dom;
    this.tipsDom.style.backgroundColor =
      params.componentType !== 'markLine' && medianPoint ? 'transparent' : 'rgba(0,0,0,0.8)';
    this.tipsDom.style.transform = 'translateY(-40px)';
    this.tipsDom.classList.add('aiops-dimension-point-tips');
    medianPoint && this.tipsDom.classList.add('aiops-dimension-point-median');
    const hideDom = () => {
      this.tipsDom.style.display = 'none';
      this.handleDownplay();
    };
    const action = () => {
      clearTimeout(this.outTime);
      this.handleHighlight();
    };
    if (!this.initTipsEvent) {
      this.tipsDom.addEventListener('mouseleave', hideDom);
      this.tipsDom.addEventListener('mouseenter', action);
      this.initTipsEvent = true;
    }

    if (params.componentType === 'markLine') {
      return [point[0] + 10, point[1]];
    }
    const rect = this.$el.getBoundingClientRect();
    const top = rect.top + point[1] + (medianPoint ? 110 : 70);
    /** 中位数高度 */
    const medianPointHeight = medianPoint ? 52 : 0;
    /** tips一次最大高度是3条数据的 */
    const mapDataLen = params.data.mapData.length > 3 ? 3 : params.data.mapData.length;
    /** 根据数据条数获取margin的高度 */
    const tipsItemMargin = [0, 12, 24];
    /** 每一条数据具体的高度 */
    const tipsItemHeight = 82;
    /** 真实高度 */
    const tipsContentHeight = 30 + tipsItemMargin[mapDataLen - 1] + mapDataLen * tipsItemHeight;
    if (top + (tipsContentHeight + 30) > window.innerHeight) {
      // 宽度为 tips宽度一半加 左右间距
      return [point[0] - (rect.width / 2 - 40), -(tipsContentHeight + medianPointHeight)];
    }
    return [point[0] - (rect.width / 2 - 40), medianPoint ? 30 : 40];
  }
  /** 自定义tips内容及异常数据点联动 */
  tipsFormatter(params) {
    /** 填充的数据不展示tips */
    if (params?.data?.is_filled) return '';
    /** 确认当前数据点与中位数是否是相近的点，如果是需要一起展示中位数 */
    const medianPoint = this.handleCheckShowMedianPoint(params?.data?.anomaly_score);
    const currParams = params;
    // 上报事件hover tips 日志
    this.reportEventLog?.('event_detail_tips');
    if (currParams.componentType === 'markLine') {
      return `<div class="aiops-dimension-line-tooltip-median"><p>${this.$t('中位数')}：${this.median}</p></div>`;
    }
    let html = '';
    currParams.data.mapData.forEach(item => {
      const value = getValueFormat(this.info.unit)(item.metric_value || 0);
      // biome-ignore lint/suspicious/noGlobalIsNan: <explanation>
      const text = isNaN(Number(item.metric_value)) ? item.metric_value : value.text + value.suffix;
      html += `<li>
              <span class="tooltip-content-label ${item.is_anomaly && 'is-anomaly-label'}" onclick="handleTooltipItem(${
                item.is_anomaly
              },'${item.id}')">
              ${item.dimension_value}
              <i class="icon-monitor icon-mc-position-tips hide-tips-icon"></i>
              </span>
              <p>${this.info.metric_alias}：${text}</p>
              <p>${this.$t('异常分值')}：${item.anomaly_score}</p>
            </li>`;
    });
    return `
      ${medianPoint ? `<p class='median-tips'>${this.$t('中位数')}：${this.median}</p>` : ''}
      <div class="aiops-dimension-line-tooltip-warp">
        <p class='aiops-dimension-count-text'>
           <span>${this.$t('共 {0} 个', [currParams.data.mapData.length])} </span>
         </p>
        <ul class='aiops-dimension-line-tooltip-content bk-scroll-y'>
          ${html}
        </ul>
      </div>
    `;
  }
  /** 挂载实例事件 */
  created() {
    const detailWrapper = document.querySelector('.event-detail-container');
    if (detailWrapper) {
      detailWrapper.addEventListener('scroll', this.hidePointTips);
    }
    window.handleTooltipItem = this.handleTooltipItem;
  }
  destroy(): void {
    window.handleTooltipItem = null;
  }
  beforeDestroy() {
    const detailWrapper = document.querySelector('.event-detail-container');
    if (detailWrapper) {
      detailWrapper.removeEventListener('scroll', this.hidePointTips);
    }
  }
  /** 隐藏tips */
  @Debounce(10)
  hidePointTips() {
    const tipsDom = document.querySelectorAll('.aiops-dimension-point-tips') || [];
    Array.from(tipsDom).forEach(dom => {
      dom.style.display = 'none';
    });
  }
  /** tips 单个数据点点击回调 */
  handleTooltipItem(is_anomaly: boolean, id: string) {
    if (is_anomaly) {
      this.$emit('tipsClick', id);
      this.hidePointTips();
    }
  }
  /** 数据点鼠标移入/移出事件 */
  mouseout(params) {
    if (params.componentType === 'markLine') return;
    /** 延迟取消防止从数据点进入tips时的触发操作 */
    this.outTime = setTimeout(() => {
      this.handleDownplay(params);
    }, 50);
  }
  mouseover(params) {
    if (params.componentType === 'markLine') return;
    this.handleHighlight(params);
  }
  render() {
    return (
      <div class='aiops-dimension-line'>
        {this.chartData.length > 0 && (
          <BaseEchart
            ref='baseChart'
            style='width: 320px;height: 40px;'
            height={40}
            options={this.customOptions}
            onMousemove={this.mouseover}
            onMouseout={this.mouseout}
          />
        )}
      </div>
    );
  }
}
