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
import {
  type GroupListItem,
  type K8sDimensionParams,
  K8sTableColumnKeysEnum,
  EDimensionKey,
  SceneEnum,
} from './typings/k8s-new';

function getWorkloadOverview(_params): Promise<(number | string)[][]> {
  const mockData = [
    ['Deployment', 7],
    ['StatefulSets', 7],
    ['DaemonSets', 7],
    ['Jobs', 7],
    ['CronJobs', 7],
  ];
  return new Promise(resolve => {
    setTimeout(() => {
      resolve(mockData);
    }, 1000);
  });
}

function getListK8SResources({ resource_type }: any): Promise<{ count: number; items: any[] }> {
  const mockData = {
    pod: {
      count: 2,
      items: [
        {
          pod: 'pod-1',
          namespace: 'default',
          workload: 'Deployment:workload-1',
        },
        {
          pod: 'pod-5',
          namespace: 'default',
          workload: 'Deployment:workload-3',
        },
      ],
    },
    workload: {
      count: 7,
      items: [
        {
          namespace: 'default',
          workload: 'Deployment:workload-1',
        },
        {
          namespace: 'demo',
          workload: 'Deployment:workload-2',
        },
        {
          namespace: 'demo',
          workload: 'Deployment:workload-3',
        },
        {
          namespace: 'demo',
          workload: 'Deployment:workload-4',
        },
        {
          namespace: 'demo',
          workload: 'Deployment:workload-5',
        },
        {
          namespace: 'demo',
          workload: 'Deployment:workload-6',
        },
        {
          namespace: 'demo',
          workload: 'Deployment:workload-7',
        },
      ],
    },
    namespace: {
      count: 10,
      items: [
        ...new Array(10).fill(null).map((_item, index) => {
          return {
            bk_biz_id: 2,
            bcs_cluster_id: 'BCS-K8S-00000',
            namespace: `default${index}`,
          };
        }),
      ],
    },
    container: {
      count: 2,
      items: [
        {
          pod: 'pod-1',
          container: 'container-1',
          namespace: 'default',
          workload: 'Deployment:workload-1',
        },
        {
          pod: 'pod-2',
          container: 'container-2',
          namespace: 'demo',
          workload: 'Deployment:wrokload-2',
        },
      ],
    },
  };

  return new Promise(resolve => {
    setTimeout(() => {
      resolve(mockData[resource_type]);
    }, 1000);
  });
}

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
   * @description rest/v2/k8s/resources/list_k8s_resources/ 获取所有维度值选项
   * @param params
   * @returns
   */
  getDimensionData(params) {
    return getListK8SResources({
      ...this.commonParams,
      ...params,
    }).catch(() => ({ count: 0, items: [] }));
  }

  /**
   * 获取性能场景所有维度的数据, 并初始化各维度的page为1
   * @param params 请求参数
   */
  async getPerformanceDimensionData(params = {}) {
    const originDimensionData = [];
    const pageMap = {};
    let workloadCategory = [];
    const promiseList = this.currentDimension.map(async dimension => {
      if (dimension === EDimensionKey.workload) {
        workloadCategory = await this.getWorkloadData({
          bcs_cluster_id: this.bcsClusterId,
          query_string: this.keyword,
        });
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
        originDimensionData.push({
          id: dimension,
          name: dimension,
          count: total,
          children,
        });
      } else {
        const data = await this.getDimensionData({
          resource_type: dimension,
          page: 1,
          ...params,
        });
        pageMap[dimension] = 1;
        originDimensionData.push({
          id: dimension,
          name: dimension,
          count: data.count,
          children: data.items.map(item => this.formatData(dimension, item)),
        });
      }
    });
    this.originDimensionData = originDimensionData;
    this.pageMap = pageMap;
    await Promise.all(promiseList);
    await this.getWorkloadChildrenData({
      filter_dict: {
        workload: `${workloadCategory[0][0]}:`,
      },
    });
  }

  /**
   * @description 获取workload维度下某个分类的数据
   */
  async getWorkloadChildrenData({ filter_dict, ...params }) {
    const { workload: workloadParams } = filter_dict;
    const [category] = workloadParams.split(':');
    const data = await getListK8SResources({
      ...this.commonParams,
      resource_type: EDimensionKey.workload,
      page: this.pageMap[category],
      filter_dict,
      ...params,
    });
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
   * @description rest/v2/k8s/resources/workload_overview/ 获取 workload分类数据
   * @param params
   * @returns
   */
  getWorkloadData(params) {
    return getWorkloadOverview({
      ...params,
    }).catch(() => []);
  }

  /**
   * @description 初始化维度数据
   */
  async init(params = {}) {
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
        const data = await this.getDimensionData({
          resource_type: dimension,
          page: this.pageMap[dimension],
          ...params,
        });
        const dimensionList = this.originDimensionData.find(item => item.id === dimension);
        dimensionList.children = dimensionList.children.concat(
          data.items.map(item => this.formatData(dimension, item))
        );
        this.originDimensionData = [...this.originDimensionData];
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
        const data = await this.getDimensionData({
          resource_type: dimension,
          page: this.pageMap[dimension],
          ...params,
        });
        const dimensionList = this.originDimensionData.find(item => item.id === dimension);
        dimensionList.children = data.items.map(item => this.formatData(fatherDimension, item));
        this.originDimensionData = [...this.originDimensionData];
      }
    } else {
      this.init();
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
  public groupFilters: K8sTableColumnKeysEnum[] = [];
  constructor(groupFilters: K8sTableColumnKeysEnum[] = []) {
    this.defaultGroupFilter = new Set(groupFilters);
    this.setGroupFilters(groupFilters);
  }

  /**
   * @description 添加 groupFilters
   * @param {K8sTableColumnKeysEnum} groupId
   */
  addGroupFilter(groupId: K8sTableColumnKeysEnum) {
    this.setGroupFilters(this.dimensionsMap[groupId]);
  }

  /**
   * @description 删除 groupFilters
   * @param {K8sTableColumnKeysEnum} groupId
   */
  deleteGroupFilter(groupId: K8sTableColumnKeysEnum) {
    const indexOrMsg = this.verifyDeleteGroupFilter(groupId);
    if (typeof indexOrMsg === 'string') return;
    this.deleteGroupFilterForce(groupId);
  }

  /**
   * @description 强制删除 groupFilter（将所在层级及所有子级对象删除）
   * @param {K8sTableColumnKeysEnum} groupId
   */
  deleteGroupFilterForce(groupId: K8sTableColumnKeysEnum) {
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
   * @returns {K8sTableColumnKeysEnum}
   */
  getLastGroupFilter() {
    return this.groupFilters[this.groupFilters.length - 1];
  }

  /**
   * @description 判断是否存在 groupId
   * @param {K8sTableColumnKeysEnum} groupId
   * @returns {boolean}
   */
  hasGroupFilter(groupId: K8sTableColumnKeysEnum) {
    return this.groupFiltersSet.has(groupId);
  }

  /**
   * @description 判断是否为默认 groupFilter
   * @param {K8sTableColumnKeysEnum} groupId
   * @returns {boolean}
   */
  isDefaultGroupFilter(groupId: K8sTableColumnKeysEnum) {
    return this.defaultGroupFilter.has(groupId);
  }

  /**
   * @description 修改 groupFilters
   * @param {K8sTableColumnKeysEnum[]} groupFilters
   */
  setGroupFilters(groupFilters: K8sTableColumnKeysEnum[]) {
    this.groupFilters = groupFilters;
    this.groupFiltersSet = new Set(groupFilters);
  }

  /**
   * @description 校验传入 groupId 是否可删除
   * @param {K8sTableColumnKeysEnum} groupId
   * @returns {string | number} string 类型表示不可删除，number 类型表示删除成功
   */
  verifyDeleteGroupFilter(groupId: K8sTableColumnKeysEnum) {
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
    K8sTableColumnKeysEnum.CLUSTER,
    K8sTableColumnKeysEnum.NAMESPACE,
    K8sTableColumnKeysEnum.WORKLOAD,
    K8sTableColumnKeysEnum.WORKLOAD_TYPE,
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
  constructor(groupFilters: K8sTableColumnKeysEnum[] = []) {
    const defaultGroupFilters = [K8sTableColumnKeysEnum.NAMESPACE];
    super([...defaultGroupFilters, ...groupFilters]);
  }
}
