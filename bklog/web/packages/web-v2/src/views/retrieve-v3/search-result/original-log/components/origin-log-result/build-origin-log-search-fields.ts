/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */
import { retrieveFieldCacheService } from '@/storage';

import { buildOriginLogSearchHeaders } from './build-origin-log-search-headers';

export { buildOriginLogSearchHeaders };

/**
 * 与主检索 getRenderFieldMetadata / getProjectionFieldNames 对齐，
 * 供上下文本地 Stream 预分词使用（不写 Vuex）。
 */
export const buildOriginLogSearchFieldPayload = (state: Record<string, any>) => {
  const fieldScope = state.indexFieldInfo?.field_scope || state.indexId || 'default';
  const fieldNameIndex = retrieveFieldCacheService.getFieldNameIndex(fieldScope);
  const cachedFields = retrieveFieldCacheService.getFieldList(fieldScope, false);

  const fieldMetadata = Object.keys(fieldNameIndex).reduce(
    (output, fieldName) => {
      const field = fieldNameIndex[fieldName];
      if (!field || typeof field !== 'object') return output;
      output[fieldName] = {
        field_name: field.field_name || fieldName,
        field_type: field.field_type,
        is_analyzed: field.is_analyzed ?? false,
        tokenize_on_chars: field.tokenize_on_chars || '',
        is_virtual_obj_node: !!field.is_virtual_obj_node,
        parent_field_name: field.parent_field_name || field.parentFieldName || null,
        child_field_names: field.child_field_names || [],
        children_count: field.children_count || 0,
        source_field_names: field.source_field_names || [],
        query_alias: field.query_alias || '',
      };
      return output;
    },
    {} as Record<string, any>,
  );

  const fields = [
    ...(state.visibleFields || []),
    ...cachedFields.filter(
      (field: any) => field?.is_time_field || field?.field_name === state.indexFieldInfo?.time_field,
    ),
  ];

  const fieldNames = Array.from(
    new Set(
      fields
        .flatMap((field: any) => {
          if (!field) return [];
          return [field.field_name, field.alias_mapping_field?.field_name, ...(field.source_field_names || [])];
        })
        .filter(Boolean),
    ),
  );

  return { fieldMetadata, fieldNames };
};
