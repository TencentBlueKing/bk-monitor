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

import { Component, Emit, Inject, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { setup } from 'monitor-api/modules/apm_meta';
import { byteConvert } from 'monitor-common/utils/utils';
import TableSkeleton from 'monitor-pc/components/skeleton/table-skeleton';
import TextOverflowCopy from 'monitor-pc/pages/monitor-k8s/components/text-overflow-copy/text-overflow-copy';

import EditableFormItem from '../../../../components/editable-form-item/editable-form-item';
import PanelItem from '../../../../components/panel-item/panel-item';
import * as authorityMap from '../../../home/authority-map';
import StorageInfoSkeleton from '../skeleton/storage-info-skeleton';

import type {
  ClusterOption,
  ETelemetryDataType,
  IAppInfo,
  IClusterItem,
  IFieldFilterItem,
  IFieldItem,
  IndicesItem,
  ITracingStorageInfo,
} from '../type';

import './storage-state-trace.scss';

interface IEvent {
  onChange?: (params: ITracingStorageInfo) => void;
}

interface IProps {
  appInfo: IAppInfo;
  clusterList: IClusterItem[];
  dataLoading?: boolean;
  fieldFilterList: IFieldFilterItem[];
  fieldList: IFieldItem[];
  fieldLoading: boolean;
  indicesList: IndicesItem[];
  indicesLoading: boolean;
  setupData: any;
  storageInfo?: ITracingStorageInfo;
  telemetryDataType?: ETelemetryDataType;
}
@Component
export default class Trace extends tsc<IProps, IEvent> {
  @Prop({ type: Object, default: () => {} }) appInfo: IAppInfo;
  @Prop({ type: Array, default: () => [] }) indicesList: IndicesItem[];
  @Prop({ type: Array, default: () => [] }) fieldList: IndicesItem[];
  @Prop({ type: Array, default: () => [] }) fieldFilterList: IFieldFilterItem[];
  @Prop({ type: Array, required: true }) clusterList: any[];
  @Prop({ type: Object, default: () => {} }) setupData;
  @Prop({ type: Boolean }) fieldLoading: boolean;
  @Prop({ type: Boolean }) indicesLoading: boolean;
  @Prop({ type: Boolean, default: false }) dataLoading: boolean;
  // 存储信息
  @Prop({ type: Object, default: () => ({}) }) storageInfo: ITracingStorageInfo;
  @Prop({ type: String, default: '' }) telemetryDataType: ETelemetryDataType;

  @Inject('authority') authority;

  whetherFilters: IFieldFilterItem[] = [
    { text: window.i18n.tc('是'), value: 'true' },
    { text: window.i18n.tc('否'), value: 'false' },
  ];

  clusterOptions: ClusterOption[] = [];
  healthMaps = {
    green: this.$t('健康'),
    yellow: this.$t('部分异常'),
    red: this.$t('异常'),
  };

  /** 选中的集群 */
  get currentCluster() {
    return this.clusterList.find(item => item.storage_cluster_id === this.storageInfo?.es_storage_cluster);
  }
  /** 过期时间的最大值 */
  get retentionDaysMax() {
    return this.currentCluster?.setup_config.retention_days_max || 7;
  }
  /** 副本最大数量 */
  get numberOfReplicasMax() {
    return this.currentCluster?.setup_config.number_of_replicas_max || 0;
  }
  /** 分片最大数量 */
  get esShardsMax() {
    return this.currentCluster?.setup_config.es_shards_max || 1;
  }

  @Emit('change')
  handleBaseInfoChange() {
    return true;
  }

  //   created() {
  //     this.getMetaConfigInfo();
  //     this.getindicesList();
  //     this.getFieldList();
  //     this.getStoreList();
  //   }

  @Watch('clusterList', { immediate: true })
  handleClusterListChange(list) {
    this.clusterOptions = list.map(item => ({
      id: item.storage_cluster_id,
      name: item.storage_cluster_name,
    }));
  }

  /**
   * @desc: 获取字段过滤列表
   * @param { Array } list 被处理的列表
   * @returns { Array } 返回值
   */
  getFieldFilterList(list) {
    const setList = new Set();
    const filterList = [];
    list.forEach(item => {
      if (!setList.has(item.field_type)) {
        setList.add(item.field_type);
        filterList.push({
          text: item.field_type,
          value: item.field_type,
        });
      }
    });
    return filterList;
  }
  fieldFilterMethod(value, row, column) {
    const { property } = column;
    return row[property] === value;
  }
  whetherFilterMethod(value, row, column) {
    const { property } = column;
    const realVal = value === 'true';
    return row[property] === realVal;
  }
  /**
   * @desc 修改副本数校验规则
   * @param { * } val
   * @param { String } filed
   */
  initValidator(val, filed: string) {
    if (!/(^\d+$)|(^\d+\.\d+$)/.test(val)) {
      return this.$t('输入正确数字');
    }
    if (filed === 'es_number_of_replicas') {
      if (val > this.numberOfReplicasMax) {
        return `${this.$t('最大副本数不能超过')}${this.numberOfReplicasMax}`;
      }
    } else if (filed === 'es_shards') {
      if (val < 1) {
        return `${this.$t('分片数不能小于1')}`;
      }
      if (val > this.esShardsMax) {
        return `${this.$t('最大分片数不能超过')}${this.esShardsMax}`;
      }
    } else if (filed === 'es_slice_size') {
      if (val < 1) {
        return `${this.$t('索引切分大小不能小于1')}`;
      }
    }
    return '';
  }
  /**
   * @desc 字段请求接口更新
   * @param { * } value
   * @param { string } field
   */
  async handleUpdateValue(value, field: string) {
    if (field === 'es_storage_cluster') {
      const isCanSubmit = await this.handleCheckCluster();
      if (!isCanSubmit) return false;
      /** 切换集群时 进行对切换的集群与当前参数对比 如果大于最大值则提示修改参数 */
      const checkSubmitValue = this.checkClusterValue(value);
      if (!checkSubmitValue) return false;
    }
    try {
      // 更新基本信息
      const datasourceConfig = Object.assign(this.storageInfo || {}, { [field]: Number(value) });

      const params = {
        application_id: this.appInfo.application_id,
        trace_datasource_option: datasourceConfig,
        telemetry_data_type: this.telemetryDataType,
      };
      await setup(params).then(() => {
        this.$emit('change', datasourceConfig);
      });
      return true;
    } catch {
      return false;
    }
  }

  /**
   * @desc: 检测当前集群参数是否大于切换的集群参数的最大值
   * @param {Number} value 切换的集群id
   * @returns {Boolean} 是否有当前值大于最大值
   */
  checkClusterValue(value: number) {
    const selectItem = this.clusterList.find(item => item.storage_cluster_id === value);
    const { es_retention, es_number_of_replicas, es_shards } = this.storageInfo;
    const { es_shards_max, number_of_replicas_max, retention_days_max } = selectItem.setup_config;
    const compareMap = [
      {
        isExceed: es_retention > retention_days_max,
        maxVal: retention_days_max,
        id: 'retention',
        name: this.$t('过期天数'),
      },
      {
        isExceed: es_shards > es_shards_max,
        maxVal: es_shards_max,
        id: 'shards',
        name: this.$t('分片数'),
      },
      {
        isExceed: es_number_of_replicas > number_of_replicas_max,
        maxVal: number_of_replicas_max,
        id: 'replicas',
        name: this.$t('副本数'),
      },
    ];
    const compareArr = compareMap.reduce((pre, cur) => {
      cur.isExceed && pre.push(cur);
      return pre;
    }, []);
    if (compareArr.length) {
      this.$bkMessage({
        // 当前设置的分片数超过/低于应用最大值/最小值xx-xx，请调整后再切换集群
        message: this.$t('当前设置的{name}超过最大值{max}, 请调整后再切换集群', {
          name: compareArr[0].name,
          max: compareArr[0].maxVal,
        }),
        theme: 'error',
      });
      return false;
    }
    return true;
  }

  /**
   * @desc: 修改集群历史二次确认弹窗
   * @returns { Boolean } 是否确认
   */
  handleCheckCluster() {
    return new Promise(resolve => {
      this.$bkInfo({
        title: `${this.$t('修改集群历史数据会全部丢失，确认要更换么')}？`,
        width: 600,
        confirmFn: () => resolve(true),
        cancelFn: () => resolve(false),
      });
    });
  }
  render() {
    const statusSlot = {
      default: props => [
        <span
          key={`status_${props.row.health}-${props.$index}`}
          class='status-wrap'
        >
          <span class={['status-icon', `status-${props.row.health}`]} />
          <span class='status-name'>{this.healthMaps[props.row.health]}</span>
        </span>,
      ],
    };
    const sizeSlot = {
      default: props => [
        <span key={`size_${props.$index}_${props.row.store_size}`}>{byteConvert(props.row.store_size)}</span>,
      ],
    };
    const analysisSlot = {
      default: props => <span>{props.row.analysis_field ? this.$t('是') : this.$t('否')}</span>,
    };
    const timeSlot = {
      default: props => <span>{props.row.time_field ? this.$t('是') : this.$t('否')}</span>,
    };
    const chFieldNameSlot = {
      default: props => <span>{props.row.ch_field_name || '--'}</span>,
    };
    return (
      <div class='conf-content trace-state-wrap'>
        <PanelItem title={this.$t('存储信息')}>
          {this.dataLoading ? (
            <StorageInfoSkeleton rows={3} />
          ) : (
            <div class='form-content'>
              <div class='item-row'>
                <EditableFormItem
                  formType='input'
                  label={this.$t('存储索引名')}
                  showEditable={false}
                  value={this.appInfo.es_storage_index_name}
                />
                <EditableFormItem
                  authority={this.authority.MANAGE_AUTH}
                  authorityName={authorityMap.MANAGE_AUTH}
                  formType='select'
                  label={this.$t('存储集群')}
                  selectList={this.clusterOptions}
                  updateValue={val => this.handleUpdateValue(val, 'es_storage_cluster')}
                  value={this.storageInfo?.es_storage_cluster}
                />
              </div>
              <div class='item-row'>
                <EditableFormItem
                  authority={this.authority.MANAGE_AUTH}
                  authorityName={authorityMap.MANAGE_AUTH}
                  formType='expired'
                  label={this.$t('过期时间')}
                  maxExpired={this.retentionDaysMax}
                  tooltips={this.$t('过期时间')}
                  updateValue={val => this.handleUpdateValue(val, 'es_retention')}
                  value={this.storageInfo?.es_retention}
                />
                <EditableFormItem
                  authority={this.authority.MANAGE_AUTH}
                  authorityName={authorityMap.MANAGE_AUTH}
                  formType='input'
                  label={this.$t('副本数')}
                  tooltips={this.$t('副本数')}
                  updateValue={val => this.handleUpdateValue(val, 'es_number_of_replicas')}
                  validator={val => this.initValidator(val, 'es_number_of_replicas')}
                  value={this.storageInfo?.es_number_of_replicas}
                />
              </div>
              <div class='item-row'>
                <EditableFormItem
                  authority={this.authority.MANAGE_AUTH}
                  authorityName={authorityMap.MANAGE_AUTH}
                  formType='input'
                  label={this.$t('分片数')}
                  tooltips={this.$t('分片数')}
                  updateValue={val => this.handleUpdateValue(val, 'es_shards')}
                  validator={val => this.initValidator(val, 'es_shards')}
                  value={this.storageInfo?.es_shards}
                />
                <EditableFormItem
                  authority={this.authority.MANAGE_AUTH}
                  authorityName={authorityMap.MANAGE_AUTH}
                  formType='input'
                  label={this.$t('索引切分大小')}
                  tooltips={this.$t('索引切分大小')}
                  unit='G'
                  updateValue={val => this.handleUpdateValue(val, 'es_slice_size')}
                  validator={val => this.initValidator(val, 'es_slice_size')}
                  value={this.storageInfo?.es_slice_size}
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
                formatter={row => <TextOverflowCopy val={row.index} />}
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
                label={this.$t('文档数量')}
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
        <PanelItem title={this.$t('字段信息')}>
          {this.fieldLoading ? (
            <TableSkeleton />
          ) : (
            <bk-table
              // v-bkloading={{ isLoading: this.fieldLoading }}
              data={this.fieldList}
              outer-border={false}
            >
              <bk-table-column
                label={this.$t('字段名')}
                prop={'field_name'}
              />
              <bk-table-column
                label={this.$t('别名')}
                scopedSlots={chFieldNameSlot}
              />
              <bk-table-column
                width={180}
                filter-method={this.fieldFilterMethod}
                filter-multiple={false}
                filters={this.fieldFilterList}
                label={this.$t('数据类型')}
                prop={'field_type'}
              />
              <bk-table-column
                width={100}
                filter-method={this.whetherFilterMethod}
                filters={this.whetherFilters}
                label={this.$t('分词')}
                prop={'analysis_field'}
                scopedSlots={analysisSlot}
              />
              <bk-table-column
                width={100}
                filter-method={this.whetherFilterMethod}
                filters={this.whetherFilters}
                label={this.$t('时间')}
                prop={'time_field'}
                scopedSlots={timeSlot}
              />
            </bk-table>
          )}
        </PanelItem>
      </div>
    );
  }
}
