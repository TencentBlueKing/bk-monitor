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

import { actionDetail, alertDetail, listAlertFeedback } from 'monitor-api/modules/alert_v2';
import { getSceneView } from 'monitor-api/modules/scene_view';
import { type SceneEnum, K8sTableColumnKeysEnum } from 'monitor-pc/pages/monitor-k8s/typings/k8s-new';
import { BookMarkModel } from 'monitor-ui/chart-plugins/typings';

import { type IActionDetail, ActionDetail } from '../typings/action-detail';
import { AlarmDetail } from '../typings/detail';

import type { AlertK8SMetricItem, AlertK8sTargetResult } from '../typings';
import type { IAlarmDetail } from '../typings/detail';

export const fetchAlarmDetail = (id: string): Promise<AlarmDetail | null> => {
  if (!id) return Promise.resolve(null);
  return alertDetail<IAlarmDetail>({
    id,
  })
    .then(res => new AlarmDetail(res))
    .catch(() => null);
};

export const fetchActionDetail = (id: string): Promise<ActionDetail | null> => {
  if (!id) return Promise.resolve(null);
  return actionDetail<IActionDetail>({
    id,
  })
    .then(res => new ActionDetail(res))
    .catch(() => null);
};

export const fetchListAlertFeedback = (id: string, bizId: number) => {
  return listAlertFeedback({ alert_id: id, bk_biz_id: bizId }).catch(() => []);
};

/**
 * @description host 场景指标视图配置信息
 * @param bizId 业务ID
 */
export const getHostSceneView = async (bizId: number) => {
  const sceneData = await getSceneView({
    bk_biz_id: bizId,
    scene_id: 'host',
    type: 'detail',
    id: 'host',
  }).catch(() => ({ id: '', panels: [], name: '' }));

  // 过滤未分组
  const transformData = new BookMarkModel(sceneData || { id: '', panels: [], name: '' });
  const unGroupKey = '__UNGROUP__';
  const panels = transformData.panels;
  /** 处理只有一个分组且为未分组时则不显示组名 */
  const rowPanels = panels.filter(item => item.type === 'row');
  let resultPanels = panels;
  if (rowPanels.length === 1 && rowPanels[0]?.id === unGroupKey) {
    resultPanels = panels.reduce((prev, curr) => {
      if (curr.type === 'row') {
        prev.push(...curr.panels);
      } else {
        prev.push(curr);
      }
      return prev;
    }, []);
  } else if (panels.length > 1 && panels.some(item => item.id === unGroupKey)) {
    /* 当有多个分组且未分组为空的情况则不显示未分组 */
    resultPanels = panels.filter(item => (item.id === unGroupKey ? !!item.panels?.length : true));
  }
  transformData.panels = resultPanels;
  return transformData;
};

// ==============================start 详情-容器-相关接口 start==============================
/**
 * @method getAlertK8sScenarioList 获取可选场景列表
 * @description 告警详情-容器-可选场景列表
 * @param {string} alertId 告警ID
 * @returns {Promise<SceneEnum[]>} 可选场景列表
 */
export const getAlertK8sScenarioList = async (alertId: string) => {
  const alertK8sScenarioList = <T>(..._args): Promise<T> => {
    return Promise.resolve(['performance', 'network'] as T);
  }; // 占位
  const data = await alertK8sScenarioList<SceneEnum[]>({ alert_id: alertId }).catch(() => []);
  return data;
};

/**
 * @method getAlertK8sScenarioMetricList 获取场景下的指标列表
 * @description 告警详情-容器-当前选中场景下的指标列表
 * @param {number} params.bizId 业务ID
 * @param {SceneEnum} params.scene 场景
 * @returns {Promise<AlertK8SMetricItem[]>} 指标列表
 */
export const getAlertK8sScenarioMetricList = async (params: { bizId: number; scene: SceneEnum }) => {
  const alertK8sMetricList = <T>(..._args): Promise<T> => {
    return Promise.resolve([] as T);
  }; // 占位
  const data = await alertK8sMetricList<AlertK8SMetricItem[]>(params).catch(() => []);
  return data.reduce((prev, curr) => {
    // show_chart 为 true 的指标才展示
    const children = curr?.children?.filter?.(e => e.show_chart) ?? [];
    const count = children?.length ?? 0;
    prev.push({ ...curr, count, children });
    return prev;
  }, []);
};

/**
 * @method getAlertK8sTarget 获取关联容器对象列表
 * @description 告警详情-容器-根据告警 id 获取关联容器对象列表
 * @param {string} alertId 告警ID
 * @returns {Promise<AlertK8sTargetResult>} 关联容器对象列表
 */
export const getAlertK8sTarget = async (alertId: string) => {
  const alertK8sTarget = <T extends AlertK8sTargetResult>(..._args): Promise<T> => {
    return Promise.resolve({
      resource_type: K8sTableColumnKeysEnum.POD,
      target_list: [
        {
          pod: 'bk-log-search-web-695db7f7f5-7jxxq',
          bcs_cluster_id: 'BCS-K8S-00000',
          namespace: 'blueking',
          workload: 'Deployment:bk-log-search-web',
        },
      ],
    } as unknown as T);
  }; // 占位
  const data = await alertK8sTarget<AlertK8sTargetResult>({ alert_id: alertId }).catch(
    () =>
      ({
        resource_type: '',
        target_list: [],
      }) as unknown as AlertK8sTargetResult
  );
  return data;
};
// ==============================end 详情-容器-相关接口 end==============================
