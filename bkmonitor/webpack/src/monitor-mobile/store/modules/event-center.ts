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

import { transformDataKey } from 'monitor-common/utils/utils';
import { Action, getModule, Module, Mutation, VuexModule } from 'vuex-module-decorators';

import { getEventList } from '../../../monitor-api/modules/mobile_event';
import store from '../store';

export interface IEventCenterState {
  allList?: IListItem[];
  count?: ICount;
  filterList?: IListItem[];
  finished?: boolean;
  limit?: number;
  page?: number;
  viewList?: IListItem[];
}
interface ICount {
  shield?: number;
  strategy?: number;
  target?: number;
}
interface IData {
  count: ICount;
  groups: IListItem[];
}
interface IEventsItem {
  dimensionMessage: string;
  duration: string;
  eventId: number;
  strategyName?: string;
  target?: string;
}
interface IListItem {
  events: IEventsItem[];
  level?: string;
  name?: string;
  strategyId?: string;
  target?: string;
}

@Module({ dynamic: true, name: 'eventCenter', namespaced: true, store })
class EventCenter extends VuexModule implements IEventCenterState {
  // type下所有数据
  public allList = [];
  // 统计数据
  public count = {};
  // level的所有数据
  public filterList = [];
  // 是否加载完当前分类下的数据
  public finished = false;
  // 每页条数
  public limit = 10;
  // 当前页
  public page = 1;
  // 页面显示的列表
  public viewList = [];

  // 增加一页数据
  @Mutation
  public addPage() {
    const start = (this.page - 1) * this.limit;
    const end = this.page * this.limit;
    if (this.viewList.length < this.filterList.length) {
      const pageList = this.filterList.slice(start, end);
      this.viewList.push(...pageList);
    }
    this.viewList.length >= this.filterList.length && (this.finished = true);
  }

  // 接口获取数据
  @Action
  public async getAllList(payload: { level?: number; type?: string }) {
    store.commit('app/setPageLoading', true);
    let data: IData = await getEventList({
      bk_biz_id: store.getters['app/curBizId'],
      type: payload.type,
    }).catch(() => []);
    store.commit('app/setPageLoading', false);
    data = transformDataKey(data);
    const list = data.groups;
    this.setListData({ allList: list, count: data.count });
    this.getFilterLIst(payload.level);
  }

  // 过滤类型数据
  @Mutation
  public getFilterLIst(level: number | string) {
    if (!level) return (this.filterList = this.allList);
    this.filterList = this.allList.filter(item => item.level === +level);
    this.page = 1;
  }

  // 设置state
  @Mutation
  public setListData(data: IEventCenterState) {
    Object.keys(data).forEach(key => {
      this[key] = data[key];
    });
  }
}

export default getModule(EventCenter);
