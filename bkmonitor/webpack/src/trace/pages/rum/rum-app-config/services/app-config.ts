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

import {
  deleteApplication,
  getApplicationInfoByAppName,
  getIndicesInfo,
  getStorageInfo,
  listEsClusterGroups,
  queryRumTokenInfo,
  setupApplication,
  startDataSource,
  stopDataSource,
  storageFieldInfo,
} from 'monitor-api/modules/rum_meta';

import type { ApplicationOperationType, IIndicesInfo, IStorageField, IStorageInfo } from '../../typings/rum-app-config';

/** 应用基础请求参数 */
interface IAppBaseParams {
  app_name: string;
  bk_biz_id: number;
}

/** 更新 Apdex 配置参数 */
interface IUpdateApdexConfigParams extends IAppBaseParams {
  application_qps_config: number;
  application_apdex_config: {
    apdex_api_request: number;
    apdex_view_load: number;
  };
}

/** 更新应用基本信息参数 */
interface IUpdateAppBasicInfoParams extends IAppBaseParams {
  app_alias: string;
  description: string;
}

/** 更新存储配置参数 */
interface IUpdateStorageConfigParams extends IAppBaseParams {
  span_datasource_config: IStorageInfo;
}

/**
 * 获取应用配置信息
 * @param appName 应用名称
 */
export const getAppConfigByAppName = async (appName: string) => {
  return getApplicationInfoByAppName({ app_name: appName });
};

/**
 * 获取 ES 集群列表
 */
export const getEsClusterList = async () => {
  return listEsClusterGroups().catch(() => []);
};

/**
 * 查询应用 TOKEN
 * @param applicationId 应用ID
 */
export const queryAppToken = async (params: { app_name: string; bk_biz_id: number }) => {
  return queryRumTokenInfo(params).catch(() => '');
};

/**
 * 更新应用基本信息（别名、描述）
 * @param params 更新参数
 */
export const updateAppBasicInfo = async (params: IUpdateAppBasicInfoParams) => {
  return setupApplication(params);
};

/**
 * 更新应用 Apdex 和 QPS 配置
 * @param params 更新参数
 */
export const updateAppApdexConfig = async (params: IUpdateApdexConfigParams) => {
  return setupApplication(params);
};

/**
 * 更新应用存储配置
 * @param params 更新参数
 */
export const updateAppStorageConfig = async (params: IUpdateStorageConfigParams) => {
  return setupApplication(params);
};

/**
 * 执行应用操作（启用/停用/删除）
 * @param type 操作类型
 * @param params 应用基础参数
 */
export const operateApplication = async (type: ApplicationOperationType, params: IAppBaseParams) => {
  const operationApiMap: Record<ApplicationOperationType, (params: IAppBaseParams) => Promise<unknown>> = {
    stop: stopDataSource,
    delete: deleteApplication,
    start: startDataSource,
  };
  return operationApiMap[type](params);
};

/**
 * 获取存储信息
 * @param params 应用基础参数
 * @param fallback 存储信息兜底数据
 */
export const getStorageInfoData = async (params: IAppBaseParams, fallback?: IStorageInfo) => {
  return getStorageInfo(params).catch(
    () =>
      fallback ?? {
        es_number_of_replicas: 0,
        es_retention: 14,
        es_shards: 3,
        es_slice_size: 100,
        es_storage_cluster: '',
      }
  );
};

/**
 * 获取物理索引数据
 * @param params 应用基础参数
 */
export const getIndicesInfoData = async (params: Pick<IAppBaseParams, 'app_name'>) => {
  return getIndicesInfo(params).catch(() => [] as IIndicesInfo[]);
};

/**
 * 获取字段信息数据
 * @param params 应用基础参数
 */
export const getFieldInfoData = async (params: IAppBaseParams) => {
  return storageFieldInfo(params).catch(() => [] as IStorageField[]);
};
