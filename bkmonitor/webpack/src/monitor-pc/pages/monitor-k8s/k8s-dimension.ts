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

import {
  type GroupListItem,
  type K8sDimensionParams,
  K8sTableColumnKeysEnum,
  EDimensionKey,
  SceneEnum,
} from './typings/k8s-new';

import type { K8sTableColumnResourceKey } from './components/k8s-table-new/k8s-table-new';

export class K8sDimension {
  bcsClusterId = '';
  endTime = 1733905598;
  /** 搜索关键字 */
  keyword = '';
  /** 所有的维度数据 */
  originDimensionData: GroupListItem[] = [];
  /** 各维度分页 */
  pageMap = {};
  /** 分页数量 */
  pageSize = 5;
  /** 分页类型 */
  pageType: K8sDimensionParams['pageType'] = 'traditional';
  /** 场景 */
  scene: SceneEnum = SceneEnum.Performance;
  /** 场景维度枚举 */
  sceneDimensionMap = {
    performance: [EDimensionKey.namespace, EDimensionKey.workload, EDimensionKey.pod, EDimensionKey.container],
  };

  startTime = 1733819169;

  withHistory = false;

  constructor(params: K8sDimensionParams) {
    this.scene = params.scene;
    this.keyword = params.keyword;
    this.pageSize = params.pageSize || 5;
    this.pageType = params.pageType || 'traditional';
    this.bcsClusterId = params.bcsClusterId || '';
  }

  get commonParams() {
    return {
      sernario: this.scene,
      bcs_cluster_id: this.bcsClusterId,
      page_size: this.pageSize,
      page_type: this.pageType,
      query_string: this.keyword,
      with_history: false,
    };
  }

  /** 当前场景的维度列表 */
  get currentDimension() {
    return this.sceneDimensionMap[this.scene];
  }

  /** 当前场景下的维度请求接口 */
  get currentSceneDimensionRequest() {
    const requestMap = {
      performance: this.getPerformanceDimensionData,
    };
    return requestMap[this.scene];
  }

  /** 当前展示的维度数据 */
  get showDimensionData() {
    return this.originDimensionData.map(dimension => {
      let children = [];
      if (dimension.id === EDimensionKey.workload) {
        children = dimension.children.map(item => {
          return {
            ...item,
            children: item.children.slice(0, this.pageSize * this.pageMap[item.id] || 1),
          };
        });
      } else {
        children = dimension.children.slice(0, this.pageSize * this.pageMap[dimension.id] || 1);
      }
      return {
        ...dimension,
        children,
      };
    });
  }

  /**
   * @description 整理items数据
   * @param type
   * @param dataItem
   * @returns
   */
  formatData(type: EDimensionKey, dataItem) {
    return {
      id: dataItem[type],
      name: dataItem[type],
      relation: dataItem, // 关联数据
    };
  }

  /**
   * 获取常规维度数据（性能场景除workload维度）
   * @param params
   */
  async getDimensionData({ resource_type, ...params }) {
    const data = await listK8sResources({
      ...this.commonParams,
      resource_type,
      page: this.pageMap[resource_type] || 1,
      ...params,
    }).catch(() => ({ count: 0, items: [] }));
    const index = this.currentDimension.findIndex(item => item === resource_type);
    const dimensionList = this.originDimensionData[index];
    if (!dimensionList) {
      this.originDimensionData[index] = {
        id: resource_type,
        name: resource_type,
        count: data.count,
        children: data.items.map(item => this.formatData(resource_type, item)),
      };
    } else {
      if (this.pageType === 'scrolling') {
        dimensionList.children = data.items.map(item => this.formatData(resource_type, item));
      } else {
        dimensionList.children = dimensionList.children.concat(
          data.items.map(item => this.formatData(resource_type, item))
        );
      }
    }
    this.originDimensionData = [...this.originDimensionData];
  }

  /**
   * 获取性能场景所有维度的数据, 并初始化各维度的page为1
   * @param params 请求参数
   */
  async getPerformanceDimensionData(params = {}) {
    this.originDimensionData = [];
    const pageMap = {};
    let workloadCategory = [];
    const promiseList = this.currentDimension.map(async (dimension, index) => {
      if (dimension === EDimensionKey.workload) {
        workloadCategory = await workloadOverview({
          bcs_cluster_id: this.bcsClusterId,
          query_string: this.keyword,
        }).catch(() => []);
        let total = 0;
        const children = workloadCategory.map(item => {
          total += item[1];
          pageMap[item[0]] = 1;
          return {
            id: item[0],
            name: item[0],
            count: item[1],
            children: [],
          };
        });
        this.originDimensionData[index] = {
          id: dimension,
          name: dimension,
          count: total,
          children,
        };
      } else {
        await this.getDimensionData({
          resource_type: dimension,
          ...params,
        });
        pageMap[dimension] = 1;
      }
    });
    this.pageMap = pageMap;
    await Promise.all(promiseList);
    if (workloadCategory.length) {
      await this.getWorkloadChildrenData({
        filter_dict: {
          workload: `${workloadCategory[0][0]}:`,
        },
        ...params,
      });
    }
  }

  /**
   * @description 获取workload维度下某个分类的数据
   */
  async getWorkloadChildrenData({ filter_dict, ...params }) {
    const { workload: workloadParams } = filter_dict;
    const [category] = workloadParams.split(':');
    const data = await listK8sResources({
      ...this.commonParams,
      resource_type: EDimensionKey.workload,
      page: this.pageMap[category],
      filter_dict,
      ...params,
    }).catch(() => ({ count: 0, items: [] }));
    const workloadList = this.originDimensionData.find(item => item.id === EDimensionKey.workload);
    const categoryList = workloadList.children.find(item => item.id === category);
    if (this.pageType === 'scrolling') {
      categoryList.children = data.items.map(item => this.formatData(EDimensionKey.workload, item));
    } else {
      categoryList.children = categoryList.children.concat(
        data.items.map(item => this.formatData(EDimensionKey.workload, item))
      );
    }
    this.originDimensionData = [...this.originDimensionData];
  }

  /**
   * @description 初始化维度数据
   */
  async init(params = {}) {
    this.pageMap = {};
    await this.currentSceneDimensionRequest(params);
  }

  /**
   * 加载某个维度（类目）下一页数据
   * @param dimension
   */
  async loadNextPageData(dimension, params = {}, fatherDimension?: string) {
    this.pageMap[dimension] += 1;
    /**
     *  1. 如果是搜索状态，接口返回的是全量数据，加载更多不需要请求接口
     *  2. 不是搜索状态，接口返回的分页数据，加载更多需要重新请求接口，并追加到原数据中
     */
    if (!this.keyword) {
      if (fatherDimension === EDimensionKey.workload) {
        await this.getWorkloadChildrenData({
          filter_dict: {
            workload: `${dimension}:`,
          },
          ...params,
        });
      } else {
        await this.getDimensionData({
          resource_type: dimension,
          page: this.pageMap[dimension],
          ...params,
        });
      }
    }
  }

  /** 搜索 */
  async search(keyword: string, params = {}, dimension?: string, fatherDimension?: EDimensionKey) {
    this.keyword = keyword;
    if (dimension) {
      this.pageMap[dimension] = 1;
      if (fatherDimension === EDimensionKey.workload) {
        await this.getWorkloadChildrenData({
          filter_dict: {
            workload: `${dimension}:`,
          },
          ...params,
        });
      } else {
        await this.getDimensionData({
          resource_type: dimension,
          page: this.pageMap[dimension],
          ...params,
        });
      }
    } else {
      await this.init(params);
    }
  }
}

/**
 * @description K8S GroupFilter 基类
 */
export abstract class K8sGroupDimension {
  /** 默认填充值（该值不可删除的！） */
  private defaultGroupFilter: Set<K8sTableColumnKeysEnum>;
  /** Set 结构的 groupFilters 参数（主要用于校验判断是否存在某个值） */
  private groupFiltersSet: Set<K8sTableColumnKeysEnum>;
  /** 实现类填充存在的 dimensions  */
  abstract dimensions: K8sTableColumnKeysEnum[];
  abstract dimensionsMap: Partial<Record<K8sTableColumnKeysEnum, K8sTableColumnKeysEnum[]>>;
  /** 已选 group by 维度 */
  // eslint-disable-next-line @typescript-eslint/member-ordering
  public groupFilters: K8sTableColumnResourceKey[] = [];
  constructor(groupFilters: K8sTableColumnResourceKey[] = []) {
    this.defaultGroupFilter = new Set(groupFilters);
    this.setGroupFilters(groupFilters);
  }

  /**
   * @description 添加 groupFilters
   * @param {K8sTableColumnResourceKey} groupId
   */
  addGroupFilter(groupId: K8sTableColumnResourceKey) {
    this.setGroupFilters(this.dimensionsMap[groupId] as K8sTableColumnResourceKey[]);
  }

  /**
   * @description 删除 groupFilters
   * @param {K8sTableColumnResourceKey} groupId
   */
  deleteGroupFilter(groupId: K8sTableColumnResourceKey) {
    const indexOrMsg = this.verifyDeleteGroupFilter(groupId);
    if (typeof indexOrMsg === 'string') return;
    this.deleteGroupFilterForce(groupId);
  }

  /**
   * @description 强制删除 groupFilter（将所在层级及所有子级对象删除）
   * @param {K8sTableColumnResourceKey} groupId
   */
  deleteGroupFilterForce(groupId: K8sTableColumnResourceKey) {
    if (!this.hasGroupFilter(groupId)) return;
    const arr = [];
    for (const v of this.groupFilters) {
      if (v === groupId) {
        break;
      }
      arr.push(v);
    }
    this.setGroupFilters(arr);
  }

  /**
   * @description 获取最后一个 groupFilter
   * @returns {K8sTableColumnResourceKey}
   */
  getLastGroupFilter() {
    return this.groupFilters[this.groupFilters.length - 1];
  }

  /**
   * @description 判断是否存在 groupId
   * @param {K8sTableColumnResourceKey} groupId
   * @returns {boolean}
   */
  hasGroupFilter(groupId: K8sTableColumnResourceKey) {
    return this.groupFiltersSet.has(groupId);
  }

  /**
   * @description 判断是否为默认 groupFilter
   * @param {K8sTableColumnResourceKey} groupId
   * @returns {boolean}
   */
  isDefaultGroupFilter(groupId: K8sTableColumnResourceKey) {
    return this.defaultGroupFilter.has(groupId);
  }

  /**
   * @description 修改 groupFilters
   * @param {K8sTableColumnResourceKey[]} groupFilters
   */
  setGroupFilters(groupFilters: K8sTableColumnResourceKey[]) {
    this.groupFilters = groupFilters;
    this.groupFiltersSet = new Set(groupFilters);
  }

  /**
   * @description 校验传入 groupId 是否可删除
   * @param {K8sTableColumnResourceKey} groupId
   * @returns {string | number} string 类型表示不可删除，number 类型表示删除成功
   */
  verifyDeleteGroupFilter(groupId: K8sTableColumnResourceKey) {
    if (this.defaultGroupFilter.has(groupId)) {
      return '默认值不可删除';
    }
    const index = this.groupFilters.findIndex(item => item === groupId);
    if (index !== this.groupFilters.length - 1) {
      return '请先删除子级维度';
    }
    return index;
  }
}

/**
 * @description 性能 类型 GroupFilter 实现类
 * */
export class K8sPerformanceGroupDimension extends K8sGroupDimension {
  readonly dimensions = [
    K8sTableColumnKeysEnum.NAMESPACE,
    K8sTableColumnKeysEnum.WORKLOAD,
    K8sTableColumnKeysEnum.POD,
    K8sTableColumnKeysEnum.CONTAINER,
  ];
  readonly dimensionsMap = {
    [K8sTableColumnKeysEnum.NAMESPACE]: [K8sTableColumnKeysEnum.NAMESPACE],
    [K8sTableColumnKeysEnum.WORKLOAD]: [K8sTableColumnKeysEnum.NAMESPACE, K8sTableColumnKeysEnum.WORKLOAD],
    [K8sTableColumnKeysEnum.POD]: [
      K8sTableColumnKeysEnum.NAMESPACE,
      K8sTableColumnKeysEnum.WORKLOAD,
      K8sTableColumnKeysEnum.POD,
    ],
    [K8sTableColumnKeysEnum.CONTAINER]: [
      K8sTableColumnKeysEnum.NAMESPACE,
      K8sTableColumnKeysEnum.WORKLOAD,
      K8sTableColumnKeysEnum.POD,
      K8sTableColumnKeysEnum.CONTAINER,
    ],
  };
  constructor(groupFilters: K8sTableColumnResourceKey[] = []) {
    const defaultGroupFilters = [K8sTableColumnKeysEnum.NAMESPACE] as K8sTableColumnResourceKey[];
    super([...defaultGroupFilters, ...groupFilters]);
  }
}
