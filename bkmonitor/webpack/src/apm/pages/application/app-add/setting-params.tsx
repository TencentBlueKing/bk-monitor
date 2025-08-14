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
import { Component, Emit, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { listEsClusterGroups } from 'monitor-api/modules/apm_meta';

import ExpiredSelect from '../../../components/expired-select/expired-select';
import ClusterTable from './cluster-table';

import type { IPluginItem, ISetupData } from './app-add';

import './setting-params.scss';

export interface IEsClusterInfo {
  es_number_of_replicas: number;
  es_retention: number;
  es_shards: number;
  es_slice_size?: '' | number;
  es_storage_cluster: number;
}
interface IEvents {
  onPreStep: void;
  onSubmit: IEsClusterInfo;
}

interface IProps {
  appInfoData: ICreateAppFormData;
  currentPlugin: IPluginItem;
  loading: boolean;
  setupData: ISetupData;
}
@Component
export default class SettingParams extends tsc<IProps, IEvents> {
  @Prop({ type: Boolean }) loading: false;
  @Prop({ type: Object }) setupData: ISetupData;
  @Prop({ type: Object }) appInfoData: ICreateAppFormData;
  @Prop({ type: Object }) currentPlugin: IPluginItem;

  /** 表单参数 */
  formData: IEsClusterInfo = {
    es_storage_cluster: 0,
    es_retention: 1,
    es_number_of_replicas: 0,
    es_shards: 1,
    es_slice_size: '',
  };

  /** 集群的详细数据 */
  esClusterList = [];
  /** 表格初始右侧margin */
  marginRight = 0;
  /** 是否动画拉伸说明 */
  sliderAnimation = false;
  /** 共享集群 */
  sharedList = [];
  /** 独享集群 */
  exclusiveList = [];
  /** tableLoading */
  tableLoading = false;

  /** 选中的集群 */
  get currentCluster() {
    return this.esClusterList.find(item => item.storage_cluster_id === this.formData.es_storage_cluster);
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
  /** table与说明的间隔 */
  get marginRightWidth() {
    return `${this.marginRight + 10}px`;
  }
  @Emit('preStep')
  handlePreStep() {}

  @Emit('submit')
  handleSubmit(): IEsClusterInfo {
    const { es_slice_size: esSliceSize, ...rest } = this.formData;
    if (esSliceSize) {
      return { ...rest, es_slice_size: Number(esSliceSize) };
    }
    return rest;
  }

  created() {
    this.getEsCluster();
  }

  /** 处理过期时间、副本数的默认值 */
  handleDefaultData() {
    this.formData.es_retention = this.currentCluster.setup_config.retention_days_default;
    this.formData.es_number_of_replicas = this.currentCluster.setup_config.number_of_replicas_default;
    this.formData.es_shards = this.currentCluster.setup_config.es_shards_default;
  }

  /** 获取es集群列表 */
  async getEsCluster() {
    try {
      this.tableLoading = true;
      const list = await listEsClusterGroups();
      this.esClusterList = list;
      /** 默认选中私有集群 */
      list.forEach(item => {
        item.is_platform ? this.sharedList.push(item) : this.exclusiveList.push(item);
      });

      this.formData.es_storage_cluster =
        this.exclusiveList[0]?.storage_cluster_id || this.sharedList[0]?.storage_cluster_id || 0;
      this.handleDefaultData();
    } catch (error) {
      console.warn(error);
    } finally {
      this.tableLoading = false;
    }
  }

  /**
   * 切换集群
   */
  handleClusterChange() {
    this.handleDefaultData();
  }

  render() {
    return (
      <div class='setting-params-wrap'>
        <bk-form
          class='setting-form'
          label-width={112}
        >
          {/* <bk-form-item label={this.$t('数据链路')}>
            <div class="form-content-text">广州链路2</div>
          </bk-form-item> */}
          <div class='form-title'>{this.$t('集群选择')}</div>
          <bk-form-item
            class='cluster-select-item'
            required
          >
            <ClusterTable
              style={{ marginRight: this.marginRightWidth }}
              class={{ 'is-animation': this.sliderAnimation }}
              v-model={this.formData.es_storage_cluster}
              v-bkloading={{ isLoading: this.tableLoading }}
              tableList={this.sharedList}
              onChange={this.handleClusterChange}
            />
            <ClusterTable
              style={{ margin: `20px ${this.marginRightWidth} 0 0` }}
              class={{ 'is-animation': this.sliderAnimation }}
              v-model={this.formData.es_storage_cluster}
              v-bkloading={{ isLoading: this.tableLoading }}
              tableList={this.exclusiveList}
              tableType='exclusive'
              onChange={this.handleClusterChange}
            />
          </bk-form-item>
          <div class='form-title'>{this.$t('存储信息')}</div>
          <bk-form-item label={this.$t('存储索引名')}>
            <div class='index-name-item'>
              <span class='index-name-label'>{this.setupData.index_prefix_name}</span>
              <span class='index-name-value'>{this.appInfoData?.name || '--'}</span>
            </div>
          </bk-form-item>
          <bk-form-item label={this.$t('过期时间')}>
            <ExpiredSelect
              v-model={this.formData.es_retention}
              max={this.retentionDaysMax}
            />
          </bk-form-item>
          <bk-form-item label={this.$t('副本数')}>
            <bk-input
              class='copies-num-item'
              v-model={this.formData.es_number_of_replicas}
              max={this.numberOfReplicasMax}
              min={0}
              type='number'
            />
          </bk-form-item>
          <bk-form-item label={this.$t('分片数')}>
            <bk-input
              class='copies-num-item'
              v-model={this.formData.es_shards}
              max={this.esShardsMax}
              min={1}
              type='number'
            />
          </bk-form-item>
          <bk-form-item label={this.$t('索引切分大小')}>
            <bk-input
              class='copies-num-item'
              v-model={this.formData.es_slice_size}
              min={1}
              type='number'
            >
              <div
                class='unit'
                slot='append'
              >
                G
              </div>
            </bk-input>
          </bk-form-item>
          <bk-form-item>
            <div class='submit-btn-group'>
              <bk-button
                class='btn'
                onClick={this.handlePreStep}
              >
                {this.$t('上一步')}
              </bk-button>
              <bk-button
                class='btn'
                loading={this.loading}
                theme='primary'
                onClick={this.handleSubmit}
              >
                {this.$t('提交')}
              </bk-button>
            </div>
          </bk-form-item>
        </bk-form>
      </div>
    );
  }
}
