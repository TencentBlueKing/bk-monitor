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
import { Component, InjectReactive, Ref } from 'vue-property-decorator';
import { ofType } from 'vue-tsx-support';

import dayjs from 'dayjs';
import bus from 'monitor-common/utils/event-bus';
import { random } from 'monitor-common/utils/utils';
import { handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';

import ChartHeader from '../../components/chart-title/chart-title';
import { VariablesService } from '../../utils/variable';
import CommonSimpleChart from '../common-simple-chart';

import type { IExtendMetricData, PanelModel } from '../../typings';
import type { ITableItem } from 'monitor-pc/pages/monitor-k8s/typings';

import './percentage-bar.scss';

interface ILineEchartProps {
  panel: PanelModel;
}

type TableFontClassType = 'font-large' | 'font-middle' | 'font-normal';

@Component
class PercentageBarChart extends CommonSimpleChart {
  @Ref() chartHeaderRef: ChartHeader;
  @Ref() tableRef: HTMLElement;
  @Ref() saveImageRef: HTMLElement;

  // 是否在分屏展示
  @InjectReactive('isSplitPanel') isSplitPanel: boolean;
  // 是否是只读模式
  @InjectReactive('readonly') readonly readonly: boolean;

  /** 图表类名 */
  tableClass = '';
  inited = false;
  refleshIntervalInstance = null;
  /** 图表数据 */
  chartDataList: any[] = [];
  metrics: IExtendMetricData[];
  emptyText = window.i18n.tc('查无数据');
  empty = true;
  // 查看更多链接
  viewMoreLink = '';
  isFetchingData = false;
  cellValueMaxWidth = 0;

  get showMoreData() {
    return this.viewMoreLink !== '';
  }
  get hasFilterBar() {
    return this.panel.options?.percentage_bar?.filter_key || false;
  }
  get filterList() {
    return this.panel.options?.percentage_bar?.filter_list || [];
  }

  /**
   * @description: 重写ResizeMixin的handleResize方法
   * 计算avr-chart-main的宽高
   */
  handleResize() {
    this.tableClass = this.handleUpdateTableFontSize();
  }

  /**
   * @description: 获取图表数据
   */
  async getPanelData(start_time?: string, end_time?: string) {
    if (!this.isInViewPort()) {
      if (this.intersectionObserver) {
        this.unregisterOberver();
      }
      this.registerObserver(start_time, end_time);
      return;
    }
    if (this.isFetchingData) return;
    this.isFetchingData = true;
    this.handleLoadingChange(true);
    this.emptyText = window.i18n.tc('加载中...');
    try {
      this.unregisterOberver();
      let moreDataUrl = '';
      let series = [];
      let metrics = [];
      const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
      const params = {
        start_time: start_time ? dayjs.tz(start_time).unix() : startTime,
        end_time: end_time ? dayjs.tz(end_time).unix() : endTime,
      };
      const interval = (this.viewOptions.interval, params.end_time - params.start_time, this.panel.collect_interval);
      const variablesService = new VariablesService({
        ...this.viewOptions,
        interval,
      });
      const promiseList = this.panel.targets.map(item =>
        (this as any).$api[item.apiModule]
          [item.apiFunc](
            {
              ...variablesService.transformVariables(item.data, {
                ...this.viewOptions.filters,
                ...this.viewOptions,
                interval,
              }),
              ...params,
            },
            { needMessage: false }
          )
          .then(res => {
            series = res.data || [];
            metrics = res.metrics || [];
            moreDataUrl = res.more_data_url || '';
            this.clearErrorMsg();
            return true;
          })
          .catch(error => {
            this.handleErrorMsgChange(error.msg || error.message);
          })
      );
      const res = await Promise.all(promiseList).catch(() => false);
      if (res && series.length) {
        this.updateChartData(series);
        this.metrics = metrics;
        this.viewMoreLink = moreDataUrl;
        this.inited = true;
        this.empty = false;
        this.$nextTick(this.handleResize);
      } else {
        this.emptyText = window.i18n.tc('查无数据');
        this.empty = true;
      }
    } catch (e) {
      this.empty = true;
      this.emptyText = window.i18n.tc('出错了');
      console.error(e);
    }
    this.isFetchingData = false;
    this.handleLoadingChange(false);
  }

  /**
   * @description: 更新图表的数据
   */
  updateChartData(srcData) {
    const hasTotal = srcData.every(data => data.total);
    if (hasTotal) {
      // 若返回数据带total 则计算百分占比则为此total
      this.chartDataList = srcData.map(item => ({
        ...item,
        usage: item.value / item.total,
      }));
    } else {
      // 如无total 则获取数组最大value作为total
      const total = srcData.reduce((pre, curv) => (pre.value < curv.value ? curv : pre))?.value;
      this.chartDataList = srcData.map(item => ({
        ...item,
        usage: item.value / total,
      }));
    }
  }

  /**
   * @description:
   * @param {number} num
   */
  handleProgressUsage(num: number) {
    if (typeof num === 'number' && num >= 0) {
      return num <= 1 ? num * 100 : num;
    }
    return 0;
  }

  /**
   * @description: 跳转更多的数据
   */
  handleShowMoreData() {
    window.open(this.viewMoreLink, '_blank');
  }

  /**
   * @desc
   * @param { Boolean } name
   * @returns { Boolean }
   */
  // link点击事件
  handleLinkClick(item: ITableItem<'link'>) {
    if (this.readonly || !item.url) return;
    if (item.target === 'self') {
      if (this.isSplitPanel) {
        const route = this.$router.resolve({
          path: item.url,
        });
        const url = `${location.origin}/${location.search}${route.href}`;
        window.open(url);
      } else {
        this.$router.push({
          path: `${window.__BK_WEWEB_DATA__?.baseroute || ''}${item.url}`.replace(/\/\//g, '/'),
        });
      }
      return;
    }
    if (item.target === 'event') {
      bus.$emit(item.key, item);
    } else {
      window.open(item.url, random(10));
    }
  }

  /**
   * @description: 更新图表的字体大小
   */
  handleUpdateTableFontSize(): TableFontClassType {
    const firstRowCellValue = this.tableRef?.querySelector('.first-row .cell-value');
    if (firstRowCellValue) {
      const { width } = firstRowCellValue.getBoundingClientRect();
      this.cellValueMaxWidth = width;
    }
    // const { height } = firstRow?.getBoundingClientRect() || { height: 0 };
    // if (height <= 50) {
    //   return 'font-normal';
    // } if (height > 50 && height <= 80) {
    //   return 'font-middle';
    // }
    // return 'font-large';

    // 暂时固定字体大小
    return 'font-normal';
  }

  render() {
    return (
      <div class='percentage-bar-chart-wrap'>
        <ChartHeader
          ref='chartHeaderRef'
          class='draggable-handle'
          draging={this.panel.draging}
          isInstant={this.panel.instant}
          metrics={this.metrics}
          showMore={false}
          subtitle={this.panel.subTitle || ''}
          title={this.panel.title}
          onUpdateDragging={() => this.panel.updateDraging(false)}
        />
        {!this.empty ? (
          <div class='avr-chart-main'>
            <table
              ref='tableRef'
              class={['avr-chart-table', this.tableClass]}
            >
              {this.inited &&
                this.chartDataList.map((item, index) => (
                  <tr
                    key={index}
                    class={['avr-chart-tr', { 'first-row': index === 0 }]}
                  >
                    <td class='avr-cell cell-label'>
                      <div class='avr-cell-content'>
                        <span class='num'>{item.value}</span>
                        <span class='unit'>{item.unit}</span>
                      </div>
                    </td>
                    <td class='avr-cell cell-value'>
                      <div class='avr-cell-content item-cell-bar'>
                        <div
                          style={{
                            maxWidth: this.cellValueMaxWidth > 10 ? `${this.cellValueMaxWidth}px` : 'initial',
                            whiteSpace: this.cellValueMaxWidth > 10 ? 'nowrap' : 'wrap',
                          }}
                          class={['content-label', { 'link-label': item.type === 'link' }]}
                          title={item.name}
                          onClick={() => (item.type === 'link' ? this.handleLinkClick(item) : false)}
                        >
                          {item.name}
                        </div>
                        <div class='progress-bar'>
                          <div
                            style={`width: ${this.handleProgressUsage(item.usage)}%;`}
                            class='progress-inner'
                          />
                        </div>
                      </div>
                    </td>
                  </tr>
                ))}
            </table>
            {this.showMoreData && (
              <div class='more-data-row'>
                <span
                  class='more-data-btn'
                  onClick={this.handleShowMoreData}
                >
                  更多数据
                </span>
              </div>
            )}
          </div>
        ) : (
          <div class='empty-chart'>{this.emptyText}</div>
        )}
      </div>
    );
  }
}

export default ofType<ILineEchartProps>().convert(PercentageBarChart);
