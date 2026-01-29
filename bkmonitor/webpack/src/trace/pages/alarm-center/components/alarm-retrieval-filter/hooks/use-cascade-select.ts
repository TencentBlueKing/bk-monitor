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

import { triggerRef } from 'vue';
import type { ShallowRef } from 'vue';

import type { ICascadeData } from '../typing/typing';

interface IAllOptions {
  data: { id: string; name: string }[];
  search: string;
  pagination: {
    isEnd: boolean;
    limit: number;
    page: number;
  };
}

export function useCascadeSelect(localValue: ShallowRef<ICascadeData[]>) {
  const allOptions: Map<string, IAllOptions> = new Map();
  function init(cascades, val) {
    localValue.value = cascades.map(item => {
      const value = val.find(v => v.key === item.id)?.value || [];
      return {
        ...item,
        value,
        isOpen: false,
        options: [],
        loading: false,
        scrollLoading: false,
      };
    });
  }
  async function handleScrollEnd(item: ICascadeData) {
    const curOption = allOptions.get(item.id);
    if (curOption && !curOption.pagination.isEnd) {
      setScrollLoading(item, true);
      const pagination = {
        page: curOption.pagination.page + 1,
        limit: 20,
      };
      const search = curOption.search;
      const oldData = curOption.data;
      const data = await mockData(search, pagination.page, pagination.limit);
      allOptions.set(item.id, {
        pagination: {
          ...pagination,
          isEnd: data.length < pagination.limit,
        },
        data: [...oldData, ...data],
        search,
      });
      renderOptions(item);
    }
  }
  async function handleSearch(item: ICascadeData, search: string) {
    setLoading(item, true);
    const pagination = {
      page: 1,
      limit: 20,
    };
    const data = await mockData(search, pagination.page, pagination.limit);
    allOptions.set(item.id, {
      pagination: {
        ...pagination,
        isEnd: data.length < pagination.limit,
      },
      data: data as any[],
      search,
    });
    renderOptions(item);
  }
  async function handleOpen(item: ICascadeData, val) {
    item.isOpen = val;
    if (val) {
      setLoading(item, true);
      const pagination = {
        page: 1,
        limit: 20,
      };
      const data = await mockData('', pagination.page, pagination.limit);
      allOptions.set(item.id, {
        pagination: {
          ...pagination,
          isEnd: data.length < pagination.limit,
        },
        data: data as any[],
        search: '',
      });
      renderOptions(item);
    } else {
      setIsOpen(item, val);
      allOptions.set(item.id, {
        pagination: {
          page: 1,
          limit: 20,
          isEnd: false,
        },
        data: [],
        search: '',
      });
    }
  }

  function renderOptions(item: ICascadeData) {
    const options = allOptions.get(item.id)?.data || [];
    const tempLocalValue = [];
    for (const val of localValue.value) {
      if (val.id === item.id) {
        tempLocalValue.push({
          ...val,
          options: options,
          loading: false,
          scrollLoading: false,
        });
      } else {
        tempLocalValue.push(val);
      }
    }
    localValue.value = tempLocalValue;
  }
  function setLoading(item: ICascadeData, loading = false) {
    for (const val of localValue.value) {
      if (val.id === item.id) {
        val.loading = loading;
        break;
      }
    }
    triggerRef(localValue);
  }
  function setScrollLoading(item: ICascadeData, loading = false) {
    for (const val of localValue.value) {
      if (val.id === item.id) {
        val.scrollLoading = loading;
        break;
      }
    }
    triggerRef(localValue);
  }
  function setIsOpen(item: ICascadeData, isOpen = false) {
    for (const val of localValue.value) {
      if (val.id === item.id) {
        val.isOpen = isOpen;
        break;
      }
    }
    triggerRef(localValue);
  }

  return {
    init,
    handleScrollEnd,
    handleSearch,
    handleOpen,
  };
}

async function mockData(search = '', page = 1, limit = 20) {
  return new Promise(resolve => {
    const list = [];
    let res = [];
    for (let i = 1; i <= 100; i++) {
      list.push({
        id: `${i}`,
        name: `${i}`,
      });
    }
    if (search) {
      res = list.filter(item => item.name.includes(search)).slice((page - 1) * limit, page * limit);
      setTimeout(() => {
        resolve(res);
      }, 1000);
      return;
    }
    setTimeout(() => {
      resolve(list.slice((page - 1) * limit, page * limit));
    }, 1000);
  });
}
