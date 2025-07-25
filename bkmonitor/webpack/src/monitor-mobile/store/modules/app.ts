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

import { Module, Mutation, VuexModule } from 'vuex-module-decorators';

export interface IAppState {
  alarmNum?: number;
  bizId: number | string;
  bkBizName: string;
  collectId: number | string;
  eventId?: number | string;
  loading?: boolean;
  refresh?: boolean;
}

@Module({ name: 'app', namespaced: true })
export default class App extends VuexModule implements IAppState {
  public alarmNum = 0;
  public bizId = -1;
  public bkBizName = '';
  public collectId = -1;
  public eventId = -1;
  public loading = false;
  public refresh = false;
  get alarmCount() {
    return this.alarmNum;
  }

  get curBizId() {
    return this.bizId;
  }

  @Mutation
  private SET_APP_DATA(data: IAppState) {
    Object.keys(data).forEach(key => {
      this[key] = data[key];
    });
  }

  @Mutation
  private SET_EVENT_ID(eventId: number) {
    this.eventId = eventId;
  }

  @Mutation
  private setAlarmNum(payload: number) {
    this.alarmNum = payload;
  }

  @Mutation
  private setDocumentTitle(title) {
    if (title) {
      document.title = title;
    }
  }

  @Mutation
  private setPageLoading(payload: boolean) {
    this.loading = !this.refresh && payload;
    !payload && (this.refresh = false);
  }

  @Mutation
  private setRefresh(payload: boolean) {
    this.loading = false;
    this.refresh = payload;
  }
}
