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
import { Component, Ref, Prop, Emit } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import SearchSelect from '@blueking/search-select-v3/vue2';
import EmptyStatus from 'monitor-pc/components/empty-status/empty-status';
import GuidePage from 'monitor-pc/components/guide-page/guide-page';
import TableSkeleton from 'monitor-pc/components/skeleton/table-skeleton';
import CommonTable from 'monitor-pc/pages/monitor-k8s/components/common-table';
import FilterPanel from 'monitor-pc/pages/strategy-config/strategy-config-list/filter-panel';
import introduceData from 'monitor-pc/router/space';

import { SEARCH_KEYS } from '../utils';

import type { PartialAppListItem } from '../apm-home';
import type { IFilterDict } from 'monitor-pc/pages/monitor-k8s/typings';

import './apm-home-list.scss';

interface IProps {
  itemRow: PartialAppListItem;
  showGuidePage?: boolean;
}

interface IEvent {
  onGetServiceData?: (appIds: number[], isScrollEnd?: boolean, isRefresh?: boolean) => void;
  onHandleSearchCondition?: (value) => void;
  onHandleToConfig?: (row: PartialAppListItem) => void;
  onLinkToOverview?: (row: PartialAppListItem) => void;
}
@Component({})
export default class ApmHomeList extends tsc<IProps, IEvent> {
  @Prop() itemRow: PartialAppListItem;
  @Prop({ default: false, type: Boolean }) showGuidePage: boolean;
  @Ref() mainResize: any;

  searchCondition = [];
  showFilterPanel = true;

  /** mock数据 */

  filterList = [
    {
      id: 'strategy_status',
      name: '状态',
      data: [
        {
          id: 'ALERT',
          name: '告警中',
          count: 24,
          icon: 'icon-mc-chart-alert',
        },
        {
          id: 'INVALID',
          name: '策略已失效',
          count: 18,
          icon: 'icon-shixiao',
        },
        {
          id: 'OFF',
          name: '已停用',
          count: 94,
          icon: 'icon-zanting1',
        },
        {
          id: 'ON',
          name: '已启用',
          count: 114,
          icon: 'icon-kaishi1',
        },
        {
          id: 'SHIELDED',
          name: '屏蔽中',
          count: 1,
          icon: 'icon-menu-shield',
        },
      ],
    },
  ];

  @Emit()
  handleEmit(...args: any[]) {
    this.$emit.apply(this, args);
    return args[0];
  }

  created() {
    const { query } = this.$route;
    if (query?.queryString) {
      this.searchCondition.push({
        id: query.queryString,
        name: query.queryString,
      });
    }
    // 批量设置搜索条件
    this.setSearchConditions(['profiling_data_status', 'is_enabled_profiling'], query);
  }

  get apmIntroduceData() {
    const apmData = introduceData['apm-home'];
    apmData.is_no_source = false;
    apmData.data.buttons[0].url = window.__POWERED_BY_BK_WEWEB__ ? '#/apm/application/add' : '#/application/add';
    return apmData;
  }
  /* 查找搜索键 */
  findSearchKey(key) {
    return SEARCH_KEYS.find(item => item.id === key) || { name: '', children: [] };
  }

  /* 批量设置搜索条件 */
  setSearchConditions(keys, query) {
    keys.reduce((acc, key) => {
      if (query?.[key]) {
        const { name, children } = this.findSearchKey(key);
        const matchingStatus = children.find(s => s.id === query[key]);
        if (matchingStatus) {
          acc.push({
            id: key,
            name,
            values: [{ ...matchingStatus }],
          });
        }
      }
      return acc;
    }, this.searchCondition);
  }

  /* 候选搜索列表过滤 */
  conditionListFilter() {
    const allKey = this.searchCondition.map(item => item.id);
    return SEARCH_KEYS.filter(item => !allKey.includes(item.id));
  }

  /* 筛选展开收起 */
  handleHidePanel() {
    this.mainResize.setCollapse();
    const time = this.mainResize.collapsed ? 350 : 0;
    setTimeout(() => {
      this.showFilterPanel = !this.mainResize.collapsed;
    }, time);
  }

  changeCollapse(width: number) {
    if (width < 200) {
      setTimeout(() => {
        this.showFilterPanel = false;
      }, 350);
    }
  }
  /**
   * @description 条件搜索
   * @param value
   */
  handleSearchCondition(value) {
    this.handleEmit('handleSearchCondition', value);
  }

  /**
   * @description 收藏
   * @param val
   * @param row
   */
  handleCollect(val, item: PartialAppListItem) {
    const apis = val.api.split('.');
    (this as any).$api[apis[0]][apis[1]](val.params).then(() => {
      item.tableData.paginationData.current = 1;
      item.tableData.paginationData.isEnd = false;
      this.handleEmit('getServiceData', [item.application_id], false, true);
    });
  }

  /**
   * @description 表格筛选
   * @param filters
   * @param item
   */
  handleFilterChange(filters: IFilterDict, item: PartialAppListItem) {
    item.tableFilters = filters;
    item.tableData.paginationData.current = 1;
    item.tableData.paginationData.isEnd = false;
    this.handleEmit('getServiceData', [item.application_id], false, true);
  }

  /**
   * @description 表格滚动到底部
   * @param row
   */
  handleScrollEnd(item: PartialAppListItem) {
    item.tableData.paginationData.current += 1;
    this.handleEmit('getServiceData', [item.application_id], true);
  }

  /**
   * @description 表格排序
   * @param param0
   * @param item
   */
  handleSortChange({ prop, order }, item: PartialAppListItem) {
    switch (order) {
      case 'ascending':
        item.tableSortKey = prop;
        break;
      case 'descending':
        item.tableSortKey = `-${prop}`;
        break;
      default:
        item.tableSortKey = undefined;
    }
    item.tableData.paginationData.current = 1;
    item.tableData.paginationData.isEnd = false;
    this.handleEmit('getServiceData', [item.application_id], false, true);
  }
  render() {
    return (
      <div class='apm-home-list'>
        <div class='header'>
          <div class='header-left'>{this.itemRow.app_alias?.value}</div>
          <div class='header-right'>
            <bk-button
              class='mr-8'
              onClick={(event: Event) => {
                event.stopPropagation();
                this.handleEmit('linkToOverview', this.itemRow);
              }}
            >
              {this.$t('应用详情')}
            </bk-button>
            <bk-button
              onClick={(event: Event) => {
                event.stopPropagation();
                this.handleEmit('handleToConfig', this.itemRow);
              }}
            >
              {this.$t('应用配置')}
            </bk-button>
          </div>
        </div>
        <div class='main'>
          <bk-resize-layout
            ref='mainResize'
            class='main-left'
            auto-minimize={200}
            border={false}
            initial-divide={201}
            min={195}
            collapsible
            on-after-resize={this.changeCollapse}
          >
            <div
              class={['main-left-filter']}
              slot='aside'
            >
              <FilterPanel
                data={this.filterList}
                show={true}
                // showSkeleton={this.authLoading || this.loading}
              >
                <div
                  class='filter-panel-header'
                  slot='header'
                >
                  <span class='title'>{this.$t('筛选')}</span>
                  <span
                    class='folding'
                    onClick={this.handleHidePanel}
                  >
                    <i class='icon-monitor icon-double-up' />
                  </span>
                </div>
              </FilterPanel>
            </div>
            <div
              class='main-left-table'
              slot='main'
            >
              {this.showGuidePage ? (
                <GuidePage
                  guideData={this.apmIntroduceData}
                  guideId='apm-home'
                />
              ) : (
                <div class='app-list-content'>
                  <div class='app-list-content-top'>
                    <bk-button
                      class={[{ 'ml-16': !this.showFilterPanel }]}
                      theme='primary'
                      outline
                    >
                      <span class='app-add-btn'>
                        <i class='icon-monitor icon-mc-add app-add-icon' />
                        <span>{this.$t('接入服务')}</span>
                      </span>
                    </bk-button>
                    <div class='app-list-search'>
                      <SearchSelect
                        v-model={this.searchCondition}
                        data={this.conditionListFilter()}
                        placeholder={this.$t('请输入服务搜索')}
                        onChange={this.handleSearchCondition}
                      />
                    </div>
                  </div>
                  <div class='app-right-content'>
                    <div class='app-list-content-data'>
                      <div
                        key={this.itemRow.application_id}
                        class='item-expand-wrap'
                      >
                        {
                          <div class='expand-content'>
                            {this.itemRow.tableData.data.length || this.itemRow.tableData.loading ? (
                              (() => {
                                if (!this.itemRow.tableData.data.length) {
                                  return <TableSkeleton class='table-skeleton' />;
                                }
                                return (
                                  // 列名接口返回
                                  <CommonTable
                                    {...{ props: this.itemRow.tableData }}
                                    hasColnumSetting={false}
                                    onCollect={val => this.handleCollect(val, this.itemRow)}
                                    onFilterChange={val => this.handleFilterChange(val, this.itemRow)}
                                    onScrollEnd={() => this.handleScrollEnd(this.itemRow)}
                                    onSortChange={val => this.handleSortChange(val as any, this.itemRow)}
                                  />
                                );
                              })()
                            ) : (
                              <EmptyStatus
                                textMap={{
                                  empty: this.$t('暂无数据'),
                                }}
                              />
                            )}
                          </div>
                        }
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
            <div
              class={['toggle-wrap']}
              slot='collapse-trigger'
              onClick={this.handleHidePanel}
            >
              <div
                class='rotate'
                v-show={!this.showFilterPanel}
              >
                <i class='icon-monitor icon-double-up' />
              </div>
            </div>
          </bk-resize-layout>
        </div>
      </div>
    );
  }
}
