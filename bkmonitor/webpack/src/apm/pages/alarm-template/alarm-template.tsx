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

import { Component, InjectReactive } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import StatusTab from 'monitor-ui/chart-plugins/plugins/table-chart/status-tab';

import AlarmTemplateTable from './components/alarm-template-table/alarm-template-table';
import AlarmTemplateSearch from './components/alarm-templte-search/alarm-template-search';
import BatchOperations from './components/batch-operations/batch-operations';
import EditTemplateSlider from './components/template-form/edit-template-slider';
import { ALARM_TEMPLATE_QUICK_FILTER_LIST, AlarmTemplateTypeMap } from './constant';
import TemplateDetails from './template-operate/template-details';
import TemplatePush from './template-operate/template-push';

import type { AlarmDeleteConfirmEvent } from './components/alarm-delete-confirm/alarm-delete-confirm';
import type {
  AlarmTemplateConditionParamItem,
  AlarmTemplateDetailTabEnumType,
  AlarmTemplateListItem,
  BatchOperationTypeEnumType,
} from './typing';
import type { SearchSelectItem } from 'monitor-pc/pages/query-template/typings';
import type { IViewOptions } from 'monitor-ui/chart-plugins/typings';

import './alarm-template.scss';

@Component
export default class AlarmTemplate extends tsc<object> {
  /** 列表请求状态 loading */
  tableLoading = false;
  /** 表格数据 */
  tableData: AlarmTemplateListItem[] = [
    {
      id: 1,
      name: '[调用分析] 主调平均耗时',
      system: 'RPC',
      category: 'RPC_CALLER',
      type: 'app',
      is_enabled: true,
      is_auto_apply: true,
      algorithms: [
        {
          level: 2,
          method: 'lte',
          threshold: 1000,
          type: 'Threshold',
        },
        {
          level: 1,
          method: 'lte',
          threshold: 3000,
          type: 'Threshold',
        },
      ],
      user_group_list: [{ id: 1, name: '应用创建者' }],
      applied_service_names: ['example.greeter1', 'example.greeter'],
      create_user: 'admin',
      create_time: '2025-08-04 17:43:26+0800',
      update_user: 'admin',
      update_time: '2025-08-04 17:43:26+0800',
    },
    {
      id: 2,
      name: '[调用分析] 主调平均耗时',
      system: 'RPC',
      category: 'RPC_CALLER',
      type: 'inner',
      is_enabled: false,
      is_auto_apply: false,
      algorithms: [
        {
          level: 3,
          method: 'lte',
          threshold: 1000,
          type: 'Threshold',
        },
        {
          level: 2,
          method: 'lte',
          threshold: 1000,
          type: 'Threshold',
        },
        {
          level: 1,
          method: 'lte',
          threshold: 3000,
          type: 'Threshold',
        },
      ],
      user_group_list: [
        { id: 1, name: '应用创建者' },
        { id: 2, name: 'admin' },
        { id: 3, name: 'ascasc' },
      ],
      applied_service_names: [
        'activity-microservce.activities-10012',
        'example.greeter',
        'example.greeter',
        'example.greeter',
        'example.greeter',
        'example.greeter',
        'example.greeter',
        'example.greeter',
        'example.greeter',
        'example.greeter',
        'example.greeter',
        'example.greeter',
        'example.greeter',
        'example.greeter',
        'example.greeter',
      ],
      create_user: 'admin',
      create_time: '2025-08-04 17:43:26+0800',
      update_user: 'admin',
      update_time: '2025-08-04 17:43:26+0800',
    },
    {
      id: 3,
      name: '[调用分析] 主调平均耗时',
      system: 'RPC',
      category: 'RPC_CALLER',
      type: 'inner',
      is_enabled: false,
      is_auto_apply: false,
      algorithms: [],
      user_group_list: [
        { id: 1, name: '应用创建者' },
        { id: 2, name: 'admin' },
        { id: 3, name: 'test' },
        { id: 4, name: 'xxxxxxz' },
      ],
      applied_service_names: ['activity-microservce.activities-10012', 'example.greeter', 'example.greeter'],
      create_user: 'admin',
      create_time: '2025-08-04 17:43:26+0800',
      update_user: 'admin',
      update_time: '2025-08-04 17:43:26+0800',
    },
  ];
  /** 模板类型快速筛选tab */
  quickStatus = 'all';
  /** 搜索关键字 */
  searchKeyword: AlarmTemplateConditionParamItem[] = [];
  /** 表格已勾选的数据行id */
  selectedRowKeys: AlarmTemplateListItem['id'][] = [];
  /** 搜索选择器选项(接口获取) */
  selectOptions: SearchSelectItem[] = [
    {
      name: window.i18n.t('全文检索') as unknown as string,
      id: 'query',
      multiple: false,
    },
  ];

  editTemplateId = null;
  editTemplateShow = false;

  /** 模板详情侧栏 */
  templateDetailObj = {
    show: false,
    params: {},
  };
  templatePushObj = {
    show: false,
    params: {},
  };

  @InjectReactive('viewOptions') readonly viewOptions!: IViewOptions;

  /**
   * @description 模板类型快捷筛选值改变后回调
   */
  handleQuickStatusChange(status: string) {
    this.quickStatus = status;
  }
  /**
   * @description 批量操作按钮点击事件
   */
  handleBatchOperationClick(operationType: BatchOperationTypeEnumType) {
    console.log('================ operationType ================', operationType);
  }

  /** 筛选值改变后回调（作用于 表格表头筛选 & 顶部筛选searchInput框） */
  handleSearchChange(keyword: AlarmTemplateConditionParamItem[]) {
    this.searchKeyword = keyword;
    // this.setRouterParams();
  }

  /**
   * @description 删除查询模板
   * @param templateId 模板Id
   */
  deleteTemplateById(templateId: AlarmTemplateListItem['id'], confirmEvent: AlarmDeleteConfirmEvent) {
    // destroyQueryTemplateById(templateId)
    //   .then(() => {
    //     confirmEvent.successCallback();
    //     this.$bkMessage({
    //       message: this.$t('删除成功'),
    //       theme: 'success',
    //     });
    //     this.handleRefresh();
    //   })
    //   .catch(() => {
    //     confirmEvent.errorCallback();
    //     this.$bkMessage({
    //       message: this.$t('删除失败'),
    //       theme: 'error',
    //     });
    //   });
  }

  /**
   * @description 下发事件回调
   */
  handleDispatch(id: AlarmTemplateListItem['id']) {
    console.log('================ 下发事件回调 ================', id);
    this.templatePushObj = {
      show: true,
      params: {
        strategy_template_ids: [id],
        app_name: this.viewOptions.filters?.app_name,
        name: this.tableData.find(item => item.id === id)?.name,
      },
    };
  }

  /**
   * @description 克隆事件回调
   */
  handleCloneTemplate(id: AlarmTemplateListItem['id']) {
    console.log('================ 克隆事件回调 ================', id);
  }

  /**
   * @description 展示模板详情事件回调
   */
  handleShowDetail(obj: { id: AlarmTemplateListItem['id']; sliderActiveTab: AlarmTemplateDetailTabEnumType }) {
    console.log('================ 展示模板详情事件回调 ================', obj);
    this.templateDetailObj = {
      show: true,
      params: {
        app_name: this.viewOptions.filters?.app_name,
        ids: [obj.id],
        name: this.tableData.find(item => item.id === obj.id)?.name,
      },
    };
  }

  /**
   * @description 表格行勾选事件回调
   */
  handleTableSelectedChange(selectedRowKeys: AlarmTemplateListItem['id'][]) {
    this.selectedRowKeys = selectedRowKeys;
    console.log('================ this.selectedRowKeys 表格行勾选事件回调 ================', this.selectedRowKeys);
  }

  /**
   * @description 批量/单个模板内属性更新事件回调
   */
  handleBatchUpdate(
    id: AlarmTemplateListItem['id'] | AlarmTemplateListItem['id'][],
    updateValue: Partial<AlarmTemplateListItem>,
    promiseEvent?: AlarmDeleteConfirmEvent
  ) {
    const ids = Array.isArray(id) ? id : [id];
    console.log('================ 批量/单个模板更新事件回调 ================', ids, updateValue);
  }

  handleEditTemplate(id: number) {
    this.editTemplateId = id;
    this.editTemplateShow = true;
  }

  render() {
    return (
      <div class='alarm-template'>
        <div class='alarm-template-header'>
          <div class='alarm-template-header-operations'>
            <BatchOperations
              disabled={!this.selectedRowKeys?.length}
              onOperationClick={this.handleBatchOperationClick}
            />
            <StatusTab
              class='alarm-template-header-filter-tab'
              v-model={this.quickStatus}
              needAll={false}
              statusList={ALARM_TEMPLATE_QUICK_FILTER_LIST.map(e => AlarmTemplateTypeMap[e])}
              onChange={this.handleQuickStatusChange}
            />
          </div>
          <div class='alarm-template-header-search'>
            <AlarmTemplateSearch
              class='search-input'
              searchKeyword={this.searchKeyword}
              selectOptions={this.selectOptions}
              onChange={this.handleSearchChange}
            />
          </div>
        </div>
        <div class='alarm-template-main'>
          <AlarmTemplateTable
            appName='tilapia'
            emptyType={this.searchKeyword?.length ? 'search-empty' : 'empty'}
            loading={this.tableLoading}
            tableData={this.tableData}
            onBatchUpdate={this.handleBatchUpdate}
            onClearSearch={() => this.handleSearchChange([])}
            onCloneTemplate={this.handleCloneTemplate}
            onDeleteTemplate={this.deleteTemplateById}
            onDispatch={this.handleDispatch}
            onEditTemplate={this.handleEditTemplate}
            onSelectedChange={this.handleTableSelectedChange}
            onShowDetail={this.handleShowDetail}
          />
        </div>

        <EditTemplateSlider
          appName={'tilapia'}
          isShow={this.editTemplateShow}
          templateId={this.editTemplateId}
          onShowChange={show => {
            this.editTemplateShow = show;
          }}
        />
        <TemplateDetails
          params={this.templateDetailObj.params}
          show={this.templateDetailObj.show}
          onShowChange={show => {
            this.templateDetailObj.show = show;
          }}
        />
        <TemplatePush
          params={this.templatePushObj.params}
          show={this.templatePushObj.show}
          onShowChange={show => {
            this.templatePushObj.show = show;
          }}
        />
      </div>
    );
  }
}
