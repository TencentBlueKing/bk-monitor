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

import _ from 'lodash';
import { Debounce } from 'monitor-common/utils';

import RenderCommonList from './components/render-common-list/index';
import RenderCustomList from './components/render-custom-list';
import RenderResultList from './components/render-result-list/index';
import customEscalationViewStore from '@store/modules/custom-escalation-view';

import type { IValue } from './components/render-result-list/components/edit-panel';

import './index.scss';

interface IEmit {
  onChange: (value: {
    common_conditions: {
      key: string;
      method: string;
      value: string[];
    }[];
    custom_data: {
      key: string;
      method: string;
      value: string[];
    }[];
    where: {
      condition: string;
      key: string;
      method: string;
      value: string[];
    }[];
  }) => void;
}

interface IProps {
  commonDimensionEnable?: boolean;
  value?: IValue[];
  commonConditionValue?: {
    alias: string;
    key: string;
    method: string;
    value: string[];
  }[];
  customData?: {
    alias: string;
    key: string;
    method: string;
    value: string[];
  }[];
}

const URL_CACHE_KEY = 'showCommonly';

@Component
export default class WhereConditions extends tsc<IProps, IEmit> {
  @Prop({ type: Array, default: () => [] }) readonly value: IProps['value'];
  @Prop({ type: Array, default: () => [] }) readonly commonConditionValue: IProps['commonConditionValue'];
  @Prop({ type: Boolean, default: false }) readonly commonDimensionEnable: IProps['commonDimensionEnable'];
  @Prop({ type: Array, default: () => [] }) readonly customData: IProps['customData'];

  localWhereValueList: Readonly<IProps['value']> = [];
  localCommonConditionValueList: Readonly<IProps['commonConditionValue']> = [];
  isShowCommonlyUsedList = true;
  localCustomDataValueList: Readonly<IProps['customData']> = [];

  get currentSelectedMetricList() {
    return customEscalationViewStore.currentSelectedMetricList;
  }
  get commonDimensionList() {
    return customEscalationViewStore.commonDimensionList;
  }

  @Watch('commonDimensionList', { immediate: true })
  commonDimensionListChange() {
    this.mergeCommonConditionValue();
  }

  @Watch('commonConditionValue', { immediate: true })
  commonConditionValueChange() {
    this.mergeCommonConditionValue();
  }

  @Watch('value', { immediate: true })
  valueChange() {
    this.localWhereValueList = Object.freeze([...this.value]);
  }

  @Watch('customData', { immediate: true })
  customDataChange() {
    this.localCustomDataValueList = Object.freeze([...this.customData]);
  }

  triggerChange() {
    this.$emit('change', {
      where: this.localWhereValueList,
      common_conditions: _.filter(this.localCommonConditionValueList, item => item.value.length > 0),
      custom_data: _.filter(this.localCustomDataValueList, item => item.value.length > 0),
    });
  }

  @Debounce(300)
  mergeCommonConditionValue() {
    if (!this.commonDimensionEnable) {
      return;
    }
    const valueMap = this.commonConditionValue.reduce<Record<string, IProps['commonConditionValue'][number]>>(
      (result, item) => {
        if (item.value.length > 0) {
          Object.assign(result, {
            [item.key]: item,
          });
        }
        return result;
      },
      {}
    );
    this.localCommonConditionValueList = Object.freeze(
      this.commonDimensionList.map(item => {
        if (valueMap[item.name]) {
          return { ...valueMap[item.name] };
        }
        return {
          key: item.name,
          alias: item.alias,
          method: 'eq',
          value: [],
        };
      })
    );
  }

  handleConditionChange(value: typeof this.localWhereValueList) {
    this.localWhereValueList = Object.freeze(value);
    this.triggerChange();
  }

  handleCommonConditinChange(value: typeof this.localCommonConditionValueList) {
    this.localCommonConditionValueList = Object.freeze(value);
    this.triggerChange();
  }
  handleCustomDataChange(value: typeof this.localCustomDataValueList) {
    this.localCustomDataValueList = Object.freeze(value);
    this.triggerChange();
  }

  handleToggleCommonlyUsedList() {
    this.isShowCommonlyUsedList = !this.isShowCommonlyUsedList;
    this.$router.replace({
      query: {
        ...this.$route.query,
        [URL_CACHE_KEY]: `${this.isShowCommonlyUsedList}`,
      },
    });
  }

  created() {
    this.isShowCommonlyUsedList = Boolean(this.$route.query[URL_CACHE_KEY]) || true;
  }

  render() {
    return (
      <div class='bk-monitor-new-metric-view-where-condition'>
        <div
          class='filter-label'
          data-role='param-label'
        >
          <div>{this.$t('过滤条件')}</div>
        </div>
        <div class='where-condition-content'>
          <RenderResultList
            value={this.localWhereValueList as IProps['value']}
            onChange={this.handleConditionChange}
          />
          {this.currentSelectedMetricList.length > 0 && this.commonDimensionEnable && this.isShowCommonlyUsedList && (
            <RenderCommonList
              data={this.localCommonConditionValueList as IProps['commonConditionValue']}
              onChange={this.handleCommonConditinChange}
            />
          )}
          {this.customData.length > 0 && (
            <RenderCustomList
              data={this.localCustomDataValueList as IProps['customData']}
              onChange={this.handleCustomDataChange}
            />
          )}
        </div>
        {this.currentSelectedMetricList.length > 0 && this.commonDimensionEnable && (
          <div
            class={{
              'commonly-used-btn': true,
              'is-active': this.isShowCommonlyUsedList,
            }}
            v-bk-tooltips={this.$t('展示/隐藏常用条件')}
            onClick={this.handleToggleCommonlyUsedList}
          >
            <i class='icon-monitor icon-a-configurationpeizhi' />
          </div>
        )}
      </div>
    );
  }
}
