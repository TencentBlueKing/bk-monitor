/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 */
import { apiCacheRepository } from '../repositories/api-cache.repository';
import { keyValueRepository } from '../repositories/key-value.repository';

const API_PREFIX = 'api:';
const KV_PREFIX = 'kv:';

export const storeCacheKeys = {
  localStorage: (key: string) => `${KV_PREFIX}localStorage:${key}`,
  api: (name: string, scope = 'default') => `${API_PREFIX}${name}:${scope}`,
};

export class StoreCacheService {
  async setLocalStorageMirror(key: string, value: any) {
    await keyValueRepository.set(storeCacheKeys.localStorage(key), value);
  }

  async getLocalStorageMirror<T = any>(key: string) {
    return keyValueRepository.get<T>(storeCacheKeys.localStorage(key));
  }

  async setApiCache(name: string, scope: string, data: any, meta: Record<string, any> = {}) {
    await apiCacheRepository.set(storeCacheKeys.api(name, scope), data, meta);
  }

  async getApiCache<T = any>(name: string, scope: string) {
    return apiCacheRepository.get<T>(storeCacheKeys.api(name, scope));
  }

  async removeApiCache(name: string, scope: string) {
    await apiCacheRepository.remove(storeCacheKeys.api(name, scope));
  }

  async removeLocalStorageMirror(key: string) {
    await keyValueRepository.remove(storeCacheKeys.localStorage(key));
  }

  async gc() {
    await Promise.all([apiCacheRepository.gc(), keyValueRepository.gc()]);
  }
}

export const storeCacheService = new StoreCacheService();
