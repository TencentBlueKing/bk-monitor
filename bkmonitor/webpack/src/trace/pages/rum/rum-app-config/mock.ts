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
import type { IRumAppConfig } from '../typings/rum-app-config';

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
 * 切换应用总开关
 * @param applicationId 应用 ID
 * @param isEnabled 是否启用
 * @returns Promise<{ success: boolean }>
 */
export function toggleRumAppStatus(applicationId: number, isEnabled: boolean): Promise<{ success: boolean }> {
  return new Promise(resolve => {
    setTimeout(() => {
      console.log(`应用 ${applicationId} 状态切换为: ${isEnabled}`);
      resolve({ success: true });
    }, 200);
  });
}

/**
 * 更新 RUM 应用配置
 * @param applicationId 应用 ID
 * @param config 应用配置
 * @returns Promise<IRumAppConfig>
 */
export function updateRumAppConfig(applicationId: number, config: Partial<IRumAppConfig>): Promise<IRumAppConfig> {
  return new Promise(resolve => {
    setTimeout(() => {
      resolve({
        ...RUM_APP_CONFIG_MOCK,
        application_id: applicationId,
        ...config,
        update_time: new Date().toISOString(),
      });
    }, 300);
  });
}
