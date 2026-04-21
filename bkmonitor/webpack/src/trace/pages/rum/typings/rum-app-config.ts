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

// TODO 等待后端确认这些子类型具体的值

/**
 * Apdex 配置
 */
export type IApdexConfig = Record<string, number>;

/**
 * 权限信息
 */
export type IPermission = Record<string, unknown>;

/**
 * QPS 配置
 */
export type IQpsConfig = Record<string, number>;

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
  application_qps_config: IQpsConfig | null;
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

/**
 * Span 存储配置
 */
export type ISpanDatasourceConfig = Record<string, unknown>;
