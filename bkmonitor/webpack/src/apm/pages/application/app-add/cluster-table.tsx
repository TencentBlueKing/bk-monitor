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
import { Component, Emit, Model, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './cluster-table.scss';

interface IProps {
  value?: number;
  tableType?: string;
  tableList: any[];
}

interface IEvent {
  onChange: number;
}

@Component
export default class ClusterTable extends tsc<IProps, IEvent> {
  @Prop({ type: String, default: 'shared' }) tableType: string;
  @Prop({ type: Array }) tableList: any[];

  @Model('modelChange', { type: Number }) readonly value: Number;

  isShowTable = true;

  labelNameList = {
    secondaryNumber: window.i18n.tc('副本数'),
    expiration: window.i18n.tc('过期时间'),
    hotData: window.i18n.tc('热冷数据'),
    logArchive: window.i18n.tc('日志归档')
  };

  get tableShowType() {
    return this.tableType !== 'exclusive';
  }

  get activeItem() {
    return this.tableList.find(item => item.storage_cluster_id === this.value) || null;
  }

  get illustrateLabelData() {
    // eslint-disable-next-line max-len
    const {
      setup_config: { number_of_replicas_max, retention_days_max },
      enable_archive,
      enable_hot_warm
    } = this.activeItem;
    return {
      secondaryNumber: `${this.$t('最大{max}个', { max: number_of_replicas_max })}`,
      expiration: `${this.$t('最大{max}天', { max: retention_days_max })}`,
      hotData: enable_hot_warm ? this.$t('支持') : this.$t('不支持'),
      logArchive: enable_archive ? this.$t('支持') : this.$t('不支持')
    };
  }

  @Watch('tableList', { immediate: true })
  handleTableListChange(list) {
    this.isShowTable = !!list.length;
  }

  @Emit('modelChange')
  handleModelChange(clusterID: number) {
    return clusterID;
  }

  @Emit('change')
  handleOnChangeCluster(clusterID: number) {
    return clusterID;
  }

  handleSelectCluster(row) {
    this.handleModelChange(row.storage_cluster_id);
    this.handleOnChangeCluster(row.storage_cluster_id);
  }

  /**
   * 格式化文件大小
   * @param {Number | String} size
   * @return {String}
   */
  formatFileSize = (size: number | string): string => {
    const value = Number(size);
    if (size && !isNaN(value)) {
      const units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB', 'BB'];
      let index = 0;
      let k = value;
      if (value >= 1024) {
        while (k > 1024) {
          k = k / 1024;
          index = index + 1;
        }
      }
      return `${k.toFixed(2)}${units[index]}`;
    }
    return '0';
  };

  getPercent(reduce = 0, divisor = 100) {
    return (100 - reduce) / divisor;
  }

  render() {
    return (
      <div class='cluster-container'>
        <div
          class='cluster-title'
          onClick={() => (this.isShowTable = !this.isShowTable)}
        >
          <div class={['cluster-title-container', this.isShowTable ? '' : 'is-hidden']}>
            <span class='bk-icon icon-angle-up-fill'></span>
            <p>{this.tableShowType ? this.$t('共享集群') : this.$t('业务独享集群')}</p>
          </div>
        </div>
        {this.tableList.length ? (
          <div class={['cluster-main', this.isShowTable ? '' : 'is-hidden']}>
            <bk-table
              class='cluster-table'
              data={this.tableList}
              max-height='254'
              on-row-click={this.handleSelectCluster}
            >
              <bk-table-column
                label={this.$t('集群名')}
                min-width='220'
                scopedSlots={{
                  default: ({ row }) => (
                    <bk-radio checked={this.value === row.storage_cluster_id}>
                      <span>{row.storage_cluster_name}</span>
                    </bk-radio>
                  )
                }}
              ></bk-table-column>
              <bk-table-column
                label={this.$t('总量')}
                min-width='110'
                scopedSlots={{
                  default: ({ row }) => <span>{this.formatFileSize(row.storage_total)}</span>
                }}
              ></bk-table-column>
              <bk-table-column
                label={this.$t('空闲率')}
                min-width='110'
                scopedSlots={{
                  default: ({ row }) => (
                    <div class='percent'>
                      <div class='percent-progress'>
                        <bk-progress
                          theme='success'
                          show-text={false}
                          percent={this.getPercent(row.storage_usage)}
                        ></bk-progress>
                      </div>
                      <span>{`${this.getPercent(row.storage_usage, 1)}%`}</span>
                    </div>
                  )
                }}
              ></bk-table-column>
              <bk-table-column
                label={this.$t('索引数')}
                prop={'index_count'}
              ></bk-table-column>
              {this.tableShowType && (
                <bk-table-column
                  label={this.$t('业务数')}
                  prop={'biz_count'}
                ></bk-table-column>
              )}
            </bk-table>
            {Boolean(this.activeItem) && (
              <div class='cluster-illustrate'>
                <p class='illustrate-title'>{this.$t('集群说明')}</p>
                <div class='illustrate-container'>
                  {Object.keys(this.labelNameList).map(item => (
                    <div>
                      <span class='illustrate-label'>{this.labelNameList[item]}:&nbsp;&nbsp;</span>
                      <span class='illustrate-value'>{this.illustrateLabelData[item]}</span>
                    </div>
                  ))}
                </div>
                <div class='illustrate-list'>
                  <pre>{this.activeItem.description}</pre>
                </div>
              </div>
            )}
          </div>
        ) : (
          <div class={['cluster-main', this.isShowTable ? '' : 'is-hidden']}>
            <div class='noData-container'>
              <div class='noData-message'>
                <span class='bk-table-empty-icon bk-icon icon-empty'></span>
                <p class='empty-message'>
                  {this.tableShowType
                    ? this.$t('当前还没有共享集群，请联系平台管理员提供')
                    : this.$t('当前还没有业务独享集群')}
                </p>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }
}
