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

import { Component, Emit, Inject, Prop, PropSync, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { indicesInfo, metaConfigInfo, setup, storageFieldInfo } from '../../../../monitor-api/modules/apm_meta';
import { byteConvert } from '../../../../monitor-common/utils/utils';
import EditableFormItem from '../../../components/editable-form-item/editable-form-item';
import PanelItem from '../../../components/panel-item/panel-item';
import * as authorityMap from '../../home/authority-map';
import { ISetupData } from '../app-add/app-add';

import { ClusterOption, IAppInfo, IClusterItem, IFieldFilterItem, IFieldItem, IndicesItem } from './type';

interface IStorageStateProps {
  appInfo: IAppInfo;
  clusterList: IClusterItem[];
}

@Component
export default class StorageState extends tsc<IStorageStateProps> {
  @PropSync('data', { type: Object, required: true }) appInfo: IAppInfo;
  @Prop({ type: Array, required: true }) clusterList: any[];

  @Inject('authority') authority;

  indicesLoading = false;
  fieldLoading = false;
  indicesList: IndicesItem[] = []; // 物理索引
  fieldList: IFieldItem[] = []; // 字段信息
  fieldFilterList: IFieldFilterItem[] = []; // 字段信息过滤列表
  whetherFilters: IFieldFilterItem[] = [
    { text: window.i18n.tc('是'), value: 'true' },
    { text: window.i18n.tc('否'), value: 'false' }
  ];
  /** 集群信息 索引名 过期时间 副本数 */
  setupData: ISetupData = {
    index_prefix_name: '',
    es_retention_days: {
      default: 0,
      default_es_max: 0,
      private_es_max: 0
    },
    es_number_of_replicas: {
      default: 0,
      default_es_max: 0,
      private_es_max: 0
    }
  };
  clusterOptions: ClusterOption[] = [];
  healthMaps = {
    green: this.$t('健康'),
    yellow: this.$t('部分异常'),
    red: this.$t('异常')
  };

  /** 选中的集群 */
  get currentCluster() {
    // eslint-disable-next-line max-len
    return this.clusterList.find(
      item => item.storage_cluster_id === this.appInfo.application_datasource_config.es_storage_cluster
    );
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

  created() {
    this.getMetaConfigInfo();
    this.getindicesList();
    this.getFieldList();
  }

  @Watch('clusterList', { immediate: true })
  handleClusterListChange(list) {
    this.clusterOptions = list.map(item => ({
      id: item.storage_cluster_id,
      name: item.storage_cluster_name
    }));
  }

  /**
   * @desc 获取过期时间最大值
   */
  async getMetaConfigInfo() {
    const data = await metaConfigInfo().catch(() => null);
    this.setupData = data.setup;
  }
  /**
   * @desc 获取物理索引
   */
  async getindicesList() {
    this.indicesLoading = true;
    this.indicesList = await indicesInfo(this.appInfo.application_id).catch(() => []);
    this.indicesLoading = false;
  }
  /**
   * @desc 获取字段信息
   */
  async getFieldList() {
    this.fieldLoading = true;
    this.fieldList = await storageFieldInfo(this.appInfo.application_id).catch(() => []);
    this.fieldFilterList = this.getFieldFilterList(this.fieldList);
    this.fieldLoading = false;
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
          value: item.field_type
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
      const datasourceConfig = Object.assign(this.appInfo.application_datasource_config, { [field]: Number(value) });

      const params = {
        application_id: this.appInfo.application_id,
        datasource_option: datasourceConfig
      };
      await setup(params);
      await this.handleBaseInfoChange();
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
    const { es_retention, es_number_of_replicas, es_shards } = this.appInfo.application_datasource_config;
    const { es_shards_max, number_of_replicas_max, retention_days_max } = selectItem.setup_config;
    const compareMap = [
      {
        isExceed: es_retention > retention_days_max,
        maxVal: retention_days_max,
        id: 'retention',
        name: this.$t('过期天数')
      },
      {
        isExceed: es_shards > es_shards_max,
        maxVal: es_shards_max,
        id: 'shards',
        name: this.$t('分片数')
      },
      {
        isExceed: es_number_of_replicas > number_of_replicas_max,
        maxVal: number_of_replicas_max,
        id: 'replicas',
        name: this.$t('副本数')
      }
    ];
    const compareArr = compareMap.reduce((pre, cur) => (cur.isExceed && pre.push(cur), pre), []);
    if (compareArr.length) {
      this.$bkMessage({
        // 当前设置的分片数超过/低于应用最大值/最小值xx-xx，请调整后再切换集群
        message: this.$t('当前设置的{name}超过最大值{max}, 请调整后再切换集群', {
          name: compareArr[0].name,
          max: compareArr[0].maxVal
        }),
        theme: 'error'
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
        cancelFn: () => resolve(false)
      });
    });
  }

  render() {
    const statusSlot = {
      default: props => [
        <span class='status-wrap'>
          <span class={['status-icon', `status-${props.row.health}`]}></span>
          <span class='status-name'>{this.healthMaps[props.row.health]}</span>
        </span>
      ]
    };
    const sizeSlot = {
      default: props => [<span>{byteConvert(props.row.store_size)}</span>]
    };
    const analysisSlot = {
      default: props => <span>{props.row.analysis_field ? this.$t('是') : this.$t('否')}</span>
    };
    const timeSlot = {
      default: props => <span>{props.row.time_field ? this.$t('是') : this.$t('否')}</span>
    };
    const chFieldNameSlot = {
      default: props => <span>{props.row.ch_field_name || '--'}</span>
    };

    return (
      <div class='conf-content storage-state-wrap'>
        <PanelItem title={this.$t('存储信息')}>
          <div class='item-content'>
            <div class='form-content'>
              <div class='item-row'>
                <EditableFormItem
                  label={this.$t('存储索引名')}
                  value={this.appInfo.es_storage_index_name}
                  formType='input'
                  showEditable={false}
                />
                <EditableFormItem
                  label={this.$t('存储集群')}
                  value={this.appInfo.application_datasource_config?.es_storage_cluster}
                  selectList={this.clusterOptions}
                  formType='select'
                  authority={this.authority.MANAGE_AUTH}
                  authorityName={authorityMap.MANAGE_AUTH}
                  // eslint-disable-next-line @typescript-eslint/no-misused-promises
                  updateValue={val => this.handleUpdateValue(val, 'es_storage_cluster')}
                />
              </div>
              <div class='item-row'>
                <EditableFormItem
                  label={this.$t('过期时间')}
                  value={this.appInfo.application_datasource_config?.es_retention}
                  formType='expired'
                  tooltips={this.$t('过期时间')}
                  maxExpired={this.retentionDaysMax}
                  authority={this.authority.MANAGE_AUTH}
                  authorityName={authorityMap.MANAGE_AUTH}
                  // eslint-disable-next-line @typescript-eslint/no-misused-promises
                  updateValue={val => this.handleUpdateValue(val, 'es_retention')}
                />
                <EditableFormItem
                  label={this.$t('副本数')}
                  value={this.appInfo.application_datasource_config?.es_number_of_replicas}
                  formType='input'
                  tooltips={this.$t('副本数')}
                  authority={this.authority.MANAGE_AUTH}
                  authorityName={authorityMap.MANAGE_AUTH}
                  validator={val => this.initValidator(val, 'es_number_of_replicas')}
                  // eslint-disable-next-line @typescript-eslint/no-misused-promises
                  updateValue={val => this.handleUpdateValue(val, 'es_number_of_replicas')}
                />
              </div>
              <div class='item-row'>
                <EditableFormItem
                  label={this.$t('分片数')}
                  value={this.appInfo.application_datasource_config?.es_shards}
                  formType='input'
                  tooltips={this.$t('分片数')}
                  authority={this.authority.MANAGE_AUTH}
                  authorityName={authorityMap.MANAGE_AUTH}
                  validator={val => this.initValidator(val, 'es_shards')}
                  // eslint-disable-next-line @typescript-eslint/no-misused-promises
                  updateValue={val => this.handleUpdateValue(val, 'es_shards')}
                />
                <EditableFormItem
                  label={this.$t('索引切分大小')}
                  value={this.appInfo.application_datasource_config?.es_slice_size}
                  formType='input'
                  unit='G'
                  tooltips={this.$t('索引切分大小')}
                  authority={this.authority.MANAGE_AUTH}
                  authorityName={authorityMap.MANAGE_AUTH}
                  validator={val => this.initValidator(val, 'es_slice_size')}
                  // eslint-disable-next-line @typescript-eslint/no-misused-promises
                  updateValue={val => this.handleUpdateValue(val, 'es_slice_size')}
                />
              </div>
            </div>
          </div>
        </PanelItem>
        <PanelItem title={this.$t('物理索引')}>
          <bk-table
            outer-border={false}
            data={this.indicesList}
            v-bkloading={{ isLoading: this.indicesLoading }}
          >
            <bk-table-column
              label={this.$t('索引')}
              width={280}
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
        </PanelItem>
        <PanelItem title={this.$t('字段信息')}>
          <bk-table
            outer-border={false}
            data={this.fieldList}
            v-bkloading={{ isLoading: this.fieldLoading }}
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
              label={this.$t('数据类型')}
              width={180}
              prop={'field_type'}
              filter-multiple={false}
              filters={this.fieldFilterList}
              filter-method={this.fieldFilterMethod}
            />
            <bk-table-column
              label={this.$t('分词')}
              width={100}
              prop={'analysis_field'}
              scopedSlots={analysisSlot}
              filters={this.whetherFilters}
              filter-method={this.whetherFilterMethod}
            />
            <bk-table-column
              label={this.$t('时间')}
              width={100}
              prop={'time_field'}
              scopedSlots={timeSlot}
              filters={this.whetherFilters}
              filter-method={this.whetherFilterMethod}
            />
          </bk-table>
        </PanelItem>
      </div>
    );
  }
}
