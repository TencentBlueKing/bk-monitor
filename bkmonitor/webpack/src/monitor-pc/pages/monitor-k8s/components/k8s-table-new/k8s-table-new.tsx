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
import { Prop, Component, Emit } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import EmptyStatus from '../../../../components/empty-status/empty-status';
import TableSkeleton from '../../../../components/skeleton/table-skeleton';
import { K8sNewTabEnum } from '../../typings/k8s-new';
import CommonTable from '../common-table';

import './k8s-table-new.scss';

interface K8sTableNewProps {
  activeTab: K8sNewTabEnum;
  loading: boolean;
}
interface K8sTableNewEvent {
  onGetList: (param: any) => void;
}
/**
 * @description: k8s table column keys 枚举 (方便后期字段名维护)
 */
enum K8sTableColumnKeysEnum {
  /**
   * @description: cluster - 集群
   */
  CLUSTER = 'cluster',
  /**
   * @description: container - 容器
   */
  CONTAINER = 'container',
  /**
   * @description: cpu - CPU使用率
   */
  CPU = 'cpu',
  /**
   * @description: internal_memory - 内存使用率
   */
  INTERNAL_MEMORY = 'internal_memory',
  /**
   * @description: namespace - namespace
   */
  NAMESPACE = 'namespace',
  /**
   * @description: pod - pod
   */
  POD = 'pod',
  /**
   * @description: workload - workload
   */
  WORKLOAD = 'workload',
  /**
   * @description: workload_type - workload_type
   */
  WORKLOAD_TYPE = 'workload_type',
}

const tabToTableColumnsMap = {
  [K8sNewTabEnum.LIST]: [
    K8sTableColumnKeysEnum.POD,
    K8sTableColumnKeysEnum.WORKLOAD,
    K8sTableColumnKeysEnum.NAMESPACE,
    K8sTableColumnKeysEnum.CPU,
    K8sTableColumnKeysEnum.INTERNAL_MEMORY,
  ],
  [K8sNewTabEnum.DETAIL]: [
    K8sTableColumnKeysEnum.CLUSTER,
    K8sTableColumnKeysEnum.NAMESPACE,
    K8sTableColumnKeysEnum.WORKLOAD,
    K8sTableColumnKeysEnum.WORKLOAD_TYPE,
    K8sTableColumnKeysEnum.POD,
    K8sTableColumnKeysEnum.CONTAINER,
    K8sTableColumnKeysEnum.CPU,
    K8sTableColumnKeysEnum.INTERNAL_MEMORY,
  ],
};

@Component
export default class K8sTableNew extends tsc<K8sTableNewProps, K8sTableNewEvent> {
  @Prop({ type: String }) activeTab: K8sNewTabEnum;
  @Prop({ type: Boolean, default: false }) loading: boolean;
  @Prop({ type: Array }) tableData: any[];
  @Prop({ type: String }) groupCondition: any[];
  @Prop({ type: Array }) filterCondition: any[];
  @Prop({ type: Object }) sortCondition: any;

  @Emit('getList')
  getList() {
    return {};
  }

  get tableColumns() {
    const map = this.getKeyToTableColumnsMap();
    return tabToTableColumnsMap[this.activeTab].map(key => map[key]);
  }

  getKeyToTableColumnsMap() {
    const { CLUSTER, POD, WORKLOAD_TYPE, WORKLOAD, NAMESPACE, CONTAINER, CPU, INTERNAL_MEMORY } =
      K8sTableColumnKeysEnum;
    return {
      [CLUSTER]: {
        id: CLUSTER,
        name: 'cluster',
        sortable: false,
        type: 'link',
        width: null,
        min_width: 90,
      },
      [POD]: {
        id: POD,
        name: 'Pod',
        sortable: false,
        type: 'link',
        width: null,
        min_width: 90,
      },
      [WORKLOAD_TYPE]: {
        id: WORKLOAD_TYPE,
        name: 'workload_type',
        sortable: false,
        type: 'link',
        width: null,
        min_width: 120,
      },
      [WORKLOAD]: {
        id: WORKLOAD,
        name: 'workload',
        sortable: false,
        type: 'link',
        width: null,
        min_width: 110,
      },
      [NAMESPACE]: {
        id: NAMESPACE,
        name: 'namespace',
        sortable: false,
        type: 'link',
        width: null,
        min_width: 260,
      },
      [CONTAINER]: {
        id: CONTAINER,
        name: 'container',
        sortable: false,
        type: 'link',
        width: null,
        min_width: 120,
      },
      [CPU]: {
        id: CPU,
        name: 'CPU使用率',
        sortable: 'custom',
        type: 'datapoints',
        width: null,
        min_width: 180,
      },
      [INTERNAL_MEMORY]: {
        id: INTERNAL_MEMORY,
        name: '内存使用率',
        sortable: 'custom',
        type: 'datapoints',
        width: null,
        min_width: 180,
      },
    };
  }

  /**
   * @description 表格排序
   * @param {Object} { column, prop, order }
   */
  handleSortChange({ prop, order }) {}

  /**
   * @description 清空搜索条件
   *
   */
  handleClearSearch() {}

  render() {
    return (
      <div class='k8s-table-new'>
        {!this.loading ? (
          <CommonTable
            style={{ display: !this.loading ? 'block' : 'none' }}
            checkable={false}
            columns={this.tableColumns}
            data={this.tableData}
            hasColumnSetting={false}
            scrollLoading={false}
            onSortChange={val => this.handleSortChange(val as any)}
          >
            <EmptyStatus
              slot='empty'
              textMap={{
                empty: this.$t('暂无数据'),
              }}
              type={this.groupCondition?.length || this.filterCondition?.length ? 'search-empty' : 'empty'}
              onOperation={() => this.handleClearSearch()}
            />
          </CommonTable>
        ) : (
          <TableSkeleton
            class='table-skeleton'
            type={5}
          />
        )}
      </div>
    );
  }
}
