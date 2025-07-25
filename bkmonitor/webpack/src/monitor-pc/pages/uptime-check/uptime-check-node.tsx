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
import { Component, Emit, Inject, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { destroyUptimeCheckNode, listUptimeCheckNode } from 'monitor-api/modules/model';
import { commonPageSizeSet } from 'monitor-common/utils';

import EmptyStatus from '../../components/empty-status/empty-status';
import TableSkeleton from '../../components/skeleton/table-skeleton';
import CommonTable from '../monitor-k8s/components/common-table';
import DeleteSubtitle from '../strategy-config/strategy-config-common/delete-subtitle';
import HeaderTools, { type IClickType } from './components/header-tools';
import OperateOptions from './components/operate-options';
import {
  type INodeData,
  type INodesTableData,
  nodeStatusMap,
  nodesToTableData,
  nodesToTableDataInit,
  paginationUtil,
  searchNodesData,
} from './uptime-check-data';

import type { EmptyStatusOperationType, EmptyStatusType } from '../../components/empty-status/types';

import './uptime-check-node.scss';

interface IUptimeCheckNodeEvents {
  refreshKey?: string;
  onLoading?: (v: boolean) => void;
  onNameChange?: (v: string) => void;
}
@Component({
  name: 'UptimeCheckNode',
})
export default class UptimeCheckNode extends tsc<IUptimeCheckNodeEvents> {
  @Prop({ type: String, default: '' }) refreshKey: string;
  @Inject('authority') authority;
  @Inject('authorityMap') authorityMap;
  @Inject('handleShowAuthorityDetail') handleShowAuthorityDetail;

  data: {
    nodes: INodeData[];
  } = {
    nodes: [],
  };

  nodesTableData: INodesTableData = nodesToTableDataInit();

  searchValue = '';

  isTableSort = false;
  sortTableData = [];
  emptyStatusType: EmptyStatusType = 'empty';
  loading = false;
  skeletonLoading = false;
  get searchData(): INodeData[] {
    return searchNodesData(this.searchValue, this.data.nodes);
  }

  @Watch('refreshKey')
  handleRefresh() {
    this.init();
  }

  activated() {
    const { query } = this.$route;
    this.searchValue = query.queryString?.toString() || '';
    this.init();
  }
  deactivated() {}

  async init() {
    this.handleLoading(true);
    const data = await listUptimeCheckNode()
      .then(res => res)
      .catch(() => {
        this.emptyStatusType = '500';
        return [];
      });
    this.handleLoading(false);
    this.data.nodes = data;
    this.nodesTableData = nodesToTableDataInit(data);
    if (this.searchValue.length) {
      this.handleSearch(this.searchValue, true);
    }
  }
  /**
   *
   * @param bizId 业务id
   * @returns 是否有编辑权限
   */
  canEdit(bizId: number) {
    return bizId === Number(this.$store.getters.bizId);
  }

  handleNodeOperate(v: 'delete' | 'edit', row: INodeData) {
    switch (v) {
      case 'edit':
        this.$router.push({
          name: 'uptime-check-node-edit',
          params: {
            id: String(row.id),
            bizId: String(row.bk_biz_id),
            title: this.$tc('编辑拨测节点'),
          },
        });
        break;
      case 'delete':
        this.$bkInfo({
          type: 'warning',
          title: this.$t('你确认要删除?'),
          subHeader: this.$createElement(DeleteSubtitle, {
            props: {
              title: this.$tc('节点名称'),
              name: row.name,
            },
          }),
          maskClose: true,
          escClose: true,
          confirmFn: () => {
            // this.handleLoading(true);
            this.loading = true;
            destroyUptimeCheckNode(row.id)
              .then(() => {
                this.$bkMessage({ theme: 'success', message: this.$t('删除成功') });
                this.init();
              })
              .catch(() => {
                // this.handleLoading(false);
                this.loading = false;
              });
          },
        });
        break;
    }
  }

  // 搜索
  handleSearch(v: string, isInit = false) {
    this.emptyStatusType = v ? 'search-empty' : 'empty';
    this.searchValue = v;
    const pagination = {
      ...this.nodesTableData.pagination,
      count: this.searchData.length,
      current: 1,
    };
    this.nodesTableData.pagination = pagination;
    this.nodesTableData.data = nodesToTableData(paginationUtil(pagination, this.searchData));

    const params = {
      name: this.$route.name,
      query: {
        ...this.$route.query,
        queryString: v.trim?.().length ? v : undefined,
      },
    };
    if (!isInit) {
      this.$router.replace(params).catch(() => {});
    }
  }

  handlePageChange(v: number) {
    const pagination = {
      count: this.searchData.length,
      current: v,
      limit: this.nodesTableData.pagination.limit,
    };
    this.nodesTableData.pagination = pagination;
    this.nodesTableData.data = nodesToTableData(
      paginationUtil(pagination, this.isTableSort ? this.sortTableData : this.searchData)
    );
  }
  handleLimitChange(v: number) {
    const pagination = {
      count: this.searchData.length,
      current: 1,
      limit: v,
    };
    this.nodesTableData.pagination = pagination;
    this.nodesTableData.data = nodesToTableData(
      paginationUtil(pagination, this.isTableSort ? this.sortTableData : this.searchData)
    );
    commonPageSizeSet(v);
  }

  // loading
  @Emit('loading')
  handleLoading(v: boolean) {
    this.skeletonLoading = v;
    return v;
  }

  handleHeaderCreate(v: IClickType) {
    switch (v) {
      case 'createNode':
        this.$router.push({
          name: 'uptime-check-node-add',
        });
        break;
    }
  }
  // 带上节点名称跳转到任务列表
  @Emit('nameChange')
  handleNameChange(v: string) {
    return v;
  }

  handleSortChange(v: { order: 'ascending' | 'descending' | null; prop: string }) {
    const columnId = v.prop;
    const { order } = v; // ascending: 升序
    let nodeData = [];
    const pagination = {
      count: this.searchData.length,
      current: 1,
      limit: 10,
    };
    if (order) {
      switch (columnId as 'task_num_text') {
        case 'task_num_text':
          nodeData = [...this.searchData].sort((a, b) => {
            if (order === 'ascending') {
              return a.task_num - b.task_num;
            }
            return b.task_num - a.task_num;
          });
          break;
      }
      this.isTableSort = true;
      this.sortTableData = nodeData;
    } else {
      nodeData = this.searchData;
      this.isTableSort = false;
      this.sortTableData = [];
    }
    this.nodesTableData.pagination = pagination;
    this.nodesTableData.data = nodesToTableData(paginationUtil(pagination, nodeData));
  }

  handleOperation(type: EmptyStatusOperationType) {
    if (type === 'clear-filter') {
      this.searchValue = '';
      this.handleSearch(this.searchValue);
      return;
    }
    if (type === 'refresh') {
      this.init();
      return;
    }
  }

  render() {
    return (
      <div class='uptime-check-task-component'>
        <div class='table-data-content'>
          <HeaderTools
            option={{
              showNode: true,
            }}
            search={this.searchValue}
            onCreate={this.handleHeaderCreate}
            onSearch={(v: string) => this.handleSearch(v)}
          />
          {this.skeletonLoading ? (
            <TableSkeleton class='mt-16' />
          ) : (
            <CommonTable
              style={{ marginTop: '16px' }}
              {...{ props: this.nodesTableData }}
              scopedSlots={{
                taskNum: (row: INodeData) => (
                  <span
                    class='task-num'
                    onClick={() => this.handleNameChange(row.name)}
                  >
                    {row.task_num || 0}
                  </span>
                ),
                opreate: (row: INodeData) => (
                  <OperateOptions
                    options={{
                      outside: [
                        {
                          id: 'edit',
                          name: window.i18n.tc('编辑'),
                          authority: this.authority.MANAGE_AUTH,
                          authorityDetail: this.authorityMap.MANAGE_AUTH,
                          disable: !this.canEdit(row.bk_biz_id),
                          tip: !this.canEdit(row.bk_biz_id) ? this.$tc('非当前业务节点') : '',
                        },
                        {
                          id: 'delete',
                          name: window.i18n.tc('删除'),
                          authority: this.authority.MANAGE_AUTH,
                          authorityDetail: this.authorityMap.MANAGE_AUTH,
                          disable: !this.canEdit(row.bk_biz_id),
                          tip: !this.canEdit(row.bk_biz_id) ? this.$tc('非当前业务节点') : '',
                        },
                      ],
                    }}
                    onOptionClick={(v: 'delete' | 'edit') => this.handleNodeOperate(v, row)}
                  />
                ),
                statusText: (row: INodeData) => (
                  <span
                    style={{ color: nodeStatusMap[row.status].color }}
                    class='status-col'
                  >
                    {nodeStatusMap[row.status].text}
                    {row.status.toString() === '-2' && (
                      <i
                        class='icon-monitor icon-shixiao status-icon'
                        v-bk-tooltips={{ content: this.$t('该主机实例不存在') }}
                      />
                    )}
                  </span>
                ),
              }}
              onLimitChange={this.handleLimitChange}
              onPageChange={this.handlePageChange}
              onSortChange={this.handleSortChange}
            >
              <EmptyStatus
                slot='empty'
                type={this.emptyStatusType}
                onOperation={this.handleOperation}
              />
            </CommonTable>
          )}
        </div>
      </div>
    );
  }
}
