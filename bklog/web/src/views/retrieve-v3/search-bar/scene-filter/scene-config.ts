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

import { SceneType } from './types';
import type { SceneConfig, SceneConfigItem } from './types';

/** 操作符 key → 页面显示符号映射（非 free_input 类型） */
export const OPERATOR_DISPLAY_MAP: Record<string, string> = {
  eq: '=',
  ne: '!=',
  req: '正则匹配',
  nreq: '正则排除',
};

/** 操作符 key → 页面显示符号映射（free_input 且 type=string） */
export const FREE_INPUT_STRING_OPERATOR_DISPLAY_MAP: Record<string, string> = {
  eq: '包含',
  ne: '不包含',
  req: '正则匹配',
  nreq: '正则排除',
};

/** 操作符 key → free_input 类型请求参数映射（仅 free_input + string 时使用） */
export const FREE_INPUT_STRING_OPERATOR_REQUEST_MAP: Record<string, string> = {
  eq: 'contains match phrase',
  ne: 'not contains match phrase',
  req: '=~',
  nreq: '!~',
};

/** 操作符显示符号/请求参数 → key 的反向映射 */
export const REVERSE_OPERATOR_MAP: Record<string, string> = Object.fromEntries(
  [
    ...Object.entries(OPERATOR_DISPLAY_MAP),
    ...Object.entries(FREE_INPUT_STRING_OPERATOR_REQUEST_MAP),
  ].map(([k, v]) => [v, k]),
);

/**
 * 本地场景映射表：根据接口返回的 id 映射显示名称和图标。
 * key 为 SceneType 枚举值（即接口 id），value 为本地展示信息。
 */
const sceneMetaMap: Record<string, { label: string; icon: string; skipI18n?: boolean }> = {
  [SceneType.Container]: { label: '容器', icon: 'bklog-container-2' },
  [SceneType.Host]: { label: '主机', icon: 'bklog-host' },
  [SceneType.PaaS]: { label: 'Paas', icon: 'bklog-paas', skipI18n: true },
  [SceneType.Service]: { label: '服务', icon: 'bklog-service' },
};

/** 默认的场景图标（映射表中未匹配时使用） */
const DEFAULT_SCENE_ICON = 'bklog-container-2';

/**
 * 将接口返回的 SceneConfigItem 转换为内部使用的 SceneConfig。
 * - 场景名称和图标从 sceneMetaMap 映射获取，未匹配时回退到接口的 name 和默认图标。
 * - disabled 为 true 时表示接口未返回该场景配置（仅本地映射存在），置灰展示。
 */
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

/**
 * 将接口返回的场景配置列表转换为内部使用的配置列表。
 * - 接口包含的场景：正常转换，disabled = false
 * - 接口不包含但本地映射表存在的场景：生成占位配置，disabled = true（置灰展示）
 */
export const transformSceneConfigs = (items: SceneConfigItem[]): SceneConfig[] => {
  const apiItems = items ?? [];
  const apiIdSet = new Set(apiItems.map(item => item.id));

  return Object.keys(sceneMetaMap).map(id => {
    if (apiIdSet.has(id)) {
      // 接口有数据，正常转换
      const apiItem = apiItems.find(item => item.id === id)!;
      return transformSceneConfigItem(apiItem, false);
    }
    // 接口无数据，但本地映射存在，生成占位配置并置灰
    return transformSceneConfigItem({ id, name: sceneMetaMap[id].label, dimensions: [] }, true);
  });
};

/**
 * 根据场景 ID 获取配置（从已转换的列表中查找）
 */
export const getSceneConfig = (sceneConfigs: SceneConfig[], sceneId: string): SceneConfig | undefined => {
  return sceneConfigs.find(scene => scene.type === sceneId);
};

/**
 * 获取指定场景的所有字段 key（从已转换的列表中查找）
 */
export const getSceneFieldKeys = (sceneConfigs: SceneConfig[], sceneId: string): string[] => {
  const config = sceneConfigs.find(s => s.type === sceneId);
  return config ? config.fields.map(f => f.key) : [];
};

/**
 * 获取所有场景的全部字段 key（去重）
 */
export const getAllSceneFieldKeys = (sceneConfigs: SceneConfig[]): string[] => {
  const keys = new Set<string>();
  (sceneConfigs ?? []).forEach(s => s.fields.forEach(f => keys.add(f.key)));
  return Array.from(keys);
};

/** 获取操作符的显示符号，未知操作符原样返回 */
export const getOperatorDisplay = (op: string, choicesType?: string, fieldType?: string): string => {
  if (choicesType === 'free_input' && fieldType === 'string') {
    const display = FREE_INPUT_STRING_OPERATOR_DISPLAY_MAP[op] ?? op;
    return window.$t(display) as string;
  }
  const display = OPERATOR_DISPLAY_MAP[op] ?? op;
  return window.$t(display) as string;
};

/** 获取操作符的请求参数值（用于 free_input + string 类型字段的 scene_filter_values 传参） */
export const getOperatorRequestParam = (op: string, choicesType?: string, fieldType?: string): string => {
  if (choicesType === 'free_input' && fieldType === 'string') {
    return FREE_INPUT_STRING_OPERATOR_REQUEST_MAP[op] ?? op;
  }
  return op;
};

/** 获取字段的默认操作符（取 ops 第一个） */
export const getDefaultOp = (ops: string[] | undefined): string => {
  return ops?.[0] ?? 'eq';
};

/**
 * 获取所有场景的全部字段 key 及其 [op] 后缀（用于 URL 清理）
 */
export const getAllSceneFieldOpKeys = (sceneConfigs: SceneConfig[]): string[] => {
  const keys = new Set<string>();
  (sceneConfigs ?? []).forEach(s => s.fields.forEach((f) => {
    keys.add(f.key);
    keys.add(`${f.key}[op]`);
  }));
  return Array.from(keys);
};
