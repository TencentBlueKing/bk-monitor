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
import { Component, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import customEscalationViewStore from '@store/modules/custom-escalation-view';

import RenderCommonList from './components/render-common-list/index';
import { type IValue } from './components/render-result-list/components/edit-panel';
import RenderResultList from './components/render-result-list/index';

import './index.scss';

interface IProps {
  value?: IValue[];
  commonDimensionEnable: boolean;
}

interface IEmit {
  onChange: (value: {
    where: {
      key: string;
      method: string;
      condition: string;
      value: string[];
    }[];
    common_conditions: {
      key: string;
      method: string;
      condition: string;
    }[];
  }) => void;
}

@Component
export default class FilterConditions extends tsc<IProps, IEmit> {
  @Prop({ type: Array, default: () => [] }) readonly value: IProps['value'];
  @Prop({ type: Boolean, default: false }) readonly commonDimensionEnable: IProps['commonDimensionEnable'];

  localConditionValueList: IValue[] = [];
  localCommonConditionValueList: Omit<IValue, 'condition'>[] = [];
  isShowCommonlyUsedList = false;

  get commonDimensionList() {
    return customEscalationViewStore.commonDimensionList;
  }

  get currentSelectedMetricList() {
    return customEscalationViewStore.currentSelectedMetricList;
  }

  @Watch('commonDimensionList', { immediate: true })
  commonDimensionListChange() {
    this.localCommonConditionValueList = this.commonDimensionList.map(item => ({
      key: item.name,
      method: 'eq',
      value: [],
    }));
  }

  triggerChange() {
    this.$emit('change', {
      where: this.localConditionValueList,
      common_conditions: this.localCommonConditionValueList,
    });
  }

  handleConditionChange(value: typeof this.localConditionValueList) {
    this.localConditionValueList = value;
    this.triggerChange();
  }

  handleCommonConditinChange(value: typeof this.localCommonConditionValueList) {
    this.localCommonConditionValueList = value;
    this.triggerChange();
  }

  handleToggleCommonlyUsedList() {
    this.isShowCommonlyUsedList = !this.isShowCommonlyUsedList;
  }

  render() {
    return (
      <div class='bk-monitor-new-metric-view-where-condition'>
        <div class='filter-label'>{this.$t('过滤条件')}</div>
        <div class='where-condition-content'>
          <RenderResultList
            value={this.localConditionValueList}
            onChange={this.handleConditionChange}
          />
          {this.isShowCommonlyUsedList && (
            <RenderCommonList
              data={this.localCommonConditionValueList}
              onChange={this.handleCommonConditinChange}
            />
          )}
        </div>
        {this.commonDimensionEnable && (
          <div
            class={{
              'commonly-used-btn': true,
              'is-active': this.isShowCommonlyUsedList,
            }}
            onClick={this.handleToggleCommonlyUsedList}
          >
            <i class='icon-monitor icon-dimension-line' />
          </div>
        )}
      </div>
    );
  }
}
