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

import bus from '../../../../monitor-common/utils/event-bus';
import { random } from '../../../../monitor-common/utils/utils';
import { handleTransformToTimestamp } from '../../../../monitor-pc/components/time-range/utils';
import { PanelModel } from '../../typings';
import { findComponentUpper } from '../../utils';
import { VariablesService } from '../../utils/variable';
import { CommonSimpleChart } from '../common-simple-chart';

import './number-chart.scss';

interface INumberChartProps {
  panel: PanelModel;
}
@Component
// eslint-disable-next-line max-len
class NumberChart extends CommonSimpleChart {
  /** 图表数据 */
  chartDataList: any[] = [];

  /**
   * @description: 获取ChartWrapper组件
   */
  handleFindChartWrapper() {
    return findComponentUpper(this, 'ChartWrapper');
  }

  /**
   * @description: 获取图表数据
   */
  async getPanelData(start_time?: string, end_time?: string) {
    this.unregisterOberver();
    this.handleLoadingChange(true);
    const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
    const params = {
      start_time: start_time ? dayjs.tz(start_time).unix() : startTime,
      end_time: end_time ? dayjs.tz(end_time).unix() : endTime
    };
    const variablesService = new VariablesService({
      ...this.viewOptions
    });
    const promiseList = this.panel.targets.map(
      item =>
        // eslint-disable-next-line max-len
        (this as any).$api[item.apiModule]
          ?.[item.apiFunc]?.({ ...params, ...variablesService.transformVariables(item.data) }, { needMessage: false })
          .then(data => {
            this.clearErrorMsg();
            return data;
          })
          .catch(error => {
            this.handleErrorMsgChange(error.msg || error.message);
            return null;
          })
    );
    const data = await Promise.all(promiseList);
    data?.filter(Boolean)?.length && this.updateChartData(data);
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

  /** 点击跳转 */
  handleLinkTo(item) {
    if (!!item.link) {
      if (item.link.target === 'self') {
        this.$router.push({
          path: `${window.__BK_WEWEB_DATA__?.baseroute || ''}${item.link.url}`.replace(/\/\//g, '/')
        });
        return;
      }
      if (item.link.target === 'event') {
        bus.$emit(item.link.key, item.link);
      } else {
        window.open(item.link.url, random(10));
      }
    }
  }

  render() {
    return (
      <div class='number-chart-wrap'>
        <ul class='number-chart-main'>
          {this.chartDataList.map(item => (
            <li
              class={['number-item', { 'is-link': !!item.link }]}
              onClick={() => this.handleLinkTo(item)}
            >
              <div class='number-item-label'>
                <span>{item.value}</span>
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
              </div>
              <div class='number-item-value'>
                <span>{item.label}</span>
              </div>
            </li>
          ))}
        </ul>
        <div class='draggable-handle draggable-handle-bar'></div>
      </div>
    );
  }
}

export default ofType<INumberChartProps>().convert(NumberChart);
