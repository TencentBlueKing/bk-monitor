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
import { computed } from 'vue';
import type { Ref } from 'vue';

import { useRumExploreStore } from '../../../store/modules/rum-explore';
import { ALL_SPAN_TYPE, SPAN_TYPE_FIELD, SPAN_TYPE_META } from '../constants';

import type { IRumFieldGroup, IRumFilter, IRumViewConfig } from '../typings';

export interface IRumSpanTypeChip {
  icon: string;
  label: string;
  value: string;
}

/**
 * span 类型快捷筛选。
 *
 * 类型列表由接口的 span_type_display_fields 决定，前端只补图标与英文文案；
 * 接口新增类型时会自动出现在 chips 里，图标走兜底、文案取 attributes.span_type 的枚举别名。
 */
export function useRumSpanType(viewConfig: Ref<IRumViewConfig>) {
  const store = useRumExploreStore();

  /** attributes.span_type 字段自带的枚举别名，用作未知类型的文案兜底 */
  const optionAliasMap = computed(() => {
    const field = viewConfig.value.fields.find(item => item.name === SPAN_TYPE_FIELD);
    return new Map((field?.option_values || []).map(option => [option.value, option.alias || option.value]));
  });

  const spanTypeList = computed<string[]>(() => Object.keys(viewConfig.value.span_type_display_fields || {}));

  const chipList = computed<IRumSpanTypeChip[]>(() =>
    spanTypeList.value.map(type => ({
      value: type,
      icon: SPAN_TYPE_META[type]?.icon || '',
      label: SPAN_TYPE_META[type]?.label || optionAliasMap.value.get(type) || type,
    }))
  );

  const activeSpanType = computed(() => store.spanType);

  /** 选中类型时附加到查询条件上的 filter，选中「全部」时为空 */
  const spanTypeFilters = computed<IRumFilter[]>(() =>
    store.spanType ? [{ key: SPAN_TYPE_FIELD, operator: 'equal', value: [store.spanType] }] : []
  );

  /** 分组是否适用于当前类型，不适用的分组在左侧栏折叠 */
  function isGroupSupported(group: IRumFieldGroup) {
    if (!store.spanType || !group.supported_span_types?.length) return true;
    return group.supported_span_types.includes(store.spanType);
  }

  function setSpanType(type: string) {
    store.spanType = type === store.spanType ? ALL_SPAN_TYPE : type;
  }

  return {
    chipList,
    activeSpanType,
    spanTypeFilters,
    isGroupSupported,
    setSpanType,
  };
}
