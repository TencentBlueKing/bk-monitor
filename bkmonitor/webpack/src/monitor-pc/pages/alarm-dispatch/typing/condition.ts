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

import { alertTopN, listAlertTags } from '../../../../monitor-api/modules/alert';
import { getAssignConditionKeys, searchObjectAttribute } from '../../../../monitor-api/modules/assign';
import { listEventPlugin } from '../../../../monitor-api/modules/event_plugin';
import { getVariableValue } from '../../../../monitor-api/modules/grafana';
import { listUsersUser } from '../../../../monitor-api/modules/model';
import {
  getMetricListV2,
  getScenarioList,
  getStrategyV2,
  plainStrategyList
} from '../../../../monitor-api/modules/strategies';
import { handleTransformToTimestamp } from '../../../components/time-range/utils';

import { CONDITIONS, ICondtionItem } from './index';

/* 通知人员需支持远程搜索 */
export const NOTICE_USERS_KEY = 'notice_users';
/* 策略标签 */
const STRATEGY_LABELS = 'labels';

/* 每个key 包含的value选项数组 */
export type TValueMap = Map<string, { id: string; name: string }[]>;
/*
  条件选择器特殊选项
  key: 组成形式 `${key}=${value}`
    表示每个此条件组中包含此条件则需把当前选项加入到TValueMap
*/
export interface ISpecialOptions {
  [key: string]: TValueMap;
}
interface IListItem {
  id: string;
  name: string;
}
export interface IConditionProps {
  // keyList?: IListItem[];
  keys?: IListItem[];
  valueMap: TValueMap;
  groupKeys: TGroupKeys;
  groupKey: string[];
}
/* 每个key前缀包含的选项 例：dimensions: ['xxx'] => dimensions.xxx */
export type TGroupKeys = Map<string, string[] | any[]>;
/* 条件选择组合key选项 */
export const GROUP_KEYS = ['dimensions', 'tags', 'set', 'module', 'host'];
/* 条件选择value固定项 */
export const IS_EMPTY_USERS_VALUES = [
  { id: '0', name: 'false' },
  { id: '1', name: 'true' }
];
export enum EKeyTags {
  all = 'all',
  cmdb = 'CMDB',
  strategy = 'strategy',
  event = 'event'
}

/* key的标签分类 */
export const KEY_FILTER_TAGS = [
  { id: EKeyTags.all, name: window.i18n.tc('全部') },
  { id: EKeyTags.cmdb, name: window.i18n.tc('CMDB属性') },
  { id: EKeyTags.strategy, name: window.i18n.tc('告警策略') },
  { id: EKeyTags.event, name: window.i18n.tc('告警事件') }
];

/* 标签包含的key选项 */
export const KEY_TAG_MAPS = {
  [EKeyTags.cmdb]: ['set', 'module', 'host'],
  [EKeyTags.strategy]: ['alert.scenario', 'alert.metric', 'alert.strategy_id', STRATEGY_LABELS],
  [EKeyTags.event]: ['alert.name', NOTICE_USERS_KEY, 'dimensions', 'ip', 'bk_cloud_id', 'alert.event_source']
};

export function conditionCompare(left: ICondtionItem, right: ICondtionItem) {
  if (!left || !right) return false;
  const leftValues = JSON.parse(JSON.stringify(left?.value || [])).sort();
  const rightValues = JSON.parse(JSON.stringify(right?.value || [])).sort();
  return (
    (left.condition || CONDITIONS[0].id) === (left.condition || CONDITIONS[0].id) &&
    left.field === right.field &&
    left.method === right.method &&
    JSON.stringify(leftValues) === JSON.stringify(rightValues)
  );
}
/* 查找替换 */
export function conditionFindReplace(
  oldCondition: ICondtionItem[],
  findData: ICondtionItem[],
  replaceData: ICondtionItem[],
  isUnshift = false
) {
  const conditions = [];
  const findConditions: ICondtionItem[] = findData.map(item => ({
    ...item,
    condition: item.condition || CONDITIONS[0].id
  })) as any;
  const replaceConditions = JSON.parse(JSON.stringify(replaceData || [])).map(item => ({
    ...item,
    condition: item.condition || CONDITIONS[0].id
  }));
  let startHitIndex = 0;
  oldCondition.forEach(condition => {
    let isHit = false;
    if (findConditions.length) {
      for (let i = 0; i < findConditions.length; i++) {
        if (conditionCompare(condition, findConditions[i])) {
          isHit = true;
          findConditions.splice(i, 1);
          break;
        }
      }
    }
    if (isHit) {
      startHitIndex = conditions.length;
    } else {
      conditions.push(condition);
    }
  });
  if (findConditions.length === 0) {
    if (isUnshift) {
      conditions.unshift(...replaceConditions);
    } else {
      conditions.splice(startHitIndex, 0, ...replaceConditions);
    }
    return conditions;
  }
  return oldCondition;
}

/* 查找当前条件是否包含在当前条件组合里 */
export function conditionsInclues(targetCondition: ICondtionItem, conditions: ICondtionItem[]) {
  let isInclues = false;
  for (const condition of conditions) {
    if (conditionCompare(targetCondition, condition)) {
      isInclues = true;
      break;
    }
  }
  return isInclues;
}

/* 获取所有的条件队列里相同条件组合 */
export function statisticsSameConditions(groups: ICondtionItem[][]) {
  const localGroups: ICondtionItem[][] = JSON.parse(JSON.stringify(groups || [])).sort((a, b) => a.length - b.length);
  let filterConditions = [];
  const isHasNull = localGroups.some(item => !item.length);
  if (isHasNull) {
    return filterConditions;
  }
  if (localGroups.length >= 2) {
    filterConditions = localGroups[0].filter(item => localGroups.every(g => conditionsInclues(item, g)));
  } else {
    filterConditions = localGroups;
  }
  return filterConditions;
}

/* topn 接口部分数据需要去掉首尾的双引号 */
export function topNDataStrTransform(value: string) {
  const result = value.replace(/(^")|("$)/g, '');
  return result;
}

/* 获取所有key和value选项 */
export async function allKVOptions(
  bkBizIds,
  setData: (type: string, key: string, values: any) => void,
  end?: () => void
) {
  // setData('valueMap', 'is_empty_users', [
  //   { id: 'true', name: window.i18n.t('是') },
  //   { id: 'false', name: window.i18n.t('否') }
  // ]);
  let i = 0;
  const awaitAll = () => {
    i += 1;
    if (i === 12) {
      end?.();
    }
  };
  // 获取key (todo)
  getAssignConditionKeys()
    .then(keyRes => {
      const keySet = new Set();
      const keys = keyRes
        .map(item => {
          keySet.add(item.key);
          return {
            id: item.key,
            name: item.display_key
          };
        })
        .filter(item => item.id !== 'tags');
      if (!keySet.has(NOTICE_USERS_KEY)) {
        keys.push({
          id: NOTICE_USERS_KEY,
          name: window.i18n.tc('通知人员')
        });
      }
      if (!keySet.has(STRATEGY_LABELS)) {
        keys.push({
          id: STRATEGY_LABELS,
          name: window.i18n.tc('策略标签')
        });
      }
      setData('keys', '', keys);
      awaitAll();
    })
    .catch(() => {
      awaitAll();
    });
  // 第三方告警源数据
  listEventPlugin()
    .then(eventPluginRes => {
      const eventPlugins = eventPluginRes.list;
      const resultEventPlugins = [
        { id: 'bkmonitor', name: window.i18n.t('监控策略') },
        ...eventPlugins.map(item => ({
          id: item.plugin_id,
          name: item.plugin_display_name
        }))
      ];
      setData('valueMap', 'alert.event_source', resultEventPlugins);
      awaitAll();
    })
    .catch(() => {
      awaitAll();
    });
  // 监控对象数据
  getScenarioList()
    .then(scenarioRes => {
      const scenarioList = [];
      scenarioRes.forEach(item => {
        item.children?.forEach(child => {
          scenarioList.push({ id: child.id, name: child.name });
        });
      });
      setData('valueMap', 'alert.scenario', scenarioList);
      awaitAll();
    })
    .catch(() => {
      awaitAll();
    });
  // 告警策略列表
  plainStrategyList()
    .then(strategyList => {
      setData(
        'valueMap',
        'alert.strategy_id',
        strategyList.map(item => ({
          ...item,
          id: String(item.id),
          name: item.name
        }))
      );
      awaitAll();
    })
    .catch(() => {
      awaitAll();
    });
  const [startTime, endTime] = handleTransformToTimestamp(['now-7d', 'now']);
  // 获取指标
  getMetricListV2({
    conditions: [{ key: 'query', value: '' }],
    page: 1,
    page_size: 1000,
    tag: ''
  })
    .then(data => {
      setData(
        'valueMap',
        'alert.metric',
        data.metric_list.map(m => ({
          id: m.metric_id,
          name: m.name
        }))
      );
      awaitAll();
    })
    .catch(() => {
      awaitAll();
    });
  // 获取告警名称 告警指标 告警IP 云区域ID 数据
  alertTopN({
    bk_biz_ids: bkBizIds,
    conditions: [],
    query_string: '',
    status: [],
    fields: ['alert_name', 'ip', 'bk_cloud_id'],
    size: 10,
    start_time: startTime,
    end_time: endTime
  })
    .then(data => {
      const { fields } = data;
      fields.forEach(fieldData => {
        const isChar = fieldData.is_char;
        if (['ip', 'bk_cloud_id'].includes(fieldData.field)) {
          setData(
            'valueMap',
            fieldData.field,
            fieldData.buckets.map(b => ({
              id: isChar ? topNDataStrTransform(b.id) : b.id,
              name: b.name
            }))
          );
        }
        if ('alert_name' === fieldData.field) {
          setData(
            'valueMap',
            'alert.name',
            fieldData.buckets.map(b => ({
              id: isChar ? topNDataStrTransform(b.id) : b.id,
              name: b.name
            }))
          );
        }
        // if ('metric' === fieldData.field) {
        //   setData('valueMap', 'alert.metric', fieldData.buckets.map(b => ({
        //     id: isChar ? topNDataStrTransform(b.id) : b.id,
        //     name: b.name
        //   })));
        // }
      });
      awaitAll();
    })
    .catch(() => {
      awaitAll();
    });
  // 获取CDMB的相关信息 集群，模块，主机set|module|host
  // 获取集群
  const setCMDBOptions = (data, type) => {
    const items = data.map(d => {
      const id = `${type}.${d.bk_property_id}`;
      if (Array.isArray(d.option)) {
        setData(
          'valueMap',
          id,
          d.option.map(o => {
            if (typeof o === 'string') {
              return {
                id: o,
                name: o
              };
            }
            return {
              id: o.id,
              name: o.name
            };
          })
        );
      }
      return {
        id,
        name: d.bk_property_name
      };
    });
    setData('groupKeys', type, items);
  };
  searchObjectAttribute({
    bk_obj_id: 'set'
  })
    .then(data => {
      setCMDBOptions(data, 'set');
      awaitAll();
    })
    .catch(() => {
      awaitAll();
    });
  // 获取模块
  searchObjectAttribute({
    bk_obj_id: 'module'
  })
    .then(data => {
      setCMDBOptions(data, 'module');
      awaitAll();
    })
    .catch(() => {
      awaitAll();
    });
  // 获取主机
  searchObjectAttribute({
    bk_obj_id: 'host'
  })
    .then(data => {
      setCMDBOptions(data, 'host');
      awaitAll();
    })
    .catch(() => {
      awaitAll();
    });
  // 通知人员(默认获取20个，其他的通过远程搜索)
  listUsersUser({
    app_code: 'bk-magicbox',
    page: 1,
    page_size: 20,
    fuzzy_lookups: ''
  })
    .then(data => {
      setData(
        'valueMap',
        NOTICE_USERS_KEY,
        data.results.map(item => ({
          id: item.username,
          name: item.display_name
        }))
      );
      awaitAll();
    })
    .catch(() => {
      awaitAll();
    });
  alertTopN({
    bk_biz_ids: bkBizIds,
    conditions: [],
    query_string: '',
    status: [],
    fields: ['labels'],
    size: 10,
    start_time: startTime,
    end_time: endTime
  })
    .then(data => {
      const topNData = data?.fields || [];
      topNData.forEach(t => {
        if (t.field === STRATEGY_LABELS) {
          const isChar = t.is_char;
          setData(
            'valueMap',
            STRATEGY_LABELS,
            t.buckets.map(b => ({
              id: isChar ? topNDataStrTransform(b.id) : b.id,
              name: b.name
            }))
          );
        }
      });
    })
    .finally(() => {
      awaitAll();
    });
  // 获取tags
  const tags = await listAlertTags({
    conditions: [],
    query_string: '',
    status: [],
    start_time: startTime,
    end_time: endTime
  }).catch(() => []);
  setData('groupKeys', 'dimensions', tags);
  // topN数据
  const tagsFieldsParams = tags.map(t => t.id) as string[];
  const topNData = await alertTopN({
    bk_biz_ids: bkBizIds,
    conditions: [],
    query_string: '',
    status: [],
    fields: tagsFieldsParams.slice(0, 50),
    size: 10,
    start_time: startTime,
    end_time: endTime
  })
    .then(data => data?.fields || [])
    .catch(() => []);
  topNData.forEach(t => {
    const isChar = t.is_char;
    setData(
      'valueMap',
      t.field,
      t.buckets.map(b => ({
        id: isChar ? topNDataStrTransform(b.id) : b.id,
        name: b.name
      }))
    );
  });
  awaitAll();
}

/* 根据策略id获取维度及维度值列表 */
export async function setDimensionsOfStrategy(strategyId, setData: (valuesMap) => void) {
  const strategyInfo = await getStrategyV2({
    id: strategyId
  }).catch(() => null);
  if (!strategyInfo) {
    return;
  }
  const valuesMap = new Map();
  const queryConfigs = strategyInfo?.items?.[0]?.query_configs || [];
  const propmiseList = [];
  const getDimensionsValueFn = params =>
    new Promise(reslove => {
      getVariableValue(params, { needMessage: false })
        .then(data => {
          valuesMap.set(
            params.params.field,
            data.map(d => ({
              id: d.value,
              name: d.label
            }))
          );
          reslove(true);
        })
        .catch(() => {
          valuesMap.set(params.params.field, []);
          reslove(true);
        });
    });
  const dimensionKeySet = new Set();
  queryConfigs.forEach(queryConfig => {
    queryConfig.agg_dimension?.forEach(dimensionKey => {
      if (!dimensionKeySet.has(dimensionKey)) {
        const params = {
          params: {
            data_source_label: queryConfig.data_source_label,
            data_type_label: queryConfig.data_type_label,
            field: dimensionKey,
            metric_field: queryConfig.metric_field,
            result_table_id: queryConfig.result_table_id,
            where: []
          },
          type: 'dimension'
        };
        propmiseList.push(getDimensionsValueFn(params));
      }
      dimensionKeySet.add(dimensionKey);
    });
  });
  await Promise.all(propmiseList);
  setData(valuesMap);
}

/* conditions去重 */
export function conditionsDeduplication(conditions: ICondtionItem[]): ICondtionItem[] {
  const target = [];
  conditions.forEach(item => {
    if (!conditionsInclues(item, target)) {
      target.push(item);
    }
  });
  return target;
}

/* 将conditions中 key和 method相同的规则合并 */
export function mergeConditions(conditions: ICondtionItem[]) {
  return conditions.reduce((result, item) => {
    const targetCondition = result.find(config => item.field === config.field);
    if (targetCondition && targetCondition?.method === item.method) {
      targetCondition.value = [...targetCondition.value, ...item.value];
    } else {
      result.push(item);
    }
    return result;
  }, []);
}
