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
import { Component, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import customEscalationViewStore from '@store/modules/custom-escalation-view';
import _ from 'lodash';

import CompareType from './components/compare-type';
import GroupBy from './components/group-by';
import LimitFunction from './components/limit-function';
import ViewColumn from './components/view-column/index';
import WhereCondition from './components/where-condition';

import './index.scss';

interface IResult {
  metrics: string[];
  where: {
    key: string;
    method: string;
    condition: string;
    value: string[];
  }[];
  common_conditions: {
    key: string;
    method: string;
    value: string[];
  }[];
  group_by: {
    field: string;
    split: boolean;
  }[];
  limit: {
    function: 'bottom' | 'top';
    limit: number;
  };
  compare: {
    type: string;
    offset: string[];
  };
  show_statistical_value: boolean;
  highlight_peak_value: boolean;
  view_column: number;
}

interface IProps {
  dimenstionParams?: Record<string, any>;
  commonDimensionEnable?: boolean;
  groupBySplitEnable?: boolean;
}

interface IEmit {
  onChange: (value: IResult) => void;
}

export const createDefaultParams = (): IResult => ({
  metrics: [],
  where: [],
  common_conditions: [],
  group_by: [],
  limit: {
    function: 'top',
    limit: 10,
  },
  compare: {
    type: '',
    offset: [],
  },
  show_statistical_value: true,
  highlight_peak_value: false,
  view_column: 1,
});

@Component
export default class HeaderBox extends tsc<IProps, IEmit> {
  @Prop({ type: Object, default: false }) readonly dimenstionParams: IProps['dimenstionParams'];
  @Prop({ type: Boolean, default: false }) readonly commonDimensionEnable: IProps['commonDimensionEnable'];
  @Prop({ type: Boolean, default: false }) readonly groupBySplitEnable: IProps['groupBySplitEnable'];

  @Ref('rootRef') rootRef: HTMLElement;

  get currentSelectedMetricList() {
    return customEscalationViewStore.currentSelectedMetricList;
  }

  params = createDefaultParams();

  @Watch('currentSelectedMetricList')
  currentSelectedMetricListChnage() {
    this.triggerChange();
  }

  @Watch('dimenstionParams', { immediate: true })
  dimenstionParamsChange() {
    if (!this.dimenstionParams) {
      return;
    }
    Object.keys(this.params).forEach(key => {
      if (this.dimenstionParams[key]) {
        this.params[key] = Object.freeze(this.dimenstionParams[key]);
      }
    });
  }

  triggerChange() {
    this.$emit('change', {
      ..._.cloneDeep(this.params),
      metrics: this.currentSelectedMetricList.map(item => item.metric_name),
    });
  }

  calcLableWidth() {
    const resizeObserver = new ResizeObserver(() => {
      const rootElLeft = this.rootRef.getBoundingClientRect().left;
      const labelElList = Array.from(this.rootRef.querySelectorAll('[role="param-label"]')) as HTMLElement[];
      let maxWidth = 0;
      const fitLeftEl: HTMLElement[] = [];
      labelElList.forEach(itemEl => {
        if (itemEl.getBoundingClientRect().left - 10 < rootElLeft) {
          maxWidth = Math.max(maxWidth, itemEl.querySelector('div').getBoundingClientRect().width);
          fitLeftEl.push(itemEl);
        } else {
          itemEl.style.width = 'auto';
        }
      });
      fitLeftEl.forEach(item => {
        item.style.width = `${maxWidth + 30}px`;
      });
    });
    resizeObserver.observe(this.rootRef);
    this.$once('hook:beforeDestroy', () => {
      resizeObserver.disconnect();
    });
  }

  handleConditionChange(payload: { where: IResult['where']; common_conditions: IResult['common_conditions'] }) {
    this.params.where = payload.where;
    this.params.common_conditions = payload.common_conditions;
    this.triggerChange();
  }

  handleGroupByChange(payload: IResult['group_by']) {
    this.params.group_by = payload;
    this.triggerChange();
  }

  handleLimitChange(payload: IResult['limit']) {
    this.params.limit = payload;
    this.triggerChange();
  }

  handleComparTypeChange(payload: IResult['compare']) {
    this.params.compare = payload;
    this.triggerChange();
  }
  mounted() {
    this.calcLableWidth();

    console.log('from header box mounted');
  }

  render() {
    return (
      <div
        ref='rootRef'
        class='bk-monitor-new-metric-view-header-box'
      >
        <WhereCondition
          commonConditionValue={this.params.common_conditions}
          commonDimensionEnable={this.commonDimensionEnable}
          value={this.params.where}
          onChange={this.handleConditionChange}
        />
        <div class='mult-item-box'>
          <GroupBy
            splitable={this.groupBySplitEnable}
            value={this.params.group_by}
            onChange={this.handleGroupByChange}
          />
          {this.params.group_by.length > 0 && (
            <LimitFunction
              value={this.params.limit}
              onChange={this.handleLimitChange}
            />
          )}
          <CompareType
            value={this.params.compare}
            onChange={this.handleComparTypeChange}
          />
          <div class='action-extend'>
            <bk-checkbox
              v-model={this.params.show_statistical_value}
              onChange={this.triggerChange}
            >
              {this.$t('展示统计值')}
            </bk-checkbox>
            {/* <bk-checkbox
              style='margin-left: 16px'
              v-model={this.params.highlight_peak_value}
              onChange={this.triggerChange}
            >
              {this.$t('高粱峰谷值')}
            </bk-checkbox> */}
            <ViewColumn
              style='margin-left: 32px;'
              v-model={this.params.view_column}
              onChange={this.triggerChange}
            />
          </div>
        </div>
      </div>
    );
  }
}
