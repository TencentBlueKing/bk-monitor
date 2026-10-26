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

import { createServer } from 'node:http';

const port = Number(process.env.AAFE_V2_MOCK_PORT || 41091);

const space = {
  bk_biz_id: '2',
  space_uid: 'bkcc__2',
  space_id: '2',
  space_name: '蓝鲸',
  space_code: 'bkcc',
  space_type_id: 'bkcc',
  permission: { view_business_v2: true },
};

const indexSet = {
  index_set_id: 1,
  index_set_name: 'nginx-access',
  scenario_id: 'log',
  collector_config_id: 1,
  permission: { search_log: true },
  support_doris: true,
  auth_wieght: 2,
  indices: [{ result_table_id: '2_bklog.nginx' }],
  children: [],
};

const favoriteGroups = [
  {
    group_id: 1,
    group_name: '个人收藏',
    group_type: 'private',
    favorites: [
      {
        id: 11,
        name: '错误日志',
        index_set_id: 1,
        index_set_name: 'nginx-access',
        params: { keyword: 'error', host_scopes: {}, addition: [], search_mode: 'ui' },
      },
    ],
  },
  {
    group_id: 2,
    group_name: '公共收藏',
    group_type: 'public',
    favorites: [],
  },
];

const collectors = [
  {
    collector_config_id: 1,
    collector_config_name: 'nginx-access',
    table_id: '2_bklog.nginx',
    category_id: 'os',
    environment: 'linux',
    status: 'running',
    target_nodes: [],
  },
];

function ok(data) {
  return { result: true, code: 0, message: '', data };
}

const envConstant = {
  SITE_URL: '/',
  AJAX_URL_PREFIX: '/api/v1',
  BK_STATIC_URL: '/',
  LOGIN_SERVICE_URL: '/login/',
  MONITOR_URL: '/',
  BKDATA_URL: '/',
  COLLECTOR_GUIDE_URL: '/',
  FEATURE_TOGGLE: JSON.stringify({
    retrieve_v3: 'on',
    log_manage_v2: 'on',
    scene_search: 'off',
    bkdata_aiops_toggle: 'off',
    log_desensitize: 'off',
    ai_assistant: 'off',
    collect_itsm: 'off',
  }),
  FEATURE_TOGGLE_WHITE_LIST: '{}',
  FEATURE_TOGGLE_BLACK_LIST: '{}',
  SPACE_UID_WHITE_LIST: '[]',
  FIELD_ANALYSIS_CONFIG: '{}',
  REAL_TIME_LOG_MAX_LENGTH: '20000',
  REAL_TIME_LOG_SHIFT_LENGTH: '500',
  RUN_VER: 'ce',
  TITLE_MENU: '日志平台',
  MENU_LOGO_URL: '',
  APP_CODE: 'bk_log_search',
  BK_DOC_URL: '/',
  BK_FAQ_URL: '/',
  BK_DOC_QUERY_URL: '/',
  BK_HOT_WARM_CONFIG_URL: '/',
  BIZ_ACCESS_URL: '/',
  DEMO_BIZ_ID: 0,
  ES_STORAGE_CAPACITY: '0',
  TAM_AEGIS_KEY: '',
  BK_LOGIN_URL: '/login/',
  BK_DOC_DATA_URL: '/',
  BK_PLAT_HOST: '/',
  BK_ARCHIVE_DOC_URL: '/',
  BK_ETL_DOC_URL: '/',
  ASSESSMEN_HOST_COUNT: 0,
  ENABLE_CHECK_COLLECTOR: false,
  IS_EXTERNAL: false,
  BCS_WEB_CONSOLE_DOMAIN: '/',
  VERSION: 'local-mock',
  BK_SHARED_RES_URL: '',
  BK_PAAS_API_HOST: '/',
  BK_USER_URL: '/',
};

const globals = {
  log_built_in_field: [],
  category: [{ id: 'os', name: 'OS' }],
  data_encoding: [{ id: 'UTF-8', name: 'UTF-8' }],
  storage_duration_time: [{ id: '7', name: '7天' }],
  etl_config: [],
  host_paths: [],
};

function payload(url) {
  if (url.includes('/meta/index_html_environment')) return ok(envConstant);
  if (url.includes('/meta/spaces/mine/')) return ok([space]);
  if (url.includes('/meta/projects/mine/')) return ok([]);
  if (url.includes('/meta/menu/')) return ok([]);
  if (url.includes('/meta/user_guide/')) return ok({});
  if (url.includes('/meta/globals/')) return ok(globals);
  if (url.includes('/meta/language/') || url.includes('/meta/scenario/')) return ok([]);
  if (url.includes('/meta/mine/') || url.includes('/api/user/')) {
    return ok({ username: 'mock', chname: 'Mock', bk_tenant_id: 'system' });
  }
  if (/\/index_set\/[^/]+\/search\//.test(url) || url.includes('/union_search/')) {
    return ok({
      total: 2,
      list: [
        { dtEventTimeStamp: Date.now(), log: 'error timeout from api', _index: 'nginx' },
        { dtEventTimeStamp: Date.now() - 60000, log: 'info user login', _index: 'nginx' },
      ],
      origin_log_list: [],
      fields: [],
    });
  }
  if (/\/index_set\/[^/]+\/fields/.test(url)) {
    return ok({
      fields: [
        { field_name: 'log', field_type: 'text', field_alias: '日志', is_display: true, is_analyzed: true },
        { field_name: 'dtEventTimeStamp', field_type: 'date', field_alias: '时间', is_display: true },
      ],
      display_fields: ['dtEventTimeStamp', 'log'],
    });
  }
  if (url.includes('/search/index_set/')) return ok([indexSet]);
  if (url.includes('/search/favorite/list_by_group/')) return ok(favoriteGroups);
  if (url.includes('/search/favorite')) return ok([]);
  if (url.includes('/databus/collectors')) return ok({ list: collectors, total: collectors.length });
  if (url.includes('/login') || url.includes('user/get_property')) return ok({});
  if (url.includes('/search/') || url.includes('/retrieve')) return ok({});
  if (url.endsWith('/') || url.includes('/api/')) return ok({});
  return ok({});
}

const server = createServer((req, res) => {
  const url = req.url || '/';
  if (req.method === 'OPTIONS') {
    res.writeHead(204, {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Headers': '*',
      'Access-Control-Allow-Methods': '*',
    });
    res.end();
    return;
  }
  const body = JSON.stringify(payload(url));
  process.stdout.write(`${req.method} ${url}\n`);
  res.writeHead(200, {
    'Content-Type': 'application/json; charset=utf-8',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': '*',
    'Access-Control-Allow-Methods': '*',
  });
  res.end(body);
});

server.listen(port, '127.0.0.1', () => {
  process.stdout.write(`v2-local-mock http://127.0.0.1:${port}\n`);
});
