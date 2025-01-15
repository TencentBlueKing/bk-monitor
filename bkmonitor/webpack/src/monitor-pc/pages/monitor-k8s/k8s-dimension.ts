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
  type K8sSortType,
} from './typings/k8s-new';

import type {
  K8sTableColumnChartKey,
  K8sTableColumnResourceKey,
  K8sTableSortContainer,
} from './components/k8s-table-new/k8s-table-new';

export const sceneDimensionMap = {
  [SceneEnum.Performance]: [
    EDimensionKey.namespace,
    EDimensionKey.workload,
    EDimensionKey.pod,
    EDimensionKey.container,
  ],
};

/**
 * k8s维度列表基类
 */
export abstract class K8sDimensionBase {
  /** 所有的维度数据 */
  public originDimensionData: GroupListItem<EDimensionKey>[] = [];
  /** 各维度分页 */
  public pageMap = {};
  /** 分页数量 */
  public pageSize = 5;
  /** 分页类型 */
  public pageType: K8sDimensionParams['page_type'] = 'scrolling';
  /** 维度列表Key */
  // eslint-disable-next-line perfectionist/sort-classes
  abstract dimensionKey: string[];

  constructor(params: K8sDimensionParams) {
    this.pageSize = params.page_size;
    this.pageType = params.page_type;
  }

  abstract get showDimensionData(): GroupListItem[];

  abstract init(params: Record<string, any>): Promise<void>;

  abstract loadNextPageData(dimensions: string[], params: Record<string, any>): Promise<void>;

  abstract search(keyword: string, params: Record<string, any>, dimensions: string[]): Promise<void>;
}

/**
 * k8s性能场景维度列表
 */
export class K8sPerformanceDimension extends K8sDimensionBase {
  commonParams: K8sDimensionParams = null;

  // /** 场景维度枚举 */
  dimensionKey = sceneDimensionMap[SceneEnum.Performance];

  constructor(params: K8sDimensionParams) {
    super(params);
    this.commonParams = params;
    this.originDimensionData = this.dimensionKey.map(key => ({
      id: key,
      name: key,
      count: 0,
      children: [],
    }));
  }

  /** 当前展示的维度数据 */
  get showDimensionData() {
    return this.originDimensionData.map(dimension => {
      let showMore = false;
      let children = [];
      if (dimension.id === EDimensionKey.workload) {
        children = dimension.children.map(item => {
          return {
            ...item,
            showMore: item.count > this.pageSize * (this.pageMap[item.id] || 1),
            children: this.removeDuplicate(item.children.slice(0, this.pageSize * this.pageMap[item.id] || 1)),
          };
        });
      } else {
        showMore = dimension.count > this.pageSize * (this.pageMap[dimension.id] || 1);
        children = this.removeDuplicate(dimension.children.slice(0, this.pageSize * this.pageMap[dimension.id] || 1));
      }
      return {
        ...dimension,
        showMore,
        children,
      };
    });
  }

  /**
   * @description 整理items数据
   * @param type 维度类型
   * @param dataItem 接口数据
   * @returns 格式化的数据
   */
  formatData(type: EDimensionKey, dataItem) {
    let name = dataItem[type];
    if (type === EDimensionKey.workload) {
      name = dataItem[type]?.split?.(':')?.[1] || '--';
    }
    return {
      id: dataItem[type],
      name: name,
      relation: dataItem, // 关联数据
    };
  }

  /**
   * 获取常规维度数据（性能场景除workload维度）
   * @param params 请求参数
   */
  async getDimensionData({ resource_type, ...params }) {
    const data = await listK8sResources({
      ...this.commonParams,
      resource_type,
      page: this.pageMap[resource_type] || 1,
      ...params,
    }).catch(() => ({ count: 0, items: [] }));
    const dimensionList = this.originDimensionData.find(item => item.id === resource_type);
    dimensionList.count = data.count;

    if (this.pageType === 'scrolling') {
      dimensionList.children = data.items.map(item => this.formatData(resource_type, item));
    } else {
      dimensionList.children = dimensionList.children.concat(
        data.items.map(item => this.formatData(resource_type, item))
      );
    }
    this.originDimensionData = [...this.originDimensionData];
  }

  /**
   * @description 获取workload维度下某个分类的数据
   */
  async getWorkloadChildrenData(params) {
    const { filter_dict, ...otherParams } = params;
    const { workload: workloadParams } = filter_dict;
    const [category] = workloadParams.split(':');
    const data = await listK8sResources({
      ...this.commonParams,
      resource_type: EDimensionKey.workload,
      page: this.pageMap[category],
      filter_dict,
      ...otherParams,
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
    const pageMap = {};
    const workloadCategory = await workloadOverview({
      bcs_cluster_id: this.commonParams.bcs_cluster_id,
      query_string: this.commonParams.query_string,
    }).catch(() => []);

    const promiseList = this.originDimensionData.map(async item => {
      if (item.id === EDimensionKey.workload) {
        item.count = 0;
        item.children = workloadCategory.map(category => {
          item.count += category[1];
          pageMap[category[0]] = 1;
          return {
            id: category[0],
            name: category[0],
            count: category[1],
            children: [],
          };
        });
        if (workloadCategory.length) {
          await this.getWorkloadChildrenData({
            filter_dict: {
              workload: `${workloadCategory[0][0]}:`,
            },
            ...params,
          });
        }
      } else {
        await this.getDimensionData({
          resource_type: item.id,
          ...params,
        });
        pageMap[item.id] = 1;
      }
    });

    this.pageMap = pageMap;
    await Promise.all(promiseList);
  }

  /**
   * 加载某个维度（类目）下一页数据
   * @param dimensions 维度链接（一级维度 -> 二级类目）
   * @param params 查询参数
   */
  async loadNextPageData(dimensions: string[] = [], params = {}) {
    const [dimension, category] = dimensions;
    if (dimension === EDimensionKey.workload) {
      this.pageMap[category] += 1;
      await this.getWorkloadChildrenData({
        filter_dict: {
          workload: `${category}:`,
        },
        ...params,
      });
    } else {
      this.pageMap[dimension] += 1;
      await this.getDimensionData({
        resource_type: dimension,
        page: this.pageMap[dimension],
        ...params,
      });
    }
  }

  /** 数组去重 */
  removeDuplicate(list: { id: string; name: string }[]) {
    const map = new Map();

    return list.filter(item => {
      if (map.has(item.id)) return false;
      map.set(item.id, item);
      return true;
    });
  }

  /**
   * 搜索所有维度或者单个维度
   * @param keyword 搜索关键字
   * @param params 搜索参数
   * @param dimensions 维度链接（一级维度 -> 二级类目）
   */
  async search(keyword: string, params = {}, dimensions = []) {
    const [dimension, category] = dimensions;
    this.commonParams.query_string = keyword;
    if (dimension) {
      if (dimension === EDimensionKey.workload) {
        this.pageMap[category] = 1;
        await this.getWorkloadChildrenData({
          ...params,
        });
      } else {
        this.pageMap[dimension] = 1;
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
  /** 默认排序字段 */
  abstract defaultSortContainer: Omit<K8sTableSortContainer, 'initDone'>;
  /** 实现类填充存在的 dimensions  */
  abstract dimensions: K8sTableColumnKeysEnum[];
  /** 当前场景实现类填充groupBy选择器可选择的维度  */
  abstract groupByDimensions: K8sTableColumnKeysEnum[];
  abstract groupByDimensionsMap: Partial<Record<K8sTableColumnKeysEnum, K8sTableColumnKeysEnum[]>>;
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
   * @param {boolean} config.single 是否单项操作（true: 单项添加，false: 将所在层级及所有父级对象加入）
   */
  addGroupFilter(groupId: K8sTableColumnResourceKey, config?: { single: boolean }) {
    if (config?.single) {
      const groupFilters = this.groupByDimensions.reduce((prev, curr) => {
        if (this.groupFiltersSet.has(curr) || curr === groupId) {
          prev.push(curr);
        }
        return prev;
      }, []);
      this.setGroupFilters(groupFilters);
      return;
    }
    this.setGroupFilters(this.groupByDimensionsMap[groupId] as K8sTableColumnResourceKey[]);
  }

  /**
   * @description 删除 groupFilter
   * @param {K8sTableColumnResourceKey} groupId
   * @param {boolean} config.single 是否单项操作（true: 单项删除，false: 将所在层级及所有子级对象删除）
   */
  deleteGroupFilter(groupId: K8sTableColumnResourceKey, config?: { single: boolean }) {
    if (!this.hasGroupFilter(groupId)) return;
    if (config?.single) {
      this.groupFiltersSet.delete(groupId);
      this.setGroupFilters([...this.groupFiltersSet] as K8sTableColumnResourceKey[]);
      return;
    }
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
   * @description 获取当前维度的资源类型 (最后一个 groupFilter)
   * @returns {K8sTableColumnResourceKey}
   */
  getResourceType() {
    return this.groupFilters.at(-1);
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
}

/**
 * @description 性能 类型 GroupFilter 实现类
 * */
export class K8sPerformanceGroupDimension extends K8sGroupDimension {
  readonly defaultSortContainer = {
    prop: K8sTableColumnKeysEnum.CPU_USAGE as K8sTableColumnChartKey,
    orderBy: 'desc' as K8sSortType,
  };
  readonly dimensions = [
    K8sTableColumnKeysEnum.CLUSTER,
    K8sTableColumnKeysEnum.NAMESPACE,
    K8sTableColumnKeysEnum.WORKLOAD,
    K8sTableColumnKeysEnum.POD,
    K8sTableColumnKeysEnum.CONTAINER,
  ];
  readonly groupByDimensions = [
    K8sTableColumnKeysEnum.NAMESPACE,
    K8sTableColumnKeysEnum.WORKLOAD,
    K8sTableColumnKeysEnum.POD,
    K8sTableColumnKeysEnum.CONTAINER,
  ];
  readonly groupByDimensionsMap = {
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
