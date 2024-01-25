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
import { Component } from 'vue-property-decorator';
import { ofType } from 'vue-tsx-support';
import dayjs from 'dayjs';

import { handleTransformToTimestamp } from '../../../../monitor-pc/components/time-range/utils';
import { PanelModel } from '../../typings';
import CommonSimpleChart from '../common-simple-chart';

import './icon-chart.scss';

interface IIconChartProps {
  panel: PanelModel;
}

enum StatusIconEnum {
  SUCCESS = 'check-line',
  WARNING = 'close-line-2',
  FAILD = 'minus-line'
}

type StatusType = 'SUCCESS' | 'WARNING' | 'FAILD';

@Component
// eslint-disable-next-line max-len
class IconChart extends CommonSimpleChart {
  /** 图表数据 */
  chartDataList: any[] = [];
  inited = false;
  emptyText = window.i18n.tc('查无数据');
  empty = true;

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
    this.handleLoadingChange(true);
    this.emptyText = window.i18n.tc('加载中...');
    try {
      this.unregisterOberver();
      const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
      const params = {
        start_time: start_time ? dayjs.tz(start_time).unix() : startTime,
        end_time: end_time ? dayjs.tz(end_time).unix() : endTime
      };
      const viewOptions = {
        ...this.viewOptions
      };
      const promiseList = this.panel.targets.map(
        item =>
          (this as any).$api[item.apiModule]
            ?.[item.apiFunc]?.(
              {
                ...item.data,
                ...params,
                view_options: {
                  ...viewOptions
                }
              },
              { needMessage: false }
            )
            .then(res => {
              this.clearErrorMsg();
              return res;
            })
            .catch(error => {
              this.handleErrorMsgChange(error.msg || error.message);
            })
      );
      const data = await Promise.all(promiseList);
      data && this.updateChartData(data);
      if (data) {
        this.updateChartData(data);
        this.inited = true;
        this.empty = false;
        if (!data.length) {
          this.emptyText = window.i18n.tc('查无数据');
          this.empty = true;
        }
      }
    } catch (e) {
      this.empty = true;
      this.emptyText = window.i18n.tc('出错了');
      console.error(e);
    }
    this.handleLoadingChange(false);
  }

  /**
   * @description: 更新图表的数据
   */
  updateChartData(srcData) {
    this.chartDataList = srcData.reduce((total, cur) => {
      if (!!cur) return total.concat(cur);
      return total;
    }, []);
  }

  render() {
    const getIcon = (status: StatusType) => StatusIconEnum[status];
    return (
      <div class='icon-chart-wrap'>
        {!this.empty ? (
          <ul class='icon-chart-main'>
            {this.chartDataList.map(item => (
              <li class='icon-item'>
                <div class='icon-wrap'>
                  <div class={`icon-box box-${item.status}`}>
                    <i class={`bk-icon icon-${getIcon(item.status)}`}></i>
                  </div>
                  <div
                    class='icon-item-label'
                    v-bk-overflow-tips
                  >
                    {item.label}
                  </div>
                </div>
                {!!this.panel.instant && (
                  <img
                    alt=''
                    class='instant-icon'
                    // eslint-disable-next-line @typescript-eslint/no-require-imports
                    src={require(`../../../../fta-solutions/static/img/home/icon_mttr.svg`)}
                    v-bk-tooltips={{
                      content: 'lgnores selected time',
                      boundary: 'window',
                      placements: ['top']
                    }}
                  />
                )}
              </li>
            ))}
          </ul>
        ) : (
          <div class='empty-chart'>{this.emptyText}</div>
        )}
        <div class='draggable-handle draggable-handle-bar'></div>
      </div>
    );
  }
}

export default ofType<IIconChartProps>().convert(IconChart);
