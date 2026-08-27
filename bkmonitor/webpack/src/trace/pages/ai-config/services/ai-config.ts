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
import { fetchAiSetting, saveAiSetting } from 'monitor-api/modules/aiops';
import {
  getSourceAnalysisConfig,
  listSourceAnalysisBkciProjects,
  listSourceAnalysisBkciRepositories,
  saveSourceAnalysisConfig,
} from 'monitor-api/modules/issue';
import { listIntelligentModels } from 'monitor-api/modules/strategies';

import type {
  EIntelligentAlgorithm,
  IAiSetting,
  ISchemeItem,
  TBkciProjectsResult,
  TBkciRepositoriesParams,
  TBkciRepositoriesResult,
  TGetSourceAnalysisConfigResult,
  TSaveSourceAnalysisConfigParams,
} from '../typings';

/** 获取 AI 设置配置，失败返回 null 由调用方决定降级表现 */
export const getAiSetting = (): Promise<IAiSetting | null> => fetchAiSetting().catch(() => null);

/** 保存 AI 设置配置，返回是否成功 */
export const updateAiSetting = (params: IAiSetting): Promise<boolean> =>
  saveAiSetting(params)
    .then(() => true)
    .catch(() => false);

/** 获取指定算法下可选的智能检测方案列表 */
export const getSchemeList = (algorithm: EIntelligentAlgorithm): Promise<ISchemeItem[]> =>
  listIntelligentModels({ algorithm }).catch(() => []);

/** 查询蓝盾项目 */
export const getBkciProjects = (): Promise<TBkciProjectsResult> =>
  listSourceAnalysisBkciProjects().catch(() => ({
    list: [],
    total: 0,
  }));

/** 查询指定蓝盾项目下的源码仓库 */
export const getBkciRepositories = (params: TBkciRepositoriesParams): Promise<TBkciRepositoriesResult> =>
  listSourceAnalysisBkciRepositories(params).catch(() => ({
    list: [],
    total: 0,
  }));

/** 保存业务代码库配置 */
export const setSaveSourceAnalysisConfig = (params: TSaveSourceAnalysisConfigParams) =>
  saveSourceAnalysisConfig(params);
/** 查询业务代码库配置 */
export const getSourceAnalysisConfigData = (params = {}): Promise<TGetSourceAnalysisConfigResult> =>
  getSourceAnalysisConfig(params);
