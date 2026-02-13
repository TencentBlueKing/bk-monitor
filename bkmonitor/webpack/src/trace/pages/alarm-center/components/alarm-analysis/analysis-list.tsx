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
import { type PropType, defineComponent } from 'vue';

import { Progress } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import EmptyStatus from '../../../../components/empty-status/empty-status';

import type { AnalysisListItemBucket } from '../../typings';

import './analysis-list.scss';

export default defineComponent({
  name: 'AnalysisList',
  props: {
    field: {
      type: String,
      default: '',
    },
    list: {
      type: Array as PropType<AnalysisListItemBucket[]>,
      default: () => [],
    },
  },
  emits: {
    conditionChange: (type: string, value: string) => type.length && value.length,
  },
  setup(_, { emit }) {
    const { t } = useI18n();

    const handleConditionChange = (type: string, value: string) => {
      emit('conditionChange', type, value);
    };

    return {
      t,
      handleConditionChange,
    };
  },
  render() {
    if (this.list.length === 0) return <EmptyStatus type='empty' />;
    return (
      <div class='analysis-list'>
        {this.list.map(item => (
          <div
            key={item.id}
            class='analysis-item'
          >
            <div class='analysis-item-info'>
              <div class='text-wrap'>
                <span
                  class='item-name'
                  v-overflow-tips
                >
                  {item.name}
                </span>
                <span class='item-count'>
                  {item.count}
                  {this.t('条')}
                </span>
                <span class='item-percent'>{item.percent}%</span>
              </div>
              <Progress
                color='#5AB8A8'
                percent={item.percent}
                show-text={false}
                stroke-width={4}
              />
            </div>
            <div class='analysis-item-tools'>
              <i
                class='icon-monitor icon-a-sousuo'
                onClick={() => this.handleConditionChange('eq', item.id)}
              />
              {this.field !== 'duration' && (
                <i
                  class='icon-monitor icon-sousuo-'
                  onClick={() => this.handleConditionChange('neq', item.id)}
                />
              )}
            </div>
          </div>
        ))}
      </div>
    );
  },
});
