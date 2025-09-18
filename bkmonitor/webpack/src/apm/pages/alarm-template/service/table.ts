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

import {
  alertsStrategyTemplate,
  batchPartialUpdateStrategyTemplate,
  destroyStrategyTemplate,
  optionValuesStrategyTemplate,
  searchStrategyTemplate,
} from 'monitor-api/modules/model';
import { bkMessage, makeMessage } from 'monitor-api/utils';

import type {
  AlarmListRequestParams,
  AlarmTemplateAlertRequestParams,
  AlarmTemplateAlertsItem,
  AlarmTemplateBatchUpdateParams,
  AlarmTemplateDestroyParams,
  AlarmTemplateListItem,
  GetAlarmTemplateOptionsParams,
} from '../typing';

/**
 *
 * @description
 * 处理告警模板列表接口返回数据
 * 由于告警模板接口直接返回的数据是没有 alert_number 关联告警数字段的，需要另外请求接口异步获取
 * 兼容 vue2 响应式需要在数据结构中先定义 alert_number 字段
 * 同时由于该逻辑是全量遍历，同时将异步获取关联告警数接口的参数 ids 拼接成数组
 * @param templateList
 * @returns 需要请求关联告警数接口的 ids 数组
 */
const formatTemplateList = (
  templateList: AlarmTemplateListItem[],
  relationsMap?: Record<AlarmTemplateAlertsItem['id'], AlarmTemplateAlertsItem['alert_number']>
) => {
  const defaultValue = relationsMap ? 0 : null;
  return templateList.reduce((prev, curr) => {
    curr.alert_number = relationsMap?.[curr.id] ?? defaultValue;
    prev.push(curr.id);
    return prev;
  }, []);
};

/**
 * @description 请求错误时消息提示处理逻辑（ cancel 类型报错不进行提示）
 * @param err
 *
 */
const requestErrorMessage = err => {
  const message = makeMessage(err.error_details || err.message);
  let isAborted = false;
  if (message && err?.message !== 'canceled' && err?.message !== 'aborted') {
    bkMessage(message);
  } else {
    isAborted = true;
  }
  return isAborted;
};

/**
 * @description 获取告警模板列表
 * @param {AlarmListRequestParams} 告警参数
 * @returns {AlarmTemplateListItem[]} 告警模板列表数据
 */
export const fetchAlarmTemplateList = async (param: AlarmListRequestParams, requestConfig = {}) => {
  const config = { needMessage: false, ...requestConfig };
  let isAborted = false;
  const { total, list: templateList } = await searchStrategyTemplate<{ list: AlarmTemplateListItem[]; total: number }>(
    param,
    config
  ).catch(err => {
    isAborted = requestErrorMessage(err);
    return {
      total: 0,
      list: [] as AlarmTemplateListItem[],
    };
  });
  const ids = formatTemplateList(templateList);
  if (ids?.length && !isAborted) {
    fetchAlarmTemplateAlarmNumber({ ids, app_name: param.app_name, need_strategies: false }, requestConfig).then(
      res => {
        if (res.isAborted) return;
        const countByIdMap = res?.list?.reduce?.((prev, curr) => {
          prev[curr.id] = curr.alert_number;
          return prev;
        }, {});
        formatTemplateList(templateList, countByIdMap);
      }
    );
  }
  return { total, templateList, isAborted };
};

/**
 * @description 获取告警模板关联告警数量
 * @param {AlarmTemplateAlertRequestParams} 告警参数
 * @returns {number} 关联数量
 */
export const fetchAlarmTemplateAlarmNumber = async (param: AlarmTemplateAlertRequestParams, requestConfig = {}) => {
  const config = { needMessage: false, ...requestConfig };
  let isAborted = false;
  const result = await alertsStrategyTemplate<{ list: AlarmTemplateAlertsItem[] }>(param, config).catch(err => {
    isAborted = requestErrorMessage(err);
    return { list: [] as AlarmTemplateAlertsItem[] };
  });
  return { list: result.list, isAborted };
};

/**
 * @description 删除告警模板
 * @param {string} id 告警模板 id
 */
export const destroyAlarmTemplateById = async (params: AlarmTemplateDestroyParams) => {
  return destroyStrategyTemplate(params);
};

/**
 * @description 告警模板批量更新
 * @param {AlarmTemplateBatchUpdateParams} 更新参数
 */
export const updateAlarmTemplateByIds = async (params: AlarmTemplateBatchUpdateParams) => {
  return batchPartialUpdateStrategyTemplate(params);
};

/**
 * @description 获取告警模板候选项值
 * @param {GetAlarmTemplateOptionsParams}
 */
export const getSelectOptions = async (params: GetAlarmTemplateOptionsParams) => {
  return optionValuesStrategyTemplate(params);
};
