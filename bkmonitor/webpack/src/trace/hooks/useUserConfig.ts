/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
import { computed, shallowRef } from 'vue';

import { createUserConfig, listUserConfig, partialUpdateUserConfig } from 'monitor-api/modules/model';

export default function useUserConfig() {
  // 配置存储id
  const storeId = shallowRef('');
  const hasBusinessAuth = computed(() => window.space_list.some(item => +item.id === +window.cc_biz_id));

  /**
   * @description: 获取用户个性化配置
   * @param {string} key key
   * @return {*}
   */
  async function handleGetUserConfig<T>(
    key: string,
    config: Record<string, any> = { reject403: true }
  ): Promise<T | undefined> {
    if (!hasBusinessAuth.value) return undefined;
    const userConfig = await listUserConfig({ key }, config).catch(() => false);
    if (!userConfig?.[0]?.id) {
      const { id } = await createUserConfig({ key, value: '""' }, config);
      storeId.value = id;
      return undefined;
    }
    storeId.value = userConfig[0].id;
    try {
      return JSON.parse(userConfig[0].value);
    } catch {
      console.error('parse user stiky note error');
    }
    return undefined;
  }
  /**
   * @description: 设置用户配置
   * @param {string} value 用户配置值
   * @param {string} configId 用户配置ID 不是key
   * @return {*}
   */
  async function handleSetUserConfig(value: string, configId?: string): Promise<boolean> {
    if (!hasBusinessAuth.value) return false;
    return await partialUpdateUserConfig(storeId.value || configId, { value }, { reject403: true })
      .then(() => true)
      .catch(() => false);
  }

  return {
    storeId,
    handleGetUserConfig,
    handleSetUserConfig,
  };
}
