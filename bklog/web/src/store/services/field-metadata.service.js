/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 */
import { getOperatorKey } from '@/common/util';
import { builtInInitHiddenList } from '@/const/index.js';
import { retrieveFieldCacheService } from '@/storage';
import {
  buildFieldNameIndex,
  buildQueryAliasIndex,
  createRetrieveFieldMeta,
} from '@/storage/utils/retrieve-field-meta';

import { createFieldItem, indexSetClusteringData } from '../default-values.ts';

const HIDDEN_FIELDS = new Set(builtInInitHiddenList);

export const createIndexSetFieldConfig = payload => {
  const output = {
    clustering_config: { ...indexSetClusteringData },
  };
  (payload?.config ?? []).forEach(item => {
    output[item.name] = item;
  });
  return output;
};

export const createOperatorDictionary = payload => {
  const output = {};
  createRetrieveFieldMeta(payload).rawFields.forEach(field => {
    const { field_operator: fieldOperator = [] } = field;
    fieldOperator.forEach(item => {
      output[getOperatorKey(item.operator)] = item;
    });
  });
  return output;
};

export const createNotTextTypeFields = payload =>
  createRetrieveFieldMeta(payload)
    .rawFields.filter(field => field.field_type !== 'text')
    .map(item => item.field_name);

export const normalizeIndexFieldInfo = payload => {
  const processedData = payload ? { ...payload } : {};
  if (!processedData.fields) {
    return processedData;
  }

  const fieldMeta = createRetrieveFieldMeta(processedData);
  const fields = fieldMeta.aliasFieldList.slice();
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

  return {
    ...processedData,
    fields,
    raw_fields: fieldMeta.rawFields,
    raw_field_list: fieldMeta.rawFieldList,
    alias_field_list: fields.filter(field => field.is_virtual_alias_field),
    field_tree: fieldMeta.fieldTree,
    fieldNameIndex: buildFieldNameIndex(fields),
    queryAliasIndex: buildQueryAliasIndex(fields),
    widthHints: fieldMeta.widthHints,
  };
};

export const resolveVisibleFields = ({ payload, catchDisplayFields = [], defaultDisplayFields = [], fieldScope }) => {
  const isVersion2Payload = payload?.version === 'v2';
  const displayFields = catchDisplayFields.length ? catchDisplayFields : null;
  const filterList =
    (isVersion2Payload ? payload.displayFieldNames : payload || displayFields) ?? defaultDisplayFields ?? [];

  const fieldsMap = new Map();
  retrieveFieldCacheService.getFieldList(fieldScope, false).forEach(field => {
    const existing = fieldsMap.get(field.field_name);
    if (!existing || !field.is_virtual_alias_field) {
      fieldsMap.set(field.field_name, field);
    }
  });

  return filterList.map(displayName => fieldsMap.get(displayName) ?? createFieldItem(displayName)).filter(Boolean);
};

export const createRetrieveDropdownData = (listData = [], notTextTypeFields = []) => {
  const output = {};
  const notTextTypeSet = new Set(notTextTypeFields);

  const recursiveIncreaseData = (dataItem, prefixFieldKey = '') => {
    dataItem &&
      Object.entries(dataItem).forEach(([field, value]) => {
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

  listData.forEach(dataItem => {
    recursiveIncreaseData(dataItem);
  });
  return output;
};

export const createIndexSetOperatorConfig = ({ indexSetFieldConfig, indexItem }) => {
  const { bkmonitor, context_and_realtime: contextAndRealtime, bcs_web_console: bcsWebConsole } = indexSetFieldConfig;

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
      contextLog: contextAndRealtime?.is_active ? window.mainComponent.$t('上下文') : contextAndRealtime?.extra?.reason,
    },
  };
};
