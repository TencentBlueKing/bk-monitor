/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 */
import { retrieveFieldCacheService, storeCacheService } from '@/storage';

import { buildTableIdConditions, isSceneRetrieve } from '../helper.ts';
import { BK_LOG_STORAGE, SEARCH_MODE_DIC } from '../store.type.ts';

export const resolveGetterVisibleFields = state => {
  if (state.storage[BK_LOG_STORAGE.SHOW_FIELD_ALIAS]) {
    const result = [];
    state.visibleFields.forEach(field => {
      if (!field.has_repeat_alias_field) {
        result.push(field);
      }

      if (field.has_repeat_alias_field && !result.includes(field.alias_mapping_field)) {
        result.push(field.alias_mapping_field);
      }
    });
    return result;
  }

  return state.visibleFields.filter(field => !field.is_virtual_alias_field);
};

export const resolveFilteredFieldList = state => {
  void state.fieldMetaVersion;
  void state.indexFieldInfo.field_meta_version;
  const fieldScope = state.indexFieldInfo.field_scope || state.indexId || 'default';
  const sourceFields = retrieveFieldCacheService.getFieldList(
    fieldScope,
    state.storage[BK_LOG_STORAGE.SHOW_FIELD_ALIAS],
  );
  const result = state.storage[BK_LOG_STORAGE.SHOW_FIELD_ALIAS]
    ? sourceFields.filter(field => !field.has_repeat_alias_field)
    : sourceFields.filter(field => !field.is_virtual_alias_field);

  return result;
};

export const resolveRawFieldList = state => {
  void state.fieldMetaVersion;
  void state.indexFieldInfo.field_meta_version;
  const fieldScope = state.indexFieldInfo.field_scope || state.indexId || 'default';
  return retrieveFieldCacheService.getFieldList(fieldScope, false);
};

export const resolveFieldTree = state => {
  void state.fieldMetaVersion;
  void state.indexFieldInfo.field_meta_version;
  const fieldScope = state.indexFieldInfo.field_scope || state.indexId || 'default';
  return retrieveFieldCacheService.getFieldTree(fieldScope);
};

export const resolveFieldAliasMap = state =>
  resolveRawFieldList(state).reduce((out, field) => {
    out[field.field_name] = field.field_alias || field.field_name;
    return out;
  }, {});

/** UI 展示专用：仅使用 query_alias，不影响既有 fieldAliasMap 业务语义 */
export const resolveDisplayFieldAliasMap = state =>
  resolveRawFieldList(state).reduce((out, field) => {
    out[field.field_name] = field.query_alias || field.field_name;
    return out;
  }, {});

export const buildOriginAddition = state => {
  const { addition = [] } = state.indexItem;
  const filterAddition = addition
    .filter(item => item.field !== '_ip-select_')
    .map(({ field, operator, value, hidden_values, disabled }) => {
      const target = {
        field,
        operator,
        value,
        hidden_values,
        disabled,
      };

      if (['is true', 'is false'].includes(target.operator)) {
        target.value = [''];
      }

      return target;
    });

  filterAddition.forEach(item => {
    if (['=~', '&=~', '!=~', '&!=~'].includes(item.operator)) {
      const fieldScope = state.indexFieldInfo.field_scope || state.indexId || 'default';
      const field = retrieveFieldCacheService.getFieldNameIndex(fieldScope)[item.field];
      if (field?.field_type === 'text' && !(field?.is_case_sensitive ?? true)) {
        item.value = item.value.map(v => v?.toLowerCase() ?? '');
      }
    }
  });

  return filterAddition;
};

export const buildRetrieveParams = (state, getters, rootGetters) => {
  const {
    start_time,
    end_time,
    begin,
    size,
    keyword = '*',
    ip_chooser,
    host_scopes,
    interval,
    sort_list,
    format,
    timezone,
  } = state.indexItem;

  const searchMode = SEARCH_MODE_DIC[state.storage[BK_LOG_STORAGE.SEARCH_TYPE]] ?? 'ui';
  const originAddition = getters.originAddition ?? buildOriginAddition(state);
  const searchParams = searchMode === 'sql' ? { keyword, addition: [] } : { addition: originAddition, keyword: '*' };

  if (state.aiMode.active) {
    searchParams.keyword = [...state.aiMode.filterList, searchParams.keyword]
      .filter(f => !/^\s*\*?\s*$/.test(f))
      .join(' AND ');
  }

  if (searchParams.keyword.replace(/\s*/, '') === '') {
    searchParams.keyword = '*';
  }

  let local_sort_list = [];
  if (state.dateTimeSort) {
    local_sort_list = state.dateTimeSortList;
  } else if (state.localSort) {
    local_sort_list = sort_list;
  } else {
    local_sort_list = getters.custom_sort_list;
  }

  const baseParams = {
    start_time,
    end_time,
    format,
    addition: originAddition,
    begin,
    size,
    ip_chooser,
    host_scopes,
    interval,
    search_mode: searchMode,
    sort_list: local_sort_list,
    bk_biz_id: state.bkBizId,
    time_zone: timezone,
    ...searchParams,
  };

  if (isSceneRetrieve(state)) {
    const { table_id_conditions, scene_filter_values } = buildTableIdConditions(
      state,
      rootGetters['retrieve/sceneConfigList'],
    );
    Object.assign(baseParams, {
      space_uid: state.spaceUid,
      table_id_conditions,
      scene_filter_values,
    });
  }

  storeCacheService
    .setApiCache('store/retrieve-params-snapshot', state.indexId || state.spaceUid || 'default', baseParams)
    .catch(() => {});

  return baseParams;
};

export const buildRequestAddition = (state, getters) => {
  const searchMode = SEARCH_MODE_DIC[state.storage[BK_LOG_STORAGE.SEARCH_TYPE]] ?? 'ui';
  if (searchMode !== 'ui') {
    return [];
  }

  const originAddition = getters.originAddition ?? buildOriginAddition(state);
  return originAddition.reduce((output, current) => {
    const { field, operator, value, hidden_values: hiddenValues = [], disabled } = current;
    if (!disabled && field !== '_ip-select_') {
      const filterFn = v => !hiddenValues.includes(v);
      const filterValue = Array.isArray(value) ? value.filter(filterFn) : [value].filter(filterFn);
      if (['does not exists', 'exists', 'is false', 'is true'].includes(operator) || filterValue.length > 0) {
        output.push({
          field,
          operator,
          value: filterValue,
        });
      }
    }
    return output;
  }, []);
};
