/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

import { SceneType } from '@/store/scene-filter-types';
import type { SceneConfig, SceneConfigItem } from '@/store/scene-filter-types';

export const OPERATOR_DISPLAY_MAP: Record<string, string> = {
  eq: '=',
  ne: '!=',
  req: '正则匹配',
  nreq: '正则排除',
};

export const FREE_INPUT_STRING_OPERATOR_DISPLAY_MAP: Record<string, string> = {
  eq: '包含',
  ne: '不包含',
  req: '正则匹配',
  nreq: '正则排除',
};

export const FREE_INPUT_STRING_OPERATOR_REQUEST_MAP: Record<string, string> = {
  eq: 'contains match phrase',
  ne: 'not contains match phrase',
  req: '=~',
  nreq: '!~',
};

export const REVERSE_OPERATOR_MAP: Record<string, string> = Object.fromEntries(
  [
    ...Object.entries(OPERATOR_DISPLAY_MAP),
    ...Object.entries(FREE_INPUT_STRING_OPERATOR_REQUEST_MAP),
  ].map(([key, value]) => [value, key]),
);

const sceneMetaMap: Record<string, { label: string; icon: string; skipI18n?: boolean }> = {
  [SceneType.Container]: { label: '容器', icon: 'bklog-container-2' },
  [SceneType.Host]: { label: '主机', icon: 'bklog-host' },
  [SceneType.PaaS]: { label: 'Paas', icon: 'bklog-paas', skipI18n: true },
  [SceneType.Service]: { label: '服务', icon: 'bklog-service' },
};

const DEFAULT_SCENE_ICON = 'bklog-container-2';

export const transformSceneConfigItem = (item: SceneConfigItem, disabled = false): SceneConfig => {
  const meta = sceneMetaMap[item.id];

  const fields = disabled
    ? []
    : (item.dimensions ?? []).map(dim => ({
      name: dim.name,
      key: dim.key,
      fieldType: dim.type,
      choicesType: dim.choices_type,
      choices: dim.choices,
      required: dim.required,
      ops: dim.ops,
      multiple: dim.multiple ?? true,
    }));

  return {
    type: item.id,
    label: meta?.label ?? item.name,
    skipI18n: meta?.skipI18n,
    icon: meta?.icon ?? DEFAULT_SCENE_ICON,
    fields,
    disabled,
  };
};

export const transformSceneConfigs = (items: SceneConfigItem[]): SceneConfig[] => {
  const apiItems = items ?? [];
  const apiIdSet = new Set(apiItems.map(item => item.id));

  return Object.keys(sceneMetaMap).map(id => {
    if (apiIdSet.has(id)) {
      const apiItem = apiItems.find(item => item.id === id)!;
      return transformSceneConfigItem(apiItem, false);
    }
    return transformSceneConfigItem({ id, name: sceneMetaMap[id].label, dimensions: [] }, true);
  });
};

export const getSceneConfig = (sceneConfigs: SceneConfig[], sceneId: string): SceneConfig | undefined => {
  return sceneConfigs.find(scene => scene.type === sceneId);
};

export const getSceneFieldKeys = (sceneConfigs: SceneConfig[], sceneId: string): string[] => {
  const config = sceneConfigs.find(scene => scene.type === sceneId);
  return config ? config.fields.map(field => field.key) : [];
};

export const getAllSceneFieldKeys = (sceneConfigs: SceneConfig[]): string[] => {
  const keys = new Set<string>();
  (sceneConfigs ?? []).forEach(scene => scene.fields.forEach(field => keys.add(field.key)));
  return Array.from(keys);
};

export const getOperatorDisplay = (op: string, choicesType?: string, fieldType?: string): string => {
  if (choicesType === 'free_input' && fieldType === 'string') {
    const display = FREE_INPUT_STRING_OPERATOR_DISPLAY_MAP[op] ?? op;
    return window.$t(display) as string;
  }
  const display = OPERATOR_DISPLAY_MAP[op] ?? op;
  return window.$t(display) as string;
};

export const getOperatorRequestParam = (op: string, choicesType?: string, fieldType?: string): string => {
  if (choicesType === 'free_input' && fieldType === 'string') {
    return FREE_INPUT_STRING_OPERATOR_REQUEST_MAP[op] ?? op;
  }
  return op;
};

export const getDefaultOp = (ops: string[] | undefined): string => {
  return ops?.[0] ?? 'eq';
};

export const getAllSceneFieldOpKeys = (sceneConfigs: SceneConfig[]): string[] => {
  const keys = new Set<string>();
  (sceneConfigs ?? []).forEach(scene => scene.fields.forEach((field) => {
    keys.add(field.key);
    keys.add(`${field.key}[op]`);
  }));
  return Array.from(keys);
};
