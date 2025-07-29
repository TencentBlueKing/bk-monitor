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
import KvSelector from 'monitor-pc/components/retrieval-filter/setting-kv-selector';

import { getCustomTsDimensionValues } from '../../../../../../services/scene_view_new';
import customEscalationViewStore from '@store/modules/custom-escalation-view';

interface IEmit {
  onChange: (value: IProps['data']) => void;
}

interface IProps {
  data: {
    alias: string;
    key: string;
    method: string;
    value: string[];
  };
}

@Component
export default class FilterConditions extends tsc<IProps, IEmit> {
  @Prop({ type: Object, required: true }) readonly data: IProps['data'];

  valueListMemo: Readonly<{ id: string; name: string }[]> = [];

  @Watch('data', { immediate: true })
  dataChange() {
    this.valueListMemo = [];
  }

  async getValueCallback({ search }: { search: string }) {
    if (this.valueListMemo.length < 1) {
      const [startTime, endTime] = customEscalationViewStore.timeRangTimestamp;
      const result = await getCustomTsDimensionValues({
        time_series_group_id: Number(this.$route.params.id),
        dimension: this.data.key,
        start_time: startTime || 0,
        end_time: endTime || 0,
        metrics: customEscalationViewStore.currentSelectedMetricList.map(item => item.metric_name),
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

  handleChange(payload: { value: string[] }) {
    this.$emit('change', {
      ...this.data,
      value: [...payload.value],
    });
  }

  render() {
    return (
      <KvSelector
        fieldInfo={{
          field: this.data.key,
          alias: this.data.alias,
          methods: [{ id: 'eq', name: '=' }],
          isEnableOptions: true,
        }}
        value={{
          key: this.data.key,
          condition: 'and' as any,
          method: 'eq',
          value: this.data.value,
        }}
        getValueFn={this.getValueCallback}
        onChange={this.handleChange}
      />
    );
  }
}
