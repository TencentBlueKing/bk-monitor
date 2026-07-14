/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 */
import { manageDraftCacheService } from './services/manage-draft-cache.service';
import { moduleLargeDataCacheService } from './services/module-large-data-cache.service';
import { retrieveFieldAliasCacheService } from './services/retrieve-field-alias-cache.service';
import { retrieveFieldCacheService } from './services/retrieve-field-cache.service';
import { retrieveRowCacheService } from './services/retrieve-row-cache.service';
import { retrieveRowProjectionService } from './services/retrieve-row-projection.service';
import {
  retrieveSearchWorkerIngestService,
  retrieveSearchWorkerService,
} from './services/retrieve-search-worker.service';
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
  retrieveRowProjection: retrieveRowProjectionService,
  retrieveSearchWorker: retrieveSearchWorkerService,
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
  retrieveRowProjectionService,
  retrieveSearchWorkerService,
  retrieveSearchWorkerIngestService,
  performanceMonitorService,
  storageHealthService,
  storeCacheService,
  workerManagerService,
};
