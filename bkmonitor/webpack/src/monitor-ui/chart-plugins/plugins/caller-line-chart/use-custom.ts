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

import { eventTags } from 'monitor-api/modules/apm_event';
import svg from 'monitor-common/svg/base64';

export enum StatisticsEventType {
  Default = 'Default',
  Normal = 'Normal',
  Warning = 'Warning',
}
interface IEventTagsItem {
  app_name: string;
  service_name: string;
  interval: number;
  where?: Record<string, string | string[]>[];
  start_time: number;
  end_time: number;
}
export const getCustomEventTagsPanelParams = (params: IEventTagsItem) => {
  return {
    app_name: params.app_name,
    service_name: params.service_name,
    start_time: params.start_time,
    end_time: params.end_time,
    expression: 'a',
    query_configs: [
      {
        data_source_label: 'bk_apm',
        data_type_label: 'event',
        table: 'builtin',
        filter_dict: {},
        interval: params.interval,
        where: [],
        query_string: '*',
        group_by: [],
        metrics: [
          {
            field: '_index',
            method: 'SUM',
            alias: 'a',
          },
        ],
      },
    ],
  };
};
export const getCustomEventTagsDetailPanelParams = (params: IEventTagsItem) => {
  return {
    app_name: params.app_name,
    service_name: params.service_name,
    start_time: params.start_time,
    end_time: params.end_time,
    query_configs: [
      {
        data_source_label: 'bk_apm',
        data_type_label: 'event',
        table: 'builtin',
        filter_dict: {},
        interval: params.interval,
        // where: [
        //   // 选中异常 Tab 时，增加该过滤条件。
        //   {
        //     condition: 'and',
        //     key: 'type',
        //     method: 'eq',
        //     value: ['Warning'],
        //   },
        // ],
        query_string: '*',
        group_by: [],
      },
    ],
    limit: 5,
  };
};
export interface ICustomEventTagsItem {
  time: number;
  items: {
    domain: string;
    source: string;
    count: number;
    statistics: Partial<Record<StatisticsEventType, number>>;
  }[];
}
interface ILabelItem {
  label: string;
  value: string;
  alias?: string;
}
export interface ICustomEventDetail {
  total?: number;
  time?: number;
  list?: {
    [key: string]: { value: string; alias: string; url?: string };
    'event.content': {
      value: string;
      alias: string;
      detail: {
        [key: string]: {
          [key: string]: string;
        } & ILabelItem;
      };
    };
  }[];
  topk?: {
    count: number;
    proportions: number;
    domain: ILabelItem;
    source: ILabelItem;
    event_name: ILabelItem;
  }[];
}
/**
 * 获取自定义事件标签数量聚合列表
 */
export const getCustomEventTags = async (params: Record<string, any>): Promise<ICustomEventTagsItem[]> => {
  return await eventTags({
    ...params,
  })
    .then(data => data?.list || [])
    .catch(() => []);
};
export const getCustomEventTagDetails = async (params: Record<string, any>, mockEventCount = 1, isWarning = false) => {
  console.info('getCustomEventTagDetails', params);
  const data = await new Promise(resole => {
    setTimeout(() => {
      const mockData = {
        result: true,
        code: 200,
        message: 'OK',
        data: {
          time: 1739877420,
          total: 10,
          // 由后台控制展示事件名统计（topk）还是事件列表。
          // =1：展示 event.content 里的 detail，其他，展示为 event_name.alias（target.alias）。
          list: [
            {
              time: {
                value: 1736927543000,
                alias: 1736927543000,
              },
              domain: {
                value: 'SYSTEM',
                alias: '系统',
              },
              source: {
                value: 'HOST',
                alias: '系统/主机',
              },
              event_name: {
                value: 'oom',
                alias: '进程 OOM',
              },
              target: {
                value: '127.0.0.1',
                alias: '127.0.0.1',
                url: 'https://xxx/host/?bk_cloud_id=&bk_cloud_ip=127.0.0.1',
              },
              'event.content': {
                value: 'oom',
                alias: '发现主机（0-127.0.0.1）存在进程（chrome）OOM 异常事件',
                detail: {
                  target: {
                    label: '主机',
                    value: '127.0.0.1',
                    alias: '直连区域[0] / 127.0.0.1',
                    type: 'link',
                    url: 'https://xxxx/host/?bk_cloud_id=&bk_cloud_ip=127.0.0.1',
                  },
                  process: {
                    label: '进程',
                    value: 'chrome',
                  },
                  task_memcg: {
                    label: '任务（进程）所属的内存 cgroup',
                    value: '/pods.slice/pods-burstable.slice/pods-burstable-pod1',
                  },
                  time: {
                    label: '开始时间',
                    value: 1736927543000,
                  },
                },
              },
            },
            {
              time: {
                value: 1736927543000,
                alias: 1736927543000,
              },
              domain: {
                value: 'K8S',
                alias: 'Kubernetes',
              },
              source: {
                value: 'BCS',
                alias: 'Kubernetes/BCS',
              },
              event_name: {
                value: 'FailedMount',
                alias: '卷挂载失效（FailedMount）',
              },
              target: {
                value: '127.0.0.1',
                alias: 'BCS-K8S-90001 / kube-system / Pod / bk-log-collector-fx97q',
                url: 'https://xxxx/k8s-new/?=bcs_cluster_id=BCS-K8S-90001&namespace=xxx',
              },
              'event.content': {
                value: 'xxx',
                alias: 'xxxxx',
                detail: {
                  bcs_cluster_id: {
                    label: '集群',
                    value: 'BCS-K8S-90001',
                    alias: '[共享集群] 蓝鲸公共-广州(BCS-K8S-90001)',
                    type: 'link',
                    detail: 'https://xxxx/k8s-new/?=bcs_cluster_id=BCS-K8S-90001',
                  },
                  namespace: {
                    label: 'NameSpace',
                    value: 'kube-system',
                    alias: 'kube-system',
                    type: 'link',
                    url: 'https://xxxx/k8s-new/?=bcs_cluster_id=BCS-K8S-90001&namespace=xxx',
                  },
                  name: {
                    label: '工作负载',
                    value: 'bk-log-collector-fx97q',
                    alias: 'Pod / bk-log-collector-fx97q',
                    type: 'link',
                    url: 'https://xxxx/k8s-new/?=bcs_cluster_id=BCS-K8S-90001&namespace=xxx',
                  },
                  time: {
                    label: '开始时间',
                    value: 1736927543000,
                  },
                  duration: {
                    label: '持续时间',
                    value: 61,
                    alias: '1m1s',
                  },
                },
              },
            },
            {
              time: {
                value: 1736927543000,
                alias: 1736927543000,
              },
              domain: {
                value: 'SYSTEM',
                alias: '系统',
              },
              source: {
                value: 'HOST',
                alias: '系统/主机',
              },
              event_name: {
                value: 'oom',
                alias: '进程 OOM',
              },
              target: {
                value: '127.0.0.1',
                alias: '127.0.0.1',
                url: 'https://xxx/host/?bk_cloud_id=&bk_cloud_ip=127.0.0.1',
              },
              'event.content': {
                value: 'oom',
                alias: '发现主机（0-127.0.0.1）存在进程（chrome）OOM 异常事件',
                detail: {
                  target: {
                    label: '主机',
                    value: '127.0.0.1',
                    alias: '直连区域[0] / 127.0.0.1',
                    type: 'link',
                    url: 'https://xxxx/host/?bk_cloud_id=&bk_cloud_ip=127.0.0.1',
                  },
                  process: {
                    label: '进程',
                    value: 'chrome',
                  },
                  task_memcg: {
                    label: '任务（进程）所属的内存 cgroup',
                    value: '/pods.slice/pods-burstable.slice/pods-burstable-pod1',
                  },
                  time: {
                    label: '开始时间',
                    value: 1736927543000,
                  },
                },
              },
            },
            {
              time: {
                value: 1736927543000,
                alias: 1736927543000,
              },
              domain: {
                value: 'K8S',
                alias: 'Kubernetes',
              },
              source: {
                value: 'BCS',
                alias: 'Kubernetes/BCS',
              },
              event_name: {
                value: 'FailedMount',
                alias: '卷挂载失效（FailedMount）',
              },
              target: {
                value: '127.0.0.1',
                alias: 'BCS-K8S-90001 / kube-system / Pod / bk-log-collector-fx97q',
                url: 'https://xxxx/k8s-new/?=bcs_cluster_id=BCS-K8S-90001&namespace=xxx',
              },
              'event.content': {
                value: 'xxx',
                alias: 'xxxxx',
                detail: {
                  bcs_cluster_id: {
                    label: '集群',
                    value: 'BCS-K8S-90001',
                    alias: '[共享集群] 蓝鲸公共-广州(BCS-K8S-90001)',
                    type: 'link',
                    detail: 'https://xxxx/k8s-new/?=bcs_cluster_id=BCS-K8S-90001',
                  },
                  namespace: {
                    label: 'NameSpace',
                    value: 'kube-system',
                    alias: 'kube-system',
                    type: 'link',
                    url: 'https://xxxx/k8s-new/?=bcs_cluster_id=BCS-K8S-90001&namespace=xxx',
                  },
                  name: {
                    label: '工作负载',
                    value: 'bk-log-collector-fx97q',
                    alias: 'Pod / bk-log-collector-fx97q',
                    type: 'link',
                    url: 'https://xxxx/k8s-new/?=bcs_cluster_id=BCS-K8S-90001&namespace=xxx',
                  },
                  time: {
                    label: '开始时间',
                    value: 1736927543000,
                  },
                  duration: {
                    label: '持续时间',
                    value: 61,
                    alias: '1m1s',
                  },
                },
              },
            },
            {
              time: {
                value: 1736927543000,
                alias: 1736927543000,
              },
              domain: {
                value: 'SYSTEM',
                alias: '系统',
              },
              source: {
                value: 'HOST',
                alias: '系统/主机',
              },
              event_name: {
                value: 'oom',
                alias: '进程 OOM',
              },
              target: {
                value: '127.0.0.1',
                alias: '127.0.0.1',
                url: 'https://xxx/host/?bk_cloud_id=&bk_cloud_ip=127.0.0.1',
              },
              'event.content': {
                value: 'oom',
                alias: '发现主机（0-127.0.0.1）存在进程（chrome）OOM 异常事件',
                detail: {
                  target: {
                    label: '主机',
                    value: '127.0.0.1',
                    alias: '直连区域[0] / 127.0.0.1',
                    type: 'link',
                    url: 'https://xxxx/host/?bk_cloud_id=&bk_cloud_ip=127.0.0.1',
                  },
                  process: {
                    label: '进程',
                    value: 'chrome',
                  },
                  task_memcg: {
                    label: '任务（进程）所属的内存 cgroup',
                    value: '/pods.slice/pods-burstable.slice/pods-burstable-pod1',
                  },
                  time: {
                    label: '开始时间',
                    value: 1736927543000,
                  },
                },
              },
            },
          ],
          topk: [
            {
              domain: {
                value: 'K8S',
                alias: 'Kubernetes',
              },
              source: {
                value: 'BCS',
                alias: 'Kubernetes/BCS',
              },
              event_name: {
                value: 'FailedMount',
                alias: '卷挂载失效（FailedMount）',
              },
              count: 5,
              proportions: 50,
            },
            {
              domain: {
                value: 'SYSTEM',
                alias: '系统',
              },
              source: {
                value: 'HOST',
                alias: '系统/主机',
              },
              event_name: {
                value: 'FailedMount',
                alias: '卷挂载失效（FailedMount）',
              },
              count: 5,
              proportions: 50,
            },
          ],
        },
      }.data;
      if (mockEventCount === 1) {
        // 只有一个事件
        return resole({
          time: Date.now(),
          total: 1,
          list: mockData.list.slice(0, 1),
        });
      }

      if (isWarning) {
        // 有告警事件
        return resole({
          time: Date.now(),
          total: 100,
          list: mockData.list.slice(),
        });
      }

      return resole({
        time: Date.now(),
        total: 1,
        topk: mockData.topk,
      });
    }, 2000);
  });
  return data;
};
export const createCustomEventSeries = (list: ICustomEventTagsItem[]) => {
  if (!list.length) return {};
  return {
    type: 'custom',
    name: 'xx',
    renderItem: (params: any, api: any) => {
      const eventData: ICustomEventTagsItem['items'] = list[params.dataIndex].items;
      const x = api.coord([api.value(0), 0])[0];
      const y0 = api.coord([0, 0])[1];

      const rectangleHeight = 16 * window.devicePixelRatio; // 矩形的高度
      const circleRadius = rectangleHeight / 2; // 圆的半径
      const totalHeight = Math.max(rectangleHeight, 2 * circleRadius);
      const line = {
        type: 'line',
        shape: {
          x1: x,
          y1: y0,
          x2: x,
          y2: 20,
        },
        style: {
          stroke: '#2F567D',
          lineWidth: 1.2,
          lineDash: 'dashed',
        },
      };
      const shapeGroupList: Array<object> = [line];
      for (let i = 0; i < eventData.length; i++) {
        const { count, statistics, source } = eventData[i];
        const info = { count, statistics, source };
        const warningText = statistics.Warning ? `${statistics.Warning}` : '';
        const countText = `${count}`;
        const baseFontWith = (text: string) => (text.length > 2 ? 5.6 : 7) * text.length;
        const rectangleWidth =
          Math.max(baseFontWith(warningText) + baseFontWith(countText), 18) * window.devicePixelRatio; // 矩形的宽度
        let middleX = x - rectangleWidth / (2 * window.devicePixelRatio) - circleRadius;
        if (!warningText && count > 1) {
          middleX += 6;
        }
        const image = {
          type: 'image',
          z2: 100000,
          info,
          style: {
            image: svg[source.toLowerCase()],
            x: count > 1 ? middleX + 2 : x - 8,
            y: 3 + i * (totalHeight - 6),
            width: circleRadius,
            height: circleRadius,
          },
        };
        shapeGroupList.push(image);
        // 单个事件
        if (count < 2) {
          continue;
        }
        const pathData = `
        M ${circleRadius},${totalHeight / 2}
        a ${circleRadius},${circleRadius} 0 0,1 ${circleRadius},-${circleRadius}
        h ${rectangleWidth}
        a ${circleRadius},${circleRadius} 0 0,1 ${circleRadius},${circleRadius}
        a ${circleRadius},${circleRadius} 0 0,1 -${circleRadius},${circleRadius}
        h -${rectangleWidth}
        a ${circleRadius},${circleRadius} 0 0,1 -${circleRadius},-${circleRadius}
        Z
        `;
        const path = {
          type: 'path',
          x: middleX,
          info,
          y: -5 + i * (totalHeight - 4),
          shape: {
            pathData,
            width: rectangleWidth,
            height: rectangleHeight,
          },
          style: api.style({
            stroke: '#2F567D',
            fill: '#2F567D',
          }),
        };
        const createTextConfig = () => {
          return {
            type: 'text',
            info,
            z2: 100000,
            style: {
              text: countText,
              fill: '#fff',
              font: `bolder ${5.5 * window.devicePixelRatio}px  sans-serif`,
              overflow: 'truncate',
              ellipsis: '',
              truncateMinChar: 1,
              x: middleX + 20,
              y: 6 + i * (totalHeight - 4),
              info,
            },
            silent: true,
            textConfig: {
              position: 'insideRight',
              inside: true,
              outsideFill: 'transparent',
              info,
            },
          };
        };
        if (statistics.Warning) {
          const warningTextConfig = createTextConfig();
          warningTextConfig.style.fill = '#F8B64F';
          warningTextConfig.style.text = warningText;
          shapeGroupList.push(warningTextConfig);
          const splitTextConfig = createTextConfig();
          splitTextConfig.style = {
            ...splitTextConfig.style,
            text: '/',
            fill: '#C4C6CC',
            x: warningTextConfig.style.x + 14,
          };
          shapeGroupList.push(splitTextConfig);
          const totalTextConfig = createTextConfig();
          totalTextConfig.style = {
            ...totalTextConfig.style,
            text: countText,
            x: splitTextConfig.style.x + 6,
          };
          shapeGroupList.push(totalTextConfig);
        } else {
          shapeGroupList.push(createTextConfig());
        }
        shapeGroupList.push(path);
      }
      return {
        type: 'group',
        children: shapeGroupList,
      };
    },
    data:
      list
        ?.filter(item => item.items?.length)
        .map(item => {
          return [item.time, item.items];
        }) || [],
    silent: false,
    z: 100000,
    tooltips: false,
  };
};
