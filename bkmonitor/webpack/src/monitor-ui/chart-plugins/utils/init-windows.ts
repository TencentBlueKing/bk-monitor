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
// 初始化日志检索的windows字段
export const initLogRetrieveWindowsFields = () => {
  window.AJAX_URL_PREFIX = '/apm_log_forward/bklog/api/v1';
  window.BK_DOC_URL = window.bk_docs_site_url;
  window.FEATURE_TOGGLE = {
    //   scenario_log: 'on',
    //   scenario_bkdata: 'on',
    //   scenario_es: 'on',
    //   es_type_object: 'on',
    //   es_type_nested: 'on',
    //   bkdata_token_auth: 'off',
    //   extract_cos: 'off',
    //   collect_itsm: 'off',
    //   monitor_report: 'on',
    //   bklog_es_config: 'on',
    //   check_collector_custom_config: 'on',
    //   trace: 'off',
    //   log_desensitize: 'on',
    //   bk_log_trace: 'on',
    //   bk_log_to_trace: 'on',
    bkdata_aiops_toggle: 'on',
    //   bk_custom_report: 'on',
    //   es_cluster_type_setup: 'on',
    //   feature_bkdata_dataid: 'on',
    // //   is_auto_deploy_plugin: 'on',
    field_analysis_config: 'on',
    //   direct_esquery_search: 'on',
    //   bklog_search_new: 'on',
  };
  // window.FIELD_ANALYSIS_CONFIG = [];
  // window.FEATURE_TOGGLE_WHITE_LIST = {};
};
