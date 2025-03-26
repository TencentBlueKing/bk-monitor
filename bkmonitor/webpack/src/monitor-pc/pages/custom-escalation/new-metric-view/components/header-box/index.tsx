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

import CompareType from './components/compare-type';
import GroupBy from './components/group-by';
import LimitFunction from './components/limit-function';
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
}

interface IProps {
  dimenstionParams?: Record<string, any>;
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
});

@Component
export default class HeaderBox extends tsc<IProps, IEmit> {
  @Prop({ type: Object, default: false }) readonly dimenstionParams: IProps['dimenstionParams'];

  @Ref('rootRef') rootRef: HTMLElement;

  params = createDefaultParams();

  @Watch('dimenstionParams', { immediate: true })
  dimenstionParamsChange() {
    if (!this.dimenstionParams) {
      return;
    }

    if (Object.keys(this.dimenstionParams).length < 1) {
      this.params = createDefaultParams();
      return;
    }

    for (const key of Object.keys(this.params)) {
      if (this.dimenstionParams[key]) {
        this.params[key] = Object.freeze(this.dimenstionParams[key]);
      }
    }
  }

  triggerChange() {
    this.$emit('change', {
      ...this.params,
    });
  }

  calcLableWidth() {
    const resizeObserver = new ResizeObserver(() => {
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
    console.log('from handleConditionChange = ', payload);
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
  }

  render() {
    return (
      <div
        ref='rootRef'
        class='bk-monitor-new-metric-view-header-box'
      >
        <WhereCondition
          commonConditionValue={this.params.common_conditions}
          commonDimensionEnable={true}
          value={this.params.where}
          onChange={this.handleConditionChange}
        />
        <div class='mult-item-box'>
          <GroupBy
            splitable={true}
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
          <div class='action-extend'>{this.$slots.actionExtend}</div>
        </div>
      </div>
    );
  }
}
