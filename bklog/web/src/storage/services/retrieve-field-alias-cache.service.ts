/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 */
import {
  retrieveFieldAliasRepository,
  type RetrieveFieldAliasConfigEntity,
} from '../repositories/retrieve-field-alias.repository';
import { createRetrieveFieldMeta } from '../utils/retrieve-field-meta';

type AliasConfigCache = {
  scope: string;
  rawFieldList: any[];
  aliasFieldList: any[];
  fieldNameIndex: Record<string, any>;
  queryAliasIndex: Record<string, any>;
  repeatAliasGroups: RetrieveFieldAliasConfigEntity['repeatAliasGroups'];
  updatedAt: number;
};

const DEFAULT_SCOPE = 'default';
const getScope = (scope?: string | number) => String(scope || DEFAULT_SCOPE);

const buildRepeatAliasGroups = (aliasFieldList: any[] = []) => {
  const groups: RetrieveFieldAliasConfigEntity['repeatAliasGroups'] = {};
  aliasFieldList
    .filter(field => field?.is_virtual_alias_field)
    .forEach(field => {
      const alias = field.query_alias || field.field_name;
      if (!alias) return;
      groups[alias] = {
        query_alias: alias,
        source_field_names: field.source_field_names ?? [],
        virtual_field_name: field.field_name,
      };
    });
  return groups;
};

const toAliasCache = (scope: string, entity: RetrieveFieldAliasConfigEntity): AliasConfigCache => ({
  scope,
  rawFieldList: entity.rawFieldList ?? [],
  aliasFieldList: entity.aliasFieldList ?? [],
  fieldNameIndex: entity.fieldNameIndex ?? {},
  queryAliasIndex: entity.queryAliasIndex ?? {},
  repeatAliasGroups: entity.repeatAliasGroups ?? {},
  updatedAt: entity.updatedAt,
});

/**
 * 独立别名配置缓存：只服务展示 / 反查，不接管字段主缓存链路。
 */
class RetrieveFieldAliasCacheService {
  private memory = new Map<string, AliasConfigCache>();

  setAliasConfig(scope: string | number, payload: Record<string, any>) {
    const cacheScope = getScope(scope);
    const meta = createRetrieveFieldMeta(payload);
    const cacheValue: AliasConfigCache = {
      scope: cacheScope,
      rawFieldList: meta.rawFieldList,
      aliasFieldList: meta.aliasFieldList,
      fieldNameIndex: meta.fieldNameIndex,
      queryAliasIndex: meta.queryAliasIndex,
      repeatAliasGroups: buildRepeatAliasGroups(meta.aliasFieldList),
      updatedAt: Date.now(),
    };
    this.memory.set(cacheScope, cacheValue);
    retrieveFieldAliasRepository
      .setAliasConfig(cacheScope, {
        rawFieldList: cacheValue.rawFieldList,
        aliasFieldList: cacheValue.aliasFieldList,
        fieldNameIndex: cacheValue.fieldNameIndex,
        queryAliasIndex: cacheValue.queryAliasIndex,
        repeatAliasGroups: cacheValue.repeatAliasGroups,
      })
      .catch(error => {
        console.warn('[retrieve-field-alias-cache] persist alias config failed', error);
      });
    return cacheValue;
  }

  getAliasConfigSync(scope: string | number) {
    return this.memory.get(getScope(scope));
  }

  async getAliasConfig(scope: string | number) {
    const cacheScope = getScope(scope);
    const memory = this.memory.get(cacheScope);
    if (memory) return memory;

    const entity = await retrieveFieldAliasRepository.getAliasConfig(cacheScope);
    if (!entity) return undefined;
    const cacheValue = toAliasCache(cacheScope, entity);
    this.memory.set(cacheScope, cacheValue);
    return cacheValue;
  }

  getRawFieldList(scope: string | number) {
    return this.getAliasConfigSync(scope)?.rawFieldList ?? [];
  }

  getAliasFieldList(scope: string | number) {
    return this.getAliasConfigSync(scope)?.aliasFieldList ?? [];
  }

  getFieldNameIndex(scope: string | number) {
    return this.getAliasConfigSync(scope)?.fieldNameIndex ?? {};
  }

  getQueryAliasIndex(scope: string | number) {
    return this.getAliasConfigSync(scope)?.queryAliasIndex ?? {};
  }

  resolveDisplayName(scope: string | number, fieldName: string, showAlias = true) {
    if (!showAlias) return fieldName;
    const field = this.getFieldNameIndex(scope)[fieldName];
    return field?.query_alias || fieldName;
  }

  changeDisplayNameToFieldName(scope: string | number, displayName: string) {
    const field = this.getQueryAliasIndex(scope)[displayName];
    if (field?.is_virtual_alias_field) {
      return displayName;
    }
    return field?.field_name || displayName;
  }

  clearScope(scope: string | number) {
    const cacheScope = getScope(scope);
    this.memory.delete(cacheScope);
    retrieveFieldAliasRepository.clearAliasConfig(cacheScope).catch(() => {});
  }
}

export const retrieveFieldAliasCacheService = new RetrieveFieldAliasCacheService();
