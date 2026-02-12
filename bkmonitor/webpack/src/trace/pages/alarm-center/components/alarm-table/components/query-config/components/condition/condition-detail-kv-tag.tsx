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

import { type PropType, computed, defineComponent } from 'vue';

import { xssFilter } from 'monitor-common/utils';
import { ConditionMethodAliasMap } from 'monitor-pc/pages/query-template/constants';

import type { AggCondition, DimensionField } from 'monitor-pc/pages/query-template/typings';

import './condition-detail-kv-tag.scss';

export default defineComponent({
  name: 'ConditionDetailKvTag',
  props: {
    /* 聚合维度信息 id-聚合维度对象 映射表 */
    allDimensionMap: {
      type: Object as PropType<Record<string, DimensionField>>,
      default: () => ({}),
    },
    /* 已选过滤条件 */
    value: {
      type: Object as PropType<AggCondition>,
      default: () => null,
    },
  },
  setup(props) {
    const viewValue = computed(() => {
      return props.value?.value?.map?.(v => ({ id: v, name: showNameSlice(v) })) || [];
    });
    const tipContent = computed(() => {
      return xssFilter(
        `<div style="max-width: 600px;">${props.value.key} ${ConditionMethodAliasMap[props.value.method]} ${viewValue.value?.map?.(v => v.id).join(' OR ')}<div>`
      );
    });

    /**
     * @description: 判断并截取视图中显示的值，当值过长时(大于20个字符)截取拼接 ... 进行展示
     * @param {string} showName 需要截取的值
     * @returns {string} 最终视图中展示的值
     */
    const showNameSlice = (showName: string) => {
      return showName.length > 20 ? `${showName.slice(0, 20)}...` : showName;
    };

    return {
      tipContent,
      viewValue,
    };
  },
  render() {
    return this.value ? (
      <div class='alert-condition-detail-kv-tag-component'>
        <div
          key={this.tipContent}
          class='condition-detail-kv-tag-component-wrap'
          v-tippy={{
            content: this.tipContent,
            delay: [300, 0],
            allowHTML: true,
          }}
        >
          <div class='key-wrap'>
            <span class='key-name'>
              {this.value.dimension_name || this.allDimensionMap?.[this.value?.key]?.name || this.value.key}
            </span>
            <span class={['key-method', this.value.method]}>{ConditionMethodAliasMap[this.value.method]}</span>
          </div>
          <div class='value-wrap'>
            {this.viewValue?.map?.((item, index) => [
              index > 0 && (
                <span
                  key={`${index}_condition`}
                  class='value-condition'
                >
                  OR
                </span>
              ),
              <span
                key={`${index}_key`}
                class='value-name'
              >
                {item.name || '""'}
              </span>,
            ]) || '--'}
          </div>
        </div>
      </div>
    ) : null;
  },
});
