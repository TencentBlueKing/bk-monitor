/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 */
import { storeCacheService } from './store-cache.service';

const CACHE_NAME = 'manage-draft';

export const manageDraftKeys = {
  collectionUpdateData: 'collectionUpdateData',
  cloneData: 'cloneData',
};

export class ManageDraftCacheService {
  async set(key: string, value: any, meta: Record<string, any> = {}) {
    await storeCacheService.setApiCache(CACHE_NAME, key, value, meta);
  }

  async get<T = any>(key: string) {
    return storeCacheService.getApiCache<T>(CACHE_NAME, key);
  }

  async remove(key: string) {
    await storeCacheService.removeApiCache(CACHE_NAME, key);
  }

  mirrorSessionValue(key: string) {
    try {
      const raw = sessionStorage.getItem(key);
      if (!raw) return;
      const value = JSON.parse(raw);
      this.set(key, value, { source: 'sessionStorage' }).catch(error => {
        console.warn('[manage-draft-cache] mirror session failed', key, error);
      });
    } catch (error) {
      console.warn('[manage-draft-cache] parse session failed', key, error);
    }
  }
}

export const manageDraftCacheService = new ManageDraftCacheService();
