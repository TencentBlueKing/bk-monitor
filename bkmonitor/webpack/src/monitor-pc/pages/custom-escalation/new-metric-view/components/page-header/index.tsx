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
import { Component as tsc } from 'vue-tsx-support';

import { customTimeSeriesList } from 'monitor-api/modules/custom_report';
import { copyText } from 'monitor-common/utils/utils';

import customEscalationViewStore from '@store/modules/custom-escalation-view';

import './index.scss';

@Component
export default class PageHeader extends tsc<object> {
  customTimeSeriesList: Readonly<{ data_label: string; name: string; time_series_group_id: number }[]> = [];

  currentCustomTimeSeriesId = 0;
  get currentCustomTimeSeriesName() {
    return (
      this.customTimeSeriesList.find(item => item.time_series_group_id === this.currentCustomTimeSeriesId)?.name || '--'
    );
  }

  get currentSelectedMetricList() {
    return customEscalationViewStore.currentSelectedMetricList;
  }

  async fetchData() {
    const result = await customTimeSeriesList({
      page_size: 200,
    });
    this.customTimeSeriesList = Object.freeze(result.list);
  }

  handleRouterBack() {
    this.$router.push({
      name: 'custom-metric',
    });
  }

  handleSeriesChange(id: number) {
    this.$router.replace({
      params: {
        id: `${id}`,
      },
    });
  }

  handleCopyLink() {
    let hasErr = false;
    copyText(window.location.href, errMsg => {
      this.$bkMessage({
        message: errMsg,
        theme: 'error',
      });
      hasErr = !!errMsg;
    });
    if (!hasErr) {
      this.$bkMessage({
        theme: 'success',
        message: this.$t('复制成功'),
      });
    }
  }

  created() {
    this.fetchData();
    this.currentCustomTimeSeriesId = Number(this.$route.params.id);
  }

  render() {
    return (
      <div class='new-metric-view-page-header'>
        <div class='custom-time-series-box'>
          <i
            class='icon-monitor icon-back-left navigation-bar-back'
            onClick={this.handleRouterBack}
          />
          <div class='custom-time-series-switcher'>
            <bk-select
              v-model={this.currentCustomTimeSeriesId}
              clearable={false}
              popover-min-width={400}
              scroll-height={300}
              searchable
              onChange={this.handleSeriesChange}
            >
              <div
                class='custom-time-series-select-value'
                slot='trigger'
              >
                {this.currentCustomTimeSeriesName}
                <i
                  style='margin-left: 10px; font-size: 12px;'
                  class='icon-monitor icon-mc-arrow-down'
                />
              </div>
              {this.customTimeSeriesList.map(item => (
                <bk-option
                  id={item.time_series_group_id}
                  key={item.time_series_group_id}
                  name={`${item.name}${item.data_label}`}
                >
                  <div
                    class='custom-time-series-name'
                    v-bk-overflow-tips
                  >
                    {item.name}
                  </div>
                  <div
                    class='custom-time-series-label'
                    v-bk-overflow-tips
                  >
                    {item.data_label}
                  </div>
                </bk-option>
              ))}
            </bk-select>
          </div>
        </div>
        {this.currentSelectedMetricList.length > 0 && (
          <div
            class='index-tag'
            v-bk-tooltips={{
              content: this.$t('复制链接'),
              placement: 'right',
            }}
            onClick={this.handleCopyLink}
          >
            {this.currentSelectedMetricList.length === 1 && (
              <span>
                {this.$t('指标：')}
                {this.currentSelectedMetricList[0].metric_name}
              </span>
            )}
            {this.currentSelectedMetricList.length > 1 && (
              <i18n path='已选 {0} 个指标'>
                <span style='font-weight: bold'>{this.currentSelectedMetricList.length}</span>
              </i18n>
            )}
            <i
              style='margin-left: 4px; color: #3A84FF'
              class='icon-monitor icon-mc-share'
            />
          </div>
        )}
        <div class='page-action-extend'>{this.$slots.default}</div>
      </div>
    );
  }
}
