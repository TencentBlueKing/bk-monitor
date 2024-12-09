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
import type { GroupListItem, SceneType, K8sDimensionParams } from './typings/k8s-new';

function getListK8SResources({ resource_type }): Promise<{ count: number; items: any[] }> {
  const mockData = {
    pod: {
      count: 1,
      items: [
        {
          pod: 'pod-1',
        },
      ],
    },
    workload: {
      count: 2,
      items: [
        {
          namespace: 'default',
          workload: 'Deployment',
        },
        {
          namespace: 'default',
          workload: 'state',
        },
      ],
    },
    namespace: {
      count: 1,
      items: [
        {
          bk_biz_id: 2,
          bcs_cluster_id: 'BCS-K8S-00000',
          namespace: 'default',
        },
      ],
    },
    container: {
      count: 1,
      items: [
        {
          pod: 'pod-1',
          namespace: 'default',
          workload: 'Deployment:workload-1',
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

/**
 * TODO : 缺少workload类型的特殊处理
 */

export class K8sDimension {
  /** 搜索关键字 */
  keyword = '';

  /** 所有的维度数据 */
  originDimensionData: GroupListItem[] = [];

  pageSize = 5;

  /** 场景 */
  scene: SceneType = 'performance';

  /** 场景维度枚举 */
  sceneDimensionMap = {
    performance: ['namespace', 'workload', 'pod', 'container'],
  };

  /** 当前展示的维度数据 */
  showDimensionData: GroupListItem[] = [];

  constructor(params: K8sDimensionParams) {
    this.scene = params.scene;
    this.keyword = params.keyword;
    this.pageSize = params.pageSize || 5;
    this.init();
  }

  /** 当前场景的维度列表 */
  get currentDimension() {
    return this.sceneDimensionMap[this.scene];
  }

  getAllDimensionData(params) {
    return Promise.all(
      this.currentDimension.map(dimension =>
        this.getDimensionData({
          ...params,
          resource_type: dimension,
        })
      )
    );
  }

  getDimensionData(params) {
    return getListK8SResources({
      ...params,
      query_string: this.keyword,
      sernario: this.scene,
    }).catch(() => ({ count: 0, items: [] }));
  }

  getWorkloadData() {
    return;
  }

  async init() {
    const data = await this.getAllDimensionData({});
    /** 初始化，不需要在意是否搜索，因为只展示第一页的数据，pageSize条 */
    this.originDimensionData = this.currentDimension.map((dimension, index) => {
      const { items, count } = data[index];
      return {
        id: dimension,
        name: dimension,
        total: count,
        hasMore: count > this.pageSize,
        children: items.map(item => ({
          id: item[dimension],
          name: item[dimension],
        })),
      };
    });
    this.showDimensionData = this.originDimensionData.map(dimension => {
      return {
        ...dimension,
        children: dimension.children.slice(0, this.pageSize),
      };
    });
  }

  /**
   * 加载更多维度数据
   * @param dimension 需要加载的维度子级链接
   */
  async loadMore(dimension: string) {
    /**
     *  1. 如果是搜索状态，接口返回的是全量数据，加载更多不需要请求接口，需要从原数据中找到分页数据，追加到当前展示的维度中
     *  2. 不是搜索状态，接口返回的分页数据，加载更多需要重新请求接口，并追加到原数据中，同时更新到当前展示的维度中
     */
    if (this.keyword) {
      const dimensions = this.originDimensionData.find(d => d.id === dimension);
      const showDimensions = this.showDimensionData.find(d => d.id === dimension);
      showDimensions.children = dimensions.children.slice(0, showDimensions.children.length + this.pageSize);
    } else {
      const { items } = await this.getDimensionData({
        resource_type: dimension,
      });
      const dimensions = this.originDimensionData.find(d => d.id === dimension);
      dimensions.children = [
        ...dimensions.children,
        ...items.map(item => ({
          id: item[dimension],
          name: item[dimension],
        })),
      ];
      const showDimensions = this.showDimensionData.find(d => d.id === dimension);
      showDimensions.children = dimensions.children;
    }
  }

  /** 搜索 */
  search(keyword: string) {
    this.keyword = keyword;
    this.init();
  }
}
