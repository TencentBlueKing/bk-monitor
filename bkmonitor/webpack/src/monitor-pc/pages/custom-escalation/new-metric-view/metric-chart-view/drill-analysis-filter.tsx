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
import { Component, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import _ from 'lodash';

import CompareType from '../components/header-box/components/compare-type';
import GroupBy from '../components/header-box/components/group-by';
import LimitFunction from '../components/header-box/components/limit-function';
import WhereCondition from '../components/header-box/components/where-condition';
import { refreshList } from './utils';

import type { IRefreshItem, IResultItem } from '../type';
import type { TimeRangeType } from 'monitor-pc/components/time-range/time-range';

import './drill-analysis-filter.scss';

interface IEmit {
  onComparTypeChange: (value: IResultItem['compare']) => void;
  onConditionChange: (value: { custom_data: IResultItem['common_conditions']; where: IResultItem['where'] }) => void;
  onGroupByChange: (value: IResultItem['group_by']) => void;
  onImmediateRefresh: () => void;
  onLimitChange: (value: IResultItem['limit']) => void;
  onRefreshInterval: (value: number) => void;
  onTimeRangeChange: (value: TimeRangeType) => void;
  onTimezoneChange: (value: string) => void;
}

interface IProps {
  isHaveGroupBy?: boolean;
  refreshInterval: number;
  timeRange: TimeRangeType;
  filterConfig: {
    commonConditions: {
      key: string;
      method: string;
      value: string[];
    }[];
    compare: {
      offset: string[];
      type: string;
    };
    group_by: {
      field: string;
      split: boolean;
    }[];
    limit: {
      function: string;
      limit: number;
    };
    where: {
      condition: string;
      key: string;
      method: string;
      value: string[];
    }[];
  };
}
@Component
export default class DrillAnalysisView extends tsc<IProps, IEmit> {
  @Prop({ type: Object, required: true }) readonly filterConfig: IProps['filterConfig'];
  @Prop({ type: Array, required: true }) readonly timeRange: IProps['timeRange'];
  @Prop({ type: Number, required: true }) readonly refreshInterval: IProps['refreshInterval'];
  @Prop({ type: Boolean, required: false }) readonly isHaveGroupBy: boolean;

  @Ref('rootRef') rootRef: HTMLElement;

  timezone = window.timezone;
  refreshList: IRefreshItem[] = refreshList;

  calcLableWidth: () => void;

  handleConditionChange(value: { custom_data: IResultItem['common_conditions']; where: IResultItem['where'] }) {
    this.$emit('conditionChange', value);
  }

  handleGroupByChange(value: IResultItem['group_by']) {
    this.$emit('groupByChange', value);
  }

  handleLimitChange(value: IResultItem['limit']) {
    this.$emit('limitChange', value);
  }

  handleComparTypeChange(value: IResultItem['compare']) {
    this.$emit('comparTypeChange', value);
  }

  created() {
    this.calcLableWidth = _.throttle(() => {
      const rootElLeft = this.rootRef.getBoundingClientRect().left;
      const labelElList = Array.from(this.rootRef.querySelectorAll('[data-role="param-label"]')) as HTMLElement[];
      let maxWidth = 0;
      const fitLeftEl: HTMLElement[] = [];

      for (const itemEl of labelElList) {
        if (itemEl.getBoundingClientRect().left - 10 < rootElLeft) {
          maxWidth = Math.max(maxWidth, itemEl.querySelector('div').getBoundingClientRect().width);
          fitLeftEl.push(itemEl);
        } else {
          itemEl.style.width = 'auto';
        }
      }
      for (const item of fitLeftEl) {
        item.style.width = `${maxWidth + 30}px`;
      }
    }, 300);
  }

  mounted() {
    const resizeObserver = new ResizeObserver(this.calcLableWidth);
    resizeObserver.observe(this.rootRef);
    this.$once('hook:beforeDestroy', () => {
      resizeObserver.disconnect();
    });
  }

  render() {
    return (
      <div
        ref='rootRef'
        class='drill-analysis-filter'
      >
        <div class='filter-confition-wrapper'>
          <WhereCondition
            customData={this.filterConfig.commonConditions}
            value={this.filterConfig.where}
            onChange={this.handleConditionChange}
          />
        </div>
        <div class='filter-compare-view'>
          {this.isHaveGroupBy && (
            <GroupBy
              value={this.filterConfig.group_by}
              onChange={this.handleGroupByChange}
            />
          )}
          {this.filterConfig.group_by.length > 0 && (
            <LimitFunction
              value={this.filterConfig.limit}
              onChange={this.handleLimitChange}
            />
          )}
          <CompareType
            exclude={['metric']}
            value={this.filterConfig.compare}
            onChange={this.handleComparTypeChange}
          />
        </div>
      </div>
    );
  }
}
