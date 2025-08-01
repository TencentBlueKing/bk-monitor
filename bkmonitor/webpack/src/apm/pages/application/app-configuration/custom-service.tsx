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

import { Component, PropSync, ProvideReactive } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { customServiceList, deleteCustomSerivice } from 'monitor-api/modules/apm_meta';

import AddServiceDialog from './add-service-dialog';

import type { IAppInfo, ICustomServiceInfo } from './type';
import type { TimeRangeType } from 'monitor-pc/components/time-range/time-range';
import type { IPanelModel, IViewOptions } from 'monitor-ui/chart-plugins/typings';

interface IPagination {
  count: number;
  current: number;
  limit: number;
}

interface IProps {
  appInfo: IAppInfo;
}

@Component
export default class CustomService extends tsc<IProps> {
  @PropSync('data', { type: Object, required: true }) appInfo: IAppInfo;

  tableLoading = false;
  /** 新增自定义服务弹窗 */
  showAddDialog = false;
  /** 表格排序 */
  sortKey = '';
  /** 当前编辑的自定义服务 */
  curServiceInfo: ICustomServiceInfo | null = null;
  dashboardPanels: IPanelModel[] = []; // 数据量趋势面板配置
  serviceList: ICustomServiceInfo[] = [];
  /** 表格分页信息 */
  pagination: IPagination = {
    current: 1,
    count: 198,
    limit: 10,
  };

  // 派发到子孙组件内的视图配置变量
  // 视图变量
  @ProvideReactive('viewOptions') viewOptions: IViewOptions = {};
  // 时间间隔
  @ProvideReactive('timeRange') timeRange: TimeRangeType = ['now-12h', 'now'];
  // 对比的时间
  @ProvideReactive('timeOffset') timeOffset: string[] = [];

  created() {
    this.getServiceList();
  }

  /**
   * @desc 获取服务详情列表
   */
  async getServiceList() {
    const { current, limit } = this.pagination;
    const params = {
      app_name: this.appInfo.app_name,
      sort: this.sortKey,
      page: current,
      page_size: limit,
    };
    this.tableLoading = true;
    await customServiceList(params)
      .then(res => {
        this.serviceList = res.data || [];
        this.pagination.count = res.total || 0;
      })
      .finally(() => (this.tableLoading = false));
  }
  /**
   * @desc 列表排序
   */
  handleSortChange({ prop, order }) {
    switch (order) {
      case 'ascending':
        this.sortKey = prop;
        break;
      case 'descending':
        this.sortKey = `-${prop}`;
        break;
      default:
        this.sortKey = undefined;
    }
    this.getServiceList();
  }
  /**
   * @desc 分页操作
   * @param { number } page 当前页
   */
  handlePageChange(page: number) {
    this.pagination.current = page;
    this.getServiceList();
  }
  /**
   * @desc 切换limit
   * @param { number } limit 每页条数
   */
  handleLimitChange(limit: number) {
    this.pagination.limit = limit;
    this.pagination.current = 1;
    this.getServiceList();
  }
  /**
   * @desc 新增自定义服务
   */
  handleAddService() {
    this.curServiceInfo = null;
    this.showAddDialog = true;
  }
  /**
   * @desc 编辑自定义服务
   */
  handleEditService(service) {
    this.curServiceInfo = service;
    this.showAddDialog = true;
  }
  /**
   * @desc 跳转服务概览页
   */
  handleViewService(serviceName: string, type: string) {
    this.$router.push({
      name: 'service',
      query: {
        'filter-service_name': `${type}:${serviceName}`,
        'filter-app_name': this.appInfo.app_name,
      },
    });
  }
  /**
   * @desc 删除服务
   */
  handleDelete(id: number) {
    this.$bkInfo({
      type: 'warning',
      title: this.$t('确认删除此服务吗？'),
      confirmLoading: true,

      confirmFn: async () => {
        const res = await deleteCustomSerivice({ id })
          .then(() => true)
          .catch(() => false);
        if (res) {
          this.$bkMessage({
            message: this.$t('删除成功'),
            theme: 'success',
          });
          this.getServiceList();
        }
      },
    });
  }

  render() {
    const serviceNameSlots = {
      default: props => [
        <div
          key={`service-info-${props.$index}`}
          class='service-info'
        >
          {props.row.icon && props.row.match_type === 'manual' && (
            <img
              class='service-icon'
              alt=''
              src={props.row.icon}
            />
          )}
          {props.row.name ? (
            <span
              class='service-name'
              onClick={() => this.handleViewService(props.row.name, props.row.type)}
            >
              {props.row.name}
            </span>
          ) : (
            '--'
          )}
        </div>,
      ],
    };
    const operatorSlot = {
      default: props => [
        <bk-button
          key='operatorSlot_setting'
          class='mr10'
          theme='primary'
          text
          onClick={() => this.handleEditService(props.row)}
        >
          {this.$t('设置')}
        </bk-button>,
        <bk-button
          key='operatorSlot_delete'
          class='mr10'
          theme='primary'
          text
          onClick={() => this.handleDelete(props.row.id)}
        >
          {this.$t('删除')}
        </bk-button>,
      ],
    };

    return (
      <div class='custom-services-wrap'>
        <bk-table
          class={'service-table'}
          v-bkloading={{ isLoading: this.tableLoading }}
          data={this.serviceList}
          outer-border={false}
          pagination={this.pagination}
          row-auto-height={true}
          on-page-change={this.handlePageChange}
          on-page-limit-change={this.handleLimitChange}
          on-sort-change={this.handleSortChange}
        >
          <bk-table-column
            label={this.$t('服务名称')}
            scopedSlots={serviceNameSlots}
          />
          <bk-table-column
            label={this.$t('远程服务类型')}
            prop={'type'}
          />
          <bk-table-column
            width='160'
            label={this.$t('域名匹配')}
            prop={'host_match_count'}
            scopedSlots={{ default: props => props.row.host_match_count?.value }}
            sortable='custom'
          />
          <bk-table-column
            width='160'
            label={this.$t('URI匹配')}
            prop={'uri_match_count'}
            scopedSlots={{ default: props => props.row.uri_match_count?.value }}
            sortable='custom'
          />
          <bk-table-column
            width='180'
            label={this.$t('操作')}
            scopedSlots={operatorSlot}
          />
        </bk-table>

        <AddServiceDialog
          v-model={this.showAddDialog}
          appName={this.appInfo.app_name}
          serviceInfo={this.curServiceInfo}
          onRefresh={() => this.getServiceList()}
        />
      </div>
    );
  }
}
