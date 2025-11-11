/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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

import { SceneEnum } from '../../../../typings/k8s-new';
import { K8sCapacityPromqlGenerator } from './capacity-promql-generator';
import { K8sNetworkPromqlGenerator } from './network-promql-generator';
import { K8sPerformancePromqlGenerator } from './performance-promql-generator';

import type { K8sBasePromqlGenerator } from './base-promql-generator';

/**
 * @class K8sPromqlGeneratorFactory K8s Promql 生成器工厂
 * @description K8s场景Promql生成器工厂
 */
export class K8sPromqlGeneratorFactory {
  /**
   * @property generatorInstancesMap 各场景生成器实例映射
   * @description 用于缓存各场景生成器实例, 避免重复创建
   */
  private generatorInstancesMap: Map<string, K8sBasePromqlGenerator>;

  constructor() {
    this.generatorInstancesMap = new Map();
  }

  /**
   * @method clearGeneratorInstances 清空生成器实例
   * @description 清空生成器实例
   */
  public clearGeneratorInstances() {
    this.generatorInstancesMap.clear();
  }
  /**
   * @method createGeneratorInstance 创建生成器实例
   * @description 创建场景 promql 语句生成器实例，目前只支持 性能 | 网络 | 容量 三个场景
   * @param scene SceneEnum 场景枚举
   * @returns K8sBasePromqlGenerator 生成器实例
   */
  public createGeneratorInstance(scene: SceneEnum) {
    switch (scene) {
      case SceneEnum.Network:
        return new K8sNetworkPromqlGenerator();
      case SceneEnum.Capacity:
        return new K8sCapacityPromqlGenerator();
      default:
        return new K8sPerformancePromqlGenerator();
    }
  }

  /**
   * @method getGeneratorInstance 获取生成器实例
   * @description 获取场景 promql 语句生成器实例，目前只支持 性能 | 网络 | 容量 三个场景
   * @param scene SceneEnum 场景枚举
   * @returns K8sBasePromqlGenerator 生成器实例
   */
  public getGeneratorInstance(scene: SceneEnum): K8sBasePromqlGenerator {
    const generatorInstance = this.generatorInstancesMap.get(scene);
    if (generatorInstance) {
      return generatorInstance;
    }
    const newGeneratorInstance = this.createGeneratorInstance(scene);
    this.generatorInstancesMap.set(scene, newGeneratorInstance);
    return newGeneratorInstance;
  }
}
