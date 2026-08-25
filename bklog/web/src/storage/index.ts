/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */

import { manageDraftCacheService } from './services/manage-draft-cache.service';
import { moduleLargeDataCacheService } from './services/module-large-data-cache.service';
import { retrieveFieldAliasCacheService } from './services/retrieve-field-alias-cache.service';
import { retrieveFieldCacheService } from './services/retrieve-field-cache.service';
import { relatedLogSearchRowCacheService, retrieveRowCacheService } from './services/retrieve-row-cache.service';
import { retrieveRowProjectionService } from './services/retrieve-row-projection.service';
import {
  retrieveSearchWorkerIngestService,
  retrieveSearchWorkerService,
} from './services/retrieve-search-worker.service';
import { clusterTableWorkerService } from './services/cluster-table-worker.service';
import { performanceMonitorService } from './services/performance-monitor.service';
import { storageHealthService } from './services/storage-health.service';
import { storeCacheService } from './services/store-cache.service';
import { workerManagerService } from './services/worker-manager.service';

export default {
  manageDraftCache: manageDraftCacheService,
  moduleLargeDataCache: moduleLargeDataCacheService,
  retrieveFieldAlias: retrieveFieldAliasCacheService,
  retrieveFields: retrieveFieldCacheService,
  retrieveRows: retrieveRowCacheService,
  relatedLogSearchRows: relatedLogSearchRowCacheService,
  retrieveRowProjection: retrieveRowProjectionService,
  retrieveSearchWorker: retrieveSearchWorkerService,
  clusterTableWorker: clusterTableWorkerService,
  performanceMonitor: performanceMonitorService,
  storageHealth: storageHealthService,
  storeCache: storeCacheService,
  workerManager: workerManagerService,
};

export {
  manageDraftCacheService,
  moduleLargeDataCacheService,
  retrieveFieldAliasCacheService,
  retrieveFieldCacheService,
  retrieveRowCacheService,
  relatedLogSearchRowCacheService,
  retrieveRowProjectionService,
  retrieveSearchWorkerService,
  retrieveSearchWorkerIngestService,
  clusterTableWorkerService,
  performanceMonitorService,
  storageHealthService,
  storeCacheService,
  workerManagerService,
};
