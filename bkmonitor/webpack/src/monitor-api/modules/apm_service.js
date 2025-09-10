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
import { request } from '../base';

export const serviceConfig = request('POST', 'apm/service/service/service_config/');
export const serviceInfo = request('POST', 'apm/service/service/service_info/');
export const listCodeRedefinedRule = request('POST', 'apm/service/service/list_code_redefined_rule/');
export const setCodeRedefinedRule = request('POST', 'apm/service/service/set_code_redefined_rule/');
export const deleteCodeRedefinedRule = request('POST', 'apm/service/service/delete_code_redefined_rule/');
export const getCodeRemarks = request('POST', 'apm/service/service/get_code_remarks/');
export const setCodeRemark = request('POST', 'apm/service/service/set_code_remark/');
export const cmdbServiceTemplate = request('POST', 'apm/service/service/cmdb_service_template/');
export const logServiceChoiceList = request('POST', 'apm/service/service/log_service_relation_choices/');
export const appQueryByIndexSet = request('POST', 'apm/service/service/app_query_by_index_set/');
export const uriregularVerify = request('POST', 'apm/service/service/uri_regular/');
export const serviceUrlList = request('POST', 'apm/service/service/service_url_list/');
export const pipelineOverview = request('POST', 'apm/service/service/pipeline_overview/');
export const listPipeline = request('POST', 'apm/service/service/list_pipeline/');
export const applicationList = request('POST', 'apm/service/application/application_list/');
export const logServiceRelationBkLogIndexSet = request('POST', 'apm/service/application/log_service_relation_bk_log_index_set/');

export default {
  serviceConfig,
  serviceInfo,
  listCodeRedefinedRule,
  setCodeRedefinedRule,
  deleteCodeRedefinedRule,
  getCodeRemarks,
  setCodeRemark,
  cmdbServiceTemplate,
  logServiceChoiceList,
  appQueryByIndexSet,
  uriregularVerify,
  serviceUrlList,
  pipelineOverview,
  listPipeline,
  applicationList,
  logServiceRelationBkLogIndexSet,
};
