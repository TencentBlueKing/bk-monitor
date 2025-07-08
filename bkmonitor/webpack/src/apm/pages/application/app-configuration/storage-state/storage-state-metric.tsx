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

import TableSkeleton from 'monitor-pc/components/skeleton/table-skeleton';

import PanelItem from '../../../../components/panel-item/panel-item';

import type { IAppInfo, IMetricStorageInfo } from '../type';

import './storage-state-metric.scss';

interface IProps {
  appInfo: IAppInfo;
  data: IMetricStorageInfo[];
  dataLoading: boolean;
}
@Component
export default class Metric extends tsc<IProps> {
  @Prop({ type: Object, default: () => {} }) appInfo: IAppInfo;
  @Prop({ type: Array, default: () => [] }) data: IMetricStorageInfo[];
  @Prop({ type: Boolean, default: false }) dataLoading: boolean;
  healthMaps = {
    green: this.$t('健康'),
    yellow: this.$t('部分异常'),
    red: this.$t('异常'),
  };
  render() {
    const statusSlot = {
      default: (props: { row: IMetricStorageInfo; index: string }) => {
        return (
          <span
            key={props.index}
            class='status-wrap'
          >
            <span class={['status-icon', `status-${props.row.status}`]} />
            <span class='status-name'>{props.row.status_display}</span>
          </span>
        );
      },
    };
    return (
      <div class='metric-wrap'>
        <PanelItem title={this.$t('存储信息')}>
          {this.dataLoading ? (
            <TableSkeleton />
          ) : (
            <bk-table
              data={this.data}
              outer-border={false}
            >
              <bk-table-column
                label={this.$t('存储表名称')}
                prop={'result_table_id'}
              />
              <bk-table-column
                formatter={row => row?.storage_type_alias || row?.storage_type || '--'}
                label={this.$t('存储类型')}
                prop={'storage_type_alias'}
              />
              <bk-table-column
                formatter={row => row?.storage_cluster_alias || row?.storage_cluster || '--'}
                label={this.$t('存储集群')}
                prop={'storage_cluster_alias'}
              />
              <bk-table-column
                label={this.$t('有效期')}
                prop={'expire_time_alias'}
              />
              <bk-table-column
                label={this.$t('运行状态')}
                scopedSlots={statusSlot}
              />
              <bk-table-column
                formatter={row => (row.created_by ? <bk-user-display-name user-id={row.created_by} /> : '--')}
                label={this.$t('创建者')}
                prop={'created_by'}
              />
              <bk-table-column
                label={this.$t('创建时间')}
                prop={'created_at'}
              />
            </bk-table>
          )}
        </PanelItem>
      </div>
    );
  }
}
