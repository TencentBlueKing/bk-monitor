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
import { Component, Ref, Watch, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import customEscalationViewStore from '@store/modules/custom-escalation-view';
import { getCustomTsDimensionValues } from 'monitor-api/modules/scene_view_new';

import './panel-value-select.scss';

interface IProps {
  keyName: string;
  method: string;
  value: string[];
}

interface IEmit {
  onMethondChange: (value: string) => void;
  onValueChange: (value: string[]) => void;
}

const methodList = [
  { id: 'eq', name: '=' },
  { id: 'gt', name: '>' },
  { id: 'gte', name: '>=' },
  { id: 'lt', name: '<' },
  { id: 'lte', name: '<=' },
  { id: 'neq', name: '!=' },
  { id: 'reg', name: 'regex' },
  { id: 'nreg', name: 'nregex' },
];

@Component
export default class ValueSelect extends tsc<IProps, IEmit> {
  @Prop({ type: String }) readonly keyName: IProps['keyName'];
  @Prop({ type: String }) readonly method: IProps['method'];
  @Prop({ type: Array }) readonly value: IProps['value'];

  @Ref('valueTagInputRef') readonly valueTagInputRef: any;

  isLoading = false;
  valueList: { id: string; name: string }[] = [];

  get currentSelectedMetricNameList() {
    return customEscalationViewStore.currentSelectedMetricNameList;
  }

  @Watch('keyName', { immediate: true })
  keyNameChangeCallback() {
    this.isLoading = false;
    this.$nextTick(() => {
      if (this.keyName) {
        this.fetchValue();
        this.valueTagInputRef.focusInputer();
      }
    });
  }

  async fetchValue() {
    try {
      this.isLoading = true;
      const [startTime, endTime] = customEscalationViewStore.timeRangTimestamp;
      const result = await getCustomTsDimensionValues({
        time_series_group_id: Number(this.$route.params.id),
        dimension: this.keyName,
        start_time: startTime || 0,
        end_time: endTime || 0,
        metrics: this.currentSelectedMetricNameList,
      });
      this.valueList = result.map(item => ({
        id: item.name,
        name: item.name,
      }));
    } finally {
      this.isLoading = false;
    }
  }

  handleMethodChange(value: string) {
    this.$emit('methondChange', value);
  }

  handleValueChange(value: string[]) {
    this.$emit('valueChange', value);
  }

  render() {
    return (
      <div class='edit-panel-value-select'>
        <div class='value-title'>{this.$t('运算符')}</div>
        <bk-select
          disabled={!this.keyName}
          value={this.method}
          onChange={this.handleMethodChange}
        >
          {methodList.map(methodItem => (
            <bk-option
              id={methodItem.id}
              name={methodItem.name}
            />
          ))}
        </bk-select>
        <div class='value-title'>{this.$t('筛选值')}</div>
        <div v-bkloading={{ 'is-loading': this.isLoading }}>
          <bk-tag-input
            ref='valueTagInputRef'
            allow-create={true}
            disabled={!this.keyName}
            has-delete-icon={true}
            list={this.valueList}
            trigger='focus'
            value={this.value}
            onChange={this.handleValueChange}
          />
        </div>
      </div>
    );
  }
}
