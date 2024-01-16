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

import { Component, Emit, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import {
  createDataPipeline,
  getClusterInfo,
  getEtlConfig,
  getTransferList,
  updateDataPipeline
} from '../../../monitor-api/modules/commons';
import SpaceSelect from '../../components/space-select/space-select';

import CustomSelect from './custom-select';

import './data-pipeline-config.scss';

interface IData {
  name: string;
  spaces: string[];
  etl_configs: string[];
  kafka_cluster_id: string;
  transfer_cluster_id: string;
  is_default: boolean;
  influxdb_storage_cluster_id: string;
  kafka_storage_cluster_id: string;
  description: string;
  spacesIds?: string[];
  etl_config?: { etl_config: string }[];
  isDefault?: boolean;
}

enum EType {
  kafka = 'kafka',
  influxdb = 'influxdb',
  es = 'elasticsearch'
}
interface IOption {
  id: string;
  name: string;
}
interface IPiplineListItem {
  isDefalut: boolean;
  name: string;
  etl_config: { etl_config: string; is_default: boolean }[];
  spaces: { space_id: string; is_default: boolean }[];
}
interface IProps {
  show?: boolean;
  data?: IData;
  piplineList?: IPiplineListItem[];
  onShowChange?: (v: boolean) => void;
  onSuccess?: () => void;
  onEdit?: (v: string) => void;
}

@Component
export default class DataPipelineConfig extends tsc<IProps> {
  @Prop({ default: false, type: Boolean }) show: boolean;
  /* 当前id */
  @Prop({ default: () => null, type: Object }) data: IData;
  /* 链路列表 */
  @Prop({ default: () => [], type: Array }) piplineList: IPiplineListItem[];

  /* 表单数据 */
  formData: IData = {
    name: '',
    spaces: [],
    etl_configs: [],
    kafka_cluster_id: '',
    transfer_cluster_id: '',
    is_default: false,
    influxdb_storage_cluster_id: '',
    kafka_storage_cluster_id: '',
    description: ''
  };
  /* 校验信息 */
  errMsg = {
    name: '',
    spaces: '',
    etl_configs: '',
    kafka_cluster_id: '',
    transfer_cluster_id: '',
    is_default: '',
    influxdb_storage_cluster_id: '',
    kafka_storage_cluster_id: '',
    description: ''
  };
  /* checkbox */
  influxdbStorageEnable = true;
  kafkaStorageEnable = true;
  loading = false;

  /* 数据类型可选项 */
  etlConfigs: IOption[] = [];
  /* kafka可选项 */
  kafkaOptions: IOption[] = [];
  /* transfer 可选项 */
  transferOptions: IOption[] = [];
  /* 投递到influxdb可选项 */
  influxdbOptions: IOption[] = [];
  /* 是否为编辑状态 */
  isEdit = false;
  /* 是否含默认链路 */
  hasDefalut = false;
  hasDefalutName = '';

  /* loading */
  getEtlConfigLoading = false;
  getTransferListLoading = false;

  getKafkaLoading = false;
  getInfluxdLoading = false;

  @Watch('show')
  async handleWatchShow(value: boolean) {
    if (value) {
      this.isEdit = !!this.data;
      this.loading = true;
      this.hasDefalut = false;
      this.hasDefalutName = '';
      /* 数据类型可选项 */
      this.getEtlConfigLoading = true;
      getEtlConfig()
        .then(etlConfigData => {
          this.etlConfigs = etlConfigData.map(item => ({ id: item, name: item }));
        })
        .finally(() => {
          this.getEtlConfigLoading = false;
        });
      /* 获取可选项 */
      this.getKafkaLoading = true;
      this.getInfluxdLoading = true;
      const kafkaOptions = [];
      const influxdbOptions = [];
      getClusterInfo({ cluster_type: EType.kafka })
        .then(clusterData => {
          kafkaOptions.push(...clusterData.map(item => ({ id: item.cluster_id, name: item.cluster_name })));
          this.kafkaOptions = kafkaOptions;
        })
        .finally(() => {
          this.getKafkaLoading = false;
        });
      getClusterInfo({ cluster_type: EType.influxdb })
        .then(clusterData => {
          influxdbOptions.push(...clusterData.map(item => ({ id: item.cluster_id, name: item.cluster_name })));
          this.influxdbOptions = influxdbOptions;
        })
        .finally(() => {
          this.getInfluxdLoading = false;
        });
      /* transfer 可选项 */
      this.getTransferListLoading = true;
      getTransferList()
        .then(transferOptions => {
          this.transferOptions = transferOptions.map(item => ({ id: item, name: item }));
        })
        .finally(() => {
          this.getTransferListLoading = false;
        });
      /* 编辑数据 */
      if (this.isEdit) {
        this.formData.name = this.data.name;
        this.formData.spaces = this.data.spaces.map((item: any) => item.space_id);
        this.formData.etl_configs = this.data.etl_config.map(item => item.etl_config);
        this.formData.kafka_cluster_id = this.data.kafka_cluster_id;
        this.formData.transfer_cluster_id = this.data.transfer_cluster_id;
        this.formData.influxdb_storage_cluster_id = this.data.influxdb_storage_cluster_id || '';
        this.formData.kafka_storage_cluster_id = this.data.kafka_storage_cluster_id || '';
        this.formData.description = this.data.description;
        this.formData.is_default = !!this.data.isDefault;
        this.influxdbStorageEnable = !!this.formData.influxdb_storage_cluster_id;
        this.kafkaStorageEnable = !!this.formData.kafka_storage_cluster_id;
      } else {
        this.formData = {
          name: '',
          spaces: [],
          etl_configs: [],
          kafka_cluster_id: '',
          transfer_cluster_id: '',
          is_default: false,
          influxdb_storage_cluster_id: '',
          kafka_storage_cluster_id: '',
          description: ''
        };
      }
      this.clearErr();
      this.loading = false;
    }
  }

  @Emit('showChange')
  emitIsShow(v: boolean) {
    return v;
  }

  /* 校验 */
  validator() {
    if (!this.formData.name) {
      this.errMsg.name = window.i18n.tc('必填项');
      return false;
    }
    if (!this.formData.spaces.length) {
      this.errMsg.spaces = window.i18n.tc('必填项');
      return false;
    }
    if (!this.formData.etl_configs.length) {
      this.errMsg.etl_configs = window.i18n.tc('必填项');
      return false;
    }
    if (!this.formData.kafka_cluster_id) {
      this.errMsg.kafka_cluster_id = window.i18n.tc('必填项');
      return false;
    }
    if (!this.formData.transfer_cluster_id) {
      this.errMsg.transfer_cluster_id = window.i18n.tc('必填项');
      return false;
    }
    return true;
  }

  /**
   *
   * @param isAll 是否清空所有错误信息
   * @description 清空错误信息
   */
  clearErr(isAll = false) {
    if (isAll) {
      this.hasDefalut = false;
      this.hasDefalutName = '';
    }
    Object.keys(this.errMsg).forEach(key => {
      this.errMsg[key] = '';
    });
  }
  /* 提交数据 */
  async handleSubmit() {
    this.handlePack();
    if (this.validator()) {
      const spaces = [];
      this.$store.getters.bizList.forEach(item => {
        if (this.formData.spaces.includes(item.id)) {
          spaces.push({
            space_type: item.space_type_id,
            space_id: item.space_id
          });
        }
      });
      let success = true;
      const params = {
        ...this.formData,
        spaces,
        username: window.user_name || window.username,
        chinese_name: this.formData.name,
        description: this.formData.description || undefined,
        influxdb_storage_cluster_id: this.influxdbStorageEnable ? this.formData.influxdb_storage_cluster_id : undefined,
        kafka_storage_cluster_id: this.kafkaStorageEnable ? this.formData.kafka_storage_cluster_id : undefined
      };
      this.loading = true;
      if (this.isEdit) {
        success = await updateDataPipeline({
          ...params,
          data_pipeline_name: params.name,
          chinese_name: undefined,
          username: undefined
        }).catch(() => false);
      } else {
        success = await createDataPipeline(params).catch(() => false);
      }
      this.loading = false;
      if (success !== false) {
        this.$bkMessage({
          theme: 'success',
          message: this.isEdit ? this.$t('修改成功') : this.$t('创建成功')
        });
        this.$emit('success');
        this.emitIsShow(false);
      }
    }
  }
  /* 使用范围 */
  handleSpaceChange(v) {
    this.formData.spaces = v;
    this.handlePack();
    this.clearErr();
  }
  /* 数据类型 */
  handleEtlConfigChange(v) {
    this.formData.etl_configs = v;
    this.clearErr(true);
  }

  /* 收起数据类型的弹层 */
  handlePack() {
    if (!this.formData.is_default) return;
    this.hasDefalutName = '';
    this.hasDefalut = false;
    const etlConfigSpaceHasDefalut = (etlConfig, spaces) => {
      const etlConfigs = etlConfig.filter(item => item.is_default).map(item => item.etl_config);
      const spaceids = spaces.filter(item => item.is_default).map(item => String(item.space_id));
      return (
        this.formData.etl_configs.some(id => etlConfigs.includes(id)) ||
        this.formData.spaces.some(id => spaceids.includes(String(id)))
      );
    };
    this.piplineList.forEach(item => {
      if (item.isDefalut && !this.hasDefalut) {
        if (this.isEdit) {
          if (this.formData.name !== item.name) {
            if (etlConfigSpaceHasDefalut(item.etl_config, item.spaces)) {
              this.hasDefalutName = item.name;
              this.hasDefalut = true;
            }
          }
        } else {
          if (this.formData.name === item.name || etlConfigSpaceHasDefalut(item.etl_config, item.spaces)) {
            this.hasDefalutName = item.name;
            this.hasDefalut = true;
          }
        }
      }
    });
  }
  /* 跳转到指定编辑 */
  handleToEdit() {
    this.emitIsShow(false);
    this.$emit('edit', this.hasDefalutName);
  }
  handleIsDefaultChange(v: boolean) {
    if (v) {
      this.handlePack();
    } else {
      this.clearErr(true);
    }
  }

  render() {
    function formItem(title, content, errMsg) {
      return (
        <div class='form-item'>
          <div class='form-item-title'>{title}</div>
          <div class='form-item-content'>{content}</div>
          {!!errMsg && (
            <div class='form-item-errmsg'>
              <span>{errMsg}</span>
            </div>
          )}
        </div>
      );
    }
    return (
      <bk-sideslider
        ext-cls='data-pipeline-config-sides'
        isShow={this.show}
        quick-close={true}
        transfer={true}
        width={640}
        {...{ on: { 'update:isShow': this.emitIsShow } }}
      >
        <div slot='header'>
          <span>{!this.isEdit ? this.$t('新增链路') : `${this.$t('编辑')} ${this.formData.name || '--'}`}</span>
        </div>
        <div
          slot='content'
          class='content-wrap'
          v-bkloading={{ isLoading: this.loading }}
        >
          <div class='content-item'>
            <div class='content-item-title'>{this.$t('链路名称')}</div>
            <div class='content-item-form'>
              {formItem(
                <span class='require'>{this.$t('链路名称')}</span>,
                <bk-input
                  v-model={this.formData.name}
                  disabled={this.isEdit}
                  onChange={() => this.clearErr(true)}
                ></bk-input>,
                this.errMsg.name
              )}
              <div class='horizontal'>
                {formItem(
                  <span class='require'>{this.$t('使用范围')}</span>,
                  <div class='width270'>
                    <SpaceSelect
                      value={this.formData.spaces}
                      spaceList={this.$store.getters.bizList}
                      needAuthorityOption={false}
                      needAlarmOption={false}
                      onChange={v => this.handleSpaceChange(v)}
                    ></SpaceSelect>
                  </div>,
                  this.errMsg.spaces
                )}
                {formItem(
                  <span class='require'>{this.$t('数据类型')}</span>,
                  <div
                    class='width270'
                    v-bkloading={{ isLoading: this.getEtlConfigLoading }}
                  >
                    <CustomSelect
                      key={`${this.etlConfigs.length}__select`}
                      list={this.etlConfigs}
                      value={this.formData.etl_configs}
                      onChange={v => this.handleEtlConfigChange(v)}
                      onPack={this.handlePack}
                    ></CustomSelect>
                  </div>,
                  this.errMsg.etl_configs
                )}
              </div>
              {formItem(
                <span class='require'>{this.$t('Kafka链路')}</span>,
                <bk-select
                  v-model={this.formData.kafka_cluster_id}
                  v-bkloading={{ isLoading: this.getKafkaLoading }}
                  onChange={() => this.clearErr()}
                >
                  {this.kafkaOptions.map(item => (
                    <bk-option
                      key={item.id}
                      id={item.id}
                      name={item.name}
                    ></bk-option>
                  ))}
                </bk-select>,
                this.errMsg.kafka_cluster_id
              )}
              {formItem(
                <span class='require'>{this.$t('Transfer链路')}</span>,
                <bk-select
                  v-model={this.formData.transfer_cluster_id}
                  v-bkloading={{ isLoading: this.getTransferListLoading }}
                  onChange={() => this.clearErr()}
                >
                  {this.transferOptions.map(item => (
                    <bk-option
                      key={item.id}
                      id={item.id}
                      name={item.name}
                    ></bk-option>
                  ))}
                </bk-select>,
                this.errMsg.transfer_cluster_id
              )}
            </div>
            <div class='is-defalut'>
              <bk-checkbox
                v-model={this.formData.is_default}
                onChange={this.handleIsDefaultChange}
              >
                {this.$t('是否为默认链路')}
              </bk-checkbox>
              {this.hasDefalut && (
                <div class='default-tip'>
                  <span class='icon-monitor icon-hint'></span>
                  <i18n path='已有默认链路{0}，如需更改需先去该链路下将其取消'>
                    <span>{this.hasDefalutName}</span>
                  </i18n>
                  <span
                    class='link'
                    onClick={this.handleToEdit}
                  >
                    {this.$t('编辑')} {this.hasDefalutName}
                  </span>
                </div>
              )}
            </div>
          </div>
          <div class='line-between'></div>
          <div class='content-item'>
            <div class='content-item-title'>{this.$t('数据投递')}</div>
            <div class='content-item-form'>
              {formItem(
                <span class='check-title'>
                  <bk-checkbox v-model={this.influxdbStorageEnable}>{this.$t('投递到Influxdb')}</bk-checkbox>
                </span>,
                <bk-select
                  v-model={this.formData.influxdb_storage_cluster_id}
                  disabled={!this.influxdbStorageEnable}
                  v-bkloading={{ isLoading: this.getInfluxdLoading }}
                >
                  {this.influxdbOptions.map(item => (
                    <bk-option
                      key={item.id}
                      id={item.id}
                      name={item.name}
                    ></bk-option>
                  ))}
                </bk-select>,
                this.errMsg.influxdb_storage_cluster_id
              )}
              {formItem(
                <span class='check-title'>
                  <bk-checkbox v-model={this.kafkaStorageEnable}>{this.$t('投递到Kafka')}</bk-checkbox>
                </span>,
                <bk-select
                  v-model={this.formData.kafka_storage_cluster_id}
                  disabled={!this.kafkaStorageEnable}
                  v-bkloading={{ isLoading: this.getKafkaLoading }}
                >
                  {this.kafkaOptions.map(item => (
                    <bk-option
                      key={item.id}
                      id={item.id}
                      name={item.name}
                    ></bk-option>
                  ))}
                </bk-select>,
                this.errMsg.kafka_storage_cluster_id
              )}
              {formItem(
                <span>{this.$t('备注说明')}</span>,
                <bk-input
                  v-model={this.formData.description}
                  type={'textarea'}
                  rows={3}
                  maxlength={100}
                ></bk-input>,
                this.errMsg.description
              )}
            </div>
          </div>
        </div>
        <div
          slot='footer'
          class='footer-content'
        >
          <bk-button
            theme='primary'
            class='submit'
            onClick={this.handleSubmit}
          >
            {this.$t('提交')}
          </bk-button>
          <bk-button
            class='cancel'
            onClick={() => this.emitIsShow(false)}
          >
            {this.$t('取消')}
          </bk-button>
        </div>
      </bk-sideslider>
    );
  }
}
