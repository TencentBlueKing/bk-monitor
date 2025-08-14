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
export default class TableStore {
  public count: number;
  public data: {
    beginTime: string;
    bizId: string;
    cycleDuration: string;
    description: string;
    dimensionConfig: string;
    failureTime: string;
    id: string;
    shieldContent: string;
    shieldType: string;
    shieldTypeName: string;
    status: string;
  }[];
  public keyword: string;
  public page: number;
  public pageList: number[];
  public pageSize: number;
  public constructor(originData = [], count) {
    this.data = [];
    this.setDefaultStore();
    this.setDefaultData(originData);
    this.count = count;
  }

  public getTableData() {
    return this.data.slice(0, this.pageSize);
  }

  public setDefaultData(originData) {
    this.data = [];
    let i = 0;
    while (i < originData.length) {
      const item = originData[i];
      this.data.push({
        id: item.id,
        bizId: item.bk_biz_id,
        shieldType: item.category,
        shieldTypeName: item.category_name,
        shieldContent: item.content,
        beginTime: item.begin_time,
        cycleDuration: item.cycle_duration,
        failureTime: item.failure_time,
        description: item.description,
        status: item.status,
        dimensionConfig: item.dimension_config,
      });
      i += 1;
    }
  }

  public setDefaultStore() {
    this.keyword = '';
    this.page = 1;
    this.pageSize = +localStorage.getItem('__common_page_size__') || 10;
    this.pageList = [10, 20, 50, 100];
    this.count = 0;
  }
}
