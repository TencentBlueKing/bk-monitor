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
import type { FilterFieldConfig, SceneConfig, SceneConfigItem } from './types';

/**
 * 本地场景映射表：根据接口返回的 id 映射显示名称和图标。
 * key 为 SceneType 枚举值（即接口 id），value 为本地展示信息。
 */
const sceneMetaMap: Record<string, { label: string; icon: string; skipI18n?: boolean }> = {
  [SceneType.Container]: { label: '容器', icon: 'bklog-container-2' },
  [SceneType.Host]: { label: '主机', icon: 'bklog-host' },
  [SceneType.PaaS]: { label: 'Paas', icon: 'bklog-paas', skipI18n: true },
  [SceneType.Service]: { label: '服务', icon: 'bklog-service' },
  [SceneType.Client]: { label: '客户端', icon: 'bklog-kehuduan' },
  [SceneType.TRPC]: { label: 'TRPC', icon: 'bklog-trpc', skipI18n: true },
};

/** 默认的场景图标（映射表中未匹配时使用） */
const DEFAULT_SCENE_ICON = 'bklog-container-2';

/**
 * 将接口返回的 SceneConfigItem 转换为内部使用的 SceneConfig。
 * - 场景名称和图标从 sceneMetaMap 映射获取，未匹配时回退到接口的 name 和默认图标。
 * - 筛选字段的 name/key 直接使用接口返回的 dimension.name/dimension.key。
 */
export const transformSceneConfigItem = (item: SceneConfigItem): SceneConfig => {
  const meta = sceneMetaMap[item.id];

  const fields: FilterFieldConfig[] = (item.dimensions ?? []).map(dim => ({
    name: dim.name,
    key: dim.key,
    fieldType: dim.type,
    inputType: 'input',
  }));

  return {
    type: item.id,
    label: meta?.label ?? item.name,
    skipI18n: meta?.skipI18n,
    icon: meta?.icon ?? DEFAULT_SCENE_ICON,
    fields,
  };
};

/**
 * 将接口返回的场景配置列表转换为内部使用的配置列表
 */
export const transformSceneConfigs = (items: SceneConfigItem[]): SceneConfig[] => {
  return (items ?? []).map(transformSceneConfigItem);
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
