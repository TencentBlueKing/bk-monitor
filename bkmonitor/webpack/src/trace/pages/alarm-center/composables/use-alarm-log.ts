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

import dayjs from 'dayjs';
import api from 'monitor-api/api';
import { getSceneView } from 'monitor-api/modules/scene_view';
import { handleTransformToTimestamp } from 'trace/components/time-range/utils';
import { VariablesService } from 'trace/utils/variable';

import type { AlarmDetail } from '../typings/detail';

const createAutoTimeRange = (
  startTime: number,
  endTime: number,
  interval = 60
): { endTime: string; startTime: string } => {
  // const interval = this.detail.extra_info?.strategy?.items?.[0]?.query_configs?.[0]?.agg_interval || 60;
  const INTERVAL_5 = 5 * interval * 1000;
  const INTERVAL_1440 = 1440 * interval * 1000;
  const INTERVAL_60 = 60 * interval * 1000;
  let newStartTime = startTime * 1000;
  let newEndTime = endTime ? endTime * 1000 : Date.now();
  newEndTime = Math.min(newEndTime + INTERVAL_5, newStartTime + INTERVAL_1440);
  let diff = INTERVAL_1440 - (newEndTime - newStartTime);
  if (diff < INTERVAL_5) {
    diff = INTERVAL_5;
  } else if (diff > INTERVAL_60) {
    diff = INTERVAL_60;
  }
  newStartTime -= diff;
  const result = {
    startTime: dayjs.tz(newStartTime).format('YYYY-MM-DD HH:mm:ss'),
    endTime: dayjs.tz(newEndTime).format('YYYY-MM-DD HH:mm:ss'),
  };
  return result;
};

export function useAlarmLog(detail: AlarmDetail) {
  const alarmDetail = detail;

  let variables: Record<string, any> = {};
  let interval = 60;
  let viewOptions = {};
  let sceneViewData = null;
  let timeRange = [];
  let tableData = [];
  let relatedBkBizId = -1;

  async function getSceneData() {
    variables = {
      bk_host_innerip: '0.0.0.0',
      bk_cloud_id: '0',
    };
    const hostMap = ['bk_host_id'];
    const ipMap = ['bk_target_ip', 'ip', 'bk_host_id'];
    const cloudMap = ['bk_target_cloud_id', 'bk_cloud_id', 'bk_host_id'];
    for (const item of alarmDetail.dimensions) {
      if (hostMap.includes(item.key) && item.value) {
        variables.bk_host_id = item.value;
      }
      if (cloudMap.includes(item.key) && item.value) {
        variables.bk_cloud_id = item.value;
      }
      if (ipMap.includes(item.key) && item.value) {
        variables.bk_host_innerip = item.value;
      }
    }
    interval = alarmDetail.extra_info?.strategy?.items?.[0]?.query_configs?.[0]?.agg_interval || 60;
    const { startTime, endTime } = createAutoTimeRange(alarmDetail.begin_time, alarmDetail.end_time, interval);
    timeRange = [startTime, endTime];
    const data = await getSceneView({
      bk_biz_id: alarmDetail.bk_biz_id,
      scene_id: 'alert',
      type: '',
      id: 'log',
      ...variables,
    }).catch(() => ({ id: '', panels: [], name: '' }));
    viewOptions = {
      method: 'AVG',
      ...variables,
      interval,
      group_by: [],
      current_target: {},
    };
    return data;
  }
  async function getIndexSetList() {
    if (!sceneViewData) {
      sceneViewData = await getSceneData();
    }
    let predicateLogData = null;
    const predicateLogTarget = sceneViewData?.overview_panels?.[0]?.targets?.find(
      item => item.dataType === 'log_predicate'
    );
    if (predicateLogTarget) {
      const variablesService = new VariablesService({
        ...viewOptions,
      });
      const apiStr = predicateLogTarget?.api || '';
      const apiFunc = apiStr?.split('.')[1] || '';
      const apiModule = apiStr?.split('.')[0] || '';
      const payload = variablesService.transformVariables(predicateLogTarget.data);
      predicateLogData = await api[apiModule]?.[apiFunc](payload, {
        needMessage: false,
      })
        .then(res => {
          return res;
        })
        .catch(() => null);
    }
    if (!predicateLogData) {
      return null;
    }
    relatedBkBizId = predicateLogData?.related_bk_biz_id || -1;
    let relatedIndexSetList = [];

    const curTarget = sceneViewData?.overview_panels?.[0]?.targets?.find(item => item.dataType === 'condition');
    if (curTarget) {
      const apiStr = curTarget?.api || '';
      const apiFunc = apiStr?.split('.')[1] || '';
      const apiModule = apiStr?.split('.')[0] || '';

      const variablesService = new VariablesService({
        ...viewOptions,
      });
      const payload = variablesService.transformVariables(curTarget.data);
      relatedIndexSetList = await api[apiModule]?.[apiFunc](payload, {
        needMessage: false,
      }).then(res => {
        return res || [];
      });
    }
    return {
      relatedIndexSetList,
      relatedBkBizId,
    };
  }

  async function updateTableData(_params: {
    index_set_id: number | string;
    keyword: string;
    limit: number;
    offset: number;
  }) {
    let data = {
      columns: [],
      data: [],
      total: 0,
    };
    if (!sceneViewData) {
      sceneViewData = await getSceneData();
    }
    const curTarget = sceneViewData?.overview_panels?.[0]?.targets?.find(item => item.dataType === 'table-chart');
    if (curTarget) {
      const [startTime, endTime] = handleTransformToTimestamp(timeRange as [string, string]);
      const apiStr = curTarget?.api || '';
      const apiFunc = apiStr?.split('.')[1] || '';
      const apiModule = apiStr?.split('.')[0] || '';
      const params = {
        start_time: startTime,
        end_time: endTime,
        keyword: _params?.keyword || '',
        limit: _params?.limit || 30,
        offset: _params?.offset || 0,
        index_set_id: _params?.index_set_id || '',
      };
      const variablesService = new VariablesService({
        ...viewOptions,
      });
      const payload = variablesService.transformVariables(curTarget.data);
      data = await api[apiModule]?.[apiFunc](
        {
          ...payload,
          ...params,
          view_options: {
            ...viewOptions,
          },
        },
        {
          needMessage: false,
        }
      ).then(res => {
        if (_params.offset) {
          tableData.push(...(res?.data || []));
        } else {
          tableData = res?.data || [];
        }
        const obj = {
          columns: res?.columns || [],
          data: [...tableData.map((item, index) => ({ ...item, index: index + 1 }))],
          total: res?.total || 0,
        };
        return obj;
      });
    }
    return data;
  }

  function resetTableData() {
    tableData = [];
  }

  return {
    getIndexSetList,
    updateTableData,
    resetTableData,
  };
}
