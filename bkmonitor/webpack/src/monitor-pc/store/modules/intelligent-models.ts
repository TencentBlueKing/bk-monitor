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
import { listIntelligentModels } from 'monitor-api/modules/strategies';
import { Action, getModule, Module, Mutation, VuexModule } from 'vuex-module-decorators';

import store from '../store';

export enum IntelligentModelsType {
  AbnormalCluster = 'AbnormalCluster',
  IntelligentDetect = 'IntelligentDetect',
  MultivariateAnomalyDetection = 'MultivariateAnomalyDetection',
  TimeSeriesForecasting = 'TimeSeriesForecasting',
}
@Module({ name: 'intelligentModels', dynamic: true, namespaced: true, store })
class IntelligentModels extends VuexModule {
  public intelligentModelsMap = new Map<IntelligentModelsType, Array<Record<string, any>>>();
  public loading = false;
  get isEnableAbnormalCluster() {
    return window.enable_aiops && this.intelligentModelsMap.get(IntelligentModelsType.AbnormalCluster)?.length > 0;
  }
  get isEnableIntelligentDetect() {
    return window.enable_aiops && this.intelligentModelsMap.get(IntelligentModelsType.IntelligentDetect)?.length > 0;
  }
  get isEnableMultivariateAnomalyDetection() {
    return (
      window.enable_aiops &&
      this.intelligentModelsMap.get(IntelligentModelsType.MultivariateAnomalyDetection)?.length > 0
    );
  }
  get isEnableTimeSeriesForecasting() {
    return (
      window.enable_aiops && this.intelligentModelsMap.get(IntelligentModelsType.TimeSeriesForecasting)?.length > 0
    );
  }
  @Mutation
  public clearIntelligentMap() {
    this.intelligentModelsMap = new Map();
  }
  @Action
  public async getListIntelligentModels(params: Record<'algorithm', IntelligentModelsType>) {
    const models = this.intelligentModelsMap.get(params.algorithm);
    if (models) return models;
    this.setLoading(true);
    const data = await listIntelligentModels(params).catch(() => []);
    this.setIntelligentModels({
      key: params.algorithm,
      data,
    });
    this.setLoading(false);
    return data;
  }
  @Action
  public initAllListIntelligentModels(): Promise<Map<IntelligentModelsType, Array<Record<string, any>>>> {
    return new Promise(resolve => {
      Promise.allSettled(
        Object.values(IntelligentModelsType).map(async v => {
          const data = await listIntelligentModels({ algorithm: v }).catch(() => []);
          this.setIntelligentModels({
            key: v,
            data,
          });
        })
      ).then(() => {
        resolve(this.intelligentModelsMap);
      });
    });
  }

  @Action
  isEnableIntelligentRule(algorithm: IntelligentModelsType) {
    return window.enable_aiops && this.intelligentModelsMap.get(algorithm)?.length > 0;
  }
  @Mutation
  public setIntelligentModels({ key, data }: { data: Array<Record<string, any>>; key: IntelligentModelsType }) {
    this.intelligentModelsMap.set(key, data);
  }
  @Mutation
  public setLoading(loading: boolean) {
    this.loading = loading;
  }
}

export default getModule(IntelligentModels);
