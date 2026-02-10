import { type PropType, defineComponent } from 'vue';

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
import { Sideslider } from 'bkui-vue';

import AnalysisList from './analysis-list';

import type { AnalysisListItemBucket } from '../../typings';

import './alarm-analysis-detail.scss';

export default defineComponent({
  name: 'AlarmAnalysisDetail',
  props: {
    show: {
      type: Boolean,
      default: false,
    },
    title: {
      type: String,
      default: '',
    },
    count: {
      type: Number,
      default: 0,
    },
    list: {
      type: Array as PropType<AnalysisListItemBucket[]>,
      default: () => [],
    },
    loading: {
      type: Boolean,
      default: true,
    },
  },
  emits: {
    'update:show': (isShow: boolean) => isShow !== undefined,
    conditionChange: (type: string, value: string) => type && value,
    copyNames: (list: AnalysisListItemBucket[]) => list.length > 0,
  },

  setup(props, { emit }) {
    const handleSliderShowChange = (isShow: boolean) => {
      emit('update:show', isShow);
    };

    const handleCopyNames = () => {
      emit('copyNames', props.list);
    };

    const handleConditionChange = (type: string, value: string) => {
      emit('conditionChange', type, value);
    };

    return {
      handleSliderShowChange,
      handleCopyNames,
      handleConditionChange,
    };
  },
  render() {
    return (
      <Sideslider
        width='640'
        ext-cls='alarm-analysis-slider'
        is-show={this.show}
        transfer={true}
        quick-close
        onUpdate:isShow={this.handleSliderShowChange}
      >
        {{
          header: () => (
            <div class='alarm-analysis-slider-header'>
              <div class='alarm-analysis-title'>
                <span
                  class='field-name'
                  v-overflow-tips
                >
                  {this.title}
                </span>
                <div class='count'>( {this.count} )</div>
                <i
                  class='icon-monitor icon-mc-copy'
                  v-bk-tooltips={{ content: '批量复制' }}
                  onClick={this.handleCopyNames}
                />
              </div>
            </div>
          ),
          default: () =>
            this.loading ? (
              <div class='skeleton-wrap'>
                {new Array(12).fill(0).map((_, i) => (
                  <div
                    key={i}
                    class='skeleton-element'
                  />
                ))}
              </div>
            ) : (
              <AnalysisList
                list={this.list}
                onConditionChange={this.handleConditionChange}
              />
            ),
        }}
      </Sideslider>
    );
  },
});
