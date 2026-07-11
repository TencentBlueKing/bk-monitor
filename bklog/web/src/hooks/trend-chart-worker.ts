/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

/**
 * 趋势图数据处理 Worker
 * 将 CPU 密集的数据处理从主线程转移到 Worker，避免阻塞 UI 渲染
 * 
 * 使用方式：
 * const worker = new Worker(new URL('./trend-chart-worker.ts', import.meta.url), { type: 'module' });
 * worker.postMessage({ aggs, fieldName, gradeOptions, ... });
 * worker.onmessage = (event) => {
 *   const { series, xLabelMap } = event.data;
 *   // 处理返回的结果
 * };
 */

import { formatTimeStampZone } from '@/global/utils/time';

interface ProcessChartDataPayload {
  aggs: any;
  fieldName?: string;
  gradeOptions: any[];
  retrieveParams: any;
  runningInterval: string;
  timezone: string;
}

interface ProcessChartDataResult {
  series: any[];
  xLabelMap: Record<number, string>;
  totalCount: number;
}

// ======= 辅助函数 =======

const getIntervalValue = (interval: string): number => {
  const timeunit = {
    s: 1,
    m: 60,
    h: 60 * 60,
    d: 24 * 60 * 60,
  };

  const matchs = (interval ?? '1h').match(/(\d+)(s|m|h|d)/);
  if (!matchs) return 60; // default to 1 minute
  
  const num = matchs[1];
  const unit = matchs[2];

  return timeunit[unit] * Number(num);
};

const getXAxisFormat = (startTime: number, endTime: number, interval: string): string => {
  const totalSpan = endTime - startTime;
  const intervalMs = getIntervalValue(interval) * 1000;

  if (totalSpan < 24 * 60 * 60 * 1000) {
    if (intervalMs <= 1000) return 'HH:mm:ss.SSS';
    if (intervalMs <= 60 * 1000) return 'HH:mm:ss';
    if (intervalMs <= 60 * 60 * 1000) return 'HH:mm';
    return 'MM-DD HH:mm';
  }

  if (intervalMs <= 1000) return 'MM-DD HH:mm:ss.SSS';
  if (intervalMs <= 60 * 1000) return 'MM-DD HH:mm:ss';
  if (intervalMs <= 60 * 60 * 1000) return 'MM-DD HH:mm';
  if (intervalMs <= 24 * 60 * 60 * 1000) return 'MM-DD HH:mm';
  return 'YYYY-MM-DD HH:mm';
};

const isMatchedGroup = (group: any, fieldValue: any, isValueMatch: boolean): boolean => {
  if (!group) return false;
  
  if (isValueMatch) {
    return group.values?.includes(fieldValue);
  }
  
  // regex matching
  const pattern = group.regex;
  if (!pattern) return false;
  
  try {
    const regex = new RegExp(pattern);
    return regex.test(fieldValue);
  } catch {
    return false;
  }
};

// ======= 数据处理主逻辑 =======

const processGroupData = (
  eggs: any,
  fieldName: string,
  gradeOptions: any[],
  retrieveParams: any,
  runningInterval: string,
  timezone: string,
): ProcessChartDataResult => {
  const { start_time, end_time } = retrieveParams;
  const formatStr = getXAxisFormat(start_time, end_time, runningInterval);
  
  const xLabelMap = new Map<number, string>();
  const dataset = new Map<string, any>();
  const buckets = eggs?.group_by_histogram?.buckets || [];
  
  const sortKeys = gradeOptions.map(g => g.id);
  let count = 0;

  // 初始化所有分组
  for (const group of gradeOptions) {
    if (!dataset.has(group.id)) {
      dataset.set(group.id, {
        group,
        data: [],
        dataMap: new Map<string, [number, number | null, string | null]>(),
      });
    }
  }

  // 处理数据
  for (const bucket of buckets) {
    const { key, key_as_string: keyAsString, doc_count: docCount } = bucket;
    const groupData = bucket[fieldName]?.buckets ?? [];

    count += docCount;

    if (groupData.length === 0) {
      // 无分组数据，初始化默认值
      for (const dstKey of sortKeys) {
        const item = dataset.get(dstKey);
        item.dataMap.set(key, [key, null, keyAsString]);
        xLabelMap.set(key, formatTimeStampZone(key, timezone, formatStr) as string);
      }
    }

    for (const d of groupData) {
      const fieldValue = d.key;
      let isMatched = false;

      for (const dstKey of sortKeys) {
        const item = dataset.get(dstKey);
        let newCount = item.dataMap.get(key)?.[1] ?? 0;

        if (!isMatched && (dstKey === 'others' || isMatchedGroup(item.group, fieldValue, false))) {
          isMatched = true;
          newCount += d.doc_count ?? 0;
        }

        const finalCount = newCount === 0 ? null : newCount;
        item.dataMap.set(key, [key, finalCount, keyAsString]);
        xLabelMap.set(key, formatTimeStampZone(key, timezone, formatStr) as string);
      }
    }
  }

  // 生成最终的 series
  const series = sortKeys.map(key => {
    const item = dataset.get(key);
    const data = Array.from(item.dataMap.values());
    
    return {
      name: item.group.name,
      data,
      color: item.group.color,
    };
  });

  return {
    series,
    xLabelMap: Object.fromEntries(xLabelMap),
    totalCount: count,
  };
};

const processDefaultData = (
  eggs: any,
  retrieveParams: any,
  runningInterval: string,
  timezone: string,
): ProcessChartDataResult => {
  const { start_time, end_time } = retrieveParams;
  const formatStr = getXAxisFormat(start_time, end_time, runningInterval);
  
  const xLabelMap = new Map<number, string>();
  const buckets = eggs?.group_by_histogram?.buckets || [];
  const optData = new Map<number, [number, string | null]>();

  let count = 0;

  for (const { key, doc_count: docCount, key_as_string: keyAsString } of buckets) {
    xLabelMap.set(key, formatTimeStampZone(key, timezone, formatStr) as string);
    optData.set(key, [docCount + (optData.get(key)?.[0] ?? 0), keyAsString]);
    count += docCount;
  }

  const keys = Array.from(optData.keys()).sort((a, b) => a - b);
  const data = keys.map((key) => {
    const val = optData.get(key);
    const itemCount = val ? (val[0] === 0 ? null : val[0]) : null;
    return [key, itemCount, val ? val[1] : null] as [number, number | null, string | null];
  });

  const series = [{
    name: '',
    data,
    color: '#A4B3CD',
  }];

  return {
    series,
    xLabelMap: Object.fromEntries(xLabelMap),
    totalCount: count,
  };
};

// ======= Worker 消息处理 =======

self.onmessage = (event: MessageEvent<ProcessChartDataPayload>) => {
  try {
    const { aggs, fieldName, gradeOptions, retrieveParams, runningInterval, timezone } = event.data;

    let result: ProcessChartDataResult;

    if (fieldName && gradeOptions?.length) {
      result = processGroupData(aggs, fieldName, gradeOptions, retrieveParams, runningInterval, timezone);
    } else {
      result = processDefaultData(aggs, retrieveParams, runningInterval, timezone);
    }

    self.postMessage({
      success: true,
      data: result,
    });
  } catch (error) {
    self.postMessage({
      success: false,
      error: (error as Error).message,
    });
  }
};
