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
import { computed, shallowRef, watch } from 'vue';

import { useI18n } from 'vue-i18n';

import { EFieldType } from '../../../components/retrieval-filter/typing';
import { handleTransformToTimestamp } from '../../../components/time-range/utils';
import { useRumExploreStore } from '../../../store/modules/rum-explore';
import { RAW_FIELD_GROUP_NAME, RUM_TIME_FIELDS } from '../constants';
import { getViewConfig } from '../services/rum-search';

import type { IFilterField } from '../../../components/retrieval-filter/typing';
import type { IRumField, IRumFieldGroup, IRumViewConfig } from '../typings';

const EMPTY_VIEW_CONFIG: IRumViewConfig = {
  fields: [],
  groups: [],
  default_sort: [],
  display_fields: [],
  span_type_display_fields: {},
};

/**
 * 视图配置：字段全集、字段分组、默认列与默认排序。
 *
 * 分组完全由接口的 groups 驱动，前端只额外补一个「原始字段」分组，
 * 它由所有 is_real 字段聚合而成，在左侧栏里按 `.` 分层展示成树。
 */
export function useRumViewConfig() {
  const { t } = useI18n();
  const store = useRumExploreStore();

  const loading = shallowRef(false);
  const viewConfig = shallowRef<IRumViewConfig>(EMPTY_VIEW_CONFIG);

  /** 业务分组 + 末尾的「原始字段」分组 */
  const fieldGroups = computed<IRumFieldGroup[]>(() => {
    const groups = viewConfig.value.groups.filter(group => group.fields.length);
    const rawFields = viewConfig.value.fields.filter(field => field.is_real);
    if (!rawFields.length) return groups;
    return [
      ...groups,
      {
        name: RAW_FIELD_GROUP_NAME,
        alias: t('原始字段'),
        supported_span_types: [],
        fields: rawFields,
      },
    ];
  });

  /** 可检索字段 */
  const searchableFields = computed(() => viewConfig.value.fields.filter(field => field.is_searched));

  /** 检索条件区需要的字段结构 */
  const retrievalFields = computed<IFilterField[]>(() =>
    searchableFields.value.map(field => ({
      name: field.name,
      alias: field.alias,
      type: toFilterFieldType(field),
      isEnableOptions: field.is_dimensions || field.type === 'boolean',
      methods: (field.supported_operations || []).map(operation => ({
        alias: operation.label,
        value: operation.operator,
        placeholder: operation.placeholder,
        wildcardValue: operation.wildcard_operator || '',
      })),
    }))
  );

  /** 可作为表格列的字段，供字段设置使用 */
  const displayableFields = computed(() => viewConfig.value.fields.filter(field => field.can_displayed));

  const fieldMap = computed(() => new Map(viewConfig.value.fields.map(field => [field.name, field])));

  function getField(name: string): IRumField | undefined {
    return fieldMap.value.get(name);
  }

  async function fetchViewConfig() {
    if (!store.appName) {
      viewConfig.value = EMPTY_VIEW_CONFIG;
      return;
    }
    loading.value = true;
    const [startTime, endTime] = handleTransformToTimestamp(store.timeRange);
    viewConfig.value = await getViewConfig({
      app_name: store.appName,
      mode: store.mode,
      filters: [],
      query_string: '',
      start_time: startTime,
      end_time: endTime,
    });
    loading.value = false;
  }

  // 字段配置只跟应用和视角有关，时间变化不重新拉取，避免每次改时间都把左侧栏重置
  watch(() => [store.appName, store.mode], fetchViewConfig, { immediate: true });

  return {
    loading,
    viewConfig,
    fieldGroups,
    retrievalFields,
    searchableFields,
    displayableFields,
    getField,
    fetchViewConfig,
  };
}

/** 接口字段类型映射到检索条件区的输入控件类型 */
function toFilterFieldType(field: IRumField): EFieldType {
  // 带微秒单位且不是时间戳的字段用耗时输入组件
  if (field.field_unit === 'us' && !RUM_TIME_FIELDS.has(field.name)) return EFieldType.duration;
  switch (field.type) {
    case 'boolean':
      return EFieldType.boolean;
    case 'date':
      return EFieldType.date;
    case 'double':
    case 'integer':
    case 'long':
      return EFieldType.integer;
    case 'text':
      return EFieldType.text;
    default:
      return EFieldType.keyword;
  }
}
