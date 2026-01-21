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

import { toRaw } from 'vue';

import type { IEntity, ITopoNode } from './types';
import type { ITargetInfo } from 'monitor-ui/chart-plugins/plugins/caller-line-chart/use-custom';

/** 根因节点样式 */
const rootNodeAttrs = {
  groupAttrs: {
    fill: 'rgba(197, 197, 197, 0.2)',
    stroke: '#979BA5',
  },
  rectAttrs: {
    stroke: '#3A3B3D',
    fill: '#F55555',
  },
  textAttrs: {
    fill: '#fff',
  },
  textNameAttrs: {
    fill: '#979BA5',
  },
};
/** 反馈根因节点 */
const feedbackRootAttrs = {
  groupAttrs: {
    fill: 'rgba(197, 197, 197, 0.2)',
    stroke: '#979BA5',
  },
  rectAttrs: {
    stroke: '#3A3B3D',
    fill: '#FF9C01',
  },
  textAttrs: {
    fill: '#fff',
  },
  textNameAttrs: {
    fill: '#979BA5',
  },
};
/** 告警未恢复 */
// const notRestoredAttrs = {
//   groupAttrs: {
//     fill: '#F55555',
//     stroke: '#F55555',
//   },
//   rectAttrs: {
//     stroke: '#3A3B3D',
//     fill: '#F55555',
//   },
//   textAttrs: {
//     fill: '#fff',
//   },
//   textNameAttrs: {
//     fill: '#F55555',
//   },
// };
/** 异常节点 */
const errorNodeAttrs = {
  groupAttrs: {
    fill: 'rgba(255, 102, 102, 0.4)',
    stroke: '#F55555',
  },
  rectAttrs: {
    stroke: '#F55555',
    fill: '#313238',
  },
  textAttrs: {
    fill: '#EAEBF0',
  },
  textNameAttrs: {
    fill: '#FF7575',
  },
};

/** 默认节点 */
const normalNodeAttrs = {
  groupAttrs: {
    fill: 'rgba(197, 197, 197, 0.2)',
    stroke: '#979BA5',
  },
  rectAttrs: {
    stroke: '#979BA5',
    fill: '#313238',
  },
  textAttrs: {
    fill: '#EAEBF0',
  },
  textNameAttrs: {
    fill: '#DCDEE5',
  },
};
/** 根据优先级返回 */
export const getNodeAttrs = (node: ITopoNode): typeof normalNodeAttrs => {
  // if (node.entity?.is_on_alert) {
  //   return { ...notRestoredAttrs };
  // }
  if (node.entity?.is_anomaly) {
    return { ...errorNodeAttrs };
  }
  if (node?.is_feedback_root) {
    return { ...feedbackRootAttrs };
  }
  if (node.entity?.is_root) {
    return { ...rootNodeAttrs };
  }
  return { ...normalNodeAttrs };
};

/**
 * 手动裁剪文本内容
 * @param {string} text - 原始文本
 * @param {number} maxWidth - 最大宽度
 * @param {number} fontSize - 字体大小
 * @param {string} fontFamily - 字体
 * @returns {string} - 裁剪后的文本
 */
export const truncateText = (text, maxWidth, fontSize, fontFamily) => {
  const canvas = document.createElement('canvas');
  const context = canvas.getContext('2d');
  context.font = `${fontSize}px ${fontFamily}`;

  let width = context.measureText(text).width;
  if (width <= maxWidth) return text;

  let truncated = text;
  while (width > maxWidth) {
    truncated = truncated.slice(0, -1);
    width = context.measureText(truncated).width;
  }

  return truncated;
};

/** 获取apm类型节点 */
export const getApmServiceType = (entity: IEntity) => {
  if (entity.entity_type === 'APMService') {
    return entity.dimensions?.apm_service_category ?? 'Service';
  }
  return entity.entity_type || 'Service';
};

/**
 * 手动裁剪文本内容，支持换行，最多3行
 * @param {string} text - 原始文本
 * @param {number} maxWidth - 最大宽度
 * @returns {string} - 换行、裁剪后的文本
 * @returns {number} - 占用行数
 */
export const truncateTextWithWrap = (text: string, maxWidth: [string, number]) => {
  const canvas = document.createElement('canvas');
  const context = canvas.getContext('2d');
  let result = '';
  let currentLine = '';
  let currentWidth = 0;
  let lineCount = 1; // 至少有一行
  const MAX_LINES = 3; // 最多三行

  for (const char of text) {
    const charWidth = context.measureText(char).width;

    // 情况1：当前行还能容纳字符
    if (currentWidth + charWidth <= maxWidth) {
      currentLine += char;
      currentWidth += charWidth;
      continue;
    }

    // 情况2：未达最大行数，换行
    if (lineCount < MAX_LINES) {
      result += `${currentLine}\n`;
      currentLine = char;
      currentWidth = charWidth;
      lineCount++;
      continue;
    }

    // 情况3：已达最大行数，处理截断
    const ellipsis = '...';
    const ellipsisWidth = context.measureText(ellipsis).width;
    let lastLine = currentLine;

    // 尝试追加当前字符（可能失败）
    if (currentWidth + charWidth + ellipsisWidth <= maxWidth) {
      lastLine += char;
      currentWidth += charWidth;
    }

    // 移除字符直到能放下省略号
    while (context.measureText(lastLine + ellipsis).width > maxWidth && lastLine.length > 0) {
      lastLine = lastLine.slice(0, -1);
    }

    return [result + lastLine + ellipsis, lineCount];
  }

  // 循环结束未触发截断的情况
  return [result + currentLine, lineCount];
};

export const getOffset = (root, lines) => {
  switch (lines) {
    case 1:
      return root ? 48 : 40;
    case 2:
      return root ? 56 : 48;
    case 3:
      return root ? 62 : 54;
  }
};

/** 不同类型的路由跳转逻辑处理 */
export const typeToLinkHandle = {
  BcsService: {
    title: '容器场景页',
    path: () => '/k8s-new',
    beforeJumpVerify: () => true,
    query: node => {
      const { namespace, cluster_id, service_name, pod_name } = node.entity?.dimensions || {};
      const filterBy = {
        service: service_name ? [service_name] : [],
        namespace: namespace ? [namespace] : [],
        pod: pod_name ? [pod_name] : [],
      };
      return {
        groupBy: JSON.stringify(['namespace', 'service']),
        scene: 'network',
        sceneId: 'kubernetes',
        activeTab: 'list',
        cluster: cluster_id ?? '',
        filterBy: JSON.stringify(filterBy),
      };
    },
  },
  BcsWorkload: {
    title: '容器场景页',
    path: () => '/k8s-new',
    beforeJumpVerify: () => true,
    query: node => {
      const { namespace, pod_name, cluster_id, workload_name, workload_type } = node.entity?.dimensions || {};
      const filterBy = {
        workload: workload_name ? [`${workload_type}:${workload_name}`] : [],
        namespace: namespace ? [namespace] : [],
        pod: pod_name ? [pod_name] : [],
      };
      return {
        sceneId: 'kubernetes',
        groupBy: JSON.stringify(['namespace', 'workload']),
        activeTab: 'list',
        cluster: cluster_id ?? '',
        filterBy: JSON.stringify(filterBy),
      };
    },
  },
  BcsPod: {
    title: '容器场景页',
    path: () => '/k8s-new',
    beforeJumpVerify: () => true,
    query: node => {
      const { namespace, pod_name, cluster_id } = node.entity?.dimensions || {};
      const filterBy = {
        namespace: namespace ? [namespace] : [],
        pod: pod_name ? [pod_name] : [],
      };
      return {
        groupBy: JSON.stringify(['namespace', 'pod']),
        sceneId: 'kubernetes',
        activeTab: 'list',
        cluster: cluster_id ?? '',
        filterBy: JSON.stringify(filterBy),
      };
    },
  },
  BkNodeHost: {
    title: '主机详情页',
    path: node => `/performance/detail/${node.entity?.dimensions?.bk_host_id}`,
    beforeJumpVerify: node => !!node.entity?.dimensions?.bk_host_id,
    query: node => ({
      'filter-bk_host_id': node.entity?.dimensions?.bk_host_id ?? '',
      'filter-bk_target_cloud_id': node.entity?.dimensions?.bk_cloud_id ?? '',
      'filter-bk_target_ip': node.entity?.dimensions?.inner_ip ?? '',
    }),
  },
  APMService: {
    title: '服务详情页',
    path: () => '/apm/service/',
    beforeJumpVerify: node => !!node.entity?.dimensions?.apm_service_name,
    query: node => ({
      'filter-app_name': node.entity?.dimensions?.apm_application_name ?? '',
      'filter-service_name': node.entity?.dimensions?.apm_service_name ?? '',
    }),
  },
  EventExplore: {
    title: '事件检索页',
    path: () => '/event-explore',
    beforeJumpVerify: () => true,
    query: (data: ITargetInfo, type: string, isClickMore: boolean, isWarningEvent: boolean, endTime: number) => {
      // 根据事件类型来创建条件配置
      const baseWhere = [];
      const dimensions = data.dimensions || {};
      const fields = type === 'pod' ? ['bcs_cluster_id', 'namespace', 'pod'] : ['bk_cloud_id', 'bk_target_ip'];

      const addCondition = key => {
        // 只有data中存在对应数据时，才添加条件
        if (dimensions[key]) {
          baseWhere.push({
            key,
            condition: 'and',
            value: [dimensions[key]],
            method: 'eq',
          });
        }
      };
      for (const field of fields) {
        addCondition(field);
      }
      if (isWarningEvent) {
        baseWhere.push({ key: 'type', condition: 'and', value: ['Warning'], method: 'eq' });
      }
      if (!isClickMore && data.event_name) {
        baseWhere.push({ key: 'event_name', condition: 'and', value: [data.event_name], method: 'eq' });
      }

      const queryConfigs: {
        data_source_label: string;
        data_type_label: string;
        filter_dict: object;
        group_by: any[];
        query_string: string;
        result_table_id?: string;
        where: any[];
      } = {
        data_type_label: 'event',
        data_source_label: 'custom',
        query_string: '',
        group_by: [],
        filter_dict: {},
        where: baseWhere,
      };
      if (data.table) {
        queryConfigs.result_table_id = data.table;
      }
      const targets = [
        {
          data: {
            query_configs: [queryConfigs],
          },
        },
      ];
      return {
        filterMode: 'ui',
        commonWhere: [],
        showResidentBtn: 'false',
        from: data.start_time.toString() || 'now-30d',
        to: endTime.toString() || 'now',
        targets: encodeURIComponent(JSON.stringify(targets)),
      };
    },
  },
  // 跳转trace检索-trace视角-trace详情侧滑/trace详情侧滑中的span详情侧滑
  TraceExplore: {
    title: 'trace检索页',
    path: () => '/trace/home',
    beforeJumpVerify: () => true,
    query: (entity: IEntity, type: string) => {
      const { rca_trace_info, observe_time_rage } = entity;
      const query: Record<string, number | string> = {};

      const incidentQuery = {
        trace_id: rca_trace_info?.abnormal_traces[0].trace_id || '',
        span_id: rca_trace_info?.abnormal_traces[0].span_id || '',
        type,
      };
      if (observe_time_rage && Object.keys(observe_time_rage).length > 0) {
        query.start_time = observe_time_rage.start_at;
        query.end_time = observe_time_rage.end_at;
      }
      return {
        app_name: rca_trace_info?.abnormal_traces_query.app_name,
        refreshInterval: '-1',
        filterMode: 'queryString',
        query: rca_trace_info.abnormal_traces_query.query,
        sceneMode: 'trace',
        incident_query: encodeURIComponent(JSON.stringify(incidentQuery)),
        ...query,
      };
    },
  },
  // 跳转trace检索-span视角-对应trace侧滑
  SpanExplore: {
    title: 'trace检索页',
    path: () => '/trace/home',
    beforeJumpVerify: () => true,
    query: (entity: IEntity, type: string) => {
      const { rca_trace_info, observe_time_rage } = entity;
      const timestamp: Record<string, number | string> = {};

      if (observe_time_rage && Object.keys(observe_time_rage).length > 0) {
        timestamp.start_time = observe_time_rage.start_at;
        timestamp.end_time = observe_time_rage.end_at;
      }
      const incidentQuery = {
        trace_id: rca_trace_info?.abnormal_traces[0].trace_id || '',
        span_id: rca_trace_info?.abnormal_traces[0].span_id || '',
        type,
      };
      const where = rca_trace_info?.abnormal_traces_query.where || [];
      return {
        app_name: rca_trace_info?.abnormal_traces_query.app_name,
        filterMode: 'ui',
        sceneMode: 'span',
        where: JSON.stringify(toRaw(where)),
        incident_query: encodeURIComponent(JSON.stringify(incidentQuery)),
        ...timestamp,
      };
    },
  },
};

/** 根据类型判断是否可以跳转 */
export function canJumpByType(node) {
  const type = node.entity.entity_type;
  // @ts-ignore
  if (!(Object.hasOwn(typeToLinkHandle, type) && !!typeToLinkHandle[type])) {
    return false;
  }
  return typeToLinkHandle[type].beforeJumpVerify(node);
}

/** 跳转事件检索页 */
export function handleToEventPage(
  targetInfo: ITargetInfo,
  type: string,
  isClickMore = false,
  isWarningEvent = false,
  endTime: number
) {
  const linkHandleByType = typeToLinkHandle.EventExplore;
  const query = linkHandleByType?.query(targetInfo, type, isClickMore, isWarningEvent, endTime);

  const queryString = Object.keys(query)
    .map(key => `${key}=${query[key]}`)
    .join('&');

  const { origin, pathname } = window.location;
  const bk_biz_id = targetInfo.dimensions.bk_biz_id;

  // 使用原始 URL 的协议、主机名和路径部分构建新的 URL
  const baseUrl = bk_biz_id ? `${origin}${pathname}?bizId=${bk_biz_id}` : '';
  window.open(`${baseUrl}#${linkHandleByType?.path()}?${queryString}`, '_blank');
}

/** 获取检索结束时间戳 */
export const handleEndTime = (begin_time, end_time) => {
  if (!begin_time) {
    return '';
  }
  if (!end_time) {
    return Math.floor(Date.now() / 1000);
  }
  return end_time;
};

/** 跳转pod页面 */
export function handleToLink(node, bkzIds, incidentDetailData) {
  if (!canJumpByType(node)) return;

  const timestamp = new Date().getTime();
  const linkHandleByType = typeToLinkHandle[node.entity.entity_type];
  const query = linkHandleByType?.query(node);

  const { begin_time, end_time } = incidentDetailData;
  const realEndTime = handleEndTime(begin_time, end_time);
  query.from = (begin_time * 1000).toString();
  query.to = (realEndTime * 1000).toString();

  const queryString = Object.keys(query)
    .map(key => `${key}=${query[key]}`)
    .join('&');

  const { origin, pathname } = window.location;
  // 使用原始 URL 的协议、主机名和路径部分构建新的 URL
  const baseUrl = bkzIds[0] ? `${origin}${pathname}?bizId=${bkzIds[0]}` : '';
  window.open(`${baseUrl}#${linkHandleByType?.path(node)}?${queryString.toString()}`, timestamp.toString());
}

/**
 * 生成长度可缩短的二次/三次贝塞尔平行曲线
 * @param {Array} path - G6路径数组，格式如 [['M', x0, y0], ['Q', cx, cy, x2, y2]]
 * @param {number} offset - 偏移距离（正数向上，负数向下）
 * @param {number} [shortenBy=0] - 路径缩短长度（默认0）
 * @param {number} [segments=50] - 采样点数量
 * @returns {Array} - 新路径数组（格式与输入相同）
 */
export const createParallelCurve = (path: any[], offset: number, shortenBy = 0, segments = 50) => {
  // 1. 检测路径类型
  const isQuadratic = path.length >= 2 && path[1][0] === 'Q'; // 二次贝塞尔曲线
  const isCubic = path.length >= 2 && path[1][0] === 'C'; // 三次贝塞尔曲线（自环边）
  const isLoop = path.length >= 4 && path[3][0] === 'C'; // 自环边可能有多个C命令

  if (!isQuadratic && !isCubic && !isLoop) {
    console.warn('Unsupported path type for parallel curve:', path);
    return path;
  }

  // 2. 解析控制点
  let controlPoints = [];

  if (isQuadratic) {
    // 二次贝塞尔曲线: [['M', x0, y0], ['Q', cx, cy, x2, y2]]
    const [[, x0, y0], [, cx, cy, x2, y2]] = path;
    controlPoints = [
      { x: x0, y: y0 }, // P0
      { x: cx, y: cy }, // Pc (控制点)
      { x: x2, y: y2 }, // P2
    ];
  } else if (isCubic || isLoop) {
    // 三次贝塞尔曲线: [['M', x0, y0], ['C', cx1, cy1, cx2, cy2, x2, y2]]
    const [[, x0, y0], [, cx1, cy1, cx2, cy2, x2, y2]] = path;
    controlPoints = [
      { x: x0, y: y0 }, // P0
      { x: cx1, y: cy1 }, // P1 (控制点1)
      { x: cx2, y: cy2 }, // P2 (控制点2)
      { x: x2, y: y2 }, // P3
    ];
  }

  // 3. 初始化变量
  const points = []; // 存储偏移点
  let totalLength = 0; // 原始曲线长度
  const cumulativeLengths = [0]; // 累计长度数组

  // 4. 采样计算曲线长度和偏移点
  for (let i = 0; i <= segments; i++) {
    const t = i / segments;
    let Bt, Tx, Ty;

    if (isQuadratic) {
      // 二次贝塞尔曲线计算
      const [P0, Pc, P2] = controlPoints;
      Bt = {
        x: (1 - t) ** 2 * P0.x + 2 * (1 - t) * t * Pc.x + t ** 2 * P2.x,
        y: (1 - t) ** 2 * P0.y + 2 * (1 - t) * t * Pc.y + t ** 2 * P2.y,
      };

      // 切线向量
      Tx = 2 * (1 - t) * (Pc.x - P0.x) + 2 * t * (P2.x - Pc.x);
      Ty = 2 * (1 - t) * (Pc.y - P0.y) + 2 * t * (P2.y - Pc.y);
    } else {
      // 三次贝塞尔曲线计算
      const [P0, P1, P2, P3] = controlPoints;
      Bt = {
        x: (1 - t) ** 3 * P0.x + 3 * (1 - t) ** 2 * t * P1.x + 3 * (1 - t) * t ** 2 * P2.x + t ** 3 * P3.x,
        y: (1 - t) ** 3 * P0.y + 3 * (1 - t) ** 2 * t * P1.y + 3 * (1 - t) * t ** 2 * P2.y + t ** 3 * P3.y,
      };

      // 切线向量
      Tx = 3 * (1 - t) ** 2 * (P1.x - P0.x) + 6 * (1 - t) * t * (P2.x - P1.x) + 3 * t ** 2 * (P3.x - P2.x);
      Ty = 3 * (1 - t) ** 2 * (P1.y - P0.y) + 6 * (1 - t) * t * (P2.y - P1.y) + 3 * t ** 2 * (P3.y - P2.y);
    }

    const magnitude = Math.sqrt(Tx * Tx + Ty * Ty) || 0.001;

    // 计算法向量并偏移
    const Nx = -Ty / magnitude;
    const Ny = Tx / magnitude;
    const offsetPoint = {
      x: Bt.x + offset * Nx,
      y: Bt.y + offset * Ny,
    };
    points.push(offsetPoint);

    // 累计曲线长度
    if (i > 0) {
      const dx = points[i].x - points[i - 1].x;
      const dy = points[i].y - points[i - 1].y;
      totalLength += Math.sqrt(dx * dx + dy * dy);
      cumulativeLengths.push(totalLength);
    }
  }

  // 5. 计算需保留的采样点数量
  const targetLength = Math.max(0, totalLength - shortenBy);
  let validPointCount = segments;
  for (let i = cumulativeLengths.length - 1; i >= 0; i--) {
    if (cumulativeLengths[i] <= targetLength) {
      validPointCount = i + 1;
      break;
    }
  }

  // 6. 构建新路径
  const newPath = [['M', points[0].x, points[0].y]];
  for (let i = 1; i < validPointCount; i++) {
    newPath.push(['L', points[i].x, points[i].y]);
  }

  return newPath;
};

/**
 * 生成两条与原始曲线平行并连接其起点的新曲线
 * 针对自环边进行特殊处理
 * @param {Array} path - G6路径数组，格式如 [['M', x0, y0], ['Q', cx, cy, x2, y2]]
 * @param {number} offset - 偏移距离（正数向上，负数向下）
 * @param {number} shortenBy - 路径缩短长度（默认0）
 * @param {number} segments - 采样点数量
 * @returns {Object} - 含上下路径及连接路径的新曲线
 */
export const createConnectedParallelCurves = (path: any[], offset: number, shortenBy = 0, segments = 50) => {
  // 检测是否为自环边（包含多个C命令）
  const isLoop = path.length >= 4 && path[3][0] === 'C';

  if (isLoop) {
    // 自环边特殊处理：使用原始路径的偏移，不添加连接线
    const upperCurve = createParallelCurve(path, offset, shortenBy, segments);
    const lowerCurve = createParallelCurve(path, -offset, shortenBy, segments);

    // 对于自环边，不添加中间的连接线，直接返回两条平行曲线
    return [upperCurve, lowerCurve, []];
  } else {
    // 普通边的原有逻辑
    const upperCurve = createParallelCurve(path, offset, shortenBy, segments);
    const lowerCurve = createParallelCurve(path, -offset, shortenBy, segments);

    // 提取上下曲线的起点
    const upperStartPoint = upperCurve[0].slice(1);
    const lowerStartPoint = lowerCurve[0].slice(1);

    // 计算用于生成椭圆曲线连接的中间控制点
    const controlPoint = {
      x: (upperStartPoint[0] + lowerStartPoint[0]) / 2,
      y: (upperStartPoint[1] + lowerStartPoint[1]) / 2 + Math.abs(offset), // 提高控制点的垂直位置
    };

    // 创建椭圆曲线连接线
    const connectingLine = [
      ['M', upperStartPoint[0], upperStartPoint[1]],
      ['Q', controlPoint.x, controlPoint.y, lowerStartPoint[0], lowerStartPoint[1]],
    ];

    return [upperCurve, lowerCurve, connectingLine];
  }
};

/**
 * @description: 在图表数据没有单位或者单位不一致时则不做单位转换 y轴label的转换用此方法做计数简化
 * @param {number} num
 * @return {*}
 */
export function handleYAxisLabelFormatter(num: number): string {
  const si = [
    { value: 1, symbol: '' },
    { value: 1e3, symbol: 'K' },
    { value: 1e6, symbol: 'M' },
    { value: 1e9, symbol: 'G' },
    { value: 1e12, symbol: 'T' },
    { value: 1e15, symbol: 'P' },
    { value: 1e18, symbol: 'E' },
  ];
  const rx = /\.0+$|(\.[0-9]*[1-9])0+$/;
  let i: number;
  for (i = si.length - 1; i > 0; i--) {
    if (num >= si[i].value) {
      break;
    }
  }
  return (num / si[i].value).toFixed(3).replace(rx, '$1') + si[i].symbol;
}

/**
 * 移除数字中不必要的尾随零
 * 如"5.00" → "5"
 */
export function removeTrailingZeros(num) {
  if (num && num !== '0') {
    return num
      .toString()
      .replace(/(\.\d*?)0+$/, '$1')
      .replace(/\.$/, '');
  }
  return num;
}

/**
 * @description: 将数组中的值缩放到指定的范围
 * @param {number[]} inputArray - 输入的数值数组
 * @param {number} [minRange=8] - 缩放后的最小值
 * @param {number} [maxRange=16] - 缩放后最大值
 * @return {number[]} 缩放后的数值数组
 */
export function scaleArrayToRange(inputArray: number[], minRange = 8, maxRange = 16): number[] {
  if (inputArray.length === 0) {
    return [];
  }

  const minInput = Math.min(...inputArray);
  const maxInput = Math.max(...inputArray);
  // 处理所有输入值相同的情况
  if (minInput === maxInput) {
    return inputArray.map(value => (value < 1 ? 0 : minRange));
  }

  return inputArray.map(value => {
    if (value < 1) {
      return 0;
    }
    // 应用线性变换公式缩放值
    const scaledValue = Math.floor(((value - minInput) / (maxInput - minInput)) * (maxRange - minRange) + minRange);
    // 确保缩放后的值在 minRange 和 maxRange 之间
    return Math.max(minRange, Math.min(maxRange, scaledValue));
  });
}
