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
import { computed, shallowRef } from 'vue';

import { Message } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import { getAiSetting, getSchemeList, updateAiSetting } from '../services/ai-config';
import { EIntelligentAlgorithm, SCENE_TYPES } from '../typings';

import type { IAiSetting, ISceneFormItem, ISchemeItem, PlanIdValue } from '../typings';

/** 单指标异常检测表单项的错误信息 key */
export const KPI_ERROR_KEY = 'kpi';

/** 场景表单项的错误信息 key */
export const getSceneErrorKey = (type: string) => `scene-${type}`;

/**
 * @description 异常检测配置：方案列表与 AI 设置的拉取、表单状态维护、校验与保存
 */
export const useAnomalyDetection = () => {
  const { t } = useI18n();

  /** 接口返回的原始配置，保存时用于透传表单未呈现的字段 */
  let rawAiSetting: IAiSetting | null = null;

  const loading = shallowRef(false);
  const saving = shallowRef(false);
  /** 单指标异常检测可选方案 */
  const singleSchemeList = shallowRef<ISchemeItem[]>([]);
  /** 场景智能异常检测可选方案 */
  const sceneSchemeList = shallowRef<ISchemeItem[]>([]);
  /** 单指标异常检测的默认方案 */
  const kpiPlanId = shallowRef<PlanIdValue>('');
  /** 各场景的默认方案 */
  const sceneList = shallowRef<ISceneFormItem[]>([]);
  /** 表单校验错误信息 */
  const errors = shallowRef<Record<string, string>>({});
  /**
   * 表单初始值快照（初始化加载完成后设定），用于判断当前表单是否被编辑过
   * key 为 kpi 单指标，value 为按 SceneType 排序后的场景快照
   */
  const initialKpiPlanId = shallowRef<null | string>(null);
  const initialSceneList = shallowRef<ISceneFormItem[]>(null);

  /** 用接口数据回填表单，并记录初始快照（用于判断是否编辑过） */
  const setFormData = (setting: IAiSetting | null) => {
    rawAiSetting = setting;
    kpiPlanId.value = setting?.kpi_anomaly_detection?.default_plan_id || '';
    sceneList.value = SCENE_TYPES.map(type => ({
      type,
      planId: setting?.multivariate_anomaly_detection?.[type]?.default_plan_id || '',
    }));
    initialKpiPlanId.value = `${kpiPlanId.value}`;
    initialSceneList.value = JSON.parse(JSON.stringify(sceneList.value));
  };

  /** 拉取各算法下的可选方案 */
  const fetchSchemeLists = async () => {
    const [singleList, multipleList] = await Promise.all([
      getSchemeList(EIntelligentAlgorithm.intelligentDetect),
      getSchemeList(EIntelligentAlgorithm.multivariateAnomalyDetection),
    ]);
    singleSchemeList.value = singleList;
    sceneSchemeList.value = multipleList;
  };

  /** 拉取已保存的配置并回填表单 */
  const fetchAiSettingData = async () => {
    setFormData(await getAiSetting());
  };

  const fetchData = async () => {
    loading.value = true;
    await Promise.all([fetchSchemeLists(), fetchAiSettingData()]);
    loading.value = false;
  };

  const clearError = (key: string) => {
    if (!errors.value[key]) return;
    const nextErrors = { ...errors.value };
    delete nextErrors[key];
    errors.value = nextErrors;
  };

  const handleKpiPlanChange = (planId: PlanIdValue) => {
    kpiPlanId.value = planId;
    clearError(KPI_ERROR_KEY);
  };

  const handleScenePlanChange = (type: string, planId: PlanIdValue) => {
    sceneList.value = sceneList.value.map(item => (item.type === type ? { ...item, planId } : item));
    clearError(getSceneErrorKey(type));
  };

  /** 默认方案为必填项 */
  const validate = () => {
    const nextErrors: Record<string, string> = {};
    const requiredTips = t('请选择默认方案');
    if (!kpiPlanId.value) {
      nextErrors[KPI_ERROR_KEY] = requiredTips;
    }
    for (const scene of sceneList.value) {
      if (!scene.planId) {
        nextErrors[getSceneErrorKey(scene.type)] = requiredTips;
      }
    }
    errors.value = nextErrors;
    return !Object.keys(nextErrors).length;
  };

  const save = async () => {
    if (!validate()) return false;
    saving.value = true;
    // eslint-disable-next-line @typescript-eslint/consistent-type-assertions
    const params = {
      ...rawAiSetting,
      kpi_anomaly_detection: {
        ...rawAiSetting?.kpi_anomaly_detection,
        default_plan_id: kpiPlanId.value as number,
        // 单指标异常检测没有「是否启用」与「敏感度」配置，提交时需剔除
        is_enabled: undefined,
        default_sensitivity: undefined,
      },
      multivariate_anomaly_detection: sceneList.value.reduce<IAiSetting['multivariate_anomaly_detection']>(
        (acc, scene) => {
          acc[scene.type] = {
            ...rawAiSetting?.multivariate_anomaly_detection?.[scene.type],
            default_plan_id: scene.planId as number,
          };
          return acc;
        },
        { ...rawAiSetting?.multivariate_anomaly_detection }
      ),
    } as IAiSetting;
    const success = await updateAiSetting(params);
    saving.value = false;
    if (!success) return false;
    Message({
      theme: 'success',
      message: t('保存成功！'),
    });
    // 保存成功后重新拉取，确保展示的是后端最终生效的配置
    await fetchAiSettingData();
    return true;
  };

  /** 当前表单相对初始快照是否被修改过：用于离开页面提示 */
  const isEdited = computed(() => {
    if (initialKpiPlanId.value === null || initialSceneList.value === null) return false;
    if (`${kpiPlanId.value}` !== `${initialKpiPlanId.value}`) return true;
    return JSON.stringify(sceneList.value) !== JSON.stringify(initialSceneList.value);
  });

  return {
    loading,
    saving,
    singleSchemeList,
    sceneSchemeList,
    kpiPlanId,
    sceneList,
    errors,
    isEdited,
    fetchData,
    handleKpiPlanChange,
    handleScenePlanChange,
    save,
  };
};
