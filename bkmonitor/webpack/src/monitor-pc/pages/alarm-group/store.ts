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
export default class TableStore {
  public data: { id: string; name: string }[];
  public keyword: string;
  public page: number;
  public pageList: number[];
  public pageSize: number;
  public searchCondition: { id: string; name: string; values?: { id: string; name: string }[] }[] = [];
  public total: number;
  public constructor(originData) {
    originData.forEach(set => {
      const item = set;
      const row = window.space_list.find(v => v.id === item.bk_biz_id);
      item.bizName = row ? row.space_name : '--';
    });
    this.setDefaultStore();
    this.total = originData.length;
    this.data = originData;
  }

  public getTableData() {
    let ret = this.data;
    const keyword = this.keyword.toLocaleLowerCase();
    if (this.keyword.length) {
      ret = ret.filter(item => item.name.toLocaleLowerCase().includes(keyword) || item.id.toString().includes(keyword));
    }
    if (this.searchCondition.length) {
      ret = this.handleSearchCondition(ret);
    }
    this.total = ret.length;
    return ret.slice(this.pageSize * (this.page - 1), this.pageSize * this.page);
  }

  /**
   * @description 条件搜索
   * @param data
   * @returns
   */
  public handleSearchCondition(data) {
    const searchIds = [];
    const searchNames = [];
    const searcOthers = [];
    const searchRules = [];
    const searchNotifyTarget = [];
    this.searchCondition.forEach(c => {
      if (c.id === 'id') {
        c?.values?.forEach(v => {
          searchIds.push(v.id);
        });
      }
      if (c.id === 'name') {
        c?.values?.forEach(v => {
          searchNames.push(v.id);
        });
      }
      if (c.id === 'rule') {
        c?.values?.forEach(v => {
          searchRules.push(v.id);
        });
      }
      if (c.id === 'notify-target') {
        c?.values?.forEach(v => {
          searchNotifyTarget.push(v.id);
        });
      }
      if (typeof c.values === 'undefined') {
        searcOthers.push(c.id);
      }
    });
    return data.filter(item => {
      const iss = [];
      if (searchIds.length) {
        iss.push(searchIds.includes(String(item.id)));
      }
      if (searchNames.length) {
        iss.push(
          searchNames.some(name => (item.name as string).toLocaleLowerCase().includes(name.toLocaleLowerCase()))
        );
      }
      if (searcOthers.length) {
        iss.push(
          searcOthers.some(name => (item.name as string).toLocaleLowerCase().includes(name.toLocaleLowerCase()))
        );
      }
      if (searchRules.length) {
        iss.push(
          searchRules.some(id =>
            item.dutyRuleNames.some(d => d.name.toLocaleLowerCase().includes(id.toLocaleLowerCase()))
          )
        );
      }
      if (searchNotifyTarget.length) {
        iss.push(
          searchNotifyTarget.some(targetId =>
            item.users.some(notifytarget =>
              `${notifytarget.id || ''}(${notifytarget.display_name || ''})`
                .toLocaleLowerCase()
                .includes(targetId.toLocaleLowerCase())
            )
          )
        );
      }
      return iss.length ? iss.some(is => is) : true;
    });
  }

  public setDefaultStore() {
    this.keyword = '';
    this.page = 1;
    this.pageSize = +localStorage.getItem('__common_page_size__') || 10;
    this.pageList = [10, 20, 50, 100];
    this.total = 0;
  }
}
