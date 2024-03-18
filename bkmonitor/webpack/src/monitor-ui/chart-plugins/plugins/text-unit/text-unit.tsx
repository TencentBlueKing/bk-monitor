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
import dayjs from 'dayjs';
import { handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';

import { getValueFormat } from '../../../monitor-echarts/valueFormats';
import ChartTitle from '../../components/chart-title/chart-title';
import { reviewInterval } from '../../utils';
import { VariablesService } from '../../utils/variable';
import CommonSimpleChart from '../common-simple-chart';

import './text-unit.scss';

interface ITextUnitSeriesItem {
  // 值
  value: string | number;
  // 单位
  unit: string | number;
}
@Component
export default class TextUnit extends CommonSimpleChart {
  series: ITextUnitSeriesItem = { value: 0, unit: '' };
  empty = true;
  emptyText = '';
  isFetchingData = false;
  async getPanelData(start_time?: string, end_time?: string) {
    const res = await this.beforeGetPanelData(start_time, end_time);
    if (!res) return;
    this.unregisterOberver();
    if (this.isFetchingData) return;
    this.isFetchingData = true;
    this.handleLoadingChange(true);
    this.emptyText = window.i18n.tc('加载中...');
    try {
      const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
      const params = {
        start_time: start_time ? dayjs.tz(start_time).unix() : startTime,
        end_time: end_time ? dayjs.tz(end_time).unix() : endTime,
        bk_biz_id: this.bkBizId || window.cc_biz_id
      };
      const variablesService = new VariablesService({
        ...this.scopedVars,
        interval: reviewInterval(
          this.viewOptions.interval,
          params.end_time - params.start_time,
          this.panel.collect_interval
        )
      });
      const promiseList = this.panel.targets.map(item =>
        (this as any).$api[item.apiModule]
          [item.apiFunc](
            {
              ...variablesService.transformVariables(item.data),
              ...params
            },
            { needMessage: false }
          )
          .then(({ value, unit }) => {
            // 单位转换
            const formater = getValueFormat(unit || '')(+value);
            this.series = {
              value: +formater.text || '',
              unit: formater.suffix
            };
            this.clearErrorMsg();
            return true;
          })
          .catch(error => {
            this.handleErrorMsgChange(error.msg || error.message);
          })
      );
      const res = await Promise.all(promiseList).catch(() => false);
      if (res) {
        this.inited = true;
        this.empty = false;
        this.emptyText = window.i18n.tc('查无数据');
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
  render() {
    return (
      <div class='text-unit'>
        <ChartTitle
          class='draggable-handle text-header'
          title={this.panel.title}
          showMore={false}
          draging={this.panel.draging}
          isInstant={this.panel.instant}
          onUpdateDragging={() => this.panel.updateDraging(false)}
        />
        <div class='text-wrapper'>
          {!this.empty && this.series?.value ? (
            <div class='text-item'>
              <div class='text-wrapper-value'>{this.series.value}</div>
              <div class='text-wrapper-unit'>{this.series.unit}</div>
            </div>
          ) : (
            <div class='text-wrapper-empty'>{this.emptyText}</div>
          )}
        </div>
      </div>
    );
  }
}
