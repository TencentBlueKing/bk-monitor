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
import { Component, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { getStorageClusterDetail, listClusters } from '../../../monitor-api/modules/commons';
import { random } from '../../../monitor-common/utils';

import ClusterConfig from './cluster-config';
// import InfluxdbChild from './influxdb-child';
import ClusterDetails from './cluster-details';
import { EClusterType, ETableColumn, FILTER_LIST, ITableDataRow, ITableRowConfig } from './type';

import './resource-register.scss';

const mockData = {
  total: 0,
  data: []
};

const childColumns = [
  { id: 'ip', name: 'ip' },
  { id: 'port', name: window.i18n.tc('端口') },
  { id: 'version', name: window.i18n.tc('版本') },
  { id: 'topic_count', name: window.i18n.tc('topic数量'), sortable: true },
  { id: 'schema', name: window.i18n.tc('协议') },
  { id: 'status', name: window.i18n.tc('状态') }
];

interface ITableData {
  data: ITableDataRow[];
}

@Component
export default class ResourceRegister extends tsc<{}> {
  @Ref() clusterOperation: any;
  /* 控制侧栏展示 */
  show = false;
  /* 侧栏标题 */
  sideSliderTitle: String = '';
  /* 是否全部展开/收起 */
  isExpandAll = false;
  /* 筛选 */
  filterType = 'all';
  /* 关键字搜索 */
  searchValue = '';
  /* 表格数据 */
  tableData: ITableData | any = {
    data: [],
    columns: [
      { id: ETableColumn.name, name: window.i18n.tc('名称'), disabled: true, checked: true, width: 246 },
      { id: ETableColumn.pipeline, name: window.i18n.tc('所属链路'), disabled: false, checked: true, width: 150 },
      { id: ETableColumn.status, name: window.i18n.tc('连接状态'), disabled: false, checked: true },
      { id: ETableColumn.operator, name: window.i18n.tc('负责人'), disabled: false, checked: true },
      { id: ETableColumn.description, name: window.i18n.tc('描述'), disabled: false, checked: true, width: 298 },
      { id: ETableColumn.use, name: window.i18n.tc('用途'), disabled: false, checked: true, width: 100 },
      { id: ETableColumn.operate, name: window.i18n.tc('操作'), disabled: true, checked: true }
    ],
    pagination: {
      current: 1,
      count: 100,
      limit: 10
    },
    expandRowKeys: []
  };
  tableSize = 'medium';
  updateTime = '';
  /* 详情侧栏 */
  detailsShow = false;
  detailsData = null;
  /* 子表数据缓存 */
  childDataCache = new Map();
  rowConfig: ITableRowConfig;

  loading = false;

  async created() {
    this.setTableData();
  }

  async setTableData() {
    this.loading = true;
    const data = await listClusters({
      page: this.tableData.pagination.current,
      page_size: this.tableData.pagination.limit,
      cluster_type: this.filterType,
      cluster_name: this.searchValue
    }).catch(() => mockData);
    this.tableData.data = data.data.map(item => {
      const labelArr = item.label.split(',');
      return {
        key: random(8),
        ...item,
        labelArr,
        childData: {
          columns: [],
          data: []
        }
      };
    });
    if (this.tableData.data.length) {
      this.updateTime = this.tableData.data[0].last_modify_time;
    }
    this.tableData.pagination.count = data.total;
    const clusterIds = this.tableData.data.map(item => item.cluster_id);
    this.setChildData(clusterIds);
    this.loading = false;
  }
  /* 获取子表数据 */
  setChildData(clusterIds: number[]) {
    const getData = id => {
      const curData = this.tableData.data.find(item => item.cluster_id === id);
      if (curData.cluster_type === EClusterType.Influxdb) {
        return;
      }
      const setColumns = (topicCount?) => {
        if (typeof topicCount !== 'number') {
          curData.childData.columns = JSON.parse(JSON.stringify(childColumns.filter(c => c.id !== 'topic_count')));
        } else {
          curData.childData.columns = JSON.parse(JSON.stringify(childColumns));
        }
      };
      if (!this.childDataCache.has(id)) {
        getStorageClusterDetail({
          cluster_id: id
        })
          .then(res => {
            setColumns(res?.[0]?.topic_count);
            this.childDataCache.set(id, res);
            curData.childData.data = res;
          })
          .catch(() => {
            curData.childData.columns = JSON.parse(JSON.stringify(childColumns.filter(c => c.id !== 'topic_count')));
          });
      } else {
        const data = this.childDataCache.get(id);
        setColumns(data?.[0]?.topic_count);
        curData.childData.data = data;
      }
    };
    clusterIds.forEach(id => {
      getData(id);
    });
  }
  /* 侧栏弹出 */
  handleOpenSideSlider(rowConfig: ITableRowConfig) {
    this.rowConfig = rowConfig;
    this.show = true;
  }
  /* influxdb组操作 */
  handleOpenInfluxdbGroupSideslider(val?: any) {
    this.clusterOperation.openInfluxdbGroupSideslider(val);
  }
  /* 从表格区域点击 (克隆/编辑)influxdb组 */
  handleGroupOperation(rowData?: any) {
    this.handleOpenInfluxdbGroupSideslider(rowData);
  }
  /* 响应侧栏关闭 */
  handleShowChange(v: boolean) {
    this.show = v;
  }
  /* 点击某一行 */
  handleRowClick(row: any) {
    const index = this.tableData.expandRowKeys.indexOf(row.key);
    if (index > -1) {
      this.tableData.expandRowKeys.splice(index, 1);
    } else {
      this.tableData.expandRowKeys.push(row.key);
    }
  }
  /* 点击筛选项 */
  handleFilterChange(id: string) {
    if (this.filterType !== id) {
      this.tableData.pagination.current = 1;
      this.filterType = id;
      this.setTableData();
    }
  }
  /* 全部展开/全部收起 */
  handleExpandAllChange() {
    this.isExpandAll = !this.isExpandAll;
    if (this.isExpandAll) {
      /* 全部展开 */
      this.tableData.expandRowKeys = this.tableData.data.map(item => item.key);
    } else {
      /* 全部收起 */
      this.tableData.expandRowKeys = [];
    }
  }
  /* 表格设置 */
  handleSettingChange({ size, fields }) {
    this.tableSize = size;
    this.tableData.columns.forEach(item => (item.checked = fields.some(field => field.id === item.id)));
    const colList = this.tableData.columns.filter(item => item.checked || item.disabled).map(item => item.id);
    return colList;
  }
  /* 分页 */
  handlePageChange(value: number) {
    this.tableData.pagination.current = value;
    this.setTableData();
  }
  /* 分页limit */
  handlePageLimitChange(value: number) {
    this.tableData.pagination.current = 1;
    this.tableData.pagination.limit = value;
    this.setTableData();
  }
  /* 打开详情 */
  handleOpenDetail(e: Event, row: any) {
    e.stopPropagation();
    this.detailsData = row;
    this.detailsShow = true;
  }
  handleDetailShowChange(v: boolean) {
    this.detailsShow = v;
  }

  handleSearchChange(value: string) {
    if (this.searchValue !== value) {
      this.searchValue = value;
      this.tableData.pagination.current = 1;
      this.setTableData();
    }
  }
  handleDetailsToEdit(clusterId: string | number) {
    const data = this.tableData.data.find(item => item.cluster_id === clusterId);
    this.detailsShow = false;
    if (data) {
      this.handleOpenSideSlider({ operationType: 'edit', rowData: data });
    }
  }

  /* 状态 */
  statusContent(status: 'normal' | 'failure') {
    return (
      <div class='status-info'>
        <div class={['status-point', status]}>
          <div></div>
        </div>
        <div>{status === 'normal' ? this.$t('正常') : this.$t('失败')}</div>
      </div>
    );
  }
  /* 表格内容 */
  handleSetFormatter(id: ETableColumn, row: ITableDataRow, _index) {
    switch (id) {
      case ETableColumn.name: {
        return (
          <span class='cluster-name'>
            <span
              class={[
                'icon-monitor icon-mc-triangle-down',
                { active: this.tableData.expandRowKeys.indexOf(row.key) > -1 }
              ]}
            ></span>
            <span class='name-wrap'>
              <span class='icon-monitor icon-DB1 name-icon'></span>
              <span
                class='name'
                onClick={(e: Event) => this.handleOpenDetail(e, row)}
              >
                {row.cluster_name}
              </span>
            </span>
          </span>
        );
      }
      case ETableColumn.use: {
        return (
          <div class='used-tags'>
            {!!row.label ? row.labelArr.map(lable => <div class='tags-item'>{lable}</div>) : '--'}
          </div>
        );
      }
      case ETableColumn.pipeline: {
        return row.pipeline_name || '--';
      }
      case ETableColumn.status: {
        return this.statusContent('normal');
      }
      case ETableColumn.operator: {
        return row.creator || '--';
      }
      case ETableColumn.description: {
        return row.description || '--';
      }
      case ETableColumn.operate: {
        return (
          <div class='operate-items'>
            {[EClusterType.Influxdb, EClusterType.Kafka, EClusterType.ES].includes(row.cluster_type) && (
              <bk-button
                class='mr20'
                text
                onClick={(e: Event) => {
                  e.stopPropagation();
                  this.handleOpenSideSlider({ operationType: 'edit', rowData: row });
                }}
              >
                {this.$t('编辑')}
              </bk-button>
            )}
            {/* todo */}
            {/* <bk-button text onClick={this.handleOpenInfluxdbGroupSideslider}>{this.$t('新增组')}</bk-button> */}
          </div>
        );
      }
      default: {
        return <span>defalut</span>;
      }
    }
  }
  render() {
    return (
      <div class='resource-register-page'>
        <div class='header-wrap'>
          <div class='header-wrap-01'>
            <bk-button
              class='mr8'
              theme='primary'
              icon='plus'
              onClick={() => this.handleOpenSideSlider({ operationType: 'add' })}
            >
              {this.$tc('新增')}
            </bk-button>
            <bk-button
              class='expand-button'
              onClick={this.handleExpandAllChange}
            >
              {this.isExpandAll ? (
                <span>
                  <span class='icon-monitor icon-zhankai1 expand-icon'></span>
                  <span>{this.$t('全部收起')}</span>
                </span>
              ) : (
                <span>
                  <span class='icon-monitor icon-shouqi1 expand-icon'></span>
                  <span>{this.$t('全部展开')}</span>
                </span>
              )}
            </bk-button>
            <span class='data-time'>
              {this.$t('数据更新时间')}：{this.updateTime || '--'}
            </span>
          </div>
          <div class='header-wrap-02'>
            <div class='header-filter'>
              {FILTER_LIST.map(item => (
                <div
                  class={['header-filter-item', { active: item.id === this.filterType }]}
                  key={item.id}
                  onClick={() => this.handleFilterChange(item.id)}
                >
                  {!!item.icon && <span class={[`icon-monitor ${item.icon} item-icon`]}></span>}
                  <span>{item.name}</span>
                </div>
              ))}
            </div>
            <div class='search-wrap'>
              <bk-input
                value={this.searchValue}
                right-icon='bk-icon icon-search'
                onEnter={this.handleSearchChange}
                onBlur={this.handleSearchChange}
              ></bk-input>
            </div>
          </div>
        </div>
        <div
          class='table-content-wrap'
          v-bkloading={{ isLoading: this.loading }}
        >
          <bk-table
            outer-border={false}
            header-border={false}
            size={this.tableSize}
            {...{
              props: {
                data: this.tableData.data,
                expandRowKeys: this.tableData.expandRowKeys,
                rowKey: row => row.key,
                pagination: this.tableData.pagination
              }
            }}
            on-row-click={this.handleRowClick}
            on-page-change={this.handlePageChange}
            on-page-limit-change={this.handlePageLimitChange}
          >
            <bk-table-column
              type='expand'
              width={0}
              scopedSlots={{
                default: ({ row }) => {
                  if (row?.cluster_type === EClusterType.Influxdb) {
                    return <div class='no-data'>暂无数据</div>;
                    // todo
                    // return <InfluxdbChild on-group-operation={() => this.handleGroupOperation(row)}></InfluxdbChild>;
                  }
                  return (
                    <div
                      class='child-table'
                      key={`${row.key}_child`}
                    >
                      <bk-table
                        outer-border={false}
                        header-border={false}
                        {...{
                          props: {
                            data: row.childData?.data || []
                          }
                        }}
                      >
                        {row.childData?.columns.map(column => {
                          const key = `column__${column.id}`;
                          return (
                            <bk-table-column
                              key={key}
                              prop={column.id}
                              label={column.name}
                              column-key={column.id}
                              sortable={column.sortable}
                              formatter={(_row, _column, _cellValue, _index) => {
                                if (column.id === 'ip') {
                                  return _row.host;
                                }
                                if (column.id === 'status') {
                                  return this.statusContent(_row?.status === 'running' ? 'normal' : 'failure');
                                }
                                if (column.id === 'trend') {
                                  return (
                                    <span
                                      v-bk-tooltips={{
                                        content: this.$t('查看趋势')
                                      }}
                                      class='icon-monitor icon-trend'
                                    ></span>
                                  );
                                }
                                return (() => {
                                  if (!!_row[column.id]) {
                                    return _row[column.id];
                                  }
                                  if (_row[column.id] === 0) {
                                    return 0;
                                  }
                                  return '--';
                                })();
                              }}
                            ></bk-table-column>
                          );
                        })}
                      </bk-table>
                    </div>
                  );
                }
              }}
            ></bk-table-column>
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
                    formatter={(row, _column, _cellValue, index) =>
                      this.handleSetFormatter(column.id as ETableColumn, row, index)
                    }
                  ></bk-table-column>
                );
              })}
          </bk-table>
        </div>
        <ClusterConfig
          ref='clusterOperation'
          show={this.show}
          row-config={this.rowConfig}
          on-show-change={this.handleShowChange}
        ></ClusterConfig>
        <ClusterDetails
          show={this.detailsShow}
          data={this.detailsData}
          onShowChange={this.handleDetailShowChange}
          onEdit={this.handleDetailsToEdit}
        ></ClusterDetails>
      </div>
    );
  }
}
