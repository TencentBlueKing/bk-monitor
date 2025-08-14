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
import { Component, Emit, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import SearchSelect from '@blueking/search-select-v3/vue2';
import { Debounce } from 'monitor-common/utils/utils';

import StatusTab from '../../plugins/table-chart/status-tab';

import type { ITableFilterItem } from 'monitor-pc/pages/monitor-k8s/typings';

import './relation-chart-title.scss';
import '@blueking/search-select-v3/vue2/vue2.css';

interface IRelationChartTitleEvent {
  onbackToCenter?: void;
  onConditionChange?: void;
  onfilterChange?: string;
  onFullScreen?: void;
  onMenuClick: void;
  onOverview?: boolean;
  onSearchChange?: number | string;
  onShowNodata?: boolean;
}

interface IRelationChartTitleProps {
  conditionOptions?: any[];
  filterList?: ITableFilterItem[];
  isFullScreen?: boolean;
  isOverview?: boolean;
  searchType?: string;
  showNoData?: boolean;
}
@Component
export default class ChartTitle extends tsc<IRelationChartTitleProps, IRelationChartTitleEvent> {
  @Prop({ default: () => [], type: Array }) filterList: ITableFilterItem[];
  @Prop({ default: true, type: Boolean }) isOverview: boolean;
  @Prop({ default: 'input', type: String }) searchType: string;
  @Prop({ default: () => [], type: Array }) conditionOptions: any[];
  @Prop({ default: true, type: Boolean }) showNoData: boolean;
  @Prop({ default: false, type: Boolean }) isFullScreen: boolean;

  status = 'all';
  /** search-select可选项数据 */
  conditionList = [];
  keyword = '';

  showEmptyNode = true;

  @Emit('overview')
  handleOverview(value: boolean) {
    return value;
  }

  @Emit('filterChange')
  handleStatusChange() {
    return this.status;
  }

  /** search select组件搜索 */
  @Debounce(300)
  @Emit('conditionChange')
  handleConditionChange(v) {
    this.conditionList = v;
    return this.conditionList;
  }
  @Debounce(300)
  @Emit('searchChange')
  handleSearchChange(value: number | string) {
    return value;
  }
  @Debounce(300)
  @Emit('backToCenter')
  handlebackToCenter() {}

  @Emit('showNodata')
  handleShowNodata(v: boolean) {
    return v;
  }
  @Emit('fullScreen')
  handleFullScreen() {}

  @Emit('clearFilter')
  handleClearFilter() {
    this.status = 'all';
    this.keyword = '';
  }

  render() {
    return (
      <div class='relation-title-wrapper'>
        <div class='chart-title'>
          <div class='filter-tools'>
            {this.filterList.length ? (
              <StatusTab
                v-model={this.status}
                needAll={false}
                statusList={this.filterList}
                onChange={this.handleStatusChange}
              />
            ) : (
              ''
            )}
            {this.isOverview && (
              <div class='empty-node-switcher'>
                <bk-switcher
                  v-model={this.showEmptyNode}
                  size='small'
                  theme='primary'
                  onChange={(v: boolean) => this.handleShowNodata(v)}
                />
                <span class='switcher-text'>{window.i18n.t('无数据节点')}</span>
              </div>
            )}
            {this.searchType === 'search_select' ? (
              <div class='search-wrapper-input'>
                <SearchSelect
                  clearable={false}
                  data={this.conditionOptions}
                  modelValue={this.conditionList}
                  onChange={this.handleConditionChange}
                />
              </div>
            ) : (
              <bk-input
                class='search-wrapper-input'
                v-model={this.keyword}
                behavior='simplicity'
                placeholder='搜索'
                right-icon='bk-icon icon-search'
                onBlur={this.handleSearchChange}
                onEnter={this.handleSearchChange}
              />
            )}
          </div>
          <div class='button-tools'>
            <span class='overview-list-options'>
              <span
                class={['overview', { active: this.isOverview }]}
                onClick={() => this.handleOverview(true)}
              >
                <i class='icon-monitor icon-mc-overview option-icon' />
              </span>
              <span
                class={['list', { active: !this.isOverview }]}
                onClick={() => this.handleOverview(false)}
              >
                <i class='icon-monitor icon-mc-list option-icon' />
              </span>
              {this.isOverview && (
                <span
                  class='list single'
                  v-bk-tooltips={window.i18n.t('回中')}
                  onClick={this.handlebackToCenter}
                >
                  <i class='bk-icon icon-circle' />
                </span>
              )}
              <span
                class='list full-screen'
                v-bk-tooltips={this.isFullScreen ? window.i18n.t('缩小') : window.i18n.t('全屏')}
                onClick={this.handleFullScreen}
              >
                <i class='bk-icon icon-full-screen' />
              </span>
            </span>
          </div>
        </div>
      </div>
    );
  }
}
