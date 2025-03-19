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
