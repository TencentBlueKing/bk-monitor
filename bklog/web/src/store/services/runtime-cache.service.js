/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 */
import { storeCacheService } from '@/storage';

const DEFAULT_SCOPE = 'default';
const retrieveDropdownDataMap = new Map();
const fieldAggsItemsMap = new Map();
const operatorDictionaryMap = new Map();
const fieldNameIndexMap = new Map();
const queryAliasIndexMap = new Map();

const getScope = scope => String(scope || DEFAULT_SCOPE);

const setCache = (map, scope, value, cacheName) => {
  const cacheScope = getScope(scope);
  const nextValue = value && typeof value === 'object' ? value : {};
  map.set(cacheScope, nextValue);
  storeCacheService.setApiCache(cacheName, cacheScope, nextValue).catch((error) => {
    console.warn('[store-runtime-cache] persist cache failed', cacheName, error);
  });
  return nextValue;
};

const getCacheSync = (map, scope) => map.get(getScope(scope)) ?? {};

export const storeRuntimeCacheService = {
  setRetrieveDropdownData(scope, data) {
    return setCache(retrieveDropdownDataMap, scope, data, 'store-runtime/retrieve-dropdown-data');
  },
  getRetrieveDropdownData(scope) {
    return getCacheSync(retrieveDropdownDataMap, scope);
  },
  clearRetrieveDropdownData(scope) {
    return this.setRetrieveDropdownData(scope, {});
  },

  setFieldAggsItems(scope, data) {
    return setCache(fieldAggsItemsMap, scope, data, 'store-runtime/field-aggs-items');
  },
  patchFieldAggsItems(scope, data) {
    const cacheScope = getScope(scope);
    const current = fieldAggsItemsMap.get(cacheScope) ?? {};
    const nextValue = {
      ...current,
      ...(data ?? {}),
    };
    return this.setFieldAggsItems(cacheScope, nextValue);
  },
  getFieldAggsItems(scope) {
    return getCacheSync(fieldAggsItemsMap, scope);
  },
  getFieldAggsItem(scope, fieldName) {
    return this.getFieldAggsItems(scope)?.[fieldName] ?? [];
  },
  clearFieldAggsItems(scope) {
    return this.setFieldAggsItems(scope, {});
  },

  setOperatorDictionary(scope, data) {
    return setCache(operatorDictionaryMap, scope, data, 'store-runtime/operator-dictionary');
  },
  getOperatorDictionary(scope) {
    return getCacheSync(operatorDictionaryMap, scope);
  },

  setFieldIndexes(scope, { fieldNameIndex = {}, queryAliasIndex = {} } = {}) {
    const cacheScope = getScope(scope);
    fieldNameIndexMap.set(cacheScope, fieldNameIndex);
    queryAliasIndexMap.set(cacheScope, queryAliasIndex);
    storeCacheService.setApiCache('store-runtime/field-indexes', cacheScope, {
      fieldNameIndex,
      queryAliasIndex,
    }).catch((error) => {
      console.warn('[store-runtime-cache] persist field indexes failed', error);
    });
  },
  getFieldNameIndex(scope) {
    return getCacheSync(fieldNameIndexMap, scope);
  },
  getQueryAliasIndex(scope) {
    return getCacheSync(queryAliasIndexMap, scope);
  },

  clearScope(scope) {
    const cacheScope = getScope(scope);
    retrieveDropdownDataMap.delete(cacheScope);
    fieldAggsItemsMap.delete(cacheScope);
    operatorDictionaryMap.delete(cacheScope);
    fieldNameIndexMap.delete(cacheScope);
    queryAliasIndexMap.delete(cacheScope);
  },
};

export default storeRuntimeCacheService;
