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
/*
 * @Date: 2021-06-13 20:42:22
 * @LastEditTime: 2021-06-26 11:33:00
 * @Description:
 */

import { applicationInfoByAppName, metaConfigInfo } from 'monitor-api/modules/apm_meta';
import { Action, getModule, Module, Mutation, VuexModule } from 'vuex-module-decorators';

import store from '@store/store';

import type { IAppSelectOptItem } from '../../pages/home/app-select';

export interface IApplicationState {
  pluginsList: IAppSelectOptItem[];
}

interface IAppInfoQuery {
  app_name: string;
  end_time: number;
  start_time: number;
}
// app_list service_list
@Module({ name: 'application', namespaced: true, dynamic: true, store })
class ApplicationStore extends VuexModule implements IApplicationState {
  /** 插件列表 */
  pluginsList: IAppSelectOptItem[] = null;

  get pluginsListGetter() {
    return this.pluginsList;
  }

  /**
   * 请求应用数据
   * @param name 应用名
   */
  @Action
  getAppInfo(query: IAppInfoQuery): Promise<Record<string, any>> {
    return applicationInfoByAppName(query);
  }
  /**
   * 请求插件列表
   */
  @Action
  async getPluginList() {
    if (this.pluginsList) return;
    const { plugins = [] } = await metaConfigInfo().catch(() => ({}));
    const pluginsList = plugins.map(
      (item): IAppSelectOptItem => ({
        id: item.id,
        name: item.name,
        icon: item.icon || '',
        desc: item.short_description || '',
      })
    );
    this.setPluginsList(pluginsList);
  }

  @Mutation
  setPluginsList(list: IAppSelectOptItem[]) {
    this.pluginsList = list;
  }
}

export default getModule(ApplicationStore);
