/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company. All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

/** 特性开关：动态 JSON 解析层级 */
export const EXT_JSON_EXPAND_DEPTH_TOGGLE = 'ext_json_expand_depth';

/** 下拉「无限」选项 id，提交时映射为 null */
export const UNLIMITED_EXPAND_DEPTH = 'unlimited' as const;

/** 首次开启动态新增时的默认层级 */
export const DEFAULT_EXPAND_DEPTH = 2;

export type ExpandDepthSelect = 1 | 2 | 3 | typeof UNLIMITED_EXPAND_DEPTH;

export type ExpandDepthSubmit = 1 | 2 | 3 | null;

export interface ExtJsonConfigPublic {
  expand_depth: ExpandDepthSubmit;
}

/** 将后台 expand_depth 转为下拉值；无配置时回填为无限 */
export const toExpandDepthSelect = (expandDepth?: ExpandDepthSubmit | undefined): ExpandDepthSelect => {
  if (expandDepth === 1 || expandDepth === 2 || expandDepth === 3) {
    return expandDepth;
  }
  return UNLIMITED_EXPAND_DEPTH;
};

/** 下拉值转为提交用 expand_depth */
export const toSubmitExpandDepth = (select: ExpandDepthSelect): ExpandDepthSubmit => {
  return select === UNLIMITED_EXPAND_DEPTH ? null : select;
};

/** 仅提取公开配置，剥离 overflow_strategy 等后台字段 */
export const pickPublicExtJsonConfig = (config?: { expand_depth?: ExpandDepthSubmit } | null): ExtJsonConfigPublic | undefined => {
  if (!config || typeof config !== 'object') {
    return undefined;
  }
  if (!('expand_depth' in config)) {
    return undefined;
  }
  const depth = config.expand_depth;
  if (depth !== null && depth !== 1 && depth !== 2 && depth !== 3) {
    return { expand_depth: null };
  }
  return { expand_depth: depth as ExpandDepthSubmit };
};

/**
 * 是否应在请求中携带 ext_json_config。
 * 存量无配置且仍为无限时不提交，避免脏写历史配置。
 */
export const shouldSubmitExtJsonConfig = (params: {
  retainExtraJson: boolean;
  featureEnabled: boolean;
  currentSelect: ExpandDepthSelect;
  originHadConfig: boolean;
  originRetainExtraJson: boolean;
}): boolean => {
  const { retainExtraJson, featureEnabled, currentSelect, originHadConfig, originRetainExtraJson } = params;
  if (!retainExtraJson || !featureEnabled) {
    return false;
  }
  // 存量已开启动态新增、无 ext_json_config，且仍选无限：不主动改写
  if (!originHadConfig && originRetainExtraJson && currentSelect === UNLIMITED_EXPAND_DEPTH) {
    return false;
  }
  return true;
};

export const getExpandDepthLabel = (select: ExpandDepthSelect, t: (key: string) => string): string => {
  if (select === UNLIMITED_EXPAND_DEPTH) {
    return t('无限');
  }
  return t(`${select} 层`);
};

export const isExpandDepthChanged = (
  currentSelect: ExpandDepthSelect,
  originSelect: ExpandDepthSelect | null,
  originHadConfig: boolean,
  originRetainExtraJson: boolean,
): boolean => {
  if (!originRetainExtraJson) {
    // 原先关闭，本次开启并带层级配置，视为变更（已生效采集项需确认）
    return true;
  }
  if (!originHadConfig) {
    return currentSelect !== UNLIMITED_EXPAND_DEPTH;
  }
  return currentSelect !== originSelect;
};
