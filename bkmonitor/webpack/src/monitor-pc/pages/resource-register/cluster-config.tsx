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
import { Component, Emit, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { checkClusterHealth, registerCluster, updateRegisteredCluster } from 'monitor-api/modules/commons';
import { random } from 'monitor-common/utils';

import { SPACE_TYPE_MAP } from '../../common/constant';
import UserSelector from '../../components/user-selector/user-selector';
import ClusterMoreConfig from './cluster-config/cluster-more-config';
import FormItem from './cluster-config/components/form-item';
// import InfluxdbGroup from './cluster-config/influxdb-group';
import MoreConfig from './cluster-config/components/more-config';
import EsBasicInfo from './cluster-config/es-basic-info';
import InfluxdbBasicInfo from './cluster-config/influxdb-basic-info';
import KafkaBasicInfo from './cluster-config/kafka-basic-info';
import { EClusterType, EScopes, type ITableRowConfig } from './type';

import './cluster-config.scss';

// 四种资源类别的属性
interface IResourceListItem {
  id: EClusterType;
  icon: string;
  name: string;
  optionTitle: string;
  label?: Array<any>;
  disabled: boolean;
  data: object;
}

const formData = {
  // 表单数据
  clusterName: '', // 集群名称
  label: [], // 用途
  kafka: {
    domain: '', // 集群域名
    port: '', // 端口
    schema: '', // 协议
    username: '', // 用户名
    password: '', // 密码
  },
  // Transfer: {},
  influxdb: {
    domain: '', // Proxy集群域名
    port: '', // 端口
    username: '', // 用户名
    password: '', // 密码
  },
  elasticsearch: {
    registered_system: '', // 来源
    address: '', // ES地址
    port: '', // 端口
    schema: '', // 协议
    username: '', // 用户名
    password: '', // 密码
  },
  operator: '', // 负责人
  description: '', // 描述
  moreConfig: {
    // 更多配置
    kafka: {
      is_register_gse: false,
    },
    elasticsearch: {
      scope: EScopes.currentSpace,
      space: [], // 可见范围
      expires: {
        // 过期时间
        default: '',
        max: '',
      },
      replica: {
        // 副本数
        default: null,
        max: null,
      },
      cold_warm_phase_settings: {
        hot: '',
        cold: '',
      },
      hotDataTag: '', // 热数据标签
      coldDataTag: '', // 冷数据标签
      capacityAssessmentValue: null, // 容量评估
      hotAndColdDataSwitcherValue: false, // 冷热数据开关值
      logArchivingSwitcherValue: false, // 日志归档开关值
      capacityAssessmentSwitcherValue: false, // 容量评估开关值
    },
  },
};

// 连通性测试状态
enum ConnectionStatus {
  default = '',
  fail = 'fail',
  success = 'success',
}

enum OperationType {
  add = '新增',
  clone = '克隆',
  edit = '编辑',
}

const labelList = [
  { id: window.i18n.tc('标签'), label: window.i18n.tc('标签') },
  { id: window.i18n.tc('消息队列'), label: window.i18n.tc('消息队列') },
  { id: window.i18n.tc('数据投递'), label: window.i18n.tc('数据投递') },
];

@Component
export default class ClusterConfig extends tsc<object> {
  @Prop({ type: Boolean, default: false }) show: boolean; // 控制侧栏显示变量
  @Prop({ type: Object, default: () => ({}) }) rowConfig: ITableRowConfig;
  @Ref() clusterOperationForm: any;
  @Ref('kafkaBasicInfo') kafkaBasicInfoRef: KafkaBasicInfo;
  @Ref('influxdbBasicInfo') influxdbBasicInfoRef: InfluxdbBasicInfo;
  @Ref('elasticsearchBasicInfo') elasticsearchBasicInfoRef: EsBasicInfo;
  // @Ref() influxdbGroup: any;
  // @Ref() clusterMoreConfig: any;
  /* 类型列表 */
  resourceList: IResourceListItem[] = [
    {
      id: EClusterType.Kafka,
      icon: 'icon-Kafka',
      name: 'Kafka',
      optionTitle: '更多配置',
      disabled: false,
      data: {},
    },
    {
      id: EClusterType.Influxdb,
      icon: 'icon-DB1',
      name: 'Influxdb cluster',
      optionTitle: '更多配置',
      disabled: false,
      data: {},
    },
    {
      id: EClusterType.ES,
      icon: 'icon-ES',
      name: 'ES',
      optionTitle: 'ES集群管理',
      disabled: false,
      data: {},
    },
  ];
  // 当前选择的资源类别
  selectedType: EClusterType = EClusterType.Kafka;
  // 当前资源类别下进行连通性测试的状态，空字符串为初始状态（未进行连通性测试）
  connectionStatus = ConnectionStatus.default;
  // 连通性测试按钮loading
  connectTestButtonLoading = false;
  // 提交按钮loading
  submitButtonLoading = false;
  influxdbGroupShow = false;
  // 表单数据
  formData = formData;
  // 校验
  formErrMsg = {
    clusterName: '',
    label: '',
    operator: '',
  };
  /* 是否为编辑状态 */
  isEdit = false;
  influxdbGroupSidesliderTitle = OperationType.add;

  spaceTypes = [];

  userSelectorKey = random(8);

  @Emit('show-change')
  emitShowChange(val: boolean) {
    return val;
  }
  @Watch('show')
  handleShowChange(v) {
    // 打开侧栏时先进行数据初始化
    this.handleInitData();
    if (!v) return;
    const { rowData: data, operationType } = this.rowConfig;
    // 编辑的情况下，除了已选择的资源类别，其他的资源类别都被禁用
    this.isEdit = operationType === 'edit';
    if (this.isEdit) {
      const type = data.cluster_type;
      if (type === EClusterType.Kafka) {
        this.formData.kafka = {
          domain: data.domain_name || '', // 集群域名
          port: data.port || '', // 端口
          schema: data.schema || '', // 协议
          username: data.username || '', // 用户名
          password: data.password || '', // 密码
        };
      } else if (type === EClusterType.Influxdb) {
        this.formData.influxdb = {
          domain: data.domain_name || '', // Proxy集群域名
          port: data.port || '', // 端口
          username: data.username || '', // 用户名
          password: data.password || '', // 密码
        };
      } else if (type === EClusterType.ES) {
        this.formData.elasticsearch = {
          registered_system: data.registered_system || '', // 来源
          address: data.domain_name || '', // ES地址
          port: data.port || '', // 端口
          schema: data.schema || '', // 协议
          username: data.username || '', // 用户名
          password: data.password || '', // 密码
        };
      }
      this.resourceList.forEach(resource => {
        if (resource.id !== type) {
          resource.disabled = true;
        }
      });
      this.formData.clusterName = data.cluster_name; // 回填集群名称
      this.formData.label = data.label ? data.label?.split(',') : []; // 回填集群用途
      this.formData.description = data.description;
      this.formData.operator = data.creator;
      this.userSelectorKey = random(8);
      this.selectedType = type;
    }
    this.selectedType = data?.cluster_type || EClusterType.Kafka;
  }

  created() {
    const spaceTypeMap: Record<string, any> = {};
    this.$store.getters.bizList.forEach(item => {
      spaceTypeMap[item.space_type_id] = 1;
      if (item.space_type_id === 'bkci' && item.space_code) {
        spaceTypeMap.bcs = 1;
      }
    });
    this.spaceTypes = Object.keys(spaceTypeMap).map(key => ({
      id: key,
      name: SPACE_TYPE_MAP[key]?.name || this.$t('未知'),
    }));
  }

  /* 资源类别的切换 */
  handleSelectChange(item) {
    // 禁用状态下不能切换
    if (item.disabled || this.isEdit || item.id === this.selectedType) return;
    this.selectedType = item.id || EClusterType.Kafka;
    // 重置连通性测试
    this.connectionStatus = ConnectionStatus.default;
    // 清除表单校验报错
    this.clearError();
  }
  getInfoParams() {
    if (this.selectedType === EClusterType.Kafka) {
      return {
        ...this.formData.kafka,
      };
    }
    if (this.selectedType === EClusterType.Influxdb) {
      return {
        ...this.formData.influxdb,
      };
    }
    if (this.selectedType === EClusterType.ES) {
      return {
        ...this.formData.elasticsearch,
      };
    }
    return {};
  }
  /* 提交表单 */
  async handleSubmit() {
    const validate = this.validate();
    if (!validate) {
      return;
    }
    const { elasticsearch } = this.formData.moreConfig;
    const spaceParams = (space: (number | string)[], scope: EScopes) => {
      if (scope === EScopes.allSpace) {
        return [];
      }
      if (scope === EScopes.currentSpace) {
        const currentSpace = this.$store.getters.bizId;
        const currentInfo = this.$store.getters.bizList.find(item => item.id === currentSpace);
        return [
          {
            space_type: currentInfo.space_type_id,
            space_id: currentInfo.space_id,
          },
        ];
      }
      if (scope === EScopes.multiSpace) {
        const temp = [];
        this.$store.getters.bizList.forEach(item => {
          if (space.includes(item.id)) {
            temp.push({
              space_type: item.space_type_id,
              space_id: item.space_id,
            });
          }
        });
        return temp;
      }
      if (scope === EScopes.spaceType) {
        return space.map(item => ({
          space_type: item,
        }));
      }
    };
    let params = {
      cluster_name: this.formData.clusterName,
      cluster_type: this.selectedType,
      label: this.formData.label.join(','),
      operator: this.formData.operator,
      description: this.formData.description,
      default_settings: {
        kafka: this.formData.moreConfig.kafka,
        elasticsearch: {
          spaces: spaceParams(elasticsearch.space, elasticsearch.scope),
          scope: elasticsearch.scope,
          expires: elasticsearch.expires,
          replica: elasticsearch.replica,
          cold_warm_phase_settings: elasticsearch.cold_warm_phase_settings,
        },
      },
      ...this.getInfoParams(),
    };
    if (this.isEdit) {
      params = Object.assign(params, { cluster_id: this.rowConfig.rowData.cluster_id });
    }
    this.submitButtonLoading = true;
    const api = this.isEdit ? updateRegisteredCluster : registerCluster;
    const res = await api(params).catch(() => false);
    this.submitButtonLoading = false;
    if (res) {
      this.$bkMessage({
        theme: 'success',
        message: this.isEdit ? this.$t('修改成功') : this.$t('创建成功'),
      });
      this.emitShowChange(false);
    }
  }
  handleAddinfluxdbGroup() {}
  /**
   * * 从外部表格点击（克隆/编辑组/新增组）
   * @param val: 新增组则无需传值，(克隆/编辑组)的情况则传入操作的类型和对应的数据
   */
  openInfluxdbGroupSideslider() {
    // this.influxdbGroupShow = true;
    // if (!val) return;
    // this.$nextTick(() => {
    //   const { operationType } = val;
    //   operationType && (this.influxdbGroupSidesliderTitle = OperationType[operationType]);
    //   this.influxdbGroup?.dataEcho?.(val); // 数据回显
    // });
  }
  /* 表单校验 */
  validate() {
    let validate = false;
    if (!this.formData.clusterName) {
      this.formErrMsg.clusterName = window.i18n.tc('必填项');
    } else if (!this.formData.label.length) {
      this.formErrMsg.label = window.i18n.tc('必选项');
    } else if (!this.formData.operator) {
      this.formErrMsg.operator = window.i18n.tc('必选项');
    }
    validate = Object.keys(this.formErrMsg).every(key => !this.formErrMsg[key]) && this.basicValidate();
    return validate;
  }

  basicValidate() {
    let validate = false;
    if (this.selectedType === EClusterType.Kafka) {
      validate = this.kafkaBasicInfoRef.formValidate();
    } else if (this.selectedType === EClusterType.Influxdb) {
      validate = this.influxdbBasicInfoRef.formValidate();
    } else if (this.selectedType === EClusterType.ES) {
      validate = this.elasticsearchBasicInfoRef.formValidate();
    }
    return validate;
  }
  /**
   * * 清除错误提示
   * @param type: 类型(all/single)
   * @param field: type为single的情况下，需要清除的错误信息的字段
   */
  clearError() {
    Object.keys(this.formErrMsg).forEach(key => {
      this.formErrMsg[key] = '';
    });
  }
  /* 初始化数据(表单数据/错误信息/连通性状态) */
  handleInitData() {
    this.formData = JSON.parse(JSON.stringify(formData));
    Object.keys(this.formErrMsg).forEach(key => {
      this.formErrMsg[key] = '';
    });
    this.connectionStatus = ConnectionStatus.default;
  }
  /* 连通性测试 */
  async handleConnectTest() {
    // 初始化连通性测试状态
    this.connectionStatus = ConnectionStatus.default;
    // kafka集群表单校验
    const validate = this.basicValidate();
    if (!validate) return;
    const params = this.getInfoParams();
    this.connectTestButtonLoading = true;
    const res = await checkClusterHealth({
      cluster_id: this.rowConfig?.rowData?.cluster_id || 0,
      cluster_type: this.selectedType,
      ...params,
    }).catch(() => false);
    this.connectTestButtonLoading = false;
    this.connectionStatus = res ? ConnectionStatus.success : ConnectionStatus.fail;
  }
  /* 资源类型为日志的查询实例列表 */
  handleSearchInstanceList() {
    // console.log(type);
    // TODO 调用接口
  }
  /* 用途多选checkbox校验、清除错误信息 */
  handleCheckboxChange() {
    this.clearError();
  }

  /* 关闭侧栏后的回调，用于初始化状态 */
  handleSliderHidden() {
    this.handleInitData();
    this.resourceList.forEach(resource => {
      Object.assign(resource, { disabled: false });
    });
  }
  /* 表单数据更新 */
  handleKafakInfoChange(kafka) {
    this.formData.kafka = kafka;
  }
  handleinfluxdbInfoChange(influxdb) {
    this.formData.influxdb = influxdb;
  }
  handleEsInfoChange(elasticsearch) {
    this.formData.elasticsearch = elasticsearch;
  }
  handleMoreDataChange(moreConfig) {
    this.formData.moreConfig = moreConfig;
  }
  handleUserSelectChange(v) {
    this.formData.operator = v;
    this.clearError();
  }

  render() {
    return (
      <bk-sideslider
        width={640}
        ext-cls='cluster-config-wrapper-component'
        isShow={this.show}
        quick-close={true}
        transfer={true}
        on={{ 'update:isShow': this.emitShowChange }}
        on-hidden={this.handleSliderHidden}
      >
        <div
          class='cluster-config-title'
          slot='header'
        >
          {(this.rowConfig.operationType === 'add' ? this.$t('新增集群') : this.$t('编辑集群')) || '加载中...'}
        </div>
        <div
          class='cluster-config-content'
          slot='content'
        >
          <div class='cluster-resource-type'>
            <div class='resource-type-title'>{this.$t('资源类别')}</div>
            <div class='type-selector'>
              {this.resourceList.map(item => (
                <div
                  key={item.id + item.name}
                  class={[
                    'resource-type-card',
                    this.selectedType === item.id && 'selected-card',
                    item.disabled && 'disabled-card',
                  ]}
                  onClick={() => this.handleSelectChange(item)}
                >
                  <div
                    class={[
                      'resource-name',
                      this.selectedType === item.id && 'selected-name',
                      item.disabled && 'disabled',
                    ]}
                  >
                    {item.name}
                  </div>
                  <i class={['icon-monitor', `${item.icon}`, 'resource-icon', item.disabled && 'disabled']} />
                </div>
              ))}
            </div>
          </div>
          <div class='cluster-basic-info'>
            <div class='info-title'>{this.$t('基础信息')}</div>
            <FormItem
              errMsg={this.formErrMsg.clusterName}
              require={true}
              title={this.$t('集群名称')}
            >
              <bk-input
                v-model={this.formData.clusterName}
                onChange={() => (this.formErrMsg.clusterName = '')}
                onFocus={() => this.clearError()}
              />
            </FormItem>
            <FormItem
              errMsg={this.formErrMsg.label}
              require={true}
              title={this.$t('用途')}
            >
              <bk-checkbox-group
                class='usage-checkbox'
                v-model={this.formData.label}
                onChange={this.handleCheckboxChange}
              >
                {labelList.map(option => (
                  <bk-checkbox
                    key={option.id}
                    class='usage-checkbox-item'
                    value={option.id}
                  >
                    {option.label}
                  </bk-checkbox>
                ))}
              </bk-checkbox-group>
            </FormItem>
            {(() => {
              switch (this.selectedType) {
                case EClusterType.Kafka:
                  return (
                    <KafkaBasicInfo
                      ref='kafkaBasicInfo'
                      data={this.formData[this.selectedType]}
                      onChange={this.handleKafakInfoChange}
                    />
                  );
                case EClusterType.Influxdb:
                  return (
                    <InfluxdbBasicInfo
                      ref='influxdbBasicInfo'
                      data={this.formData[this.selectedType]}
                      onChange={this.handleinfluxdbInfoChange}
                    />
                  );
                case EClusterType.ES:
                  return (
                    <EsBasicInfo
                      ref='elasticsearchBasicInfo'
                      data={this.formData[this.selectedType]}
                      onChange={this.handleEsInfoChange}
                    />
                  );
              }
            })()}
            <div class='connection-test'>
              <bk-button
                loading={this.connectTestButtonLoading}
                outline={this.connectionStatus === ConnectionStatus.success}
                theme='primary'
                onClick={this.handleConnectTest}
              >
                {this.$t('连通性测试')}
              </bk-button>
              {(() => {
                if (this.connectionStatus === ConnectionStatus.success) {
                  return (
                    <div class='connection-tips'>
                      <i class='icon-monitor icon-mc-check-fill' />
                      <span>{this.$tc('测试通过')}</span>
                    </div>
                  );
                }
                if (this.connectionStatus === ConnectionStatus.fail) {
                  return (
                    <div class='connection-tips'>
                      <i class='icon-monitor icon-mc-close-fill' />
                      <span>{this.$tc('测试失败')}</span>
                    </div>
                  );
                }
                return undefined;
              })()}
            </div>
          </div>
          <MoreConfig cardTitle={this.selectedType === EClusterType.ES ? this.$tc('ES集群管理') : this.$tc('更多配置')}>
            {[EClusterType.Kafka, EClusterType.ES].includes(this.selectedType) && (
              <ClusterMoreConfig
                ref='clusterMoreConfig'
                data={this.formData.moreConfig}
                selected-type={this.selectedType}
                spaceTypes={this.spaceTypes}
                onChange={this.handleMoreDataChange}
              />
            )}
            <FormItem
              errMsg={this.formErrMsg.operator}
              title={this.$tc('负责人')}
              require
            >
              <UserSelector
                kye={this.userSelectorKey}
                multiple={false}
                userIds={this.formData.operator}
                onChange={v => this.handleUserSelectChange(v)}
              />
            </FormItem>
            <FormItem title={this.$tc('描述')}>
              <bk-input
                v-model={this.formData.description}
                maxlength={100}
                type='textarea'
                show-word-limit
              />
            </FormItem>
          </MoreConfig>
        </div>
        <div
          class='footer-operation-wrapper'
          slot='footer'
        >
          <div class='button-wrapper'>
            <bk-button
              class='footer-button'
              disabled={this.connectionStatus !== ConnectionStatus.success}
              loading={this.submitButtonLoading}
              theme='primary'
              onClick={() => this.handleSubmit()}
            >
              {this.$t('提交')}
            </bk-button>
            {/* {
                this.selectedType === EClusterType.Influxdb && (
                  <bk-button
                    class="footer-button"
                    disabled={this.connectionStatus !== ConnectionStatus.success}
                    loading={this.submitButtonLoading}
                    onClick={() => this.handleAddinfluxdbGroup()}>
                    {this.$t('提交并新增influxdb组')}
                  </bk-button>
                )
              } */}
            <bk-button onClick={() => this.emitShowChange(false)}>{this.$t('取消')}</bk-button>
          </div>
        </div>
      </bk-sideslider>
      // <InfluxdbGroup
      //   ref="influxdbGroup"
      //   is-show={this.influxdbGroupShow}
      //   influxdb-group-title={this.influxdbGroupSidesliderTitle}
      //   on-show-change={val => this.influxdbGroupShow = val}>
      // </InfluxdbGroup>
    );
  }
}
