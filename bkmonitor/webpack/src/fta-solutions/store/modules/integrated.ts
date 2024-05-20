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
import { listEventPlugin } from 'monitor-api/modules/event_plugin';
import { Action, getModule, Module, VuexModule } from 'vuex-module-decorators';

import store from '../store';

@Module({ name: 'integrated', dynamic: true, namespaced: true, store })
class Integrated extends VuexModule {
  @Action
  async getFilterGroupData() {
    return new Promise(resolve => {
      setTimeout(() => {
        const data = [
          {
            id: 'classification',
            name: '分类',
            data: [
              {
                id: 'event',
                name: '事件插件',
                data: [
                  {
                    id: 'PUSH',
                    name: 'PUSH',
                  },
                  {
                    id: 'PULL',
                    name: 'PULL',
                  },
                ],
              },
              {
                id: 'service',
                name: '周边服务',
                data: [
                  {
                    id: '1',
                    name: '通知服务',
                  },
                  {
                    id: '2',
                    name: '协助',
                  },
                ],
              },
            ],
          },
          {
            id: 'status',
            name: '状态',
            data: [
              {
                id: '1',
                name: '有更新',
              },
              {
                id: '2',
                name: '已下架',
              },
            ],
          },
        ];
        resolve(data);
      }, 1000);
    });
  }

  @Action
  async getPluginData() {
    const randomStatus = () => {
      const status = ['ENABLED', 'UPDATABLE', 'NO_DATA', 'REMOVE_SOON', 'REMOVED', 'DISABLED', 'AVAILABLE'];
      return status[Math.floor(Math.random() * 7)];
    };
    return new Promise(resolve => {
      setTimeout(() => {
        const pluginData = [
          {
            id: 'installed',
            name: '已安装',
            data: [
              {
                name: '事件插件',
                list: [],
              },
              {
                name: '周边服务',
                list: [],
              },
            ],
          },
          {
            id: 'disabled',
            name: '已停用',
            data: [
              {
                list: [],
              },
            ],
          },
          {
            id: 'enabled',
            name: '可用',
            data: [
              {
                name: '事件插件',
                list: [],
              },
              {
                name: '周边服务',
                list: [],
              },
            ],
          },
        ];

        for (let i = 0; i < 10; i++) {
          const official = Math.random() * 10 > 8;
          pluginData[0].data[0].list.push({
            status: randomStatus(),
            id: i,
            title: `xxxx插件${i}`,
            pluginType: official ? '官方' : '其他',
            official,
            heatCount: Math.floor(Math.random() * 10),
            desc: `这是描述这是描述这是描述这是描述这是描述这是描述这是描述这是描述这是描述这是描述${i}`,
          });
        }

        for (let i = 20; i < 25; i++) {
          const official = Math.random() * 10 > 8;
          pluginData[0].data[1].list.push({
            status: randomStatus(),
            id: i,
            title: `xxxx插件${i}`,
            pluginType: official ? '官方' : '其他',
            official,
            heatCount: Math.floor(Math.random() * 10),
            desc: `这是描述这是描述这是描述这是描述这是描述这是描述这是描述这是描述这是描述这是描述${i}`,
          });
        }

        for (let i = 0; i < 10; i++) {
          const official = Math.random() * 10 > 8;
          pluginData[1].data[0].list.push({
            status: 'DISABLED',
            id: i,
            title: `xxxx插件${i}`,
            pluginType: official ? '官方' : '其他',
            official,
            heatCount: Math.floor(Math.random() * 10),
            desc: `这是描述这是描述这是描述这是描述这是描述这是描述这是描述这是描述这是描述这是描述${i}`,
          });
        }

        for (let i = 0; i < 10; i++) {
          const official = Math.random() * 10 > 8;
          pluginData[2].data[0].list.push({
            status: 'AVAILABLE',
            id: i,
            title: `xxxx插件${i}`,
            pluginType: official ? '官方' : '其他',
            official,
            heatCount: Math.floor(Math.random() * 10),
            desc: `这是描述这是描述这是描述这是描述这是描述这是描述这是描述这是描述这是描述这是描述${i}`,
          });
        }

        resolve(pluginData);
      }, 1000);
    });
  }

  @Action
  async getPluginEvent(params): Promise<any> {
    return await listEventPlugin(params).catch(() => ({ count: {}, list: [], emptyType: '500' }));
  }
}

export default getModule(Integrated);
