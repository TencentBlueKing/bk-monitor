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
import { type RouteConfig } from 'vue-router';

import { spaceIntroduce } from '../../monitor-api/modules/commons';
import { ISPaceIntroduceData } from '../types';

export enum IntroduceRouteKey {
  'performance' = 'performance',
  'uptime-check' = 'uptime-check',
  'apm-home' = 'apm-home',
  'k8s' = 'k8s',
  'custom-scenes' = 'custom-scenes',
  'collect-config' = 'collect-config',
  'plugin-manager' = 'plugin-manager'
}
export type IntroduceStoreData = Record<
  IntroduceRouteKey,
  {
    introduce: ISPaceIntroduceData;
    loading: boolean;
  }
>;
class IntroduceStore {
  // 使用一个对象存储介绍数据和加载状态
  data: Partial<IntroduceStoreData> = {};
  constructor() {
    // eslint-disable-next-line no-restricted-syntax
    for (const key in IntroduceRouteKey) {
      this.data[key] = {
        introduce: null,
        loading: false
      };
    }
  }
  // 通过 tag 参数获取介绍数据
  async getIntroduce(tag: IntroduceRouteKey) {
    // 如果已有数据，直接返回
    if (this.data[tag].introduce) return;

    // 如果正在加载，等待加载完成
    if (this.data[tag].loading) {
      await new Promise(resolve => {
        const interval = setInterval(() => {
          if (this.data[tag].introduce) {
            clearInterval(interval);
            resolve(undefined);
          }
        }, 1);
      });
      return;
    }

    // 设置加载状态，发送请求并更新数据
    this.data[tag].loading = true;
    const data = await spaceIntroduce({ tag }).catch(() => undefined);
    this.data[tag].loading = false;
    this.data[tag].introduce = data;
  }

  // 初始化所有介绍数据
  initIntroduce(to: RouteConfig) {
    const toNavId = to.meta.navId;
    Object.keys(this.data).forEach((tag: IntroduceRouteKey) => {
      // 如果已有数据，直接返回
      if (this.data[tag].introduce) return;
      if (!this.data[tag].loading) {
        requestIdleCallback(() => {
          if (toNavId === tag) {
            this.getIntroduce(tag);
          } else {
            this.data[tag].loading = true;
            spaceIntroduce({ tag })
              .then(data => {
                this.data[tag].introduce = data;
              })
              .catch(() => (this.data[tag].introduce = undefined))
              .finally(() => (this.data[tag].loading = false));
          }
        });
      }
    });
  }

  // 获取路由对应的 getIntroduce 方法
  getRouteFunc(routeId: IntroduceRouteKey) {
    return this.getIntroduce(routeId);
  }

  // 根据路由判断是否显示指南页面
  getShowGuidePageByRoute(routeId: IntroduceRouteKey) {
    if (routeId === IntroduceRouteKey['plugin-manager']) return !!this.data[routeId]?.introduce.is_no_source;
    return !!(this.data[routeId]?.introduce.is_no_data || this.data[routeId]?.introduce.is_no_source);
  }
}

const module = new IntroduceStore();
export default module;
