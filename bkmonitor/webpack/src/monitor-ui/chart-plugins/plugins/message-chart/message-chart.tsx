/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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
import { Component, Prop } from 'vue-property-decorator';

import dayjs from 'dayjs';
import { handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';

// import { getValueFormat } from '../../../monitor-echarts/valueFormats';
import { reviewInterval } from '../../utils';
import { VariablesService } from '../../utils/variable';
import CommonSimpleChart from '../common-simple-chart';

import type { ITablePagination } from 'monitor-pc/pages/monitor-k8s/typings';

import './message-chart.scss';

@Component
export default class MessageChart extends CommonSimpleChart {
  @Prop() a: number;
  empty = true;
  emptyText = '';
  isFetchingData = false;
  series = [];
  expand = [];
  pagination: ITablePagination = {
    current: 1,
    count: 0,
    limit: 10,
  };
  total = 0;

  get description() {
    return this.panel.options?.header?.tips || '';
  }

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
        bk_biz_id: this.bkBizId || window.cc_biz_id,
      };
      const variablesService = new VariablesService({
        ...this.scopedVars,
        interval: reviewInterval(
          this.viewOptions.interval,
          params.end_time - params.start_time,
          this.panel.collect_interval
        ),
      });
      const promiseList = this.panel.targets.map(item =>
        (this as any).$api[item.apiModule]
          [item.apiFunc](
            {
              ...variablesService.transformVariables(item.data),
              ...params,
              page: this.pagination.current,
              page_size: this.pagination.limit,
            },
            { needMessage: false }
          )
          .then(res => {
            this.series = (res.data || []).map(item => ({
              ...item,
              showAll: false,
              id: item.id.toString(),
            }));
            this.pagination.count = res.total;
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
        this.empty = !this.series.length;
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
  handleTimeRangeChange() {
    this.pagination.current = 1;
    this.getPanelData();
  }
  handlePageChange(type: 'down' | 'last' | 'up') {
    if (type === 'last') {
      this.pagination.current = Math.ceil(this.pagination.count / this.pagination.limit);
    } else {
      this.pagination.current += type === 'up' ? -1 : 1;
    }
    this.getPanelData();
  }

  async handleLimitChange(limit: number): Promise<void> {
    this.pagination.current = 1;
    this.pagination.limit = limit;
    await this.getPanelData();
  }
  handleCollapseClick(v: string[]) {
    this.expand = v;
  }
  handleItemShow(item) {
    item.showAll = !item.showAll;
  }
  render() {
    return (
      <div class='message-chart'>
        <div class='message-chart-title'>
          {this.panel.title}
          {!!this.description && (
            <i
              class='bk-icon icon-info-circle tips-icon'
              v-bk-tooltips={{
                content: this.description,
                allowHTML: true,
                boundary: 'window',
                distance: 0,
                placements: ['top'],
              }}
            />
          )}
        </div>
        {!this.empty ? (
          [
            <div
              key={'01'}
              class='message-chart-pagination'
            >
              {this.$t('共计')}
              <span class='bold-num'>{this.pagination.count}</span>
              {this.$t('条')}
              <span class='pagination-list'>
                {this.$t('当前为第')}
                <span class='bold-num'>
                  {this.pagination.current} / {Math.ceil(this.pagination.count / this.pagination.limit)}
                </span>
                {this.$t('页')}
              </span>
              <div class='pagination-btn'>
                <bk-button
                  disabled={this.pagination.current === 1}
                  onClick={() => this.handlePageChange('up')}
                >
                  {this.$t('上一页')}
                </bk-button>
                <bk-button
                  disabled={this.pagination.current === Math.ceil(this.pagination.count / this.pagination.limit)}
                  onClick={() => this.handlePageChange('down')}
                >
                  {this.$t('下一页')}
                </bk-button>
                <bk-button
                  disabled={this.pagination.current === Math.ceil(this.pagination.count / this.pagination.limit)}
                  onClick={() => this.handlePageChange('last')}
                >
                  {this.$t('末页')}
                </bk-button>
              </div>
            </div>,
            <div
              key={'02'}
              class='collapse-wrapper'
            >
              <bk-collapse
                class='message-chart-collapse'
                active-name={this.expand}
                on-item-click={this.handleCollapseClick}
              >
                {this.series.map(item => (
                  <bk-collapse-item
                    key={item.id}
                    class='collapse-item'
                    hide-arrow={true}
                    name={item.id}
                  >
                    <span
                      class={`icon-monitor icon-mc-triangle-down collapse-item-icon ${
                        this.expand.includes(item.id) ? 'is-expand' : ''
                      }`}
                    />
                    <div class='collapse-item-title'>
                      <div class='item-title'>{item.title}</div>
                      <div class='item-subtitle'>{item.subtitle}</div>
                    </div>
                    <div
                      class='collapse-item-content'
                      slot='content'
                    >
                      {item.content.slice(0, item.showAll ? item.content.length - 1 : 4).map((text, index) => (
                        <pre
                          key={index}
                          class='content-item'
                        >
                          {text}
                        </pre>
                      ))}
                      {item.content.length > 4 && (
                        <bk-button
                          text
                          onClick={() => this.handleItemShow(item)}
                        >
                          {!item.showAll ? this.$t('展开全部') : this.$t('收起')}
                        </bk-button>
                      )}
                    </div>
                  </bk-collapse-item>
                ))}
              </bk-collapse>
            </div>,
          ]
        ) : (
          <div class='empty-chart'>{this.emptyText}</div>
        )}
      </div>
    );
  }
}
