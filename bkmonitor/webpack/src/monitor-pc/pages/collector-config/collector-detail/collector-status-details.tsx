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
import { Component, Inject, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import {
  batchRetry,
  batchRevokeTargetNodes,
  getCollectLogDetail,
  isTaskReady,
  retryTargetNodes,
  revokeTargetNodes
} from '../../../../monitor-api/modules/collecting';
import { copyText } from '../../../../monitor-common/utils/utils.js';
import ExpandWrapper from '../../../components/expand-wrapper/expand-wrapper';
import { transformJobUrl } from '../../../utils/index';
import {
  colorMap,
  EStatus,
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
  onCanPolling: (_v) => void;
  onRefresh: () => void;
}

@Component
export default class CollectorStatusDetails extends tsc<IProps> {
  @Prop({ type: Object, default: () => null }) data: any;
  @Prop({ type: String, default: '' }) updateKey: boolean;
  @Prop({ type: Boolean, default: true }) isRunning: boolean;

  @Inject('authority') authority;
  @Inject('handleShowAuthorityDetail') handleShowAuthorityDetail;
  @Inject('authorityMap') authorityMap;

  /* 所有表格内容 */
  contents: IContentsItem[] = [];

  /* 表格字段 */
  tableColumns = [
    { id: EColumn.name, name: window.i18n.t('目标'), width: 278 },
    { id: EColumn.alert, name: window.i18n.t('告警'), minWidth: 217, width: 217 },
    { id: EColumn.status, name: window.i18n.t('状态'), width: 165 },
    { id: EColumn.version, name: window.i18n.t('版本'), width: 228 },
    { id: EColumn.detail, name: window.i18n.t('详情') },
    { id: EColumn.operate, name: '', width: 200 }
  ];
  /* 详情侧栏 */
  side = {
    show: false,
    title: '',
    detail: '',
    loading: false
  };

  config = null;

  refresh = false;

  /* 头部状态 */
  header = {
    status: EStatus.ALL,
    batchRetry: false,
    data: {
      successNum: 0,
      failedNum: 0,
      pendingNum: 0,
      total: 0
    }
  };

  disBatch = false;

  /* 判断当前可否复制ip或者服务实例 */
  targetNodeType = '';

  get haveDeploying() {
    const resArr = [];
    this.contents.forEach(item => {
      const res = item.child.some(one => ['DEPLOYING', EStatus.RUNNING, 'PENDING'].includes(one.status));
      resArr.push(res);
    });
    return resArr.some(item => item);
  }

  /**
   * @description 更新数据
   */
  @Watch('updateKey')
  handleUpdate() {
    if (!!this.data) {
      const sumData = {
        pending: {},
        success: {},
        failed: {}
      };
      this.config = this.data.config_info;
      this.targetNodeType = this.data.config_info?.target_node_type || '';
      this.contents = this.data.contents.map(item => {
        const table = [];
        const nums = {
          failedNum: 0,
          pendingNum: 0,
          successNum: 0
        };
        let showAlertHistogram = true;
        item.child.forEach(set => {
          // const alertHistogram = set?.alert_histogram?.map(a => ({ level: a[1] })) || [];
          const alertHistogram = set?.alert_histogram || [];
          showAlertHistogram = !!set?.alert_histogram;
          // 表格内容
          if (
            STATUS_LIST.includes(set.status) ||
            set.status === this.header.status ||
            this.header.status === EStatus.ALL
          ) {
            table.push({
              ...set,
              alertHistogram
            });
          }
          // 数量及状态
          if (set.status === EStatus.SUCCESS) {
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
          showAlertHistogram,
          isExpan: true
        };
      });
      const headerData: any = {};
      headerData.failedNum = Object.keys(sumData.failed).length;
      headerData.pendingNum = Object.keys(sumData.pending).length;
      headerData.successNum = Object.keys(sumData.success).length;
      headerData.total = headerData.successNum + headerData.failedNum + headerData.pendingNum;
      this.header.data = headerData;
    }
  }

  bkMsg(theme, message) {
    this.$bkMessage({
      theme,
      message,
      ellipsisLine: 0
    });
  }

  /**
   * @description 表格详情按钮
   * @param data
   */
  handleGetMoreDetail(data) {
    this.side.show = true;
    const { instance_name } = data;
    if (instance_name !== this.side.title) {
      this.side.title = instance_name;
      this.side.loading = true;
      getCollectLogDetail(
        {
          instance_id: data.instance_id,
          task_id: data.task_id,
          id: this.config.id
        },
        { needMessage: false }
      )
        .then(data => {
          this.side.detail = data.log_detail;
          this.side.loading = false;
        })
        .catch(error => {
          this.bkMsg('error', error.message || this.$t('获取更多数据失败'));
          this.side.show = false;
          this.side.loading = false;
        });
    }
  }

  /**
   * @description 筛选状态
   * @param id
   */
  handleFilterChange(id) {
    this.header.status = id;
    this.contents.forEach(item => {
      const table = [];
      let showAlertHistogram = true;
      item.child.forEach(set => {
        if ((id === EStatus.RUNNING && STATUS_LIST.includes(set.status)) || set.status === id || id === EStatus.ALL) {
          // const alertHistogram = set?.alert_histogram?.map(a => ({ level: a[1] })) || [];
          const alertHistogram = set?.alert_histogram || [];
          showAlertHistogram = !!set?.alert_histogram;
          table.push({
            ...set,
            alertHistogram
          });
        }
      });
      item.showAlertHistogram = showAlertHistogram;
      item.table = table;
    });
  }

  /**
   * @description 重试
   * @param data
   * @param table
   */
  async handleRetry(data, table) {
    this.refresh = false;
    if (this.side.title === data.instance_name) {
      this.side.title = '';
    }
    this.contents.forEach(content => {
      if (content.child?.length) {
        const setData = content.child.find(
          set => set.instance_id === data.instance_id && set.status === EStatus.FAILED
        );
        if (setData) {
          setData.status = 'PENDING';
          content.pendingNum += 1;
          content.failedNum -= 1;
        }
      }
    });
    this.header.data.pendingNum += 1;
    this.header.data.failedNum -= 1;
    this.handleFilterChange(this.header.status);
    this.handlePolling(false);
    retryTargetNodes({
      id: this.config.id,
      instance_id: data.instance_id
    })
      .then(async () => {
        const isReady = await this.taskReadyStatus(this.config.id).catch(() => false);
        if (isReady) {
          this.refresh = true;
          this.handlePolling();
        }
      })
      .catch(() => {
        data.status = EStatus.FAILED;
        table.failedNum += 1;
        table.pendingNum -= 1;
        this.header.data.failedNum += 1;
        this.header.data.pendingNum -= 1;
        this.refresh = true;
        this.handlePolling();
      });
  }

  handlePolling(v = true) {
    this.$emit('canPolling', v);
  }

  handleRevoke(data, table) {
    revokeTargetNodes({
      id: this.config.id,
      instance_ids: [data.instance_id]
    }).finally(() => {
      data.status = 'FAILED';
      table.pendingNum -= 1;
      table.failedNum += 1;
      this.header.data.pendingNum -= 1;
      this.header.data.failedNum += 1;
      this.handleFilterChange(this.header.status);
      this.refresh = true;
      this.handlePolling();
    });
  }

  /**
   * @description 准备状态
   * @param id
   * @returns
   */
  async taskReadyStatus(id) {
    let timer = null;
    clearTimeout(timer);
    // eslint-disable-next-line @typescript-eslint/no-misused-promises
    return new Promise(async resolve => {
      const isShow = await isTaskReady({ collect_config_id: id }).catch(() => false);
      if (isShow) {
        resolve(true);
        return;
      }
      timer = setTimeout(() => {
        this.taskReadyStatus(id).then(res => {
          resolve(res);
        });
      }, 2000);
    });
  }

  /**
   * @description 批量重试
   */
  handleBatchRetry() {
    const failedList = [];
    this.refresh = false;
    this.header.batchRetry = true;
    this.side.title = '';
    this.contents.forEach(item => {
      item.child.forEach(set => {
        if (EStatus.FAILED === set.status) {
          set.status = 'PENDING';
          failedList.push(set);
        }
      });
      item.pendingNum += item.failedNum;
      item.failedNum = 0;
    });
    this.header.data.pendingNum += this.header.data.failedNum;
    this.header.data.failedNum = 0;
    this.handleFilterChange(this.header.status);
    this.handlePolling(false);
    batchRetry({ id: this.config.id })
      .then(async () => {
        const isStatusReady = await this.taskReadyStatus(this.config.id);
        if (isStatusReady) {
          this.refresh = true;
          this.header.batchRetry = false;
          this.handlePolling();
        }
      })
      .catch(() => {
        failedList.forEach(item => (item.status = EStatus.FAILED));
        this.header.data.pendingNum = 0;
        this.header.batchRetry = false;
        this.header.data.failedNum = failedList.length;
        this.refresh = true;
        this.handlePolling();
      });
  }

  /**
   * @description 批量停止
   */
  handleBatchStop() {
    this.disBatch = true;
    this.refresh = false;
    batchRevokeTargetNodes({ id: this.config.id }).finally(() => {
      this.header.batchRetry = false;
      this.refresh = true;
      this.disBatch = false;
      this.handleRefreshData();
    });
  }

  /**
   * @description 刷新表格数据
   */
  handleRefreshData() {
    this.$emit('refresh');
  }

  /**
   * @description 复制目标
   */
  handleCopyTargets(type?: 'ip' | 'instance') {
    let copyStr = '';
    this.contents.forEach(ct => {
      if (type === 'ip' || this.targetNodeType === 'HOST') {
        ct.table.forEach(item => (copyStr += `${item.ip}\n`));
      } else {
        ct.table.forEach(item => (copyStr += `${item.instance_name}\n`));
      }
    });
    copyText(copyStr, msg => {
      this.$bkMessage({
        theme: 'error',
        message: msg
      });
      return;
    });
    this.$bkMessage({
      theme: 'success',
      message: this.$t('复制成功')
    });
  }

  render() {
    return (
      <div class='collector-status-details-component'>
        <div class='header-opreate'>
          <div class='header-filter'>
            {FILTER_TYPE_LIST.map(item => (
              <div
                class={['header-filter-item', { active: item.id === this.header.status }]}
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
                  if (item.id === EStatus.RUNNING) {
                    return (
                      <bk-spin
                        size='mini'
                        class='mr-3'
                      ></bk-spin>
                    );
                  }
                  return undefined;
                })()}
                <span class='mr-3'>{item.name}</span>
                <span class='mt-2'>
                  {(() => {
                    if (item.id === EStatus.ALL) return this.header.data.total;
                    if (item.id === EStatus.SUCCESS) return this.header.data.successNum;
                    if (item.id === EStatus.FAILED) return this.header.data.failedNum;
                    if (item.id === EStatus.RUNNING) return this.header.data.pendingNum;
                  })()}
                </span>
              </div>
            ))}
          </div>
          <div class='batch-opreate'>
            <bk-button
              class='mr-10'
              v-authority={{ active: !this.authority.MANAGE_AUTH }}
              disabled={
                this.header.batchRetry || !(this.header.data.failedNum > 0 && this.header.data.pendingNum === 0)
              }
              hover-theme='primary'
              onClick={() => (this.authority.MANAGE_AUTH ? this.handleBatchRetry() : this.handleShowAuthorityDetail())}
            >
              <span class='icon-monitor icon-zhongzhi1 mr-6'></span>
              <span>{this.$t('批量重试')}</span>
            </bk-button>
            <bk-button
              class='mr-10'
              v-authority={{ active: !this.authority.MANAGE_AUTH }}
              icon={this.disBatch ? 'loading' : ''}
              disabled={!this.haveDeploying || this.disBatch}
              hover-theme='primary'
              onClick={() => (this.authority.MANAGE_AUTH ? this.handleBatchStop() : this.handleShowAuthorityDetail())}
            >
              {this.$t('批量终止')}
            </bk-button>
            {this.targetNodeType === 'INSTANCE' ? (
              <bk-dropdown-menu>
                <div slot='dropdown-trigger'>
                  <span class='copy-target-btn'>{this.$t('复制目标')}</span>
                </div>
                <ul
                  class='bk-dropdown-list'
                  slot='dropdown-content'
                >
                  <li>
                    <a onClick={() => this.handleCopyTargets('ip')}>{this.$t('复制主机IP')}</a>
                  </li>
                  <li>
                    <a onClick={() => this.handleCopyTargets('instance')}>{this.$t('复制服务实例')}</a>
                  </li>
                </ul>
              </bk-dropdown-menu>
            ) : (
              <bk-button
                hover-theme='primary'
                onClick={() => this.handleCopyTargets()}
              >
                {this.$t('复制目标')}
              </bk-button>
            )}
          </div>
        </div>
        <div class='table-content'>
          {this.contents
            .filter(content => !!content.table?.length)
            .map(content => (
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
                    if (this.isRunning) {
                      const temp = [];
                      if (content.successNum && this.header.status !== EStatus.FAILED) {
                        temp.push(
                          <span class='num fix-same-code'>
                            <i18n path='{0}个成功'>
                              <span style={{ color: '#2dcb56' }}>{content.successNum}</span>
                            </i18n>
                            {(content.failedNum && [EStatus.ALL, EStatus.FAILED].includes(this.header.status)) ||
                            content.pendingNum
                              ? ','
                              : undefined}
                          </span>
                        );
                      }
                      if (content.failedNum && [EStatus.ALL, EStatus.FAILED].includes(this.header.status)) {
                        temp.push(
                          <span class='num fix-same-code'>
                            <i18n path='{0}个失败'>
                              <span style={{ color: '#ea3636' }}>{content.failedNum}</span>
                            </i18n>
                            {content.pendingNum ? ',' : undefined}
                          </span>
                        );
                      }
                      if (content.pendingNum) {
                        temp.push(
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
                            {this.config?.target_object_type ? (
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
                      return temp;
                    }
                    return (
                      <span class='num fix-same-code'>
                        <i18n
                          path={`共{0}${
                            this.config?.target_object_type === 'HOST' ? this.$t('台主机') : this.$t('个实例')
                          }`}
                        >
                          {content.successNum + content.failedNum + content.pendingNum}
                        </i18n>
                      </span>
                    );
                  })()}
                </span>
                <div
                  slot='content'
                  class='table-content-wrap'
                >
                  <bk-table
                    {...{
                      props: {
                        data: content.table
                      }
                    }}
                  >
                    {this.tableColumns
                      .filter(column => (column.id === EColumn.alert ? !!content?.showAlertHistogram : true))
                      .map(column => {
                        const key = `column_${column.id}`;
                        return (
                          <bk-table-column
                            key={key}
                            prop={column.id}
                            label={column.name}
                            width={column.width}
                            minWidth={column?.minWidth}
                            formatter={(row: any) => {
                              switch (column.id) {
                                case EColumn.name: {
                                  return <span>{row.instance_name}</span>;
                                }
                                case EColumn.alert: {
                                  return <AlertHistogram value={row.alertHistogram}></AlertHistogram>;
                                }
                                case EColumn.status: {
                                  return (
                                    <span class='col-status'>
                                      {[
                                        this.isRunning && STATUS_LIST.includes(row.status) ? (
                                          <bk-spin
                                            size='mini'
                                            class='mr-3'
                                          ></bk-spin>
                                        ) : undefined,
                                        this.isRunning &&
                                        [EStatus.FAILED, EStatus.WARNING, EStatus.SUCCESS, 'STOPPED'].includes(
                                          row.status
                                        ) ? (
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
                                      {this.isRunning && row.status === EStatus.FAILED && (
                                        <span
                                          class='col-detail-more fix-same-code'
                                          onClick={() => this.handleGetMoreDetail(row)}
                                        >
                                          {this.$t('详情')}
                                        </span>
                                      )}
                                    </span>
                                  );
                                }
                                case EColumn.operate: {
                                  return [
                                    this.isRunning && row.status === EStatus.FAILED ? (
                                      <div
                                        class='col-retry'
                                        onClick={() =>
                                          this.authority.MANAGE_AUTH
                                            ? this.handleRetry(row, content)
                                            : this.handleShowAuthorityDetail()
                                        }
                                      >
                                        {this.$t('重试')}
                                      </div>
                                    ) : undefined,
                                    this.isRunning && ['DEPLOYING', EStatus.RUNNING, 'PENDING'].includes(row.status) ? (
                                      <div
                                        class='col-retry fix-same-code'
                                        onClick={() =>
                                          ['DEPLOYING', 'RUNNING', 'PENDING'].includes(row.status) &&
                                          this.handleRevoke(row, content)
                                        }
                                      >
                                        {this.$t('终止')}
                                      </div>
                                    ) : undefined
                                  ];
                                }
                                default: {
                                  return <span>--</span>;
                                }
                              }
                            }}
                          ></bk-table-column>
                        );
                      })}
                  </bk-table>
                </div>
              </ExpandWrapper>
            ))}
        </div>
        <bk-sideslider
          class='fix-same-code'
          is-show={this.side.show}
          quick-close={true}
          width={900}
          title={this.side.title}
          {...{ on: { 'update:isShow': v => (this.side.show = v) } }}
        >
          <div
            class='side-detail fix-same-code'
            slot='content'
            v-bkloading={{ isLoading: this.side.loading }}
          >
            <pre
              class='side-detail-code fix-same-code'
              domProps={{
                innerHTML: transformJobUrl(this.side.detail)
              }}
            ></pre>
          </div>
        </bk-sideslider>
      </div>
    );
  }
}
