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

import { LANGUAGE_COOKIE_KEY } from 'monitor-common/utils/constant';
import { docCookies } from 'monitor-common/utils/utils';

import {
  type IGetValueFnParams,
  type IWhereValueOptionsItem,
  EMode,
} from '../../../../../components/retrieval-filter/typing';
import { AlarmServiceFactory } from '../../../../../pages/alarm-center/services/factory';
import { AlarmType } from '../../../../../pages/alarm-center/typings';

type ICandidateValueMap = Map<
  string,
  {
    count: number;
    isEnd: boolean;
    values: { id: string; name: string }[];
  }
>;

const isEn = docCookies.getItem(LANGUAGE_COOKIE_KEY) === 'en';
export const commonAlertFieldMap = {
  status: [
    {
      zhId: '未恢复',
      id: 'ABNORMAL',
      name: window.i18n.t('未恢复'),
    },
    {
      zhId: '已恢复',
      id: 'RECOVERED',
      name: window.i18n.t('已恢复'),
    },
    {
      zhId: '已失效',
      id: 'CLOSED',
      name: window.i18n.t('已失效'),
    },
  ],
  severity: [
    {
      zhId: '致命',
      id: 1,
      name: window.i18n.t('致命'),
    },
    {
      zhId: '预警',
      id: 2,
      name: window.i18n.t('预警'),
    },
    {
      zhId: '提醒',
      id: 3,
      name: window.i18n.t('提醒'),
    },
  ],
  stage: [
    {
      zhId: '已通知',
      id: 'is_handled',
      name: window.i18n.t('已通知'),
    },
    {
      zhId: '已确认',
      id: 'is_ack',
      name: window.i18n.t('已确认'),
    },
    {
      zhId: '已屏蔽',
      id: 'is_shielded',
      name: window.i18n.t('已屏蔽'),
    },
    {
      zhId: '已流控',
      id: 'is_blocked',
      name: window.i18n.t('已流控'),
    },
  ],
};
const commonActionFieldMap = {
  status: [
    {
      zhId: '执行中',
      id: 'RUNNING',
      name: window.i18n.t('执行中'),
    },
    {
      zhId: '成功',
      id: 'SUCCESS',
      name: window.i18n.t('成功'),
    },
    {
      zhId: '失败',
      id: 'FAILURE',
      name: window.i18n.t('失败'),
    },
  ],
};

const commonIncidentFieldMap = {
  status: [
    {
      zhId: '未恢复',
      id: 'ABNORMAL',
      name: window.i18n.t('未恢复'),
    },
    {
      zhId: '观察中',
      id: 'RECOVERING',
      name: window.i18n.t('观察中'),
    },
    {
      zhId: '已恢复',
      id: 'RECOVERED',
      name: window.i18n.t('已恢复'),
    },
    {
      zhId: '已解决',
      id: 'CLOSED',
      name: window.i18n.t('已解决'),
    },
  ],
  level: [
    {
      zhId: '致命',
      id: 'ERROR',
      name: window.i18n.t('致命'),
    },
    {
      zhId: '预警',
      id: 'INFO',
      name: window.i18n.t('预警'),
    },
    {
      zhId: '提醒',
      id: 'WARN',
      name: window.i18n.t('提醒'),
    },
  ],
};

export function useAlarmFilter(
  options: () => { alarmType: AlarmType; commonFilterParams: Record<string, any>; filterMode: EMode }
) {
  let axiosController = new AbortController();
  let candidateValueMap: ICandidateValueMap = new Map();

  let preAlarmType = options().alarmType;

  function getRetrievalFilterValueData(params: IGetValueFnParams): Promise<IWhereValueOptionsItem> {
    if (preAlarmType !== options().alarmType) {
      candidateValueMap.clear();
      preAlarmType = options().alarmType;
    }
    return getFieldsOptionValuesProxy(params) as any;
  }

  function getFieldsOptionValuesProxy(params: IGetValueFnParams) {
    function getMapKey(params: IGetValueFnParams) {
      return `${options().alarmType}____${options().filterMode}____${params.fields.join('')}____`;
    }
    function removeQuotesIfWrapped(str) {
      // 正则表达式匹配被双引号包裹的字符串
      const regex = /^"(.*)"$/;

      // 如果匹配成功，则返回去掉一层双引号的内容
      if (regex.test(str)) {
        return str.replace(regex, '$1');
      }

      // 如果不匹配，返回原字符串
      return str;
    }
    return new Promise(resolve => {
      // if (params?.isInit__) {
      //   candidateValueMap = new Map();
      // }
      const searchValue = String(params.where?.[0]?.value?.[0] || '');
      const searchValueLower = searchValue.toLocaleLowerCase();
      const candidateItem = candidateValueMap.get(getMapKey(params));

      // 故障部分字段枚举值
      const paramsField = params?.fields?.[0];
      const listTranslate = (list: { id: number | string; name: string; zhId: string }[]) => {
        return list.map(item => ({
          id: isEn || options().filterMode === EMode.ui ? item.id : item.zhId,
          name: item.zhId,
        }));
      };
      if (options().alarmType === AlarmType.ALERT && ['status', 'severity', 'stage'].includes(paramsField)) {
        resolve({
          list: listTranslate(commonAlertFieldMap[paramsField]),
          count: commonAlertFieldMap[paramsField].length,
        });
      } else if (options().alarmType === AlarmType.ACTION && ['status'].includes(paramsField)) {
        resolve({
          list: listTranslate(commonActionFieldMap[paramsField]),
          count: commonActionFieldMap[paramsField].length,
        });
      } else if (options().alarmType === AlarmType.INCIDENT && ['status', 'level'].includes(paramsField)) {
        resolve({
          list: listTranslate(commonIncidentFieldMap[paramsField]),
          count: commonIncidentFieldMap[paramsField].length,
        });
      } else if (candidateItem?.isEnd && !params?.queryString) {
        if (searchValue) {
          const filterValues = candidateItem.values.filter(item => {
            const idLower = `${item.id}`.toLocaleLowerCase();
            const nameLower = item.name.toLocaleLowerCase();
            return idLower.includes(searchValueLower) || nameLower.includes(searchValueLower);
          });
          resolve({
            count: filterValues.length,
            list: filterValues,
          });
        } else {
          const list = candidateItem.values.slice(0, params.limit);
          resolve({
            count: list.length,
            list: list,
          });
        }
      } else {
        axiosController.abort();
        axiosController = new AbortController();
        AlarmServiceFactory(options().alarmType)
          .getRetrievalFilterValues(
            {
              ...options().commonFilterParams,
              conditions: [],
              fields: params.fields,
              size: params.limit,
            },
            {
              signal: axiosController.signal,
              needMessage: false,
            }
          )
          .then(res => {
            const values = (res.fields?.find(f => f.field === paramsField)?.buckets || []).map(item => {
              if (options().filterMode === EMode.ui) {
                return {
                  ...item,
                  id: removeQuotesIfWrapped(item.id),
                };
              }
              return item;
            });
            const isEnd = values.length < params.limit;
            const newMap = new Map();
            if (!searchValue && isEnd) {
              // 只在聚焦失焦是缓存
              newMap.set(getMapKey(params), {
                values: values,
                isEnd: isEnd,
                count: values.length,
              });
            }
            candidateValueMap = newMap;
            resolve({
              list: values,
              count: values.length,
            });
          })
          .catch(err => {
            if (err?.message !== 'canceled') {
              resolve({
                count: 0,
                list: [],
              });
            }
          });
      }
    });
  }

  return {
    getRetrievalFilterValueData,
  };
}
