/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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

/** 列表行（对接接口后由服务端类型替换） */
export interface RumAppRow {
  accessStatus: string;
  alias: string;
  apiFailRate: null | number;
  appStatus: string;
  createdAt: number;
  creator: string;
  dataStatus: 'abnormal' | 'healthy';
  domain: string;
  id: string;
  jsErrorRate: null | number;
  lcpP75Sec: null | number;
  updatedAt: number;
  updater: string;
}

/** 设计稿示例数据，用于 UI 联调；接入 API 后删除 */
export const RUM_APP_LIST_MOCK: RumAppRow[] = [
  {
    id: '1',
    domain: 'www.example.com',
    alias: 'Web 端官网',
    lcpP75Sec: 1.8,
    jsErrorRate: 0.3,
    apiFailRate: 1.5,
    dataStatus: 'healthy',
    accessStatus: '已接入',
    appStatus: '启用',
    creator: 'zhangsan',
    updater: 'lisi',
    createdAt: Date.now() - 86400000 * 30,
    updatedAt: Date.now() - 3600000,
  },
  {
    id: '2',
    domain: 'event.example.com',
    alias: '活动专题页',
    lcpP75Sec: 1.7,
    jsErrorRate: 0.2,
    apiFailRate: 0.8,
    dataStatus: 'healthy',
    accessStatus: '已接入',
    appStatus: '启用',
    creator: 'wangwu',
    updater: 'wangwu',
    createdAt: Date.now() - 86400000 * 20,
    updatedAt: Date.now() - 7200000,
  },
  {
    id: '3',
    domain: 'bkiam.woa.com',
    alias: '权限中心',
    lcpP75Sec: null,
    jsErrorRate: 0.1,
    apiFailRate: 2.2,
    dataStatus: 'abnormal',
    accessStatus: '已接入',
    appStatus: '启用',
    creator: 'system',
    updater: 'ops',
    createdAt: Date.now() - 86400000 * 90,
    updatedAt: Date.now() - 86400000,
  },
  {
    id: '4',
    domain: 'bkjob.woa.com',
    alias: '作业平台',
    lcpP75Sec: 2.4,
    jsErrorRate: 1.2,
    apiFailRate: 4.5,
    dataStatus: 'healthy',
    accessStatus: '接入中',
    appStatus: '启用',
    creator: 'dev',
    updater: 'dev',
    createdAt: Date.now() - 86400000 * 10,
    updatedAt: Date.now() - 600000,
  },
  {
    id: '5',
    domain: 'bkbase.woa.com',
    alias: '运维基础计算平台',
    lcpP75Sec: 3.2,
    jsErrorRate: 2.0,
    apiFailRate: 6.0,
    dataStatus: 'abnormal',
    accessStatus: '已接入',
    appStatus: '停用',
    creator: 'admin',
    updater: 'admin',
    createdAt: Date.now() - 86400000 * 200,
    updatedAt: Date.now() - 86400000 * 2,
  },
  {
    id: '6',
    domain: 'bk-cmdb.woa.com',
    alias: '配置平台',
    lcpP75Sec: 1.2,
    jsErrorRate: 0.05,
    apiFailRate: 0.4,
    dataStatus: 'healthy',
    accessStatus: '已接入',
    appStatus: '启用',
    creator: 'cmdb',
    updater: 'cmdb',
    createdAt: Date.now() - 86400000 * 400,
    updatedAt: Date.now() - 1800000,
  },
  {
    id: '7',
    domain: 'bkmonitor.woa.com',
    alias: '监控平台',
    lcpP75Sec: 1.5,
    jsErrorRate: 0.4,
    apiFailRate: 1.1,
    dataStatus: 'healthy',
    accessStatus: '已接入',
    appStatus: '启用',
    creator: 'monitor',
    updater: 'monitor',
    createdAt: Date.now() - 86400000 * 500,
    updatedAt: Date.now() - 900000,
  },
];

/** 生成与设计稿分页一致的数据量（198 条），前 7 条与稿面示例一致 */
export function buildRumDemoRows(): RumAppRow[] {
  const base = RUM_APP_LIST_MOCK;
  return Array.from({ length: 198 }, (_, i) => {
    const tmpl = base[i % base.length];
    if (i < base.length) {
      return { ...tmpl };
    }
    return {
      ...tmpl,
      id: String(i + 1),
      domain: `demo-${i + 1}.${tmpl.domain}`,
      alias: `${tmpl.alias}（${i + 1}）`,
    };
  });
}
