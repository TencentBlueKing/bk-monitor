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
import { BK_LOG_STORAGE } from './store.type';
import { getDefaultOp, REVERSE_OPERATOR_MAP, getOperatorRequestParam } from '@/store/scene-filter-config';
import { isFeatureToggleOn } from '@/hooks/use-feature-toggle';
import { retrieveFieldCacheService, storeCacheService } from '@/storage';

export { isFeatureToggleOn };

export const SESSION_STORAGE_KEY = 'CommonFilterAddition';

const mirrorSessionStorage = (key: string, value: any) => {
  storeCacheService.setLocalStorageMirror(`sessionStorage:${key}`, value).catch(error => {
    console.warn('[store-cache] mirror sessionStorage failed', key, error);
  });
};

export type FilterAdditionStorageItem = {
  indexSetIdList: string[];
  sceneKey?: string; // 场景化检索键，格式 "bk_biz_id-scene_active"
  filterAddition: Record<string, any>[];
  t: number; // ISO 8601 format timestamp
};

export type OldFilterAdditionStorageItem = {
  indexId: string;
  value: Record<string, any>[];
};

export const isAiAssistantActive = (val: string[]) => {
  return isFeatureToggleOn('ai_assistant', val);
};

export const getStorageCommonFilterAddition = () => {
  const value = sessionStorage.getItem(SESSION_STORAGE_KEY);
  let jsonValue: FilterAdditionStorageItem[] | OldFilterAdditionStorageItem = [];
  try {
    jsonValue = JSON.parse(value || '[]');

    if (!Array.isArray(jsonValue) && 'indexId' in jsonValue && 'value' in jsonValue) {
      jsonValue = [{ indexSetIdList: [jsonValue.indexId], filterAddition: [jsonValue.value], t: Date.now() }];
    }
  } catch (e) {
    console.error('Failed to parse common filter addition:', e);
  }

  mirrorSessionStorage(SESSION_STORAGE_KEY, jsonValue);
  return jsonValue as FilterAdditionStorageItem[];
};

export const filterCommontAdditionByIndexSetId = (indexSetIdList: string[], list?: FilterAdditionStorageItem[]) => {
  const jsonValue: FilterAdditionStorageItem[] = list ?? getStorageCommonFilterAddition();
  const formatList = indexSetIdList.map(id => `${id}`);
  return jsonValue?.find(
    item =>
      item.indexSetIdList.length === formatList.length && item.indexSetIdList.every(id => formatList.includes(`${id}`)),
  );
};

export const filterCommontAdditionBySceneKey = (sceneKey: string, list?: FilterAdditionStorageItem[]) => {
  const jsonValue: FilterAdditionStorageItem[] = list ?? getStorageCommonFilterAddition();
  return jsonValue?.find(item => item.sceneKey === sceneKey);
};

/** 获取场景化检索的 sessionStorage 键，格式 "bk_biz_id-scene_active" */
export const getSceneFilterKey = (state: any): string => `${state.bkBizId}-${state.indexItem.scene_active}`;

/**
 * 获取常驻字段过滤设置
 * @param store
 * @returns
 */
export const getCommonFilterFieldsList = state => {
  if (Array.isArray(state.retrieve.catchFieldCustomConfig?.filterSetting)) {
    return state.retrieve.catchFieldCustomConfig?.filterSetting ?? [];
  }

  return [];
};

export const getCommonFilterAddition = state => {
  const isScene = isSceneRetrieve(state);
  const additionValue = isScene
    ? filterCommontAdditionBySceneKey(getSceneFilterKey(state))
    : filterCommontAdditionByIndexSetId(state.indexItem.ids);
  const storedValue = additionValue?.filterAddition ?? [];

  const storedCommonAddition =
    (state.retrieve.catchFieldCustomConfig.filterAddition ?? []).map(({ field, operator, value }) => ({
      field,
      operator,
      value,
    })) ?? [];

  // 合并策略优化
  return getCommonFilterFieldsList(state).map(item => {
    const storedItem = storedValue?.find(v => v.field === item.field_name);
    const storeItem = storedCommonAddition?.find(addition => addition.field === item.field_name);

    // 优先级：本地存储 > store > 默认值
    return (
      storedItem ||
      storeItem || {
        field: item.field_name || '',
        operator: item.field_operator[0]?.operator ?? '=',
        value: [],
        list: [],
      }
    );
  });
};

export const getCommonFilterAdditionWithValues = state =>
  (getCommonFilterAddition(state).filter(item => item.value?.length) ?? []).map(({ field, value, operator }) => ({
    field,
    value,
    operator,
  }));

export const setStorageCommonFilterAddition = (state, filterAddition: Record<string, any>[]) => {
  const allStorage = getStorageCommonFilterAddition();
  const isScene = isSceneRetrieve(state);
  const currentItem: FilterAdditionStorageItem | undefined = isScene
    ? filterCommontAdditionBySceneKey(getSceneFilterKey(state), allStorage)
    : filterCommontAdditionByIndexSetId(state.indexItem.ids, allStorage);

  if (currentItem !== undefined) {
    currentItem.filterAddition = filterAddition;
    currentItem.t = Date.now();
    sessionStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(allStorage));
    mirrorSessionStorage(SESSION_STORAGE_KEY, allStorage);
    return;
  }

  const newItem: FilterAdditionStorageItem = {
    indexSetIdList: isScene ? [] : state.indexItem.ids.map(id => `${id}`),
    filterAddition,
    t: Date.now(),
  };
  if (isScene) {
    newItem.sceneKey = getSceneFilterKey(state);
  }
  allStorage.push(newItem);

  /**
   * 如果本地存储超过5条，则移除最早的一条数据
   */
  if (allStorage.length > 5) {
    allStorage.sort((a, b) => a.t - b.t);
    allStorage.shift(); // 移除最早的一条数据
  }

  sessionStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(allStorage));
  mirrorSessionStorage(SESSION_STORAGE_KEY, allStorage);
};

export const clearStorageCommonFilterAddition = state => {
  const allStorage = getStorageCommonFilterAddition();
  const isScene = isSceneRetrieve(state);
  const currentItem: FilterAdditionStorageItem | undefined = isScene
    ? filterCommontAdditionBySceneKey(getSceneFilterKey(state), allStorage)
    : filterCommontAdditionByIndexSetId(state.indexItem.ids, allStorage);
  if (currentItem !== undefined) {
    const index = allStorage.indexOf(currentItem);
    if (index > -1) {
      allStorage.splice(index, 1);
      sessionStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(allStorage));
      mirrorSessionStorage(SESSION_STORAGE_KEY, allStorage);
    }
  }
};

/**
 * 格式化 addition 字段
 * 如果 showFieldAlias 为 true，则将 addition 字段替换为 query_alias
 * @param state
 * @returns addition
 */
export const formatAdditionalFields = (state: any, addition: Record<string, any>[]) => {
  const copyAddition = structuredClone(addition);
  if (state.storage[BK_LOG_STORAGE.SHOW_FIELD_ALIAS]) {
    const fieldScope = state.indexFieldInfo.field_scope || state.indexId || 'default';
    const fieldNameIndex = retrieveFieldCacheService.getFieldNameIndex(fieldScope);
    copyAddition.forEach(item => {
      const result = fieldNameIndex[item.field];
      if (result?.query_alias) {
        item.field = result.query_alias;
      }
    });
  }

  return copyAddition;
};

/**
 * 判断当前是否为场景化检索模式
 * 需同时满足：retrieve_type === 'scene' 且灰度开关对当前业务开启
 */
export const isSceneRetrieve = (state: any): boolean => {
  if (state.indexItem?.retrieve_type !== 'scene') return false;
  if (!isFeatureToggleOn('scene_search', [String(state.bkBizId), String(state.spaceUid)])) {
    return false;
  }
  return true;
};

/**
 * 判断场景过滤值的单个字段值是否为空
 * 空值定义：undefined / null / '' / []
 */
export const isEmptyFilterValue = (val: any): boolean => {
  if (val === undefined || val === null || val === '') return true;
  if (typeof val === 'object' && !Array.isArray(val) && 'op' in val && 'value' in val) {
    return isEmptyFilterValue(val.value);
  }
  if (Array.isArray(val) && val.length === 0) return true;
  return false;
};

/**
 * 判断场景过滤条件整体是否为空（所有字段值均为空时返回 true）
 */
export const isSceneFilterValuesEmpty = (filterValues: Record<string, any> | undefined | null): boolean => {
  if (!filterValues || typeof filterValues !== 'object') return true;
  return Object.values(filterValues).every(isEmptyFilterValue);
};

/**
 * 根据 scene_active 和 scene_filter_values 组装 table_id_conditions 和 scene_filter_values
 * - static / dynamic 类型的字段 → table_id_conditions
 * - free_input 类型的字段 → scene_filter_values
 *
 * @param state Vuex state
 * @param sceneConfigs 场景配置列表（来自 retrieve/sceneConfigList getter）
 */
export const buildTableIdConditions = (
  state: any,
  sceneConfigs: any[] = [],
): {
  table_id_conditions: Array<Array<{ field_name: string; value: any[]; op: string }>>;
  scene_filter_values: Array<{ field: string; operator: string; value: any[] }>;
} => {
  const { scene_active: sceneActive, scene_filter_values = {} } = state.indexItem ?? {};

  const emptyResult = {
    table_id_conditions: [],
    scene_filter_values: [],
  };

  if (!sceneActive) return emptyResult;

  // 根据 sceneActive 找到当前场景的配置，建立 fieldName → choicesType、fieldName → fieldType 和 fieldName → ops 的映射
  const activeConfig = sceneConfigs.find((s: any) => s.type === sceneActive);
  const fieldChoicesTypeMap: Record<string, string> = {};
  const fieldFieldTypeMap: Record<string, string> = {};
  const fieldOpsMap: Record<string, string[]> = {};
  if (activeConfig) {
    (activeConfig.fields ?? []).forEach((f: any) => {
      fieldChoicesTypeMap[f.key] = f.choicesType ?? 'static';
      fieldFieldTypeMap[f.key] = f.fieldType;
      fieldOpsMap[f.key] = f.ops ?? [];
    });
  }

  const conditions: Array<{ field_name: string; value: any[]; op: string }> = [];
  const filterValues: Array<{ field: string; operator: string; value: any[] }> = [];

  // 第一个固定条件：场景
  conditions.push({
    field_name: 'scene',
    value: [sceneActive],
    op: 'eq',
  });

  // 由 scene_filter_values 生成后续条件，根据 choicesType 分类
  for (const [fieldName, fieldValue] of Object.entries(scene_filter_values)) {
    const fv = fieldValue as any;
    const op = fv?.op ?? getDefaultOp(fieldOpsMap[fieldName]);
    const rawValue = fv?.value ?? fieldValue;
    if (rawValue === undefined || rawValue === null || rawValue === '') continue;

    const valueArray = Array.isArray(rawValue) ? rawValue : [rawValue];
    if (valueArray.length === 0) continue;

    const choicesType = fieldChoicesTypeMap[fieldName] ?? 'static';
    const fieldType = fieldFieldTypeMap[fieldName] ?? '';

    if (choicesType === 'free_input') {
      // free_input 类型放入 scene_filter_values
      filterValues.push({
        field: fieldName,
        operator: getOperatorRequestParam(op, choicesType, fieldType),
        value: valueArray,
      });
    } else {
      // static / dynamic 类型放入 table_id_conditions
      conditions.push({
        field_name: fieldName,
        value: valueArray,
        op,
      });
    }
  }

  return {
    table_id_conditions: [conditions],
    scene_filter_values: filterValues,
  };
};

/**
 * 从历史记录中的 table_id_conditions 和 scene_filter_values 反向解析出 scene_active 和 scene_filter_values
 * - table_id_conditions 中 field_name 为 "scene" 的条目 → 提取为 scene_active
 * - table_id_conditions 中除 scene 外的字段 → 转换为 { fieldName: { op, value } } 格式，写入 scene_filter_values
 * - 历史记录中的 scene_filter_values（{field, operator, value} 格式）→ 转换为 { fieldName: { op, value } } 格式，
 * 合并到 scene_filter_values
 *
 * @param tableIdConditions 历史记录中的 table_id_conditions
 * @param sceneFilterValues 历史记录中的 scene_filter_values
 */
export const parseTableIdConditions = (
  tableIdConditions?: Array<Array<{ field_name: string; value: any[]; op: string }>>,
  sceneFilterValues?: Array<{ field: string; operator: string; value: any[] }>,
): {
  scene_active: string;
  scene_filter_values: Record<string, any>;
} => {
  let sceneActive = '';
  const filterValues: Record<string, any> = {};

  // 从 table_id_conditions 解析
  if (Array.isArray(tableIdConditions) && tableIdConditions.length > 0) {
    const innerConditions = tableIdConditions[0];
    if (Array.isArray(innerConditions)) {
      for (const condition of innerConditions) {
        const { field_name: fieldName, value, op = 'eq' } = condition;
        if (fieldName === 'scene') {
          // scene 字段 → scene_active
          sceneActive = Array.isArray(value) ? (value[0] ?? '') : value;
        } else {
          // 非 scene 字段 → scene_filter_values
          filterValues[fieldName] = {
            op,
            value,
          };
        }
      }
    }
  }

  // 从历史记录的 scene_filter_values 合并
  if (Array.isArray(sceneFilterValues)) {
    for (const item of sceneFilterValues) {
      const { field, value, operator = '=' } = item;
      // 从显示符号反查 op key
      const opKey = REVERSE_OPERATOR_MAP[operator] ?? 'eq';
      filterValues[field] = {
        op: opKey,
        value,
      };
    }
  }

  return {
    scene_active: sceneActive,
    scene_filter_values: filterValues,
  };
};
