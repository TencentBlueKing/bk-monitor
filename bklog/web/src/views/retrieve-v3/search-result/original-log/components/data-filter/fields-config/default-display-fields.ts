import type { Store } from 'vuex';

interface IFieldItem {
  field_name: string;
  field_type?: string;
}

const getStoreFieldList = (store: Store<any>): IFieldItem[] => {
  const filteredFieldList = store.getters.filteredFieldList;
  if (Array.isArray(filteredFieldList) && filteredFieldList.length) {
    return filteredFieldList;
  }

  const fields = store.state.indexFieldInfo?.fields;
  return Array.isArray(fields) ? fields : [];
};

/**
 * 获取上下文 / 实时日志默认展示字段。
 * 优先级：用户配置字段 -> log（必须存在于字段列表）-> 第一个 text 类型字段 -> 字段列表前 N 个字段。
 */
export const getDefaultDisplayFields = (
  store: Store<any>,
  contextDisplayFields?: string[],
  fallbackCount = 1,
): string[] => {
  const allFields = getStoreFieldList(store);
  const totalFieldNames = allFields.map(item => item.field_name);
  const configuredFields = contextDisplayFields?.filter(field => totalFieldNames.includes(field));
  if (configuredFields?.length) {
    return configuredFields;
  }

  const logField = allFields.find(field => field.field_name === 'log')?.field_name;
  if (logField) {
    return [logField];
  }

  const textField = allFields.find(field => field.field_type === 'text')?.field_name;
  if (textField) {
    return [textField];
  }

  return totalFieldNames.slice(0, Math.max(1, fallbackCount));
};
