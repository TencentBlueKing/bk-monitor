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

export type SceneId = 'none' | 'k8s' | 'host';

export interface SceneOption {
  id: SceneId;
  title: string;
}

export interface SceneFilterField {
  key: string;
  title: string;
}

export interface SceneSnapshot {
  scene: SceneId;
  filters: Record<string, string>;
}

export const SCENE_OPTIONS: SceneOption[] = [
  { id: 'none', title: '常规检索' },
  { id: 'k8s', title: '容器' },
  { id: 'host', title: '主机' },
];

export const SCENE_FILTERS: Record<SceneId, SceneFilterField[]> = {
  none: [],
  k8s: [
    { key: 'bcs_cluster', title: '集群' },
    { key: 'namespace', title: '命名空间' },
  ],
  host: [{ key: 'serverIp', title: 'IP' }],
};

export class SceneController {
  private snapshot: SceneSnapshot = { scene: 'none', filters: {} };

  getState(): SceneSnapshot {
    return { scene: this.snapshot.scene, filters: { ...this.snapshot.filters } };
  }

  getFields(): SceneFilterField[] {
    return SCENE_FILTERS[this.snapshot.scene].map(item => ({ ...item }));
  }

  isRegular(): boolean {
    return this.snapshot.scene === 'none';
  }

  setScene(scene: SceneId): SceneSnapshot {
    const next = SCENE_OPTIONS.some(item => item.id === scene) ? scene : 'none';
    this.snapshot = { scene: next, filters: {} };
    return this.getState();
  }

  setFilter(key: string, value: string): SceneSnapshot {
    if (!SCENE_FILTERS[this.snapshot.scene].some(item => item.key === key)) {
      return this.getState();
    }
    this.snapshot = {
      ...this.snapshot,
      filters: { ...this.snapshot.filters, [key]: String(value ?? '').trim() },
    };
    return this.getState();
  }
}
