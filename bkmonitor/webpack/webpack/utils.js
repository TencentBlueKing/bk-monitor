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
const transformDistDir = app => {
  switch (app) {
    case 'mobile':
      return 'weixin';
    case 'fta':
    case 'apm':
    case 'email':
    case 'trace':
    case 'external':
      return app;
    default:
      return 'monitor';
  }
};
const transformAppDir = app => {
  switch (app) {
    case 'mobile':
      return 'monitor-mobile';
    case 'fta':
      return 'fta-solutions';
    case 'apm':
      return 'apm';
    case 'trace':
      return 'trace';
    default:
      return 'monitor-pc';
  }
};
const mobileBuildVariates = `
<script>
    window.site_url = "\${WEIXIN_SITE_URL}"
    window.static_url = "\${WEIXIN_STATIC_URL}"
    window.cc_biz_id = \${BK_BIZ_ID}
    window.user_name = "\${UIN}"
    window.csrf_cookie_name = "\${CSRF_COOKIE_NAME}"
    window.csrf_token = "\${csrf_token}"
    window.userInfo = {
        username: "\${UIN}",
        isSuperuser: \${IS_SUPERUSER},
    }
    window.ageisId = "\${TAM_ID}"
    window.graph_watermark = "\${GRAPH_WATERMARK}" == "True" ? true : false
</script>`;

const pcBuildVariates = `
<script>
window.site_url = "\${SITE_URL}"
window.static_url = "\${STATIC_URL}"
window.csrf_cookie_name = "\${CSRF_COOKIE_NAME}"
</script>`;

const externalBuildVariates = `
<script>
<%
import json
def to_json(val):
    return json.dumps(val)
%>
window.site_url = "\${SITE_URL}"
window.static_url = "\${STATIC_URL}"
window.csrf_cookie_name = "\${CSRF_COOKIE_NAME}"
window.bk_biz_ids = \${to_json(BK_BIZ_IDS) | n}
</script>`;

const mobileBuildVariatesOld = `
<script>
    window.site_url = "\${WEIXIN_SITE_URL}"
    window.static_url = "\${WEIXIN_STATIC_URL}"
    window.cc_biz_id = \${BK_BIZ_ID}
    window.user_name = "\${UIN}"
    window.csrf_cookie_name = "\${CSRF_COOKIE_NAME}"
    window.csrf_token = "\${csrf_token}"
    window.userInfo = {
        username: "\${UIN}",
        isSuperuser: \${IS_SUPERUSER},
    }
    window.ageisId = "\${TAM_ID}"
    window.graph_watermark = "\${GRAPH_WATERMARK}" == "True" ? true : false
</script>`;

const pcBuildVariatesOld = `
<script>
<%
import json
def to_json(val):
    return json.dumps(val)
%>
window.platform = {
    "te": \${to_json(PLATFORM.te)},
    "ee": \${to_json(PLATFORM.ee)},
    "ce": \${to_json(PLATFORM.ce)}
}
window.bk_biz_list = \${to_json(BK_BIZ_LIST) | n}
window.space_list = \${to_json(SPACE_LIST) | n}
window.app_code = "\${APP_CODE}"
window.enable_grafana = "\${ENABLE_GRAFANA}" == "True" ? true : false
window.site_url = "\${SITE_URL}"
window.static_url = "\${STATIC_URL}"
window.cc_biz_id = \${to_json(BK_BIZ_ID) | n}
window.csrf_cookie_name = "\${CSRF_COOKIE_NAME}"
window.csrf_token = "\${csrf_token}"
window.doc_host = "\${DOC_HOST}"
window.job_url = "\${BK_JOB_URL}"
window.cmdb_url = "\${BK_CC_URL}"
window.agent_setup_url = "\${AGENT_SETUP_URL}"
window.user_name = "\${UIN}"
window.utcOffset = \${UTC_OFFSET}
window.bk_url = "\${BK_URL}"
window.bkPaasHost = "\${BK_PAAS_HOST}"
window.bkchat_manage_url = "\${BKCHAT_MANAGE_URL}"
window.version_log_url = "version_log/"
window.userInfo = {
    username: "\${UIN}",
    isSuperuser: \${IS_SUPERUSER},
}
window.enable_message_queue = \${ENABLE_MESSAGE_QUEUE}
window.message_queue_dsn = "\${MESSAGE_QUEUE_DSN}"
window.ce_url = "\${CE_URL}"
window.max_available_duration_limit = \${MAX_AVAILABLE_DURATION_LIMIT}
window.bk_log_search_url = "\${BKLOGSEARCH_HOST}"
window.bk_nodeman_host = "\${BK_NODEMAN_HOST}"
window.graph_watermark = "\${GRAPH_WATERMARK}" == "True" ? true : false
window.ageisId = "\${TAM_ID}"
window.mail_report_biz = "\${MAIL_REPORT_BIZ}"
window.enable_aiops =  \${ENABLE_AIOPS}
window.enable_apm = \${ENABLE_APM}
window.collecting_config_file_maxsize = \${COLLECTING_CONFIG_FILE_MAXSIZE}
window.enable_cmdb_level = "\${ENABLE_CMDB_LEVEL}" == "True" ? true : false
window.bk_docs_site_url = "\${BK_DOCS_SITE_URL}"
window.migrate_guide_url = "\${MIGRATE_GUIDE_URL}"
window.bk_bcs_url = "\${BK_BCS_URL}"
window.enable_create_chat_group = "\${ENABLE_CREATE_CHAT_GROUP}" == "True" ? true : false
window.is_container_mode = "\${IS_CONTAINER_MODE}" == "True" ? true : false
window.space_introduce = \${to_json(SPACE_INTRODUCE) | n}
window.monitor_managers = \${to_json(MONITOR_MANAGERS) | n}
window.cluster_setup_url = "\${CLUSTER_SETUP_URL}"
window.loginUrl = "\${LOGIN_URL}"
window.uptimecheck_out_fields =\${to_json(UPTIMECHECK_OUTPUT_FIELDS) | n}
window.wxwork_bot_send_image = "\${WXWORK_BOT_SEND_IMAGE}" == "True" ? true : false
window.host_data_fields = \${to_json(HOST_DATA_FIELDS) | n}
window.bk_component_api_url = "\${BK_COMPONENT_API_URL}"
window.bk_domain = "\${BK_DOMAIN}"
window.show_realtime_strategy = "\${SHOW_REALTIME_STRATEGY}" == "True" ? true : false
window.apm_ebpf_enabled = \${APM_EBPF_ENABLED}
window.enable_apm_profiling = \${ENABLE_APM_PROFILING}
window.bk_shared_res_url = \${BK_SHARED_RES_URL}
window.footer_version = \${FOOTER_VERSION}
</script>`;
const externalBuildVariatesOld = `
<script>
<%
import json
def to_json(val):
    return json.dumps(val)
%>
window.platform = {
    "te": \${to_json(PLATFORM.te)},
    "ee": \${to_json(PLATFORM.ee)},
    "ce": \${to_json(PLATFORM.ce)}
}
window.bk_biz_list = \${to_json(BK_BIZ_LIST) | n}
window.space_list = \${to_json(SPACE_LIST) | n}
window.app_code = "\${APP_CODE}"
window.enable_grafana = "\${ENABLE_GRAFANA}" == "True" ? true : false
window.site_url = "\${SITE_URL}"
window.static_url = "\${STATIC_URL}"
window.cc_biz_id = \${BK_BIZ_ID}
window.csrf_cookie_name = "\${CSRF_COOKIE_NAME}"
window.csrf_token = "\${csrf_token}"
window.user_name = "\${external_user}"
window.userInfo = {
  username: "\${external_user}",
  isSuperuser: \${IS_SUPERUSER},
}
window.enable_message_queue = \${ENABLE_MESSAGE_QUEUE}
window.message_queue_dsn = "\${MESSAGE_QUEUE_DSN}"
window.max_available_duration_limit = \${MAX_AVAILABLE_DURATION_LIMIT}
window.graph_watermark = "\${GRAPH_WATERMARK}" == "True" ? true : false
window.mail_report_biz = "\${MAIL_REPORT_BIZ}"
window.enable_aiops =  \${ENABLE_AIOPS}
window.enable_apm = \${ENABLE_APM}
window.collecting_config_file_maxsize = \${COLLECTING_CONFIG_FILE_MAXSIZE}
window.enable_cmdb_level = "\${ENABLE_CMDB_LEVEL}" == "True" ? true : false
window.enable_create_chat_group = "\${ENABLE_CREATE_CHAT_GROUP}" == "True" ? true : false
window.is_container_mode = "\${IS_CONTAINER_MODE}" == "True" ? true : false
window.space_introduce = \${to_json(SPACE_INTRODUCE) | n}
window.monitor_managers = \${to_json(MONITOR_MANAGERS) | n}
window.uptimecheck_out_fields =\${to_json(UPTIMECHECK_OUTPUT_FIELDS) | n}
window.wxwork_bot_send_image = "\${WXWORK_BOT_SEND_IMAGE}" == "True" ? true : false
window.host_data_fields = \${to_json(HOST_DATA_FIELDS) | n}
</script>`;
module.exports = {
  transformDistDir,
  transformAppDir,
  mobileBuildVariates,
  pcBuildVariates,
  externalBuildVariates,
};
