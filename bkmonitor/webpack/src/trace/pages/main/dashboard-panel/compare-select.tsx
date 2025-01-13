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
import { defineComponent, ref } from 'vue';

import { Select } from 'bkui-vue';

import TargetCompareSelect from './target-compare-select';
import TimeCompareSelect from './time-compare-select';

import './compare-select.scss';

/** 不对比 | 时间对比 | 目标对比 | 指标对比 */
enum CompareId {
  metric = 'metric',
  none = 'none',
  target = 'target',
  time = 'time',
}

const COMPARE_LIST = [
  {
    id: CompareId.none,
    name: window.i18n.t('不对比'),
  },
  {
    id: CompareId.target,
    name: window.i18n.t('目标对比'),
  },
  {
    id: CompareId.time,
    name: window.i18n.t('时间对比'),
  },
  // {
  //   id: 'metric',
  //   name: window.i18n.t('指标对比'),
  // },
];

export default defineComponent({
  name: 'CompareSelect',
  props: {
    curTarget: { type: [String, Number], default: '' },
    targetList: { type: Array, default: () => [] },
  },
  setup() {
    const localType = ref(CompareId.none);

    function handleTargetChange() {}

    return {
      localType,
      handleTargetChange,
    };
  },
  render() {
    const contentRender = () => {
      if (this.localType === CompareId.time) {
        return (
          <div>
            <TimeCompareSelect class='ml-12' />
          </div>
        );
      }
      if (this.localType === CompareId.target) {
        return (
          <span class='compare-target-wrap ml-12'>
            {this.curTarget && (
              <span
                class='compare-target-ip'
                v-bk-overflow-tips
              >
                {this.curTarget}
              </span>
            )}
            <span class='target-compare-select'>
              <TargetCompareSelect
                list={[]}
                value={[]}
                onChange={this.handleTargetChange}
              />
            </span>
          </span>
        );
      }
      return undefined;
    };
    return (
      <div class='dashboard-panel__compare-select'>
        <span class='compare-select-label'>{this.$t('对比方式')}</span>
        <Select
          class='compare-select'
          v-model={this.localType}
          behavior='simplicity'
          clearable={false}
          filterable={false}
          size={'small'}
        >
          {{
            default: () =>
              COMPARE_LIST.map(item => (
                <Select.Option
                  id={item.id}
                  key={item.id}
                  name={item.name}
                />
              )),
          }}
        </Select>
        <span class='compare-select-content'>{contentRender()}</span>
      </div>
    );
  },
});
