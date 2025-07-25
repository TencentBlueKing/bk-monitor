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
import { Component, Inject, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { setup } from 'monitor-api/modules/apm_meta';
import { byteConvert } from 'monitor-common/utils/utils';
import TableSkeleton from 'monitor-pc/components/skeleton/table-skeleton';

import EditableFormItem from '../../../../components/editable-form-item/editable-form-item';
import PanelItem from '../../../../components/panel-item/panel-item';
import * as authorityMap from '../../../home/authority-map';
import StorageInfoSkeleton from '../skeleton/storage-info-skeleton';

import type { ETelemetryDataType, IAppInfo, IClusterItem, ILogStorageInfo, IndicesItem } from '../type';

import './storage-state-log.scss';
interface IProps {
  appInfo: IAppInfo;
  clusterList: IClusterItem[];
  dataLoading?: boolean;
  indicesList: IndicesItem[];
  indicesLoading: boolean;
  storageInfo?: ILogStorageInfo;
  telemetryDataType?: ETelemetryDataType;
  onChange?: (params: ILogStorageInfo) => void;
}
@Component
export default class Log extends tsc<IProps> {
  @Prop({ type: Object, default: () => ({}) }) appInfo: IAppInfo;
  @Prop({ type: Array, default: () => [] }) indicesList: IndicesItem[];
  @Prop({ type: Boolean, default: false }) dataLoading: boolean;
  @Prop({ type: Boolean, default: false }) indicesLoading: boolean;
  // 存储信息
  @Prop({ type: Object, default: () => ({}) }) storageInfo: ILogStorageInfo;
  @Prop({ type: String, default: '' }) telemetryDataType: ETelemetryDataType;
  @Prop({ type: Array, required: true }) clusterList: any[];

  @Inject('authority') authority;

  healthMaps = {
    green: window.i18n.tc('健康'),
    yellow: window.i18n.tc('部分异常'),
    red: window.i18n.tc('异常'),
  };

  /** 选中的集群 */
  get currentCluster() {
    return this.clusterList.find(item => item.storage_cluster_id === this.storageInfo?.es_storage_cluster);
  }

  get retentionDaysMax() {
    return this.currentCluster?.setup_config.retention_days_max || 7;
  }

  async handleUpdateValue(value, field: string) {
    try {
      // 更新基本信息
      const obj = {};
      for (const key in this.storageInfo) {
        if (/^es/.test(key)) {
          obj[key] = this.storageInfo[key];
        }
      }
      const logsourceConfig = Object.assign(obj, { [field]: Number(value) });
      const params = {
        application_id: this.appInfo.application_id,
        log_datasource_option: logsourceConfig,
        telemetry_data_type: this.telemetryDataType,
      };
      await setup(params).then(() => {
        this.$emit('change', logsourceConfig);
      });
      return true;
    } catch {
      return false;
    }
  }

  /**
   * @desc 修改副本数校验规则
   * @param { * } val
   * @param { String } filed
   */
  initValidator(val, _filed: string) {
    if (!/(^\d+$)|(^\d+\.\d+$)/.test(val)) {
      return this.$t('输入正确数字');
    }
    return '';
  }

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
          {this.dataLoading ? (
            <StorageInfoSkeleton />
          ) : (
            <div class='form-content'>
              <div class='item-row'>
                <EditableFormItem
                  formType='input'
                  label={this.$t('集群名称')}
                  showEditable={false}
                  value={this.storageInfo?.display_storage_cluster_name}
                />
                <EditableFormItem
                  formType='input'
                  label={this.$t('索引集名称')}
                  showEditable={false}
                  value={this.storageInfo?.display_es_storage_index_name}
                />
              </div>
              <div class='item-row'>
                <EditableFormItem
                  authority={this.authority.MANAGE_AUTH}
                  authorityName={authorityMap.MANAGE_AUTH}
                  formType='expired'
                  label={this.$t('过期时间')}
                  maxExpired={this.retentionDaysMax}
                  showEditable={true}
                  tooltips={this.$t('过期时间')}
                  updateValue={val => this.handleUpdateValue(val, 'es_retention')}
                  validator={val => this.initValidator(val, 'es_retention')}
                  value={this.storageInfo?.es_retention}
                />
                <EditableFormItem
                  formType='input'
                  label={this.$t('分列规则')}
                  showEditable={false}
                  tooltips={this.$t('分列规则')}
                  value={this.storageInfo?.display_index_split_rule}
                />
              </div>
            </div>
          )}
        </PanelItem>
        <PanelItem title={this.$t('物理索引')}>
          {this.indicesLoading ? (
            <TableSkeleton />
          ) : (
            <bk-table
              // v-bkloading={{ isLoading: this.indicesLoading }}
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
          )}
        </PanelItem>
      </div>
    );
  }
}
