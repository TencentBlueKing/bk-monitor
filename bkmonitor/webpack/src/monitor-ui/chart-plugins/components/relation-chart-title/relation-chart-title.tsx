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

import { Debounce } from '../../../../monitor-common/utils/utils';
import { ITableFilterItem } from '../../../../monitor-pc/pages/monitor-k8s/typings';
import StatusTab from '../../plugins/table-chart/status-tab';

import './relation-chart-title.scss';

interface IRelationChartTitleProps {
  filterList?: ITableFilterItem[];
  isOverview?: boolean;
  searchType?: string;
  conditionOptions?: any[];
  showNoData?: boolean;
  isFullScreen?: boolean;
}

interface IRelationChartTitleEvent {
  onMenuClick: void;
  onOverview?: boolean;
  onSearchChange?: number | string;
  onConditionChange?: void;
  onbackToCenter?: void;
  onShowNodata?: boolean;
  onfilterChange?: string;
  onFullScreen?: void;
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
  handleConditionChange() {
    return this.conditionList;
  }
  @Debounce(300)
  @Emit('searchChange')
  handleSearchChange(value: string | number) {
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
                  theme='primary'
                  size='small'
                  onChange={(v: boolean) => this.handleShowNodata(v)}
                ></bk-switcher>
                <span class='switcher-text'>{window.i18n.t('无数据节点')}</span>
              </div>
            )}
            {this.searchType === 'search_select' ? (
              <bk-search-select
                value={this.conditionList}
                class='search-wrapper-input'
                behavior='simplicity'
                show-condition={false}
                data={this.conditionOptions}
                onChange={this.handleConditionChange}
              />
            ) : (
              <bk-input
                class='search-wrapper-input'
                behavior='simplicity'
                placeholder='搜索'
                v-model={this.keyword}
                onEnter={this.handleSearchChange}
                onBlur={this.handleSearchChange}
                right-icon='bk-icon icon-search'
              />
            )}
          </div>
          <div class='button-tools'>
            <span class='overview-list-options'>
              <span
                class={['overview', { active: this.isOverview }]}
                onClick={() => this.handleOverview(true)}
              >
                <i class='icon-monitor icon-mc-overview option-icon'></i>
              </span>
              <span
                class={['list', { active: !this.isOverview }]}
                onClick={() => this.handleOverview(false)}
              >
                <i class='icon-monitor icon-mc-list option-icon'></i>
              </span>
              {this.isOverview && (
                <span
                  class='list single'
                  v-bk-tooltips={window.i18n.t('回中')}
                  onClick={this.handlebackToCenter}
                >
                  <i class='bk-icon icon-circle'></i>
                </span>
              )}
              <span
                class='list full-screen'
                v-bk-tooltips={this.isFullScreen ? window.i18n.t('缩小') : window.i18n.t('全屏')}
                onClick={this.handleFullScreen}
              >
                <i class='bk-icon icon-full-screen'></i>
              </span>
            </span>
          </div>
        </div>
      </div>
    );
  }
}
