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
import { request } from 'monitor-api/base';

import type { IIndicesInfo, IRumAppConfig, IStorageField, IStorageInfo } from '../typings/rum-app-config';

/** 获取存储信息 */
export const storageInfo = request('post', 'rum/meta/application/storage_info/');

/** 获取索引信息 */
export const indicesInfo = request('post', 'rum/meta/application/indices_info/');

/** 获取存储字段 */
export const storageField = request('post', 'rum/meta/application/storage_field/');

/**
 * ============================================
 * 索引信息相关接口 Mock
 * ============================================
 */

const HEALTH_STATUS = ['green', 'yellow', 'red'] as const;

/**
 * 生成索引信息列表
 * @param count 数量，默认为 10
 * @returns IIndicesInfo[]
 */
export function generateIndicesInfoList(count = 10): IIndicesInfo[] {
  return Array.from({ length: count }, (_, i) => generateIndicesInfo(i + 1));
}

/**
 * 生成单个索引信息
 * @param index 索引序号
 * @returns IIndicesInfo
 */
function generateIndicesInfo(index: number): IIndicesInfo {
  const health = HEALTH_STATUS[index % 3];
  const date = new Date();
  const dateStr = date.toISOString().slice(0, 10).replace(/-/g, '');
  const docsCount = Math.floor(Math.random() * 1000000) + 10000;
  const storeSize = Math.floor(Math.random() * 5000000000) + 100000000;

  return {
    docs_count: docsCount,
    docs_deleted: Math.floor(docsCount * 0.01),
    health,
    index: `v2_apm_global_shared_trace_${String(index).padStart(4, '0')}_${dateStr}_${index % 5}`,
    pri: Math.floor(Math.random() * 5) + 1,
    pri_store_size: Math.floor(storeSize * 0.4),
    rep: Math.floor(Math.random() * 3) + 1,
    status: 'open',
    store_size: storeSize,
    uuid: `${Math.random().toString(36).substring(2, 8)}${Math.random().toString(36).substring(2, 8)}`,
  };
}

/**
 * 索引信息 Mock 数据（默认10条）
 */
export const INDICES_INFO_MOCK: IIndicesInfo[] = generateIndicesInfoList(10);

/**
 * ============================================
 * RUM 应用配置相关接口 Mock
 * ============================================
 */

/**
 * RUM 应用配置 Mock 数据
 */
export const RUM_APP_CONFIG_MOCK: IRumAppConfig = {
  application_id: 1,
  bk_biz_id: 2,
  app_name: 'web_official',
  app_alias: 'Web 端官网',
  description: '企业官网 Web 端性能监控应用',
  client_type: 'web',
  is_enabled: true,
  application_apdex_config: {
    load: 1000,
    request: 500,
  },
  application_qps_config: {
    qps: 1000,
  },
  span_datasource_config: {
    datasource_id: 1,
    datasource_name: 'elasticsearch',
    cluster_name: 'rum-span-cluster',
    retention_days: 7,
  },
  span_result_table_id: 'rum_span_xxx',
  metric_result_table_id: 'rum_metric_xxx',
  time_series_group_id: 123,
  data_status: 'healthy',
  no_data_period: 300,
  create_user: 'admin',
  create_time: '2025-01-15 10:30:00',
  update_user: 'admin',
  update_time: '2025-04-16 14:20:00',
  permission: {
    view: true,
    edit: true,
    delete: false,
  },
  bk_tenant_id: 1,
  es_storage_index_name: 'apm_global_shared_trace_0001',
};

/**
 * ============================================
 * 存储字段相关接口 Mock
 * ============================================
 */

const FIELD_TEMPLATES = [
  { field_name: 'span_id', ch_field_name: 'Span ID', field_type: 'keyword', analysis_field: false, time_field: false },
  {
    field_name: 'trace_id',
    ch_field_name: 'Trace ID',
    field_type: 'keyword',
    analysis_field: false,
    time_field: false,
  },
  { field_name: 'timestamp', ch_field_name: '时间戳', field_type: 'date', analysis_field: false, time_field: true },
  { field_name: 'service_name', ch_field_name: '服务名', field_type: 'text', analysis_field: true, time_field: false },
  {
    field_name: 'operation_name',
    ch_field_name: '操作名',
    field_type: 'text',
    analysis_field: true,
    time_field: false,
  },
  { field_name: 'duration', ch_field_name: '持续时间', field_type: 'long', analysis_field: false, time_field: false },
  {
    field_name: 'status_code',
    ch_field_name: '状态码',
    field_type: 'integer',
    analysis_field: false,
    time_field: false,
  },
  { field_name: 'error', ch_field_name: '错误信息', field_type: 'text', analysis_field: true, time_field: false },
  { field_name: 'host_ip', ch_field_name: '主机IP', field_type: 'ip', analysis_field: false, time_field: false },
  {
    field_name: 'container_id',
    ch_field_name: '容器ID',
    field_type: 'keyword',
    analysis_field: false,
    time_field: false,
  },
  { field_name: 'pod_name', ch_field_name: 'Pod名称', field_type: 'keyword', analysis_field: false, time_field: false },
  {
    field_name: 'namespace',
    ch_field_name: '命名空间',
    field_type: 'keyword',
    analysis_field: false,
    time_field: false,
  },
];

/**
 * 生成存储字段列表
 * @param count 数量，默认为 20
 * @returns IStorageField[]
 */
export function generateStorageFieldList(count = 20): IStorageField[] {
  return Array.from({ length: count }, (_, i) => generateStorageField(i));
}

/**
 * 生成单个存储字段
 * @param index 索引序号
 * @returns IStorageField
 */
function generateStorageField(index: number): IStorageField {
  const template = FIELD_TEMPLATES[index % FIELD_TEMPLATES.length];
  const suffix = index >= FIELD_TEMPLATES.length ? `_${Math.floor(index / FIELD_TEMPLATES.length)}` : '';

  return {
    ...template,
    field_name: `${template.field_name}${suffix}`,
    ch_field_name: `${template.ch_field_name}${suffix}`,
  };
}

/**
 * 存储字段 Mock 数据列表（默认20条）
 */
export const STORAGE_FIELD_LIST_MOCK: IStorageField[] = generateStorageFieldList(20);

/**
 * ============================================
 * 存储信息相关接口 Mock
 * ============================================
 */

/**
 * 存储信息 Mock 数据
 */
export const STORAGE_INFO_MOCK: IStorageInfo = {
  es_number_of_replicas: 1,
  es_retention: 7,
  es_shards: 3,
  es_slice_size: 100,
  es_storage_cluster: 'es-cluster-01',
};

/**
 * ============================================
 * Mock 函数
 * ============================================
 */

/**
 * 获取索引信息
 * @param params 请求参数 { app_name: string; count?: number }
 * @returns Promise<IIndicesInfo>
 */
export function getIndicesInfoMock(params: { app_name: string; count?: number }): Promise<IIndicesInfo[]> {
  console.log('getIndicesInfoMock params:', params);
  const count = params.count || 10;
  return new Promise(resolve => {
    setTimeout(() => {
      resolve(generateIndicesInfoList(count));
    }, 300);
  });
}

/**
 * 获取 RUM 应用配置
 * @returns Promise<IRumAppConfig>
 */
export function getRumAppConfigMock(params: { app_name: string }): Promise<IRumAppConfig> {
  return new Promise(resolve => {
    // 模拟网络延迟
    setTimeout(() => {
      resolve({
        ...RUM_APP_CONFIG_MOCK,
        app_name: params.app_name,
      });
    }, 300);
  });
}

/**
 * 获取存储字段列表
 * @param params 请求参数 { count?: number }
 * @returns Promise<IStorageField[]>
 */
export function getStorageFieldMock(params?: { count?: number }): Promise<IStorageField[]> {
  const count = params?.count || 20;
  return new Promise(resolve => {
    setTimeout(() => {
      resolve(generateStorageFieldList(count));
    }, 300);
  });
}

/**
 * 获取存储信息
 * @param params 请求参数 { bk_biz_id: number; app_name: string }
 * @returns Promise<IStorageInfo>
 */
export function getStorageInfoMock(params: { app_name: string; bk_biz_id: number }): Promise<IStorageInfo> {
  console.log('getStorageInfoMock params:', params);
  return new Promise(resolve => {
    setTimeout(() => {
      resolve({ ...STORAGE_INFO_MOCK });
    }, 300);
  });
}
