/* Copyright (C) 2021 THL A29 Limited, a Tencent company.
 * 蓝鲸智云PaaS平台 (BlueKing PaaS), MIT License. */
import { ref, type Ref } from 'vue';
interface UserConfiguration {
  id: string;
  value: string;
}
type RequestConfig = Record<string, unknown>;
export interface UserConfigurationServices {
  create(data: { key: string; value: string }, config: RequestConfig): Promise<{ id: string }>;
  list(data: { key: string }, config: RequestConfig): Promise<UserConfiguration[]>;
  update(id: string | undefined, data: { value: string }, config: RequestConfig): Promise<unknown>;
}
// V2 does not connect these monitor-api operations in the log application.
// Preserve its observable behavior; do not invent endpoints during Vue migration.
const legacyServices: UserConfigurationServices = {
  async create(...args) {
    console.warn('createUserConfig函数暂未实现', args);
    return { id: '' };
  },
  async list(...args) {
    console.warn('listUserConfig函数暂未实现:', args);
    return [];
  },
  async update(...args) {
    console.warn('partialUpdateUserConfig函数暂未实现:', args);
    return true;
  },
};
// The previous module exported one shared UserConfigMixin instance.
const sharedStoreId = ref('');
export function useUserConfiguration(
  services: UserConfigurationServices = legacyServices,
  storeId: Ref<string> = sharedStoreId,
) {
  async function handleGetUserConfig<T>(
    key: string,
    config: RequestConfig = { reject403: true },
  ): Promise<T | undefined> {
    const configurations = await services.list({ key }, config).catch(() => false);
    const first = Array.isArray(configurations) ? configurations[0] : undefined;
    if (!first?.id) {
      const { id } = await services.create({ key, value: '""' }, config);
      storeId.value = id;
      return;
    }
    storeId.value = first.id;
    try {
      return JSON.parse(first.value) as T;
    } catch {
      console.error('parse user stiky note error');
    }
  }
  async function handleSetUserConfig(_key: string, value: string, configId?: string): Promise<boolean> {
    return await services
      .update(storeId.value || configId, { value }, { reject403: true })
      .then(() => true)
      .catch(() => false);
  }
  return { storeId, handleGetUserConfig, handleSetUserConfig };
}
