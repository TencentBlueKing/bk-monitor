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

import { EMode, type IWhereItem } from '../../components/retrieval-filter/utils';
import { APIType } from './api-utils';
import EventExplore from './event-explore';

import type { IFormData } from './typing';

import './apm-event-explore.scss';

interface K8sEventExploreProps {
  dataId: string;
}

@Component
export default class K8sEventExplore extends tsc<
  K8sEventExploreProps,
  object,
  {
    filterPrepend?: string;
  }
> {
  @Prop({ type: String, required: true }) dataId!: string;

  dataTypeLabel = 'event';
  dataSourceLabel = 'custom';
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

  filterMode = EMode.ui;

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
              query_configs: [{ data_type_label, where, query_string: queryString }],
            },
          },
        ] = targetsList;
        this.dataTypeLabel = data_type_label;
        this.where = where || [];
        this.queryString = queryString || '';
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

  render() {
    return (
      <EventExplore
        class={'apm-event-explore'}
        defaultLayoutConfig={{
          defaultWidth: 280,
        }}
        commonWhere={this.commonWhere}
        dataId={this.dataId}
        dataSourceLabel={this.dataSourceLabel}
        dataTypeLabel={this.dataTypeLabel}
        filterMode={this.filterMode}
        queryString={this.queryString}
        scopedSlots={this.$scopedSlots}
        source={APIType.MONITOR}
        where={this.where}
        onFilterModeChange={this.handleFilterModelChange}
        onQueryStringChange={this.handleQueryStringChange}
        onSetRouteParams={this.setRouteParams}
        onWhereChange={this.handleWhereChange}
      />
    );
  }
}
