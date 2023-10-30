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
import { Component, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import { Divider, Table, TableColumn } from 'bk-magic-vue';

import './storage-state.scss';

interface StorageStateProps {
  collectId: number;
}

@Component
export default class StorageState extends tsc<StorageStateProps, {}> {
  @Prop({ type: Number, required: true }) collectId: number;

  clusterTableList = [];
  clusterTableLoading = false;

  render() {
    return (
      <div class='storage-state-component'>
        <div class='storage-info'>
          <div class='title'>{this.$t('存储信息')}</div>
          <div class='info-form'>
            <div class='info-row'>
              <div class='info-item'>
                <div class='info-label'>
                  <span class='label'>{this.$t('存储索引名')}</span>
                </div>
                <div class='info-value'>trace_agg_scene</div>
              </div>
              <div class='info-item'>
                <div class='info-label'>
                  <span class='label'>{this.$t('存储集群')}</span>
                </div>
                <div class='info-value'>trace_agg_scene</div>
              </div>
            </div>
            <div class='info-row'>
              <div class='info-item'>
                <div class='info-label'>
                  <span class='label underline'>{this.$t('过期时间')}</span>
                </div>
                <div class='info-value'>trace_agg_scene</div>
              </div>
              <div class='info-item'>
                <div class='info-label'>
                  <span class='label underline'>{this.$t('副本数')}</span>
                </div>
                <div class='info-value'>trace_agg_scene</div>
              </div>
            </div>
          </div>
        </div>
        <Divider class='divider' />
        <div class='cluster-status'>
          <div class='title'>{this.$t('集群状态')}</div>
          <div class='table-content'>
            <Table
              class='data-sample-table'
              data={this.clusterTableList}
              v-bkloading={{ isLoading: this.clusterTableLoading }}
            >
              <TableColumn label={this.$t('索引')} />
              <TableColumn label={this.$t('运行状态')} />
              <TableColumn
                label={this.$t('主分片')}
                sortable
              />
              <TableColumn
                label={this.$t('副本分片')}
                sortable
              />
              <TableColumn
                label={this.$t('文档计数')}
                sortable
              />
              <TableColumn
                label={this.$t('存储大小')}
                sortable
              />
            </Table>
          </div>
        </div>
        <Divider class='divider' />
        <div class='index-status'>
          <div class='title'>{this.$t('索引状态')}</div>
          <div class='table-content'>
            <Table
              class='data-sample-table'
              data={this.clusterTableList}
              v-bkloading={{ isLoading: this.clusterTableLoading }}
            >
              <TableColumn label={this.$t('索引')} />
              <TableColumn label={this.$t('运行状态')} />
              <TableColumn
                label={this.$t('主分片')}
                sortable
              />
              <TableColumn
                label={this.$t('副本分片')}
                sortable
              />
              <TableColumn
                label={this.$t('文档计数')}
                sortable
              />
              <TableColumn
                label={this.$t('存储大小')}
                sortable
              />
            </Table>
          </div>
        </div>
      </div>
    );
  }
}
