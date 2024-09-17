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

import { byteConvert } from 'monitor-common/utils/utils';

import EditableFormItem from '../../../../components/editable-form-item/editable-form-item';
import PanelItem from '../../../../components/panel-item/panel-item';

import type { IAppInfo, IndicesItem } from '../type';

import './log.scss';
interface IProps {
  appInfo: IAppInfo;
  dataLoading?: boolean;
  indicesLoading: boolean;
  indicesList: IndicesItem[];
}
@Component
export default class Log extends tsc<IProps> {
  @Prop({ type: Object, default: () => ({}) }) appInfo: IAppInfo;
  @Prop({ type: Array, default: () => [] }) indicesList: IndicesItem[];
  @Prop({ type: Boolean }) dataLoading: boolean;
  @Prop({ type: Boolean }) indicesLoading: boolean;
  healthMaps = {
    green: this.$t('健康'),
    yellow: this.$t('部分异常'),
    red: this.$t('异常'),
  };
  render() {
    const statusSlot = {
      default: props => [
        <span
          key={`${props.index}_status`}
          class='status-wrap'
        >
          <span class={['status-icon', `status-${props.row.health}`]} />
          <span class='status-name'>{this.healthMaps[props.row.health]}</span>
        </span>,
      ],
    };
    const sizeSlot = {
      default: props => [<span key={`${props.index}_size`}>{byteConvert(props.row.store_size)}</span>],
    };
    return (
      <div class='log-wrap'>
        <PanelItem title={this.$t('存储信息')}>
          <div class='form-content'>
            <div class='item-row'>
              <EditableFormItem
                formType='input'
                label={this.$t('集群名称')}
                showEditable={false}
                value={this.appInfo.application_datasource_config?.es_storage_cluster}
              />
              <EditableFormItem
                formType='input'
                label={this.$t('索引集名称')}
                showEditable={false}
                value={this.appInfo.es_storage_index_name}
              />
            </div>
            <div class='item-row'>
              <EditableFormItem
                formType='expired'
                label={this.$t('过期时间')}
                showEditable={false}
                tooltips={this.$t('过期时间')}
                value={this.appInfo.application_datasource_config?.es_retention}
              />
              <EditableFormItem
                formType='input'
                label={this.$t('分列规则')}
                showEditable={false}
                tooltips={this.$t('分列规则')}
                value={this.appInfo.application_datasource_config?.es_number_of_replicas}
              />
            </div>
          </div>
        </PanelItem>
        <PanelItem title={this.$t('物理索引')}>
          <bk-table
            v-bkloading={{ isLoading: this.indicesLoading }}
            data={this.indicesList}
            outer-border={false}
          >
            <bk-table-column
              width={280}
              label={this.$t('索引')}
              prop={'index'}
            />
            <bk-table-column
              label={this.$t('运行状态')}
              scopedSlots={statusSlot}
            />
            <bk-table-column
              label={this.$t('主分片')}
              prop={'pri'}
              sortable
            />
            <bk-table-column
              label={this.$t('副本分片')}
              prop={'rep'}
              sortable
            />
            <bk-table-column
              label={this.$t('文档计数')}
              prop={'docs_count'}
              sortable
            />
            <bk-table-column
              label={this.$t('存储大小')}
              prop={'store_size'}
              scopedSlots={sizeSlot}
              sortable
            />
          </bk-table>
        </PanelItem>
      </div>
    );
  }
}
