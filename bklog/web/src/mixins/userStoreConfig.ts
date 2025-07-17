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
// import * as authorityMap from '../common/authority-map';

// import { createUserConfig, listUserConfig, partialUpdateUserConfig } from 'monitor-api/modules/model';
// 1、函数作用：创建一组新的个性化配置项（增）
const createUserConfig = async (...args: any[]) => {
  console.warn('createUserConfig函数暂未实现', args);
  return { id: '' };
};
// 2、函数作用：获取用户的个性化配置项（查）
const listUserConfig = async (...args: any[]) => {
  console.warn('listUserConfig函数暂未实现:', args);
  return [];
};
// 3、函数作用：更新用户个性化配置项（改）
const partialUpdateUserConfig = async (...args: any[]) => {
  console.warn('partialUpdateUserConfig函数暂未实现:', args);
  return true;
};

@Component
// 设置全局通用的Loading
export default class UserConfigMixin extends Vue {
  // 配置存储id
  storeId = '';
  // 表示当前用户是否拥有访问某个业务空间的权限（返回一个布尔值）
  // get hasBusinessAuth() {
  //   return window.space_list.some(item => +item.id === +window.cc_biz_id);
  // }
  // if (!space.permission?.[authorityMap.VIEW_BUSINESS]) return;
  
  /**1
   * @description: 获取用户个性化配置
   * @param {string} key key
   * @return {*}
   */
  public async handleGetUserConfig<T>(
    key: string,
    config: Record<string, any> = { reject403: true },
  ): Promise<T | undefined> {
    // if (!this.hasBusinessAuth) return undefined;
    // 获取用户个性化配置项（默认bizId）
    const userConfig = await listUserConfig({ key }, config).catch(() => false);
    // 若配置项不存在，则创建一个
    if (!userConfig?.[0]?.id) {
      const { id } = await createUserConfig({ key, value: '""' }, config);
      this.storeId = id;
      return undefined;
    }
    // 若配置项存在，则设置storeId
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
    // console.log('handleSetUserConfig:', key, value);
    // if (!this.hasBusinessAuth) return false;
    return await partialUpdateUserConfig(this.storeId || configId, { value }, { reject403: true })
      .then(() => true)
      .catch(() => false);
  }
}
