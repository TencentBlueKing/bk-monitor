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
import { Component, InjectReactive, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import _ from 'lodash';
import ValueTagSelector from 'monitor-pc/components/retrieval-filter/value-tag-selector';
import customEscalationViewStore from 'monitor-pc/store/modules/custom-escalation-view';

import { methodMap } from '../../index';

// import { getCustomTsDimensionValues } from '../../../../../../../../../../services/scene_view_new';
import type { RequestHandlerMap } from '../../../../../../../../../../../../type';

import './index.scss';

interface IEmit {
  onMethondChange: (value: string) => void;
  onValueChange: (value: string[]) => void;
}

interface IProps {
  keyName: string;
  method: string;
  value: string[];
}

@Component
export default class PanelValueSelect extends tsc<IProps, IEmit> {
  @Prop({ type: String }) readonly keyName: IProps['keyName'];
  @Prop({ type: String }) readonly method: IProps['method'];
  @Prop({ type: Array }) readonly value: IProps['value'];
  @InjectReactive('timeSeriesGroupId') readonly timeSeriesGroupId: number;
  @InjectReactive('isApm') readonly isApm: boolean;
  @InjectReactive('appName') readonly appName: string;
  @InjectReactive('serviceName') readonly serviceName: string;
  @InjectReactive('requestHandlerMap') readonly requestHandlerMap!: RequestHandlerMap;

  @Ref('valueTagInputRef') readonly valueTagInputRef: HTMLDivElement;

  methodList = Object.freeze(
    Object.keys(methodMap).map(key => ({
      id: key,
      name: methodMap[key],
    }))
  );
  valueListMemo: Readonly<{ id: string; name: string }[]> = [];

  get currentSelectedMetricNameList() {
    return customEscalationViewStore.currentSelectedMetricList.map(metricItem => ({
      name: metricItem.metric_name, // 指标名称
      scope_name: metricItem.scope_name, // 分组名称
    }));
  }

  @Watch('keyName', { immediate: true })
  keyNameChangeCallback() {
    this.$nextTick(() => {
      if (this.keyName) {
        this.valueTagInputRef.focusFn();
      }
      this.valueListMemo = [];
    });
  }

  async getValueCallback({ search }: { search: string }) {
    if (!this.keyName) {
      return {
        count: 0 as const,
        list: [],
      };
    }

    if (this.valueListMemo.length < 1) {
      const [startTime, endTime] = customEscalationViewStore.timeRangTimestamp;
      const params = {
        time_series_group_id: Number(this.timeSeriesGroupId),
      };
      if (this.isApm) {
        delete params.time_series_group_id;
        Object.assign(params, {
          apm_app_name: this.appName,
          apm_service_name: this.serviceName,
        });
      }
      const result = await this.requestHandlerMap.getCustomTsDimensionValues({
        // time_series_group_id: Number(this.timeSeriesGroupId),
        ...params,
        dimension: this.keyName,
        start_time: startTime || 0,
        end_time: endTime || 0,
        metrics: this.currentSelectedMetricNameList,
      });
      this.valueListMemo = result.map(item => ({
        id: item.name,
        name: item.name,
      }));
    }

    const list = _.filter(this.valueListMemo, item =>
      item.name.toLocaleLowerCase().includes(search.toLocaleLowerCase())
    );

    return {
      count: 0 as const,
      list,
    };
  }

  handleMethodChange(value: string) {
    this.$emit('methondChange', value);
  }

  handleValueChange(payload: { id: string; name: string }[]) {
    this.$emit(
      'valueChange',
      payload.map(item => item.id)
    );
  }

  render() {
    return (
      <div class='edit-panel-value-select'>
        <div class='value-title'>{this.$t('运算符')}</div>
        <bk-select
          popover-options={{
            appendTo: 'parent',
          }}
          disabled={!this.keyName}
          value={this.method}
          onChange={this.handleMethodChange}
        >
          {this.methodList.map(methodItem => (
            <bk-option
              id={methodItem.id}
              key={methodItem.id}
              name={methodItem.name}
            />
          ))}
        </bk-select>
        <div class='value-title'>{this.$t('筛选值')}</div>
        <ValueTagSelector
          ref='valueTagInputRef'
          style='width: auto'
          fieldInfo={{
            field: this.keyName,
            alias: this.keyName,
            methods: [{ id: this.method, name: this.method }],
            isEnableOptions: true,
          }}
          value={this.value.map(item => ({
            id: item,
            name: item,
          }))}
          getValueFn={this.getValueCallback}
          onChange={this.handleValueChange}
        />
      </div>
    );
  }
}
