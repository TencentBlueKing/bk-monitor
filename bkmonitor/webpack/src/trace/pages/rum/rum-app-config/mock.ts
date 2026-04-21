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

/**
 * 索引信息 Mock 数据
 */
export const INDICES_INFO_MOCK: IIndicesInfo = {
  docs_count: 1250000,
  docs_deleted: 500,
  health: 'green',
  index: 'rum_span_2025.01.15',
  pri: 5,
  pri_store_size: 1073741824,
  rep: 1,
  status: 'open',
  store_size: 2147483648,
  uuid: 'a1b2c3d4e5f6',
};

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
};

/**
 * ============================================
 * 存储字段相关接口 Mock
 * ============================================
 */

/**
 * 存储字段 Mock 数据列表
 */
export const STORAGE_FIELD_LIST_MOCK: IStorageField[] = [
  {
    analysis_field: false,
    ch_field_name: 'Span ID',
    field_name: 'span_id',
    field_type: 'keyword',
    time_field: false,
  },
  {
    analysis_field: false,
    ch_field_name: 'Trace ID',
    field_name: 'trace_id',
    field_type: 'keyword',
    time_field: false,
  },
  {
    analysis_field: false,
    ch_field_name: '时间戳',
    field_name: 'timestamp',
    field_type: 'date',
    time_field: true,
  },
  {
    analysis_field: true,
    ch_field_name: '服务名',
    field_name: 'service_name',
    field_type: 'text',
    time_field: false,
  },
  {
    analysis_field: true,
    ch_field_name: '操作名',
    field_name: 'operation_name',
    field_type: 'text',
    time_field: false,
  },
];

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
 * @param params 请求参数 { app_name: string; bk_biz_id: number }
 * @returns Promise<IIndicesInfo>
 */
export function getIndicesInfoMock(params: { app_name: string; bk_biz_id: number }): Promise<IIndicesInfo> {
  console.log('getIndicesInfoMock params:', params);
  return new Promise(resolve => {
    setTimeout(() => {
      resolve({ ...INDICES_INFO_MOCK });
    }, 300);
  });
}

/**
 * 获取 RUM 应用配置
 * @returns Promise<IRumAppConfig>
 */
export function getRumAppConfigMock(params: { app_name: string; is_get_detail: boolean }): Promise<IRumAppConfig> {
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
 * @param params 请求参数 { bk_biz_id: number }
 * @returns Promise<IStorageField[]>
 */
export function getStorageFieldMock(params: { bk_biz_id: number }): Promise<IStorageField[]> {
  console.log('getStorageFieldMock params:', params);
  return new Promise(resolve => {
    setTimeout(() => {
      resolve([...STORAGE_FIELD_LIST_MOCK]);
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
