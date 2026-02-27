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

import { computed, shallowRef, watchEffect } from 'vue';

import { useStorage } from '@vueuse/core';

import { useAlarmCenterStore } from '@/store/modules/alarm-center';

import type { AnalysisListItem, AnalysisTopNDataResponse } from '../typings';

export function useAlarmAnalysis() {
  const alarmStore = useAlarmCenterStore();
  // 告警、故障、处理记录 分析Field TopN列表
  const analysisFieldTopNData = shallowRef<AnalysisTopNDataResponse<AnalysisListItem>>({
    doc_count: 0,
    fields: [],
  });
  // 告警、故障、处理记录 分析Filed TopN列表loading
  const analysisFieldTopNLoading = shallowRef(false);
  // 告警、故障、处理记录 dimension tags 分析TopN列表
  const analysisDimensionTopNData = shallowRef<AnalysisTopNDataResponse<AnalysisListItem>>({
    doc_count: 0,
    fields: [],
  });
  // 维度分析loading
  const analysisDimensionLoading = shallowRef(false);
  // 告警、故障、处理记录 dimension Tag 列表
  const dimensionTags = computed(() => alarmStore.dimensionTags);
  // 告警、故障、处理记录 字段列表
  const analysisFields = computed(() => alarmStore.alarmService.analysisFields);
  // 告警、故障、处理记录 字段名称映射
  const analysisFieldsMap = computed(() => alarmStore.alarmService.analysisFieldsMap);
  const storageAnalysisKey = computed(() => alarmStore.alarmService.storageAnalysisKey);
  // 告警、故障、处理记录 展示的告警分析设置项
  const analysisSettings = useStorage<string[]>(storageAnalysisKey, [
    ...alarmStore.alarmService.analysisDefaultSettingsFields,
  ]);

  const effectFunc = () => {
    analysisFieldTopNLoading.value = true;
    getAnalysisDimensionFields();
    getAnalysisFieldData(analysisFields.value);
  };

  /** 获取分析字段TopN数据 */
  const getAnalysisFieldData = async (fields: string[], isAll = false) => {
    getAnalysisDataByFields(fields, isAll)
      .then(analysisTopN => {
        analysisFieldTopNData.value = {
          doc_count: analysisTopN.doc_count,
          fields: analysisTopN.fields.map(item => ({
            ...item,
            name: analysisFieldsMap.value[item.field] || item.field,
          })),
        };
      })
      .finally(() => {
        analysisFieldTopNLoading.value = false;
      });
  };

  /** 获取告警分析维度Tag列表 */
  const getAnalysisDimensionFields = () => {
    getAnalysisDimensionData(dimensionTags.value.map(item => item.id));
  };

  /** 获取分析 dimension Tag列表对应的TopN数据 */
  const getAnalysisDimensionData = async (fields: string[], isAll = false) => {
    analysisDimensionLoading.value = true;
    const data = await getAnalysisDataByFields(fields, isAll);
    analysisDimensionTopNData.value = {
      doc_count: data.doc_count,
      fields: data.fields.map(item => ({
        ...item,
        name: dimensionTags.value.find(tag => tag.id === item.field)?.name || item.field,
      })),
    };
    analysisDimensionLoading.value = false;
  };

  /**
   * @description: 获取分析数据
   * @param {string[]} fields 维度分析字段列表
   * @param {boolean} isAll 是否获取全部数据
   */
  const getAnalysisDataByFields = async (
    fields: string[],
    isAll = false
  ): Promise<AnalysisTopNDataResponse<Omit<AnalysisListItem, 'name'>>> => {
    const data = await alarmStore.alarmService.getAnalysisTopNData(
      {
        ...alarmStore.commonFilterParams,
        fields: fields,
      },
      isAll
    );

    return {
      doc_count: data.doc_count,
      fields: data.fields.map(item => ({
        ...item,
        buckets: item.buckets.map(bucket => ({
          ...bucket,
          percent: data.doc_count ? Number(((bucket.count / data.doc_count) * 100).toFixed(2)) : 0,
        })),
      })),
    };
  };
  watchEffect(effectFunc);

  return {
    analysisFieldTopNData,
    analysisFieldTopNLoading,
    analysisDimensionTopNData,
    analysisDimensionLoading,
    analysisFields,
    dimensionTags,
    analysisFieldsMap,
    analysisSettings,
    getAnalysisDataByFields,
  };
}
