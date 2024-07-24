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
import { Component, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import TimeRange, { type TimeRangeType } from 'monitor-pc/components/time-range/time-range';
import { getDefaultTimezone, updateTimezone } from 'monitor-pc/i18n/dayjs';

import './details-side.scss';

interface IProps {
  show: boolean;
  onClose?: () => void;
}

@Component
export default class DetailsSide extends tsc<IProps> {
  @Prop({ type: Boolean, default: false }) show: boolean;

  /* 时间 */
  timeRange: TimeRangeType = ['now-1d', 'now'];
  timezone: string = getDefaultTimezone();
  /*  */
  selectOptions = [
    { id: 'avg', name: '平均响应耗时' },
    { id: 'error', name: '总错误数' },
  ];
  selected = 'avg';

  typeOptions = [
    { id: 'initiative', name: '主调' },
    { id: 'passive', name: '被调' },
  ];
  curType = 'initiative';

  compareTimeInfo = [
    {
      id: 'refer',
      name: window.i18n.t('参照时间'),
      time: '2024.1.1 00:00',
      color: '#FF9C01',
    },
    {
      id: 'compare',
      name: window.i18n.t('对比时间'),
      time: '2024.1.1 00:00',
      color: '#7B29FF',
    },
  ];

  isCompare = false;

  searchValue = '';

  handleClose() {
    this.$emit('close');
  }

  handleTimeRangeChange(date) {
    this.timeRange = date;
  }

  handleTimezoneChange(timezone: string) {
    updateTimezone(timezone);
    this.timezone = timezone;
  }

  handleTypeChange(id: string) {
    this.curType = id;
  }

  handleSearch() {}

  render() {
    return (
      <bk-sideslider
        width={960}
        extCls='apm-time-series-details-side'
        beforeClose={this.handleClose}
        isShow={this.show}
        quickClose={true}
        transfer={true}
      >
        <div
          class='header-wrap'
          slot='header'
        >
          <div class='left-title'>请求数详情</div>
          <div class='right-time'>
            <TimeRange
              timezone={this.timezone}
              value={this.timeRange}
              onChange={this.handleTimeRangeChange}
              onTimezoneChange={this.handleTimezoneChange}
            />
          </div>
        </div>
        <div
          class='content-wrap'
          slot='content'
        >
          <div class='content-header-wrap'>
            <div class='left-wrap'>
              <bk-select
                class='theme-select-wrap'
                v-model={this.selected}
                clearable={false}
              >
                {this.selectOptions.map(item => (
                  <bk-option
                    id={item.id}
                    key={item.id}
                    name={item.name}
                  />
                ))}
              </bk-select>
              <div class='bk-button-group'>
                {this.typeOptions.map(item => (
                  <bk-button
                    key={item.id}
                    class={this.curType === item.id ? 'is-selected' : ''}
                    onClick={() => this.handleTypeChange(item.id)}
                  >
                    {item.name}
                  </bk-button>
                ))}
              </div>
              <div class='compare-switcher'>
                <bk-switcher
                  v-model={this.isCompare}
                  theme='primary'
                />
                <span class='switcher-text'>{this.$t('对比')}</span>
              </div>
              {this.isCompare && (
                <div class='compare-time-wrap'>
                  {this.compareTimeInfo.map((item, index) => [
                    index ? (
                      <div
                        key={`${item.id}${index}`}
                        class='split-line'
                      />
                    ) : undefined,
                    <div
                      key={item.id}
                      class='compare-time-item'
                    >
                      <span
                        style={{ backgroundColor: item.color }}
                        class='point'
                      />
                      <span class='time-text'>{`${item.name}: ${item.time}`}</span>
                    </div>,
                  ])}
                </div>
              )}
            </div>
            <div class='right-wrap'>
              <bk-input
                v-model={this.searchValue}
                placeholder={this.$t('搜索服务名称')}
                right-icon='bk-icon icon-search'
                clearable
                onChange={this.handleSearch}
                onRightIconClick={this.handleSearch}
              />
            </div>
          </div>
        </div>
      </bk-sideslider>
    );
  }
}
