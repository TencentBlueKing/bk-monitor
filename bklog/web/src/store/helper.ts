export const isFeatureToggleOn = (key: string, value: string | string[]) => {
  const featureToggle = window.FEATURE_TOGGLE?.[key];
  if (featureToggle === 'debug') {
    const whiteList = (window.FEATURE_TOGGLE_WHITE_LIST?.[key] ?? []).map(id => `${id}`);

    if (Array.isArray(value)) {
      return value.some(v => whiteList.includes(v));
    }

    return whiteList.includes(value);
  }

  return featureToggle === 'on';
};

export const isAiAssistantActive = (val: string[]) => {
  return isFeatureToggleOn('ai_assistant', val);
};

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
  const additionValue = JSON.parse(localStorage.getItem('commonFilterAddition'));

  const isSameIndex = additionValue?.indexId === state.indexId;
  const storedValue = isSameIndex ? additionValue?.value ?? [] : [];

  const storedCommonAddition =
    (state.retrieve.catchFieldCustomConfig.filterAddition ?? []).map(({ field, operator, value }) => ({
      field,
      operator,
      value,
    })) ?? [];

  // 合并策略优化
  return getCommonFilterFieldsList(state).map(item => {
    const storedItem = storedValue.find(v => v.field === item.field_name);
    const storeItem = storedCommonAddition.find(addition => addition.field === item.field_name);

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
  getCommonFilterAddition(state).filter(item => item.value?.length) ?? [];
