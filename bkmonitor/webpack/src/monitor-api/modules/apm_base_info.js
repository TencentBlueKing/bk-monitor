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
import { request } from '../base';

export const serviceInfo = request('POST', 'apm/service/service/service_info/'); // 获取服务信息
export const CMDBInfoList = request('POST', 'apm/service/service/cmdb_service_template/');// 获取CMDB服务模板列表
export const applicationList = request('POST', 'apm/service/application/application_list/');// 获取业务下应用列表
export const setCMDBInfo = request('POST', 'apm/service/service/cmdb_service_relation/'); // 获取/设置/删除 服务与CMDB服务模板的关联信息
export const setAppInfo = request('POST', 'apm/service/service/app_service_relation/'); // 获取/设置/删除 服务与业务应用的关联信息
export const setLogsInfo = request('POST', 'apm/service/service/log_service_relation/'); // 获取/设置/删除 服务与日志的关联信息
export const logList = request('POST', 'apm/service/service/log_service_relation_choices/');

export default {
  serviceInfo,
  CMDBInfoList,
  applicationList,
  setCMDBInfo,
  setAppInfo,
  setLogsInfo,
  logList
};
