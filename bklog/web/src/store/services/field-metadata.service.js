/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 */
import { getOperatorKey } from '@/common/util';
import { builtInInitHiddenList } from '@/const/index.js';

import { createFieldItem, indexSetClusteringData } from '../default-values.ts';

const HIDDEN_FIELDS = new Set(builtInInitHiddenList);

export const createIndexSetFieldConfig = (payload) => {
  const output = {
    clustering_config: { ...indexSetClusteringData },
  };
  (payload?.config ?? []).forEach((item) => {
    output[item.name] = item;
  });
  return output;
};

export const createOperatorDictionary = (payload) => {
  const output = {};
  (payload?.fields ?? []).forEach((field) => {
    const { field_operator: fieldOperator = [] } = field;
    fieldOperator.forEach((item) => {
      output[getOperatorKey(item.operator)] = item;
    });
  });
  return output;
};

export const createNotTextTypeFields = payload => (
  (payload?.fields ?? [])
    .filter(field => field.field_type !== 'text')
    .map(item => item.field_name)
);

export const normalizeIndexFieldInfo = (payload) => {
  const processedData = payload ? { ...payload } : {};
  if (!Array.isArray(processedData.fields)) {
    return processedData;
  }

  const fields = processedData.fields.slice();
  const fieldAliasMap = new Map();

  fields.forEach((field) => {
    const fieldAlias = field.query_alias;
    if (!fieldAlias) return;

    const existValue = fieldAliasMap.get(fieldAlias) ?? {
      count: 0,
      field_alias: fieldAlias,
      resolved: false,
      fields: [],
      target: null,
    };
    existValue.count += 1;
    existValue.fields.push(field);
    fieldAliasMap.set(fieldAlias, existValue);
  });

  Array.from(fieldAliasMap.values()).forEach((value) => {
    if (value.count <= 1) return;

    const target = createFieldItem(value.field_alias, 'keyword', {
      ...(value.fields[0] ?? {}),
      field_alias: '',
      query_alias: '',
      field_name: value.field_alias,
      is_virtual_alias_field: true,
      has_repeat_alias_field: false,
      alias_mapping_field: null,
      source_field_names: [],
    });

    value.fields.forEach((field) => {
      field.has_repeat_alias_field = true;
      field.alias_mapping_field = target;
      if (!target.source_field_names.includes(field.field_name)) {
        target.source_field_names.push(field.field_name);
      }
    });

    fields.push(target);
  });

  fields.sort((a, b) => {
    if (a.field_name === 'dtEventTimeStamp') return -1;
    if (b.field_name === 'dtEventTimeStamp') return 1;
    const aWeight = HIDDEN_FIELDS.has(a.field_name) ? 1 : 0;
    const bWeight = HIDDEN_FIELDS.has(b.field_name) ? 1 : 0;
    if (aWeight !== bWeight) return aWeight - bWeight;
    if (a.is_built_in !== b.is_built_in) {
      return a.is_built_in ? 1 : -1;
    }
    return 0;
  });

  const fieldNameIndex = {};
  const queryAliasIndex = {};
  fields.forEach((f) => {
    fieldNameIndex[f.field_name] = f;
    if (f.query_alias) {
      queryAliasIndex[f.query_alias] = f;
    }
  });

  return {
    ...processedData,
    fields,
    fieldNameIndex,
    queryAliasIndex,
  };
};

export const resolveVisibleFields = ({ payload, catchDisplayFields = [], indexFieldInfo }) => {
  const isVersion2Payload = payload?.version === 'v2';
  const displayFields = catchDisplayFields.length ? catchDisplayFields : null;
  const filterList = (isVersion2Payload ? payload.displayFieldNames : payload || displayFields)
    ?? indexFieldInfo.display_fields
    ?? [];

  const fieldsMap = new Map();
  (indexFieldInfo.fields ?? []).forEach((field) => {
    const existing = fieldsMap.get(field.field_name);
    if (!existing || !field.is_virtual_alias_field) {
      fieldsMap.set(field.field_name, field);
    }
  });

  return filterList
    .map(displayName => fieldsMap.get(displayName))
    .filter(Boolean);
};

export const createRetrieveDropdownData = (listData = [], notTextTypeFields = []) => {
  const output = {};
  const notTextTypeSet = new Set(notTextTypeFields);

  const recursiveIncreaseData = (dataItem, prefixFieldKey = '') => {
    dataItem
      && Object.entries(dataItem).forEach(([field, value]) => {
        if (value && typeof value === 'object' && !Array.isArray(value)) {
          recursiveIncreaseData(value, `${prefixFieldKey + field}.`);
          return;
        }

        const fullFieldKey = prefixFieldKey ? prefixFieldKey + field : field;
        let fieldData = output[fullFieldKey];
        if (fieldData) fieldData.__totalCount += 1;
        if (value || value === 0) {
          if (!fieldData) {
            output[fullFieldKey] = Object.defineProperties(
              {},
              {
                __fieldType: { value: typeof value },
                __totalCount: { value: 1, writable: true },
                __validCount: { value: 0, writable: true },
              },
            );
            fieldData = output[fullFieldKey];
          }
          fieldData.__validCount += 1;
          if (notTextTypeSet.has(field) && !fieldData?.[value]) {
            fieldData[value] = 1;
          } else {
            fieldData[value] += 1;
          }
        }
      });
  };

  listData.forEach(dataItem => recursiveIncreaseData(dataItem));
  return output;
};

export const createIndexSetOperatorConfig = ({ indexSetFieldConfig, indexItem }) => {
  const {
    bkmonitor,
    context_and_realtime: contextAndRealtime,
    bcs_web_console: bcsWebConsole,
  } = indexSetFieldConfig;

  let indexSetValue;
  if (!indexItem.isUnionIndex) {
    const item = indexItem.items[0];
    indexSetValue = {
      scenarioID: item?.scenario_id,
      sortFields: item?.sort_fields ?? [],
      targetFields: item?.target_fields ?? [],
    };
  } else {
    indexSetValue = {};
  }

  return {
    bkmonitor,
    bcsWebConsole,
    contextAndRealtime,
    indexSetValue,
    toolMessage: {
      webConsole: bcsWebConsole?.is_active ? 'WebConsole' : bcsWebConsole?.extra?.reason,
      realTimeLog: contextAndRealtime?.is_active
        ? window.mainComponent.$t('实时日志')
        : contextAndRealtime?.extra?.reason,
      contextLog: contextAndRealtime?.is_active
        ? window.mainComponent.$t('上下文')
        : contextAndRealtime?.extra?.reason,
    },
  };
};
