/* eslint-disable @typescript-eslint/naming-convention */
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
import { Component, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import { Button, Spin, Table, TableColumn } from 'bk-magic-vue';

import ExpandWrapper from '../../../components/expand-wrapper/expand-wrapper';
import {
  colorMap,
  FILTER_TYPE_LIST,
  IContentsItem,
  labelMap,
  STATUS_LIST,
  statusMap
} from '../collector-host-detail/utils';

import AlertHistogram from './components/alert-histogram';

import './collector-status-details.scss';

enum EColumn {
  name = 'name',
  status = 'status',
  version = 'version',
  detail = 'detail',
  operate = 'operate',
  alert = 'alert'
}

interface IProps {
  data: any;
  updateKey: string;
}

@Component
export default class CollectorStatusDetails extends tsc<IProps> {
  @Prop({ type: Object, default: () => null }) data: any;
  @Prop({ type: String, default: '' }) updateKey: boolean;
  @Prop({ type: Boolean, default: true }) isRunning: boolean;
  /* 当前类型 */
  filterType = 'ALL';
  /* 所有表格内容 */
  contents: IContentsItem[] = [];
  /* 头部统计数据 */
  headerData = {
    failedNum: 0,
    pendingNum: 0,
    successNum: 0
  };
  configInfo = {
    target_object_type: ''
  };

  /* 表格字段 */
  tableColumns = [
    { id: EColumn.name, name: window.i18n.t('目标'), width: 278 },
    { id: EColumn.alert, name: window.i18n.t('告警'), width: 298 },
    { id: EColumn.status, name: window.i18n.t('状态'), width: 165 },
    { id: EColumn.version, name: window.i18n.t('版本'), width: 228 },
    { id: EColumn.detail, name: window.i18n.t('详情') },
    { id: EColumn.operate, name: '', width: 200 }
  ];

  @Watch('updateKey')
  handleUpdate() {
    if (!!this.data) {
      const sumData = {
        pending: {},
        success: {},
        failed: {}
      };
      this.contents = this.data.contents.map(item => {
        const table = [];
        const nums = {
          failedNum: 0,
          pendingNum: 0,
          successNum: 0
        };
        item.child.forEach(set => {
          // 表格内容
          if (STATUS_LIST.includes(set.status) || set.status === this.filterType || this.filterType === 'ALL') {
            table.push(set);
          }
          // 数量及状态
          if (set.status === 'SUCCESS') {
            nums.successNum += 1;
            sumData.success[set.instance_id] = set.instance_id;
          } else if (STATUS_LIST.includes(set.status)) {
            sumData.pending[set.instance_id] = set.instance_id;
            nums.pendingNum += 1;
          } else {
            nums.failedNum += 1;
            sumData.failed[set.instance_id] = set.instance_id;
          }
        });
        return {
          ...item,
          ...nums,
          table,
          isExpan: true
        };
      });
    }
  }

  handleFilterChange(id) {
    this.filterType = id;
  }

  render() {
    return (
      <div class='collector-status-details-component'>
        <div class='header-opreate'>
          <div class='header-filter'>
            {FILTER_TYPE_LIST.map(item => (
              <div
                class={['header-filter-item', { active: item.id === this.filterType }]}
                key={item.id}
                onClick={() => this.handleFilterChange(item.id)}
              >
                {(() => {
                  if (!!item.color) {
                    return (
                      <span
                        class='point mr-3'
                        style={{ background: item.color[0] }}
                      >
                        <span
                          class='s-point'
                          style={{ background: item.color[1] }}
                        ></span>
                      </span>
                    );
                  }
                  if (item.id === 'RUNNING') {
                    return (
                      <Spin
                        size='mini'
                        class='mr-3'
                      ></Spin>
                    );
                  }
                  return undefined;
                })()}
                <span>{item.name}</span>
              </div>
            ))}
          </div>
          <div class='batch-opreate'>
            <Button class='mr-10'>
              <span class='icon-monitor icon-zhongzhi1 mr-6'></span>
              <span>{this.$t('批量重试')}</span>
            </Button>
            <Button class='mr-10'>{this.$t('批量终止')}</Button>
            <Button>{this.$t('复制目标')}</Button>
          </div>
        </div>
        <div class='table-content'>
          {this.contents.map(content => (
            <ExpandWrapper
              class='mt-20'
              value={content.isExpan}
              onChange={v => (content.isExpan = v)}
            >
              {!!content.is_label && (
                <span slot='pre-header'>
                  <span
                    class='pre-panel-name fix-same-code'
                    style={{
                      backgroundColor: labelMap[content.label_name].color
                    }}
                  >
                    {labelMap[content.label_name].name}
                  </span>
                  <span
                    class='pre-panel-mark fix-same-code'
                    style={{
                      borderColor: labelMap[content.label_name].color
                    }}
                  ></span>
                </span>
              )}
              <span slot='header'>
                {(() => {
                  if (content.successNum && this.filterType !== 'FAILED') {
                    return (
                      <span class='num fix-same-code'>
                        <i18n path='{0}个成功'>
                          <span style={{ color: '#2dcb56' }}>{content.successNum}</span>
                        </i18n>
                        {(content.failedNum && ['ALL', 'FAILED'].includes(this.filterType)) || content.pendingNum
                          ? ','
                          : undefined}
                      </span>
                    );
                  }
                  if (content.failedNum && ['ALL', 'FAILED'].includes(this.filterType)) {
                    return (
                      <span class='num fix-same-code'>
                        <i18n path='{0}个失败'>
                          <span style={{ color: '#ea3636' }}>{content.failedNum}</span>
                        </i18n>
                        {content.pendingNum ? ',' : undefined}
                      </span>
                    );
                  }
                  if (content.pendingNum) {
                    return (
                      <span class='num fix-same-code'>
                        <i18n path='{0}个执行中'>
                          <span style={{ color: '#3a84ff' }}>{content.failedNum}</span>
                        </i18n>
                      </span>
                    );
                  }
                  if (!content.child.length) {
                    return (
                      <span class='num'>
                        {this.configInfo.target_object_type ? (
                          <i18n path='共{0}台主机'>
                            <span style='color: #63656e;'>0</span>
                          </i18n>
                        ) : (
                          <i18n path='共{0}个实例'>
                            <span style='color: #63656e;'>0</span>
                          </i18n>
                        )}
                      </span>
                    );
                  }
                  return undefined;
                })()}
              </span>
              <div
                slot='content'
                class='table-content-wrap'
              >
                <Table
                  {...{
                    props: {
                      data: content.table
                    }
                  }}
                >
                  {this.tableColumns.map(column => {
                    const key = `column_${column.id}`;
                    return (
                      <TableColumn
                        key={key}
                        prop={column.id}
                        label={column.name}
                        width={column.width}
                        formatter={(row: any) => {
                          switch (column.id) {
                            case EColumn.name: {
                              return <span>{row.instance_name}</span>;
                            }
                            case EColumn.alert: {
                              return <AlertHistogram></AlertHistogram>;
                            }
                            case EColumn.status: {
                              return (
                                <span class='col-status'>
                                  {[
                                    this.isRunning && STATUS_LIST.includes(row.status) ? (
                                      <Spin
                                        size='mini'
                                        class='mr-3'
                                      ></Spin>
                                    ) : undefined,
                                    this.isRunning &&
                                    ['FAILED', 'WARNING', 'SUCCESS', 'STOPPED'].includes(row.status) ? (
                                      <span
                                        class='point mr-3'
                                        style={{ background: colorMap[row.status][0] }}
                                      >
                                        <span
                                          class='s-point'
                                          style={{ background: colorMap[row.status][1] }}
                                        ></span>
                                      </span>
                                    ) : undefined,
                                    this.isRunning ? (
                                      <span class='content-panel-span'>{statusMap[row.status].name}</span>
                                    ) : (
                                      <span>--</span>
                                    )
                                  ]}
                                </span>
                              );
                            }
                            case EColumn.version: {
                              return <span>{row.plugin_version}</span>;
                            }
                            case EColumn.detail: {
                              return (
                                <span class='col-detail'>
                                  <span class='col-detail-data'>{row.log || '--'}</span>
                                  {this.isRunning && row.status === 'FAILED' && (
                                    <span class='col-detail-more fix-same-code'>{this.$t('详情')}</span>
                                  )}
                                </span>
                              );
                            }
                            case EColumn.operate: {
                              return [
                                this.isRunning && row.status === 'FAILED' ? (
                                  <div class='col-retry'>{this.$t('重试')}</div>
                                ) : undefined,
                                this.isRunning && ['DEPLOYING', 'RUNNING', 'PENDING'].includes(row.status) ? (
                                  <div class='col-retry fix-same-code'>{this.$t('终止')}</div>
                                ) : undefined
                              ];
                            }
                            default: {
                              return <span>--</span>;
                            }
                          }
                        }}
                      ></TableColumn>
                    );
                  })}
                </Table>
              </div>
            </ExpandWrapper>
          ))}
        </div>
      </div>
    );
  }
}
