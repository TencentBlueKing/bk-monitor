/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

export type AiLevelSelectValue = AlertLevel | AlertLevel[] | IAiAlertLevelValue;
export type AlertLevel = 1 | 2 | 3;

export type AlertLevelMode = 'auto' | 'manual';

export interface IAiAlertLevelValue {
  alertLevels: AlertLevel[];
  level: AlertLevel;
  mode: AlertLevelMode;
}

interface IAlertLevelRule {
  level?: number;
  type?: string;
  config?: {
    alert_level_mode?: unknown;
    alert_levels?: unknown;
  };
}

export const DEFAULT_AUTO_ALERT_LEVELS: AlertLevel[] = [1, 2, 3];
export const AUTO_ALERT_TECHNICAL_LEVEL: AlertLevel = 2;

export function createAiAlertLevelValue(rule?: IAlertLevelRule): IAiAlertLevelValue {
  if (isAutoAlertLevelRule(rule)) {
    return {
      mode: 'auto',
      level: AUTO_ALERT_TECHNICAL_LEVEL,
      alertLevels: normalizeAlertLevels(rule?.config?.alert_levels),
    };
  }
  return {
    mode: 'manual',
    level: isAlertLevel(rule?.level) ? rule.level : 1,
    alertLevels: [],
  };
}

export function getConfiguredAlertLevels(rule?: IAlertLevelRule): AlertLevel[] {
  if (isAutoAlertLevelRule(rule)) return normalizeAlertLevels(rule?.config?.alert_levels);
  return isAlertLevel(rule?.level) ? [rule.level] : [];
}

export function hydrateAiLevelSelectValue(value: unknown): IAiAlertLevelValue {
  if (isAiAlertLevelValue(value)) {
    return {
      mode: value.mode,
      level: isAlertLevel(value.level) ? value.level : value.mode === 'auto' ? AUTO_ALERT_TECHNICAL_LEVEL : 1,
      alertLevels: normalizeAlertLevels(value.alertLevels),
    };
  }
  if (Array.isArray(value)) {
    return {
      mode: 'auto',
      level: AUTO_ALERT_TECHNICAL_LEVEL,
      alertLevels: normalizeAlertLevels(value),
    };
  }
  return {
    mode: 'manual',
    level: isAlertLevel(value) ? value : 1,
    alertLevels: [],
  };
}

export function isAiAlertLevelValue(value: unknown): value is IAiAlertLevelValue {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false;
  const candidate = value as Partial<IAiAlertLevelValue>;
  return (candidate.mode === 'auto' || candidate.mode === 'manual') && Array.isArray(candidate.alertLevels);
}

export function isAutoAlertLevelRule(rule?: IAlertLevelRule): boolean {
  return rule?.config?.alert_level_mode === 'auto';
}

export function normalizeAlertLevels(value: unknown): AlertLevel[] {
  if (!Array.isArray(value)) return [];
  return [...new Set(value.filter(isAlertLevel))].sort((left, right) => left - right);
}

export function serializeAiAlertLevelValue(value: IAiAlertLevelValue) {
  if (value.mode === 'auto') {
    return {
      level: AUTO_ALERT_TECHNICAL_LEVEL,
      config: {
        alert_level_mode: 'auto' as const,
        alert_levels: normalizeAlertLevels(value.alertLevels),
      },
    };
  }
  return {
    level: value.level,
    config: { alert_level_mode: 'manual' as const },
  };
}

export function serializeAiLevelSelectValue(value: IAiAlertLevelValue, structured: boolean): AiLevelSelectValue {
  if (structured) return { ...value, alertLevels: [...value.alertLevels] };
  return value.mode === 'auto' ? normalizeAlertLevels(value.alertLevels) : value.level;
}

export function switchAiAlertLevelMode(_value: IAiAlertLevelValue, mode: AlertLevelMode): IAiAlertLevelValue {
  if (mode === 'auto') {
    return {
      mode,
      level: AUTO_ALERT_TECHNICAL_LEVEL,
      alertLevels: [...DEFAULT_AUTO_ALERT_LEVELS],
    };
  }
  return { mode, level: 1, alertLevels: [] };
}

function isAlertLevel(value: unknown): value is AlertLevel {
  return Number.isInteger(value) && [1, 2, 3].includes(value as number);
}
