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

import * as alertStrategy from '../../features/alerts/services/alert_strategy';
import * as archive from '../../features/archive/services/archive';
import * as auth from '../../features/authorization/services/auth';
import * as authorization from '../../features/authorization/services/authorization';
import * as biz from '../../platform/services/biz';
import * as clean from '../../features/cleaning/services/clean';
import * as collect from '../../features/collection/services/collect';
import * as container from '../../features/collection/services/container';
import * as custom from '../../features/index-sets/services/custom';
import * as clientLog from '../../features/client-logs/services/client-log';
import * as docs from '../../platform/services/docs';
import * as example from '../../platform/services/example';
import * as extract from '../../features/extraction/services/extract';
import * as extractManage from '../../features/extraction/services/extract-manage';
import * as favorite from '../../features/retrieval/services/favorite';
import * as graphAnalysis from '../../features/retrieval/services/graph-analysis';
import * as grok from '../../features/grok/services/grok';
import * as indexSet from '../../features/index-sets/services/indexSet';
import * as ipChooser from '../../features/collection/services/ip-chooser';
import * as linkConfiguration from '../../features/data-links/services/link-configuration';
import * as logClustering from '../../features/retrieval/services/log-clustering';
import * as masking from '../../features/masking/services/masking';
import * as meta from '../../platform/services/meta';
import * as migrate from '../../features/migration/services/migrate';
import * as monitor from '../../features/monitoring/services/monitor';
import * as newReport from '../../features/reporting/services/new-report';
import particulars from '../../features/retrieval/services/particulars';
import * as plugins from '../../features/integrations/services/plugins';
import * as resultTables from '../../features/index-sets/services/result-tables';
import * as retrieve from '../../features/retrieval/services/retrieve';
import * as source from '../../features/index-sets/services/source';
import * as unionSearch from '../../features/retrieval/services/union-search';
import * as userInfo from '../../platform/services/userInfo';
import * as dashboard from '../../features/dashboards/services/dashboard.ts';
const getMyProjectList = {
  url: '/meta/projects/mine/',
  method: 'get',
};

const getMySpaceList = {
  url: '/meta/spaces/mine/',
  method: 'get',
};
const frontendEventReport = {
  url: '/frontend_event/report/',
  method: 'post',
};

export default {
  project: {
    getMyProjectList,
  },
  space: {
    getMySpaceList,
  },
  report: {
    frontendEventReport,
  },
  userInfo,
  example,
  retrieve,
  indexSet,
  source,
  meta,
  monitor,
  auth,
  plugins,
  resultTables,
  biz,
  particulars,
  collect,
  migrate,
  extract,
  extractManage,
  linkConfiguration,
  clean,
  archive,
  logClustering,
  custom,
  container,
  docs,
  favorite,
  ipChooser,
  authorization,
  masking,
  unionSearch,
  newReport,
  graphAnalysis,
  grok,
  alertStrategy,
  dashboard,
  clientLog,
};
