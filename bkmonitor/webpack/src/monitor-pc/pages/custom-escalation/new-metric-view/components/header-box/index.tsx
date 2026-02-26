/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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

import _ from 'lodash';

import CompareType from './components/compare-type';
import DecimalSelector from './components/decimal-selector';
import GroupBy from './components/group-by';
import IntervalCreator from './components/interval/index';
import LimitFunction from './components/limit-function';
import WhereCondition from './components/where-condition';

import type { ChartSettingsParams } from '../../type';

import './index.scss';

interface IEmit {
  onChange: (value: IResult) => void;
  onChartSettingChange: (value: ChartSettingsParams) => void;
}

interface IProps {
  chartSettingParams?: ChartSettingsParams;
  dimenstionParams?: Record<string, any>;
  exclude?: string[];
  isShowExpand?: boolean;
  offsetSingle?: boolean;
  splitable?: boolean;
}

interface IResult {
  interval: number | string;
  metrics: string[];
  common_conditions: {
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
    function: 'bottom' | 'top';
    limit: number;
  };
  where: {
    condition: string;
    key: string;
    method: string;
    value: string[];
  }[];
}

export const createDefaultParams = (): IResult => ({
  metrics: [],
  where: [],
  common_conditions: [],
  group_by: [],
  limit: {
    function: 'top',
    limit: 50,
  },
  compare: {
    type: '',
    offset: [],
  },
  interval: 'auto',
});

@Component
export default class HeaderBox extends tsc<IProps, IEmit> {
  @Prop({ type: Object, default: false }) readonly dimenstionParams: IProps['dimenstionParams'];
  @Prop({ type: Object, default: null }) readonly chartSettingParams: ChartSettingsParams;
  @Prop({ type: Boolean, default: true }) readonly isShowExpand: boolean;
  @Prop({ type: Array, default: () => [] }) readonly exclude: string[];
  @Prop({ type: Boolean, default: true }) readonly splitable: IProps['splitable'];
  @Prop({ type: Boolean, default: false }) readonly offsetSingle: IProps['offsetSingle'];
  @Ref('rootRef') rootRef: HTMLElement;

  isExpaned = true;
  params = createDefaultParams();
  chartSettings: ChartSettingsParams = {
    autoYAxis: true,
    decimal: 0,
  };
  calcLableWidth: () => void;

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

  @Watch('chartSettingParams', { immediate: true })
  chartSettingParamsChange() {
    if (!this.chartSettingParams) {
      return;
    }
    this.chartSettings = { ...this.chartSettingParams };
  }

  triggerChange() {
    this.$emit('change', {
      ...this.params,
    });
  }

  triggerChartSettingChange() {
    this.$emit('chartSettingChange', { ...this.chartSettings });
  }

  handleConditionChange(payload: { common_conditions: IResult['common_conditions']; where: IResult['where'] }) {
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

  handleDecimalChange(payload: ChartSettingsParams['decimal']) {
    this.chartSettings.decimal = payload;
    this.triggerChartSettingChange();
  }

  handleToogleExpand() {
    this.isExpaned = !this.isExpaned;
  }

  // 改变配置周期时间
  handleChangeInterval(payload: IResult['interval']) {
    this.params.interval = payload;
    this.triggerChange();
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
        class='bk-monitor-new-metric-view-header-box'
      >
        <bk-transition name='collapse'>
          <div v-show={this.isExpaned}>
            <WhereCondition
              commonConditionValue={this.params.common_conditions}
              commonDimensionEnable={true}
              value={this.params.where}
              onChange={this.handleConditionChange}
            />
            <div class='mult-item-box'>
              <GroupBy
                splitable={this.splitable}
                value={this.params.group_by}
                onChange={this.handleGroupByChange}
              />
              {/* {this.params.group_by.length > 0 && ( */}
              <LimitFunction
                value={this.params.limit}
                onChange={this.handleLimitChange}
              />
              <IntervalCreator
                value={this.params.interval}
                onChange={this.handleChangeInterval}
              />
              {/* )} */}
              <CompareType
                exclude={this.exclude}
                offsetSingle={this.offsetSingle}
                value={this.params.compare}
                onChange={this.handleComparTypeChange}
              />
              <DecimalSelector
                value={this.chartSettings.decimal}
                onChange={this.handleDecimalChange}
              />
              <div class='action-extend'>{this.$slots.actionExtend}</div>
            </div>
          </div>
        </bk-transition>
        {this.isShowExpand && (
          <div
            class={{
              'toggle-btn': true,
              'is-expaned': this.isExpaned,
            }}
            onClick={this.handleToogleExpand}
          >
            <i class='bk-icon icon-angle-left' />
          </div>
        )}
      </div>
    );
  }
}
