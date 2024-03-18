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
import { defineComponent, PropType } from 'vue';
import { Button } from 'bkui-vue';

import ProfilingGraph from '../../../plugins/charts/profiling-graph/profiling-graph';
import { IQueryParams } from '../../../typings/trace';
import { DataTypeItem } from '../typings/profiling-retrieval';

import TrendChart from './trend-chart';

import './profiling-retrieval-view.scss';

export default defineComponent({
  name: 'ProfilingRetrievalView',
  props: {
    dataType: {
      type: String,
      default: 'cpu'
    },
    dataTypeList: {
      type: Array as PropType<DataTypeItem[]>,
      default: () => []
    },
    queryParams: {
      type: Object as PropType<IQueryParams>,
      required: true
    }
  },
  emits: ['update:dataType'],
  setup() {},
  render() {
    return (
      <div class='profiling-retrieval-view-component'>
        <div class='data-type'>
          {this.$t('数据类型')}
          <Button.ButtonGroup
            class='data-type-list'
            size='small'
          >
            {this.dataTypeList.map(item => {
              return (
                <Button
                  key={item.key}
                  selected={item.key === this.dataType}
                  onClick={() => {
                    this.$emit('update:dataType', item.key);
                  }}
                >
                  {item.name}
                </Button>
              );
            })}
          </Button.ButtonGroup>
        </div>
        <TrendChart queryParams={this.queryParams} />
        <div class='profiling-graph-view-content'>
          <ProfilingGraph queryParams={this.queryParams} />
        </div>
      </div>
    );
  }
});
