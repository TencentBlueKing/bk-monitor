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

/** 应用操作类型 */
export type ApplicationOperationType = 'delete' | 'start' | 'stop';

// TODO 等待后端确认这些子类型具体的值

/**
 * Apdex 配置
 */
export type IApdexConfig = {
  apdex_api_request: number;
  apdex_view_load: number;
};

/**
 * 索引信息接口返回数据
 */
export interface IIndicesInfo {
  /** 删除文档数 */
  docs_count: number;
  /** 文档数 */
  docs_deleted: number;
  /** 索引健康状态 */
  health: string;
  /** 索引名 */
  index: string;
  /** 主分片存储体积，字节 */
  pri: number;
  /** 主分片数 */
  pri_store_size: number;
  /** 副本数 */
  rep: number;
  /** 存储体积，字节 */
  status: string;
  /** 索引状态 */
  store_size: number;
  /** 索引 UUID */
  uuid: string;
}

/**
 * 权限信息
 */
export type IPermission = Record<string, boolean>;

/**
 * RUM 应用配置接口
 */
export interface IRumAppConfig {
  /** 展示名称 */
  app_alias: string;
  /** 应用名称 */
  app_name: string;
  /** 当前 Apdex 配置 */
  application_apdex_config: IApdexConfig | null;
  /** 应用 ID */
  application_id: number;
  /** 当前 qps 配置 */
  application_qps_config: number;
  /** 业务 ID */
  bk_biz_id: number;
  /** 租户 ID */
  bk_tenant_id: number;
  /** 前端类型 */
  client_type: string;
  /** 创建时间 */
  create_time: string;
  /** 创建人 */
  create_user: string;
  /** 数据状态 */
  data_status: string;
  /** 描述 */
  description: string;
  es_storage_index_name: string;
  /** 应用总开关 */
  is_enabled: boolean;
  /** 指标结果表 */
  metric_result_table_id: string;
  /** 无数据判定周期 */
  no_data_period: number;
  /** 权限信息，可选 */
  permission?: IPermission;
  /** span 存储配置快照，可选 */
  span_datasource_config?: ISpanDatasourceConfig;
  /** span 原始结果表 */
  span_result_table_id: string;
  /** 时序分组 */
  time_series_group_id: number;
  /** 更新时间 */
  update_time: string;
  /** 更新人 */
  update_user: string;
}

export interface IRumApplicationSetupRequestParams {
  app_alias?: string;
  app_name: string;
  application_apdex_config?: IApdexConfig;
  application_qps_config?: number;
  bk_biz_id: number;
  description?: string;
  span_datasource_config?: IStorageInfo;
}

/**
 * ============================================
 * 存储信息相关类型
 * ============================================
 */

/**
 * Span 存储配置
 */
export type ISpanDatasourceConfig = Record<string, unknown>;

/**
 * ============================================
 * 索引信息相关类型
 * ============================================
 */

/**
 * 存储字段接口返回数据
 */
export interface IStorageField {
  /** 是否分词 */
  analysis_field: boolean;
  /** 别名 */
  ch_field_name: string;
  /** 字段名 */
  field_name: string;
  /** 数据类型 */
  field_type: string;
  /** 是否时间字段 */
  time_field: boolean;
}

/**
 * ============================================
 * 存储字段相关类型
 * ============================================
 */

/**
 * 存储信息接口返回数据
 */
export interface IStorageInfo {
  /** 副本数 */
  es_number_of_replicas: number;
  /** 保留天数 */
  es_retention: number;
  /** 分片数 */
  es_shards: number;
  /** 切分大小 */
  es_slice_size: number;
  /** 存储集群 ID */
  es_storage_cluster: number | string;
}
