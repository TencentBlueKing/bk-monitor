/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 */
import { manageDraftCacheService } from './services/manage-draft-cache.service';
import { moduleLargeDataCacheService } from './services/module-large-data-cache.service';
import { retrieveRowCacheService } from './services/retrieve-row-cache.service';
import { retrieveRowProjectionService } from './services/retrieve-row-projection.service';
import { retrieveSearchWorkerIngestService } from './services/retrieve-search-worker-ingest.service';
import { storageHealthService } from './services/storage-health.service';
import { storeCacheService } from './services/store-cache.service';

export default {
  manageDraftCache: manageDraftCacheService,
  moduleLargeDataCache: moduleLargeDataCacheService,
  retrieveRows: retrieveRowCacheService,
  retrieveRowProjection: retrieveRowProjectionService,
  retrieveSearchWorkerIngest: retrieveSearchWorkerIngestService,
  storageHealth: storageHealthService,
  storeCache: storeCacheService,
};

export {
  manageDraftCacheService,
  moduleLargeDataCacheService,
  retrieveRowCacheService,
  retrieveRowProjectionService,
  retrieveSearchWorkerIngestService,
  storageHealthService,
  storeCacheService,
};
