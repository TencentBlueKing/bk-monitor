/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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

import { typeTools } from 'monitor-common/utils/utils';

import type { ISpanClassifyItem, ITraceData, ITraceTree } from '../../../typings';
/**
 * @desc 插入跨应用 span 合并 trace_tree
 * @param { ITraceTree } originTree
 * @param { ITraceTree } newTree
 * @returns { ITraceTree }
 */
export const mergeTraceTree = (originTree: ITraceTree, newTree: ITraceTree) => {
  const result = Object.keys(originTree).reduce((pre: any, cur: string) => {
    if (typeTools.isString(originTree[cur])) {
      pre[cur] = originTree[cur];
    } else if (typeTools.isArray(originTree[cur])) {
      pre[cur] = [...originTree[cur], ...(newTree as ITraceTree)[cur]];
    } else if (typeTools.isObject(originTree[cur])) {
      pre[cur] = { ...originTree[cur], ...(newTree as ITraceTree)[cur] };
    }
    return pre;
  }, {});
  return result;
};

/**
 * @desc 跨应用转换 trace_info 基本信息
 * 主要处理 trace_info span_classify original_data
 * @param { ITraceData } newData
 * @param { ITraceData } oldData
 * @returns { ITraceData }
 */
export const transformTraceInfo = (newData: ITraceData, oldData: ITraceData) => {
  const {
    trace_info: {
      app_name: newAppName,
      trace_start_time: newStartTime,
      trace_end_time: newEndTime,
      min_duration: newMinDuration,
      max_duration: newMaxDuration,
    },
    span_classify: newSpanClassify,
    original_data: oldOriginalData,
    topo_relation: newTopoRelation,
  } = newData;
  const {
    trace_info: {
      app_name: oldAppName,
      trace_start_time: oldStartTime,
      trace_end_time: oldEndTime,
      min_duration: oldMinDuration,
      max_duration: oldMaxDuration,
    },
    span_classify: oldSpanClassify,
    original_data: newOriginalData,
    topo_relation: oldTopoRelation,
    ...oldRest
  } = oldData;

  /**
   * 总耗时：取 endTime 的最大值 - startTime 的最小值
   * 耗时区间：min(min_duration) 至 max(max_duration)
   */
  const minStartTime = Math.min(newStartTime as number, oldStartTime as number);
  const maxEndTime = Math.max(newEndTime as number, oldEndTime as number);
  const newInfo = {
    ...oldData.trace_info,
    trace_start_time: minStartTime,
    trace_end_time: maxEndTime,
    trace_duration: maxEndTime - minStartTime,
    min_duration: Math.min(newMinDuration as number, oldMinDuration as number),
    max_duration: Math.max(newMaxDuration as number, oldMaxDuration as number),
  };

  /**
   * span 分类
   * 1. type = service
   *    · 跨应用的请求后，需要将name补充上app_name前缀，然后去重
   *    · 去重后对于相同名字则累加，不同的名字则新开一个分类展示
   * 2. type = error 直接累加，不做不同应用的分类展示
   * 3. type = max_duratino 取 max(max_duration)
   */
  const newClassify = [...oldSpanClassify];
  newSpanClassify.forEach((item: ISpanClassifyItem) => {
    if (item.type === 'max_duration' && newMaxDuration > oldMaxDuration) {
      const maxDurationIndex = newClassify.findIndex(val => val.type === 'max_duration');
      newClassify.splice(maxDurationIndex, 1, item);
    } else if (item.type === 'error' || item.type === 'service') {
      const newService = item;
      if (item.type === 'service' && newAppName !== oldAppName) {
        // 应用名称不同 则说明当前服务为跨应用
        newService.name = `${newAppName}: ${newService.name}`;
        newService.app_name = newAppName;
      }

      // 通过 name 去重叠加 count 否则加入分类
      const repectIndex = newClassify.findIndex(val => val.name === newService.name);
      if (repectIndex > -1) {
        newClassify[repectIndex].count += newService.count;
      } else {
        newClassify.unshift(newService);
      }
    }
  });

  return {
    ...oldRest,
    trace_info: newInfo,
    span_classify: newClassify,
    original_data: [...oldOriginalData, ...newOriginalData],
    topo_relation: [...oldTopoRelation, ...newTopoRelation],
  };
};
