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
import { Component, Vue } from 'vue-property-decorator';

import { createUserConfig, listUserConfig, partialUpdateUserConfig } from 'monitor-api/modules/model';

@Component
// 设置全局通用的Loading
export default class UserConfigMixin extends Vue {
  // 配置存储id
  storeId = '';
  get hasBusinessAuth() {
    return window.space_list.some(item => +item.id === +window.cc_biz_id);
  }
  /**
   * @description: 获取用户个性化配置
   * @param {string} key key
   * @return {*}
   */
  public async handleGetUserConfig<T>(
    key: string,
    config: Record<string, any> = { reject403: true }
  ): Promise<T | undefined> {
    if (!this.hasBusinessAuth) return undefined;
    const userConfig = await listUserConfig({ key }, config).catch(() => false);
    if (!userConfig?.[0]?.id) {
      const { id } = await createUserConfig({ key, value: '""' }, config);
      this.storeId = id;
      return undefined;
    }
    this.storeId = userConfig[0].id;
    try {
      return JSON.parse(userConfig[0].value);
    } catch (_) {
      console.error('parse user stiky note error');
    }
    return undefined;
  }
  /**
   * @description: 设置用户配置
   * @param {string} key
   * @param {string} value
   * @return {*}
   */
  public async handleSetUserConfig(key: string, value: string, configId?: string): Promise<boolean> {
    if (!this.hasBusinessAuth) return false;
    return await partialUpdateUserConfig(this.storeId || configId, { value }, { reject403: true })
      .then(() => true)
      .catch(() => false);
  }
}
