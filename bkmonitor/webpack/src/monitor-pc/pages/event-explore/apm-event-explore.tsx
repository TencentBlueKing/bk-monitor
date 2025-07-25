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

import { type IWhereItem, ECondition, EMode } from '../../components/retrieval-filter/utils';
import { APIType } from './api-utils';
import EventExplore from './event-explore';
import { type IFormData, ExploreSourceTypeEnum } from './typing';

import './apm-event-explore.scss';
const APM_EVENT_DATA_ID = 'builtin';
@Component
export default class ApmEventExplore extends tsc<object> {
  dataTypeLabel = 'event';
  dataSourceLabel = 'apm';
  /** 数据Id */
  dataId = '';
  /** 数据ID列表 */
  dataIdList = [];
  /** 查询语句 */
  queryString = '';
  /** UI查询 */
  where: IWhereItem[] = [];
  /** 常驻筛选查询 */
  commonWhere: IWhereItem[] = [];
  /** 是否展示常驻筛选 */
  showResidentBtn = false;
  /** 维度列表 */
  group_by: IFormData['group_by'] = [];
  /** 过滤条件 */
  filter_dict: IFormData['filter_dict'] = {};
  /** 用于 日志 和 事件关键字切换 换成查询 */
  cacheQuery = null;
  filterMode = EMode.ui;

  eventSourceType = [ExploreSourceTypeEnum.ALL];

  created() {
    this.getRouteParams();
  }
  /** 兼容以前的事件检索URL格式 */
  getRouteParams() {
    const { targets, filterMode, commonWhere, showResidentBtn } = this.$route.query;
    if (targets) {
      try {
        const targetsList = JSON.parse(decodeURIComponent(targets as string));
        const [
          {
            data: {
              query_configs: [
                { data_type_label, where, query_string: queryString, group_by: groupBy, filter_dict: filterDict },
              ],
            },
          },
        ] = targetsList;
        this.dataTypeLabel = data_type_label;
        this.where = where || [];
        const hasSource = this.where.find(item => item.key === 'source');
        if (hasSource) {
          this.where = this.where.filter(item => item.key !== 'source');
          this.eventSourceType = hasSource.value as ExploreSourceTypeEnum[];
        }
        this.queryString = queryString || '';
        this.group_by = groupBy || [];
        this.filter_dict = filterDict || {};
        this.filterMode = (
          [EMode.ui, EMode.queryString].includes(filterMode as EMode) ? filterMode : EMode.ui
        ) as EMode;
        this.commonWhere = JSON.parse((commonWhere as string) || '[]');
        this.showResidentBtn = JSON.parse((showResidentBtn as string) || 'false') || false;
      } catch (error) {
        console.log('route query:', error);
      }
    }
  }

  setRouteParams(otherQuery = {}) {
    const where = [...this.where];
    if (!this.eventSourceType.includes(ExploreSourceTypeEnum.ALL)) {
      where.push({ key: 'source', method: 'eq', condition: ECondition.and, value: this.eventSourceType });
    }
    const query = {
      ...this.$route.query,
      targets: JSON.stringify([
        {
          data: {
            query_configs: [
              {
                result_table_id: this.dataId,
                data_type_label: this.dataTypeLabel,
                data_source_label: this.dataSourceLabel,
                where,
                query_string: this.queryString,
                group_by: this.group_by,
                filter_dict: this.filter_dict,
              },
            ],
          },
        },
      ]),
      filterMode: this.filterMode,
      commonWhere: JSON.stringify(this.commonWhere),
      showResidentBtn: String(this.showResidentBtn),
      ...otherQuery,
    };

    const targetRoute = this.$router.resolve({
      query,
    });

    /** 防止出现跳转当前地址导致报错 */
    if (targetRoute.resolved.fullPath !== this.$route.fullPath) {
      this.$router.replace({
        query,
      });
    }
  }
  handleFilterModelChange(mode: EMode) {
    this.filterMode = mode;
    this.setRouteParams();
  }
  handleWhereChange(where: IFormData['where']) {
    this.where = where;
    this.setRouteParams();
  }
  handleQueryStringChange(queryString: string) {
    this.queryString = queryString;
    this.setRouteParams();
  }
  handleFilterChange(filter_dict: IFormData['filter_dict']) {
    this.filter_dict = filter_dict;
    this.setRouteParams();
  }
  /** 常驻筛选项修改 */
  handleCommonWhereChange(where: IWhereItem[]) {
    this.commonWhere = where;
    this.setRouteParams();
  }

  /** 常驻筛选显隐 */
  handleShowResidentBtnChange(isShow: boolean) {
    this.showResidentBtn = isShow;
    this.setRouteParams();
  }

  handleEventSourceTypeChange(eventSourceType: ExploreSourceTypeEnum[]) {
    this.eventSourceType = eventSourceType;
    this.setRouteParams();
  }

  render() {
    return (
      <EventExplore
        class={'apm-event-explore'}
        commonWhere={this.commonWhere}
        dataId={APM_EVENT_DATA_ID}
        dataSourceLabel={'apm'}
        defaultShowResidentBtn={this.showResidentBtn}
        eventSourceType={this.eventSourceType}
        filter_dict={this.filter_dict}
        filterMode={this.filterMode}
        group_by={this.group_by}
        queryString={this.queryString}
        source={APIType.APM}
        where={this.where}
        onCommonWhereChange={this.handleCommonWhereChange}
        onEventSourceTypeChange={this.handleEventSourceTypeChange}
        onFilterModeChange={this.handleFilterModelChange}
        onQueryStringChange={this.handleQueryStringChange}
        onSetRouteParams={this.setRouteParams}
        onShowResidentBtnChange={this.handleShowResidentBtnChange}
        onWhereChange={this.handleWhereChange}
      />
    );
  }
}
