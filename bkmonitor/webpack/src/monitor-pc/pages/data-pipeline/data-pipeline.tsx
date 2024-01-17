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

/* eslint-disable max-len  */
import { Component } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import {
  checkClusterHealth,
  listDataPipeline,
  listDataSourceByDataPipeline,
  updateDataPipeline
} from '../../../monitor-api/modules/commons';
import { random } from '../../../monitor-common/utils';

import DataPipelineConfig from './data-pipeline-config';

import './data-pipeline.scss';

enum EColunm {
  name = 'name',
  scope = 'scope',
  type = 'type',
  kafka = 'Kafka',
  transfer = 'Transfer',
  influxdbStorage = 'influxdbStorage',
  kafkaStorage = 'kafkaStorage',
  isDefault = 'isDefault',
  isEnable = 'isEnable',
  operate = 'operate'
}
enum EChildColunm {
  name = 'name',
  space = 'space',
  type = 'type',
  kafkaTopic = 'kafkaTopic',
  influxdbStorage = 'influxdbStorage',
  kafkaTopicStorage = 'kafkaTopicStorage'
}

interface IChildTableData {
  dataId: number;
  dataName: string;
  kafkaTopic: string;
  influxdbDomainName: string;
  kafkaStorageTopic: string;
  isPlatformDataId: boolean;
  spaceName: string;
  spaceId: string;
}
interface IChildTable {
  page: number;
  total: number;
  data: IChildTableData[];
}

interface IPiplineData {
  key?: string;
  name?: string;
  chinese_name?: string;
  label?: string;
  kafka_cluster_id?: number;
  transfer_cluster_id?: string;
  influxdb_storage_cluster_id?: number;
  kafka_storage_cluster_id?: number;
  kafka_cluster_name?: string;
  kafka_storage_cluster_name?: string;
  influxdb_storage_cluster_name?: string;
  es_storage_cluster_id?: number;
  vm_storage_cluster_id?: number;
  is_enable?: boolean;
  description?: string;
  is_default?: boolean;
  etl_config?: any[];
  spaces?: any[];
  creator?: string;
  create_time?: string;
  updater?: string;
  update_time?: string;
  childTable: IChildTable;
  etlConfigStr?: string;
  spaceStr?: string;
  id: string;
  isDefault?: boolean;
}

interface ITableData {
  columns: any[];
  expandRowKeys: string[];
  data: IPiplineData[];
  filterData: IPiplineData[];
}

type TCountStatus = 1 | 2 | 3;

const STATUS_01 = [1, 1, 1, 1, 1, 1];
const STATUS_02 = [2, 2, 2, 2, 2, 2];

@Component
export default class DataPipeline extends tsc<{}> {
  /* 搜索 */
  searchValue = '';
  /* 表格数据 */
  tableData: ITableData = {
    columns: [
      { id: EColunm.name, name: window.i18n.tc('链路名称'), width: 125, disabled: true, checked: true },
      { id: EColunm.scope, name: window.i18n.tc('使用范围'), disabled: false, checked: true },
      { id: EColunm.type, name: window.i18n.tc('数据类型'), disabled: false, checked: true },
      { id: EColunm.kafka, name: 'Kafka', width: 163, disabled: false, checked: true },
      { id: EColunm.transfer, name: 'Transfer', width: 163, disabled: false, checked: true },
      { id: EColunm.influxdbStorage, name: window.i18n.tc('投递到存储'), width: 163, disabled: false, checked: true },
      { id: EColunm.kafkaStorage, name: window.i18n.tc('投递到Kafka'), width: 163, disabled: false, checked: true },
      { id: EColunm.isDefault, name: window.i18n.tc('是否默认'), disabled: false, checked: true },
      {
        id: EColunm.isEnable,
        name: window.i18n.tc('是否可用'),
        width: 100,
        disabled: false,
        checked: true,
        filters: [
          { text: window.i18n.tc('是'), value: true },
          { text: window.i18n.tc('否'), value: false }
        ],
        filterMultiple: false
      },
      { id: EColunm.operate, name: window.i18n.tc('操作'), width: 70, disabled: true, checked: true }
    ],
    expandRowKeys: [],
    /* 搜索及筛选数据 */
    filterData: [],
    data: []
  };
  childTableColumns = [
    { id: EChildColunm.name, name: window.i18n.tc('数据名'), width: 300 },
    { id: EChildColunm.space, name: window.i18n.tc('所属空间') },
    { id: EChildColunm.type, name: window.i18n.tc('类型') },
    { id: EChildColunm.kafkaTopic, name: 'Kafka (topic)' },
    { id: EChildColunm.influxdbStorage, name: window.i18n.tc('投递到 influxdb') },
    { id: EChildColunm.kafkaTopicStorage, name: window.i18n.tc('投递到 Kafka (topic)') }
  ];
  childTablePageSize = 10; // 子表格每页显示条数
  childTableLoading = false; // 子表格loading
  tableSize = 'medium';
  /* loading */
  loading = false; // 表格loading
  bottomLoading = false; // 底部loading

  /* 侧栏新建及编辑数据 */
  configData: { data: IPiplineData; show: boolean } = {
    show: false,
    data: null
  };
  /* 是否启用筛选 */
  filterIsEnable = -1;
  /* 数据更新时间 */
  dataUpdateTime = '--';
  /* 判断创建页面的校验 */
  piplineList = [];
  tableKey = random(8);
  /* 方块状态合集 */
  statusCompilation = new Map(); // 方块状态合集
  statusKey = random(8); // 方块状态合集key

  // throttleHandleScroll = () => {};

  async created() {
    await this.init();
    this.piplineList = this.tableData.data.map(item => ({
      isDefalut: item.isDefault,
      name: item.name,
      etl_config: item.etl_config,
      spaces: item.spaces
    }));
  }
  /* 初始化 */
  async init() {
    this.loading = true;
    const data = await listDataPipeline({
      name: this.searchValue,
      is_enable: (() => {
        if (this.filterIsEnable === -1) {
          return 'all';
        }
        if (this.filterIsEnable === 1) {
          return true;
        }
        return false;
      })(),
      page_size: 999
    }).catch(() => ({
      data: [],
      total: 0
    }));
    const spaceMap = new Map();
    this.$store.getters.bizList.forEach(item => {
      spaceMap.set(String(item.id), item);
    });
    this.tableData.data = data.data.map(item => {
      const key = random(8);
      const spaceStr = item.spaces.map(s => spaceMap.get(String(s.space_id))?.name || '--').join(',');
      const isDefault = item.etl_config.some(etl => etl.is_default) || item.spaces.some(s => s.is_default);
      return {
        ...item,
        key,
        etlConfigStr: item.etl_config.map(item => item.etl_config).join(','),
        spaceStr,
        isDefault,
        childTable: {
          total: 0,
          page: 0,
          data: []
        }
      };
    }) as any;
    if (this.tableData.data.length) {
      this.dataUpdateTime = this.tableData.data[0].update_time;
    }
    this.setAllStauts();
    this.loading = false;
  }
  /* 子表滚动到底触发 */
  handleScrollEnd() {
    const key = this.tableData.expandRowKeys?.[0];
    if (key) {
      this.setChildTableData(key);
    }
  }

  /**
   * @description: 设置子表格数据
   */
  async setAllStauts() {
    const clusterIdsSet = new Set();
    const transferId = new Set();
    this.tableData.data.forEach(item => {
      !!item.kafka_cluster_id && clusterIdsSet.add(item.kafka_cluster_id);
      /* transfer需要加上cluster_type */
      if (!!item.transfer_cluster_id) {
        clusterIdsSet.add(item.transfer_cluster_id);
        transferId.add(item.transfer_cluster_id);
      }
      !!item.kafka_storage_cluster_id && clusterIdsSet.add(item.kafka_storage_cluster_id);
      !!item.influxdb_storage_cluster_id && clusterIdsSet.add(item.influxdb_storage_cluster_id);
    });
    const setStatus = async id =>
      checkClusterHealth({
        /* transfer需要加上cluster_type */
        cluster_type: transferId.has(id) ? 'transfer' : undefined,
        cluster_id: id
      })
        .then(res => {
          this.statusCompilation.set(id, {
            success: !!res
          });
        })
        .catch(() => {
          this.statusCompilation.set(id, {
            success: false
          });
        });
    const promiseList = [];
    Array.from(clusterIdsSet).forEach(id => {
      if (!this.statusCompilation.has(id)) {
        promiseList.push(setStatus(id));
      }
    });
    await Promise.all(promiseList);
    this.statusKey = random(8);
  }
  /* 状态列，暂定为6个小方块 */
  getStautsContent(clusterId) {
    if (!this.statusCompilation.has(clusterId)) {
      return [];
    }
    return this.statusCompilation.get(clusterId)?.success ? STATUS_01 : STATUS_02;
  }

  /* 点击某一行 */
  async handleRowClick(row: IPiplineData) {
    if (row.key === this.tableData.expandRowKeys?.[0]) {
      this.tableData.expandRowKeys = [];
    } else {
      this.tableData.expandRowKeys = [row.key];
      this.setChildTableData(row.key);
    }
  }
  /* 获取子表数据 */
  async setChildTableData(key: string) {
    if (this.childTableLoading || this.bottomLoading) return;
    const tableData = this.tableData.data.find(item => item.key === key);
    const { childTable } = tableData;
    if (childTable) {
      const { page, total } = childTable as any;
      if (childTable.data.length >= total && total !== 0) {
        // 到底了
        return;
      }
      const curPage = page + 1;
      if (curPage > 1) {
        this.bottomLoading = true;
      } else {
        this.childTableLoading = true;
      }
      const data = await listDataSourceByDataPipeline({
        data_pipeline_name: tableData.name,
        page: curPage,
        page_size: this.childTablePageSize
      })
        .then(res => ({
          ...res,
          data: res.data.map(item => {
            const kafkaTopic = item?.mq_config?.storage_config?.topic;
            const influxdbDomainName = item?.result_table_list?.[0].shipper_list?.find(
              r => r.cluster_type === 'influxdb'
            )?.cluster_config?.domain_name;
            const kafkaStorageTopic = item?.result_table_list?.[0].shipper_list?.find(r => r.cluster_type === 'kafka')
              ?.storage_config?.topic;
            const spaceName = this.$store.getters.bizList.find(b => b.space_id === item.space.space_id)?.name;
            return {
              dataId: item.data_id,
              dataName: item.data_name,
              kafkaTopic,
              influxdbDomainName,
              kafkaStorageTopic,
              isPlatformDataId: !!item.is_platform_data_id,
              spaceId: item.space.space_id,
              spaceName
            };
          })
        }))
        .catch(() => ({
          total: 0,
          data: []
        }));
      if (data.data.length) {
        childTable.page = curPage;
        childTable.total = data.total;
      }
      childTable.data.push(...data.data);
      this.childTableLoading = false;
      this.bottomLoading = false;
    }
  }
  /* 表格设置 */
  handleSettingChange({ size, fields }) {
    this.tableSize = size;
    this.tableData.columns.forEach(item => (item.checked = fields.some(field => field.id === item.id)));
    const colList = this.tableData.columns.filter(item => item.checked || item.disabled).map(item => item.id);
    return colList;
  }
  /* 表格过滤 */
  handleFilterChange(filter) {
    const isEnableData = filter[EColunm.isEnable];
    if (isEnableData?.length) {
      this.filterIsEnable = isEnableData[0] ? 1 : 0;
    } else {
      this.filterIsEnable = -1;
    }
    this.init();
  }
  /* 侧栏展开 */
  handleShowChange(value: boolean) {
    this.configData.show = value;
  }
  /* 添加 */
  handleShowConfigAdd() {
    this.configData.data = null;
    this.configData.show = true;
  }
  /* 编辑 */
  handleEdit(row: IPiplineData) {
    this.configData.data = JSON.parse(JSON.stringify(row));
    this.configData.show = true;
  }
  /* 启用/停用 */
  handleEnable(row) {
    return new Promise((resolve, _reject) => {
      updateDataPipeline({
        data_pipeline_name: row.name,
        name: row.name,
        chinese_name: row.chinese_name,
        spaces: row.spaces,
        etl_configs: row.etl_configs,
        kafka_cluster_id: row.kafka_cluster_id,
        transfer_cluster_id: row.transfer_cluster_id,
        influxdb_storage_cluster_id: row.influxdb_storage_cluster_id,
        kafka_storage_cluster_id: row.kafka_storage_cluster_id,
        is_enable: !row.is_enable,
        description: row.description
      })
        .then(() => {
          resolve(!row.is_enable);
        })
        .catch(() => {
          _reject();
        });
    });
  }
  /* 编辑或创建成功 */
  handleSuccess() {
    this.init();
  }
  /* 搜索 */
  handleSearchBlur(value) {
    if (this.searchValue !== value) {
      this.searchValue = value;
      this.init();
    }
  }
  /* 搜索 */
  handleSearchEnter(value) {
    if (this.searchValue !== value) {
      this.searchValue = value;
      this.init();
    }
  }
  /* 编辑 */
  async handleEditPipline(name: string) {
    this.searchValue = '';
    this.filterIsEnable = 1;
    await this.init();
    this.tableKey = random(8);
    const item = this.tableData.data.find(item => item.name === name);
    if (!!item) {
      this.handleEdit(item);
    }
  }

  /* 主机数量和状态 */
  countStatusContent(list: TCountStatus[]) {
    const indexs = [];
    const len = list.length;
    let tempIndex = 0;
    while (tempIndex <= len) {
      tempIndex = tempIndex + 20;
      indexs.push([tempIndex - 20, tempIndex - 1]);
    }
    const domList = indexs.map((item, index_) => (
      <div
        class='count-status'
        key={index_}
      >
        {list.slice(...item).map((status, index) => (
          <div
            key={index}
            class={['status-cube', `status-${status}`]}
          ></div>
        ))}
      </div>
    ));
    return domList;
  }

  /* 表格内容 */
  handleSetFormatter(id: EColunm, row: IPiplineData, _index) {
    switch (id) {
      case EColunm.name: {
        return (
          <span class='pipline-name'>
            <span
              class={['icon-monitor icon-mc-triangle-down', { active: this.tableData.expandRowKeys?.[0] === row.key }]}
            ></span>
            <span v-bk-overflow-tips>{row.name}</span>
          </span>
        );
      }
      case EColunm.scope: {
        return <div v-bk-overflow-tips>{row.spaceStr}</div>;
      }
      case EColunm.type: {
        return row.etlConfigStr;
      }
      case EColunm.transfer: {
        return (
          <span class='count-status-info'>
            <div class='name-info'>
              <span class='name'>{row?.transfer_cluster_id || '--'}</span>
              <span class='icon-monitor icon-fenxiang'></span>
            </div>
            {this.countStatusContent(this.getStautsContent(row?.transfer_cluster_id) as any)}
          </span>
        );
      }
      case EColunm.kafka: {
        return (
          <span
            class='count-status-info'
            key={`${this.statusKey}_kafka_cluster`}
          >
            <div class='name-info'>
              <span class='name'>{row.kafka_cluster_name || '--'}</span>
              <span class='icon-monitor icon-fenxiang'></span>
            </div>
            {this.countStatusContent(this.getStautsContent(row.kafka_cluster_id) as any)}
          </span>
        );
      }
      case EColunm.influxdbStorage: {
        <span
          class='count-status-info'
          key={`${this.statusKey}_influxdb_storage_cluste`}
        >
          <div class='name-info'>
            <span class='name'>{row.influxdb_storage_cluster_name || '--'}</span>
            <span class='icon-monitor icon-fenxiang'></span>
          </div>
          {this.countStatusContent(this.getStautsContent(row.influxdb_storage_cluster_id) as any)}
        </span>;
      }
      case EColunm.kafkaStorage: {
        return (
          <span
            class='count-status-info'
            key={`${this.statusKey}_kafka_storage_cluster`}
          >
            <div class='name-info'>
              <span class='name'>{row.kafka_storage_cluster_name || '--'}</span>
              <span class='icon-monitor icon-fenxiang'></span>
            </div>
            {this.countStatusContent(this.getStautsContent(row.kafka_storage_cluster_id) as any)}
          </span>
        );
      }
      case EColunm.isDefault: {
        return <span>{row.isDefault ? this.$t('是') : this.$t('否')}</span>;
      }
      case EColunm.isEnable: {
        return (
          <div onClick={(e: Event) => e.stopPropagation()}>
            <bk-switcher
              theme='primary'
              size='small'
              value={row.is_enable}
              pre-check={() => this.handleEnable(row)}
            ></bk-switcher>
          </div>
        );
      }
      case EColunm.operate: {
        return (
          <div
            onClick={(e: Event) => {
              e.stopPropagation();
              this.handleEdit(row);
            }}
          >
            <bk-button text>{this.$t('编辑')}</bk-button>
          </div>
        );
      }
      default: {
        return <span>defalut</span>;
      }
    }
  }
  /* 子表格内容 */
  handleSetChildFormatter(id: EChildColunm, row: IChildTableData) {
    switch (id) {
      case EChildColunm.name: {
        return (
          <span class='data-name'>
            <div class='title'>{row.dataName}</div>
            <div class='subtitle'>{row.dataId}</div>
          </span>
        );
      }
      case EChildColunm.space: {
        return (
          <span class='data-name'>
            <div class='title'>{row.spaceName}</div>
            <div class='subtitle'>{row.spaceId}</div>
          </span>
        );
      }
      case EChildColunm.type: {
        return row.isPlatformDataId ? this.$t('公共') : this.$t('私有');
      }
      case EChildColunm.kafkaTopic: {
        return row.kafkaTopic;
      }
      case EChildColunm.influxdbStorage: {
        return row.influxdbDomainName || '--';
      }
      case EChildColunm.kafkaTopicStorage: {
        return row.kafkaStorageTopic || '--';
      }
      default: {
        return <span>defalut</span>;
      }
    }
  }

  render() {
    return (
      <div class='data-pipline-page'>
        <div class='head-operate'>
          <div class='left'>
            <bk-button
              icon='plus'
              theme='primary'
              class='mr24'
              onClick={this.handleShowConfigAdd}
            >
              {this.$t('新增')}
            </bk-button>
            <span class='update-time'>
              {this.$t('数据更新时间')}：{this.dataUpdateTime}
            </span>
          </div>
          <div class='right'>
            <bk-input
              placeholder={this.$t('输入')}
              right-icon={'bk-icon icon-search'}
              value={this.searchValue}
              on-blur={this.handleSearchBlur}
              on-enter={this.handleSearchEnter}
            ></bk-input>
          </div>
        </div>
        <div
          class='table-content'
          v-bkloading={{ isLoading: this.loading }}
        >
          <bk-table
            key={this.tableKey}
            outer-border={false}
            header-border={false}
            size={this.tableSize}
            {...{
              props: {
                data: this.tableData.data,
                expandRowKeys: this.tableData.expandRowKeys,
                rowKey: row => row.key
              }
            }}
            on-row-click={this.handleRowClick}
            on-filter-change={this.handleFilterChange}
          >
            {
              <bk-table-column
                type='expand'
                width={0}
                scopedSlots={{
                  /* 子表 */
                  default: ({ row }) => (
                    <div
                      class='child-table'
                      v-bkloading={{ isLoading: this.childTableLoading }}
                      // onScroll={this.throttleHandleScroll}
                    >
                      <bk-table
                        outer-border={false}
                        header-border={false}
                        row-class-name={'child-row'}
                        size={'medium'}
                        max-height={311}
                        {...{
                          props: {
                            data: row.childTable.data,
                            scrollLoading: {
                              isLoading: this.bottomLoading
                            }
                          }
                        }}
                        on-scroll-end={this.handleScrollEnd}
                      >
                        {this.childTableColumns.map(childColumn => (
                          <bk-table-column
                            key={childColumn.id}
                            label={childColumn.name}
                            width={childColumn.width}
                            formatter={(row: any) => this.handleSetChildFormatter(childColumn.id as any, row)}
                          ></bk-table-column>
                        ))}
                      </bk-table>
                    </div>
                  )
                }}
              ></bk-table-column>
            }
            {
              <bk-table-column type='setting'>
                <bk-table-setting-content
                  key={'__settings'}
                  class='event-table-setting'
                  fields={this.tableData.columns}
                  value-key='id'
                  label-key='name'
                  size={this.tableSize}
                  selected={this.tableData.columns.filter(item => item.checked || item.disabled)}
                  on-setting-change={this.handleSettingChange}
                />
              </bk-table-column>
            }
            {this.tableData.columns
              .filter(column => column.checked)
              .map(column => {
                const key = `column_${column.id}`;
                return (
                  <bk-table-column
                    key={key}
                    prop={column.id}
                    label={column.name}
                    column-key={column.id}
                    width={column.width}
                    filters={column.filters}
                    filter-multiple={!!column.filterMultiple}
                    formatter={(row, _column, _cellValue, index) =>
                      this.handleSetFormatter(column.id as EColunm, row, index)
                    }
                  ></bk-table-column>
                );
              })}
          </bk-table>
        </div>
        <DataPipelineConfig
          show={this.configData.show}
          data={this.configData.data as any}
          piplineList={this.piplineList}
          onSuccess={this.handleSuccess}
          onShowChange={this.handleShowChange}
          onEdit={this.handleEditPipline}
        ></DataPipelineConfig>
      </div>
    );
  }
}
