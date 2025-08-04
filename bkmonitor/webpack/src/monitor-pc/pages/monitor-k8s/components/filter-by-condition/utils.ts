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
import { listK8sResources, workloadOverview } from 'monitor-api/modules/k8s';

import { handleTransformToTimestamp } from '../../../../components/time-range/utils';
import { sceneDimensionMap } from '../../k8s-dimension';
import { EDimensionKey } from '../../typings/k8s-new';
export interface IFilterByItem {
  key: string;
  value: string[];
}

export interface IGroupOptionsItem {
  count: number;
  id: string;
  name: string;
}

export interface ITagListItem {
  id: string;
  key: string;
  name: string;
  values: IValue[];
}

export interface IValueItem {
  checked: boolean;
  count?: number;
  id: string;
  name: string;
  children?: {
    checked: boolean;
    id: string;
    name: string;
  }[];
}
interface IValue {
  id: string;
  name: string;
}

export class FilterByOptions {
  commonParams: Record<string, any> = {}; // 通用参数
  dimensionData = []; // 维度数据
  isUpdate = false;
  pageMap: Record<string, number> = {}; // 分页数据
  pageSize = 10;
  scenario = 'performance';
  constructor(params) {
    this.scenario = params.scenario;
    this.commonParams = params;
    this.pageSize = params.page_size || 10;
    this.dimensionData = sceneDimensionMap[this.scenario].map(id => ({
      id: id,
      name: id,
      count: 0,
      children: [],
    }));
  }
  async getCountData(dimensions: EDimensionKey[], search: string, setData: (v: Map<EDimensionKey, number>) => void) {
    const countData = new Map();
    for (const dimension of dimensions) {
      if (dimension === EDimensionKey.workload) {
        workloadOverview({
          bcs_cluster_id: this.commonParams.bcs_cluster_id,
          query_string: search,
          namespace: this.isUpdate ? undefined : this.commonParams?.filter_dict?.namespace?.join?.(',') || undefined,
        }).then(data => {
          let total = 0;
          for (const d of data) {
            total += d[1];
          }
          countData.set(dimension, total);
          setData(countData);
        });
      } else {
        const { timeRange, ...commonParams } = this.commonParams;
        const formatTimeRange = handleTransformToTimestamp(timeRange);
        listK8sResources({
          ...commonParams,
          start_time: formatTimeRange[0],
          end_time: formatTimeRange[1],
          resource_type: dimension,
          page: 1,
          page_size: 1,
          ...this.queryStringParams(dimension),
          query_string: search,
        }).then(({ count }) => {
          countData.set(dimension, count);
          setData(countData);
        });
      }
    }
  }

  // 下一页
  async getNextPageData(dimension: EDimensionKey, categoryDim?: string) {
    this.nextPage(dimension, categoryDim);
    const page = this.getPage(dimension, categoryDim);
    const { timeRange, ...commonParams } = this.commonParams;
    const formatTimeRange = handleTransformToTimestamp(timeRange);
    const data = await listK8sResources({
      ...commonParams,
      start_time: formatTimeRange[0],
      end_time: formatTimeRange[1],
      resource_type: dimension,
      page: page,
      ...this.queryStringParams(dimension, categoryDim),
    }).catch(() => ({ count: 0, items: [] }));
    this.setData(dimension, categoryDim, data);
    return this.dimensionData;
  }

  getPage(dimension: EDimensionKey, categoryDim?: string) {
    if (dimension === EDimensionKey.workload && categoryDim) {
      return this.pageMap?.[`${dimension}_____${categoryDim}`] || 0;
    }
    return this.pageMap?.[dimension] || 0;
  }

  // 是否滚动到底了
  getPageEnd(dimension: EDimensionKey, categoryDim?: string) {
    const count = this.getPage(dimension, categoryDim) * this.pageSize;
    let list = [];
    for (const item of this.dimensionData) {
      if (item.id === dimension) {
        if (item.id === EDimensionKey.workload) {
          list = item.children.find(c => c.id === categoryDim)?.children || [];
        } else {
          list = item.children;
        }
        break;
      }
    }
    return count > list.length;
  }

  // 初始化数据
  async init() {
    await this.setWorkloadOverview({
      bcs_cluster_id: this.commonParams.bcs_cluster_id,
    });
    const promiseList = [];
    const setData = async (id: EDimensionKey) => {
      if (id === EDimensionKey.workload) {
        const categoryDim = this.dimensionData.find(item => item.id === id)?.children[0]?.id;
        if (categoryDim) {
          return await this.initOfType(id, categoryDim);
        }
      } else {
        return await this.initOfType(id);
      }
    };
    for (const item of this.dimensionData) {
      promiseList.push(setData(item.id));
    }
    await Promise.all(promiseList);
  }

  async initOfType(dimension: EDimensionKey, categoryDim?: string) {
    this.setPage(1, dimension, categoryDim);
    const page = this.getPage(dimension, categoryDim);
    const { timeRange, ...commonParams } = this.commonParams;
    const formatTimeRange = handleTransformToTimestamp(timeRange);
    const data = await listK8sResources({
      ...commonParams,
      start_time: formatTimeRange[0],
      end_time: formatTimeRange[1],
      resource_type: dimension,
      page: page,
      ...this.queryStringParams(dimension, categoryDim),
    }).catch(() => ({ count: 0, items: [] }));
    this.setData(dimension, categoryDim, data);
  }

  nextPage(dimension: EDimensionKey, categoryDim?: string) {
    if (dimension === EDimensionKey.workload && categoryDim) {
      this.pageMap[`${dimension}_____${categoryDim}`] = this.getPage(dimension, categoryDim) + 1;
    }
    this.pageMap[dimension] = this.getPage(dimension) + 1;
  }

  queryStringParams(dimension: EDimensionKey, categoryDim?: string) {
    const dimensionIndex = sceneDimensionMap[this.scenario];
    const filterDict = {};
    if (!this.isUpdate) {
      for (const key of dimensionIndex) {
        if (key === dimension) {
          break;
        }
        if (this.commonParams.filter_dict?.[key]?.length) {
          filterDict[key] = this.commonParams.filter_dict[key];
        }
      }
    }
    if (this.commonParams.query_string) {
      return {
        query_string: this.commonParams.query_string,
        filter_dict: {
          ...filterDict,
          ...(dimension === EDimensionKey.workload && categoryDim
            ? {
                [EDimensionKey.workload]: `${categoryDim}:`,
              }
            : {}),
        },
      };
    }
    return {
      query_string: dimension === EDimensionKey.workload && categoryDim ? `${categoryDim}:` : '',
      filter_dict: filterDict,
    };
  }

  // 搜索
  async search(search: string, dimension: EDimensionKey, categoryDim?: string) {
    if (dimension === EDimensionKey.workload) {
      await this.setWorkloadOverview({
        bcs_cluster_id: this.commonParams.bcs_cluster_id,
        query_string: search,
      });
    }
    this.commonParams.query_string = search;
    this.setPage(1, dimension, categoryDim);
    const page = this.getPage(dimension, categoryDim);
    const { timeRange, ...commonParams } = this.commonParams;
    const formatTimeRange = handleTransformToTimestamp(timeRange);
    const data = await listK8sResources({
      ...commonParams,
      start_time: formatTimeRange[0],
      end_time: formatTimeRange[1],
      resource_type: dimension,
      page: page,
      ...this.queryStringParams(dimension, categoryDim),
    }).catch(() => ({ count: 0, items: [] }));
    this.setData(dimension, categoryDim, data);
  }

  setCommonParams(params) {
    this.commonParams = {
      ...this.commonParams,
      ...params,
    };
  }

  setData(dimension: EDimensionKey, categoryDim: string, data: any) {
    if (dimension === EDimensionKey.workload) {
      for (const dim of this.dimensionData) {
        if (dim.id === dimension) {
          // dim.count = data.count;
          for (const child of dim.children) {
            if (child.id === categoryDim) {
              child.count = data.count;
              child.children = data.items.map(item => {
                const id = item[dimension];
                return {
                  id: id,
                  name: id,
                };
              });
              break;
            }
          }
          break;
        }
      }
    } else {
      for (const dim of this.dimensionData) {
        if (dim.id === dimension) {
          dim.count = data.count;
          dim.children = data.items.map(item => {
            const id = item[dimension];
            return {
              id: id,
              name: id,
            };
          });
          break;
        }
      }
    }
    return this.dimensionData;
  }
  setIsUpdate(v: boolean) {
    this.isUpdate = v;
  }
  setPage(page: number, dimension: EDimensionKey, categoryDim?: string) {
    if (dimension === EDimensionKey.workload && categoryDim) {
      this.pageMap[`${dimension}_____${categoryDim}`] = page;
    }
    this.pageMap[dimension] = page;
  }

  async setWorkloadOverview(params: any) {
    const data = await workloadOverview({
      ...params,
      namespace: this.isUpdate ? undefined : this.commonParams?.filter_dict?.namespace?.join?.(',') || undefined,
    }).catch(() => []);
    for (const dim of this.dimensionData) {
      if (dim.id === EDimensionKey.workload) {
        let total = 0;
        dim.children = data.map(item => {
          const id = item[0];
          const count = item[1];
          total += count;
          return {
            id: id,
            name: id,
            count,
            children: [],
          };
        });
        dim.count = total;
        break;
      }
    }
    return this.dimensionData;
  }
}
