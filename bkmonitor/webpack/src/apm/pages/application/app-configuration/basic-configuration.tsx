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

import { Component, Emit, Inject, Prop, PropSync, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import {
  Button,
  DropdownMenu,
  Form,
  FormItem,
  Icon,
  Input,
  Option,
  RadioButton,
  RadioGroup,
  Select,
  Switcher
} from 'bk-magic-vue';

import {
  getDataEncoding,
  instanceDiscoverKeys,
  queryBkDataToken,
  setup,
  start,
  stop
} from '../../../../monitor-api/modules/apm_meta';
import ChangeRcord from '../../../../monitor-pc/components/change-record/change-record';
import { IIpV6Value, INodeType, TargetObjectType } from '../../../../monitor-pc/components/monitor-ip-selector/typing';
import { transformValueToMonitor } from '../../../../monitor-pc/components/monitor-ip-selector/utils';
import StrategyIpv6 from '../../../../monitor-pc/pages/strategy-config/strategy-ipv6/strategy-ipv6';
import EditableFormItem from '../../../components/editable-form-item/editable-form-item';
import PanelItem from '../../../components/panel-item/panel-item';
import * as authorityMap from '../../home/authority-map';

import { IApdexConfig, IAppInfo, IApplicationSamplerConfig, IInstanceOption } from './type';

interface IProps {
  appInfo: IAppInfo;
  recordData: Record<string, string>;
}

type IFormData = IApdexConfig &
  IApplicationSamplerConfig & {
    app_alias: string;
    description: string;
  } & {
    plugin_config: {
      target_nodes: any[];
      paths: string[];
      data_encoding: string;
      target_node_type: INodeType;
      target_object_type: TargetObjectType;
      bk_data_id: number | string;
      bk_biz_id: number | string;
    };
  };

@Component
export default class BasicInfo extends tsc<IProps> {
  @PropSync('data', { type: Object, required: true }) appInfo: IAppInfo;
  @Prop({ type: Object, required: true }) recordData: Record<string, string>;

  @Ref() editInfoForm: any;
  @Ref() editApdexForm: any;
  @Ref() editSamplerForm: any;

  @Inject('authority') authority;
  @Inject('handleShowAuthorityDetail') handleShowAuthorityDetail;

  isLoading = false;
  /** 秘钥 */
  secureKey = '';
  /** 编辑态 */
  isEditing = false;
  /** 操作记录弹窗配置 */
  record: {
    data: Record<string, string>;
    show: boolean;
  } = {
    show: false,
    data: {}
  };
  formData: IFormData = {
    app_alias: '', // 别名
    description: '', // 描述
    apdex_default: 0,
    apdex_http: 0,
    apdex_db: 0,
    apdex_rpc: 0,
    apdex_backend: 0,
    apdex_messaging: 0,
    sampler_type: '',
    sampler_percentage: 0,
    plugin_config: {
      target_nodes: [],
      paths: [''],
      data_encoding: '',
      target_node_type: 'INSTANCE',
      target_object_type: 'HOST',
      bk_data_id: '',
      bk_biz_id: window.bk_biz_id
    }
  };
  rules = {
    app_alias: [
      {
        required: true,
        message: window.i18n.tc('必填项'),
        trigger: 'blur'
      }
    ],
    sampler_percentage: [
      {
        required: true,
        message: window.i18n.tc('必填项'),
        trigger: 'blur'
      },
      {
        validator: val => /^(?:0|[1-9][0-9]?|100)(\.[0-9]{0,2})?$/.test(val),
        message: window.i18n.t('仅支持0-100的数字'),
        trigger: 'blur'
      }
    ],
    sampler_type: [
      {
        required: true,
        message: window.i18n.tc('必填项'),
        trigger: 'blur'
      }
    ],
    'plugin_config.target_nodes': [
      {
        required: true,
        message: window.i18n.tc('必填项'),
        trigger: 'change'
      }
    ],
    'plugin_config.paths': [
      {
        required: true,
        validator: (val: []) => val.every(item => !!item),
        message: window.i18n.tc('必填项'),
        trigger: 'blur'
      }
    ],
    'plugin_config.data_encoding': [
      {
        required: true,
        message: window.i18n.tc('必填项'),
        trigger: 'blur'
      }
    ]
  };
  apdexOptionList = [
    { id: 'apdex_default', name: window.i18n.tc('默认') },
    { id: 'apdex_http', name: window.i18n.tc('网页') },
    { id: 'apdex_rpc', name: window.i18n.tc('远程调用') },
    { id: 'apdex_db', name: window.i18n.tc('数据库') },
    { id: 'apdex_messaging', name: window.i18n.tc('消息队列') },
    { id: 'apdex_backend', name: window.i18n.tc('后台任务') }
  ];
  samplingTypeList = [{ id: 'random', name: window.i18n.tc('随机') }];
  samplingTypeMaps = {
    random: window.i18n.tc('随机')
  };
  localInstanceList: IInstanceOption[] = [];
  dimessionList = [
    { name: 'kind', alias: '类型' },
    { name: 'status_code', alias: '状态码' },
    { name: 'service_name', alias: '服务名' }
  ];
  /** 拖拽数据 */
  dragData: { from: number; to: number } = {
    from: null,
    to: null
  };
  drag = {
    active: -1
  };
  /** 是否显示实例选择框 */
  showInstanceSelector = false;
  /** 实例配置选项列表 */
  instanceOptionList: IInstanceOption[] = [];
  selectorDialog: { isShow: boolean } = {
    isShow: false
  };

  selectedTargetTips = {
    INSTANCE: '已选择{0}个静态主机',
    TOPO: '已动态选择{0}个节点',
    SERVICE_TEMPLATE: '已选择{0}个服务模板',
    SET_TEMPLATE: '已选择{0}个集群模板'
  };

  logAsciiList = [];
  isFetchingEncodingList = false;

  pluginIdMapping = {
    log_trace: 'Logs to Traces',
    opentelemetry: 'OpenTelemetry'
  };

  // eslint-disable-next-line @typescript-eslint/naming-convention
  DBTypeRules = [
    // {
    //   trace_mode: [
    //     {
    //       required: true,
    //       message: '必填项',
    //       trigger: 'change'
    //     }
    //   ],
    //   threshold: [
    //     {
    //       required: true,
    //       message: '必填项',
    //       trigger: 'blur'
    //     }
    //   ],
    //   length: [
    //     {
    //       required: true,
    //       message: '必填项',
    //       trigger: 'blur'
    //     }
    //   ]
    // }
  ];

  traceModeMapping = {
    closed: '不储存',
    no_parameters: '无参数命令',
    origin: '原始命令'
  };

  /** 应用ID */
  get appId() {
    return Number(this.$route.params?.id || 0);
  }

  /** 样例展示 */
  get sampleStr() {
    if (!this.localInstanceList.length) return '--';
    return this.localInstanceList.map(item => item.value).join(':');
  }

  get isShowLog2TracesFormItem() {
    // TODO：等到后端开发好后再解开注释
    return this.appInfo.plugin_id === 'log_trace';
    // return true;
  }

  @Watch('recordData', { immediate: true })
  handleRecoedDataChange(data: Record<string, string>) {
    this.record.data = data;
  }
  @Watch('appInfo', { immediate: true, deep: true })
  handleAppInfoChange(data: IAppInfo) {
    this.localInstanceList = [...data.application_instance_name_config?.instance_name_composition];
  }

  @Emit('change')
  handleBaseInfoChange() {
    return true;
  }

  created() {
    this.DBTypeRules = this.appInfo.application_db_config.map(item => {
      return {
        trace_mode: [
          {
            required: true,
            message: '必填项',
            trigger: 'change'
          }
        ],
        threshold: [
          {
            required: item.enabled_slow_sql,
            message: '必填项',
            trigger: 'blur'
          }
        ],
        length: [
          {
            required: true,
            message: '必填项',
            trigger: 'blur'
          }
        ]
      };
    });
    this.getInstanceOptions();
    this.apdexOptionList.forEach(item => {
      this.rules[item.id] = [
        {
          required: true,
          message: window.i18n.tc('必填项'),
          trigger: 'blur'
        },
        {
          validator: val => /^[0-9]*$/.test(val),
          message: window.i18n.t('仅支持数字'),
          trigger: 'blur'
        }
      ];
    });
  }

  /**
   * @desc 获取实例配置选项
   */
  async getInstanceOptions() {
    const data = await instanceDiscoverKeys({ app_name: this.appInfo.app_name }).catch(() => []);
    this.instanceOptionList = data;
  }
  /**
   * @desc 字段请求接口更新
   * @param { * } value 更新值
   * @param { string } field 更新字段
   */
  async handleUpdateValue() {
    if (!this.authority.MANAGE_AUTH) {
      this.handleShowAuthorityDetail(authorityMap.MANAGE_AUTH);
      return false;
    }

    this.secureKey = await queryBkDataToken(this.appId).catch(() => '');
    return true;
  }
  /**
   * @desc 开关前置校验
   * @param { boolean } val 当前开关状态
   */
  handleEnablePreCheck(val: boolean) {
    if (!this.authority.MANAGE_AUTH) {
      this.handleShowAuthorityDetail(authorityMap.MANAGE_AUTH);
      return Promise.reject();
    }

    const { application_id: applicationId } = this.appInfo;
    return new Promise((resolve, reject) => {
      this.$bkInfo({
        title: val ? this.$t('你确认要停用？') : this.$t('你确认要启用？'),
        confirmLoading: true,
        // eslint-disable-next-line @typescript-eslint/no-misused-promises
        confirmFn: async () => {
          const api = val ? stop : start;
          const isPass = await api({ application_id: applicationId })
            .then(() => {
              this.handleBaseInfoChange();
              return true;
            })
            .catch(() => false);
          isPass ? resolve(true) : reject();
        },
        cancelFn: () => {
          reject();
        }
      });
    });
  }
  handleEditClick(show: boolean, isSubmit = false) {
    this.isEditing = show;
    this.showInstanceSelector = !show;
    if (show) {
      if (!this.logAsciiList.length && this.isShowLog2TracesFormItem) this.fetchEncodingList();
      // eslint-disable-next-line @typescript-eslint/naming-convention
      const { app_alias: appAlias, description, plugin_config } = this.appInfo;
      const apdexConfig = this.appInfo.application_apdex_config || {};
      const samplerConfig = this.appInfo.application_sampler_config || {};
      Object.assign(this.formData, apdexConfig, samplerConfig, { app_alias: appAlias, description, plugin_config });
    }
    if (!isSubmit) {
      this.localInstanceList = [...this.appInfo.application_instance_name_config?.instance_name_composition];
    }
  }
  /**
   * @description: 拖拽开始
   * @param {DragEvent} evt
   * @param {number} index
   */
  handleDragStart(evt: DragEvent, index: number) {
    this.dragData.from = index;
    // eslint-disable-next-line no-param-reassign
    evt.dataTransfer.effectAllowed = 'move';
  }

  /**
   * @description: 拖拽结束
   */
  handleDragend() {
    // 动画结束后关闭拖拽动画效果
    setTimeout(() => {
      this.dragData.from = null;
      this.dragData.to = null;
    }, 500);
    this.drag.active = -1;
  }
  /**
   * @description: 拖拽放入
   */
  handleDrop() {
    const { from, to } = this.dragData;
    if (from === to || [from, to].includes(null)) return;
    const temp = this.localInstanceList[from];
    this.localInstanceList.splice(from, 1);
    this.localInstanceList.splice(to, 0, temp);
    this.drag.active = -1;
  }
  /**
   * @description: 拖拽进入
   * @param {number} index
   */
  handleDragEnter(index: number) {
    this.dragData.to = index;
  }
  /**
   * @description: 拖拽经过
   * @param {DragEvent} evt
   */
  handleDragOver(evt: DragEvent, index: number) {
    evt.preventDefault();
    this.drag.active = index;
  }
  /**
   * @description: 删除实例配置
   * @param {number} index
   */
  handleDeleteInstance(index) {
    this.localInstanceList.splice(index, 1);
  }
  /**
   * @description: 拖拽离开
   */
  handleDragLeave() {
    this.drag.active = -1;
  }
  /**
   * @description: 添加实例
   */
  handleSelectInstance(id: string) {
    const instance = this.instanceOptionList.find(option => option.id === id);
    if (instance) {
      this.localInstanceList.push(instance);
      this.showInstanceSelector = false;
    }
  }
  /**
   * @description: 获取提交参数
   */
  getParams() {
    const {
      app_alias: appAlias,
      description,
      sampler_type: samplerType,
      sampler_percentage: samplerPercentage,
      // eslint-disable-next-line @typescript-eslint/naming-convention
      plugin_config,
      ...apdexConfig
    } = this.formData;
    Object.keys(apdexConfig).map(val => (apdexConfig[val] = Number(apdexConfig[val])));
    const instanceList = this.localInstanceList.map(item => item.name);
    const params = {
      application_id: this.appInfo.application_id,
      is_enabled: this.appInfo.is_enabled,
      app_alias: appAlias,
      description,
      application_sampler_config: {
        sampler_type: samplerType,
        sampler_percentage: Number(samplerPercentage)
      },
      application_apdex_config: apdexConfig,
      application_instance_name_config: {
        instance_name_composition: instanceList
      },
      application_db_config: this.appInfo.application_db_config,
      application_db_system: this.appInfo.application_db_system
    };
    if (this.isShowLog2TracesFormItem) {
      plugin_config.bk_data_id = this.appInfo.plugin_config.bk_data_id;
      // @ts-ignore
      params.plugin_config = plugin_config;
    }
    return params;
  }
  /**
   * @description: 提交编辑
   */
  async handleSubmit() {
    // DB 设置 所有的表单都要验证一次
    const cardFormList = [];
    const cardFormListValidationPromise = [];
    for (let index = 0; index < this.DBTypeRules.length; index++) {
      cardFormList.push(`cardForm${index}`);
    }
    cardFormList.forEach(s => {
      cardFormListValidationPromise.push((this.$refs[s] as any).validate());
    });

    const promiseList = ['editInfoForm', 'editApdexForm', 'editSamplerForm'].map(item => this[item]?.validate());
    await Promise.all(promiseList.concat(cardFormListValidationPromise))
      .then(async () => {
        if (!this.localInstanceList.length) {
          this.$bkMessage({
            message: this.$t('实例配置不能为空'),
            theme: 'error'
          });
          return;
        }

        const params = this.getParams();
        this.isLoading = true;
        await setup(params)
          .then(async () => {
            this.$bkMessage({
              message: this.$t('保存成功'),
              theme: 'success'
            });
            await this.handleBaseInfoChange();
            this.handleEditClick(false, true);
          })
          .finally(() => {
            this.isLoading = false;
          });
      })
      .catch(err => {
        console.warn(err);
      });
  }

  addDBType(s: string) {
    this.appInfo.application_db_config.push({
      db_system: s,
      trace_mode: 'closed',
      length: 10,
      threshold: 500,
      enabled_slow_sql: true
    });
    this.DBTypeRules.push({
      trace_mode: [
        {
          required: true,
          message: '必填项',
          trigger: 'change'
        }
      ],
      threshold: [
        {
          required: true,
          message: '必填项',
          trigger: 'blur'
        }
      ],
      length: [
        {
          required: true,
          message: '必填项',
          trigger: 'blur'
        }
      ]
    });
  }

  deleteCurrentConfigCard(index: number) {
    this.appInfo.application_db_config.splice(index, 1);
    this.DBTypeRules.splice(index, 1);
  }

  handleSelectorChange(data: { value: IIpV6Value; nodeType: INodeType }) {
    // TODO: 将数据拍平，不知道最后是否用得着
    const value = transformValueToMonitor(data.value, data.nodeType);
    this.formData.plugin_config.target_nodes = value.map(item => ({
      bk_host_id: item.bk_host_id
    }));
    // 这里利用 nodeType 控制显示哪种类型的提示文本。
    this.formData.plugin_config.target_node_type = data.nodeType;
  }

  /**
   * 获取 日志字符集
   */
  async fetchEncodingList() {
    this.isFetchingEncodingList = true;
    const encodingList = await getDataEncoding()
      .catch(console.log)
      .finally(() => (this.isFetchingEncodingList = false));
    if (Array.isArray(encodingList)) this.logAsciiList = encodingList;
  }

  render() {
    return (
      <div class='conf-content base-info-wrap'>
        <PanelItem title={this.$t('基础信息')}>
          <div
            slot='titleExtend'
            style='display: flex;align-items: center;'
          >
            {/* <EditableFormItem
              label={this.$t('启/停')}
              value={this.appInfo.is_enabled}
              formType='switch'
              authority={this.authority.MANAGE_AUTH}
              preCheckSwitcher={val => this.handleEnablePreCheck(val)}
            /> */}
            <Switcher
              v-model={this.appInfo.is_enabled}
              v-authority={{ active: !this.authority.MANAGE_AUTH }}
              class='switcher-self'
              theme='primary'
              size='small'
              pre-check={() => this.handleEnablePreCheck(this.appInfo.is_enabled)}
            />
            <span class='switcher-text'>{this.$t('启/停')}</span>
          </div>
          <div class='form-content'>
            <div class='item-row'>
              <EditableFormItem
                label={this.$t('应用名')}
                value={this.appInfo.app_name}
                formType='input'
                showEditable={false}
              />
              {!this.isEditing && (
                <EditableFormItem
                  label={this.$t('应用别名')}
                  value={this.appInfo.app_alias}
                  formType='input'
                  authority={this.authority.MANAGE_AUTH}
                  authorityName={authorityMap.MANAGE_AUTH}
                  showEditable={false}
                />
              )}
              {this.isEditing && (
                <EditableFormItem
                  label={this.$t('所有者')}
                  value={this.appInfo.create_user}
                  formType='input'
                  showEditable={false}
                />
              )}
            </div>
            <div class='item-row'>
              <EditableFormItem
                label={this.$t('支持插件')}
                value={this.pluginIdMapping[this.appInfo.plugin_id]}
                formType='input'
                authority={this.authority.MANAGE_AUTH}
                authorityName={authorityMap.MANAGE_AUTH}
                showEditable={false}
              />
              {!this.isEditing && this.isShowLog2TracesFormItem && (
                <EditableFormItem
                  label={this.$t('采集目标')}
                  value={this.$t(this.selectedTargetTips[this.appInfo?.plugin_config?.target_node_type], [
                    this.appInfo?.plugin_config?.target_nodes?.length || 0
                  ])}
                  formType='input'
                  authority={this.authority.MANAGE_AUTH}
                  authorityName={authorityMap.MANAGE_AUTH}
                  showEditable={false}
                />
              )}
              {this.isEditing && (
                <EditableFormItem
                  label='Token'
                  value={this.secureKey}
                  formType='password'
                  showEditable={false}
                  authority={this.authority.MANAGE_AUTH}
                  // eslint-disable-next-line @typescript-eslint/no-misused-promises
                  updateValue={() => this.handleUpdateValue()}
                />
              )}
            </div>
            {!this.isEditing && (
              <div>
                {this.isShowLog2TracesFormItem && (
                  <div class='item-row'>
                    {/* <EditableFormItem
                    label={this.$t('日志路径')}
                    value={'todo'}
                    formType='input'
                    authority={this.authority.MANAGE_AUTH}
                    authorityName={authorityMap.MANAGE_AUTH}
                    showEditable={false}
                  /> */}
                    <div class='log-path-item-row'>
                      <div class='label'>{this.$t('日志路径')}</div>
                      <div class='value-container'>
                        {this.appInfo.plugin_config.paths.map(path => (
                          <div class='value'>{path}</div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
                <div class='item-row'>
                  {this.isShowLog2TracesFormItem && (
                    <EditableFormItem
                      label={this.$t('日志字符集')}
                      value={this.appInfo.plugin_config.data_encoding}
                      formType='input'
                      authority={this.authority.MANAGE_AUTH}
                      authorityName={authorityMap.MANAGE_AUTH}
                      showEditable={false}
                    />
                  )}
                  <EditableFormItem
                    label={this.$t('描述')}
                    value={this.appInfo.description}
                    formType='input'
                    authority={this.authority.MANAGE_AUTH}
                    authorityName={authorityMap.MANAGE_AUTH}
                    showEditable={false}
                  />
                </div>
                <div class='item-row'>
                  <EditableFormItem
                    label={this.$t('所有者')}
                    value={this.appInfo.create_user}
                    formType='input'
                    showEditable={false}
                  />
                  <EditableFormItem
                    label='Token'
                    value={this.secureKey}
                    formType='password'
                    showEditable={false}
                    authority={this.authority.MANAGE_AUTH}
                    // eslint-disable-next-line @typescript-eslint/no-misused-promises
                    updateValue={() => this.handleUpdateValue()}
                  />
                </div>
              </div>
            )}
            {this.isEditing && (
              <Form
                class='edit-config-form'
                {...{
                  props: {
                    model: this.formData,
                    rules: this.rules
                  }
                }}
                label-width={116}
                ref='editInfoForm'
              >
                <FormItem
                  label={this.$t('应用别名')}
                  required
                  property='app_alias'
                  error-display-type='normal'
                >
                  <Input
                    v-model={this.formData.app_alias}
                    class='alias-name-input'
                  />
                </FormItem>
                {this.isShowLog2TracesFormItem && (
                  <FormItem
                    label={this.$t('采集目标')}
                    required
                    property='plugin_config.target_nodes'
                    error-display-type='normal'
                  >
                    <div style='display: flex;align-items: center;'>
                      <bk-button
                        theme='default'
                        icon='plus'
                        class='btn-target-collect'
                        onClick={() => (this.selectorDialog.isShow = true)}
                      >
                        {this.$t('选择目标')}
                      </bk-button>
                      {this.formData.plugin_config.target_nodes.length > 0 && (
                        <i18n
                          path={this.selectedTargetTips[this.formData.plugin_config.target_node_type]}
                          style='margin-left: 8px;'
                        >
                          <span style='color: #4e99ff;'>{this.formData.plugin_config.target_nodes.length}</span>
                        </i18n>
                      )}
                    </div>
                  </FormItem>
                )}
                {this.isShowLog2TracesFormItem && (
                  <FormItem
                    label={this.$t('日志路径')}
                    required
                    property='plugin_config.paths'
                    error-display-type='normal'
                  >
                    {this.formData.plugin_config.paths.map((path, index) => (
                      <div>
                        <div
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            marginBottom: index > 0 && index < this.formData.plugin_config.paths.length - 1 && '20px'
                          }}
                        >
                          <bk-input
                            v-model={this.formData.plugin_config.paths[index]}
                            placeholder={this.$t('请输入')}
                            style='width: 490px;'
                          />
                          <Icon
                            class='log-path-icon log-path-icon-plus'
                            type='plus-circle-shape'
                            onClick={() => this.formData.plugin_config.paths.push('')}
                          />
                          <Icon
                            class={{
                              'log-path-icon': true,
                              'log-path-icon-minus': true,
                              disabled: this.formData.plugin_config.paths.length <= 1
                            }}
                            type='minus-circle-shape'
                            onClick={() =>
                              this.formData.plugin_config.paths.length > 1 &&
                              this.formData.plugin_config.paths.splice(index, 1)
                            }
                          />
                        </div>
                        {index === 0 && <div class='log-path-hint'>{this.$t('日志文件为绝对路径，可使用通配符')}</div>}
                      </div>
                    ))}
                  </FormItem>
                )}
                {this.isShowLog2TracesFormItem && (
                  <FormItem
                    label={this.$t('日志字符集')}
                    required
                    property='plugin_config.data_encoding'
                    error-display-type='normal'
                  >
                    <bk-select
                      v-model={this.formData.plugin_config.data_encoding}
                      disabled={this.isFetchingEncodingList}
                      style='width: 490px;'
                    >
                      {this.logAsciiList.map(item => (
                        <bk-option
                          key={item.id}
                          id={item.id}
                          name={item.name}
                        ></bk-option>
                      ))}
                    </bk-select>
                  </FormItem>
                )}
                <FormItem
                  label={this.$t('描述')}
                  property='description'
                >
                  <Input
                    v-model={this.formData.description}
                    type='textarea'
                    class='description-input'
                    show-word-limit
                    maxlength='100'
                  />
                </FormItem>
              </Form>
            )}
          </div>
        </PanelItem>
        <PanelItem
          title={this.$t('Apdex设置')}
          flexDirection='column'
        >
          <div
            class='panel-intro'
            style='position:relative'
          >
            <div>
              {this.$t(
                'Apdex（Application Performance Index）是由 Apdex 联盟开发的用于评估应用性能的工业标准。Apdex 标准从用户的角度出发，将对应用响应时间的表现，转为用户对于应用性能的可量化范围为 0-1 的满意度评价。'
              )}
            </div>
            <div>
              {this.$t(
                'Apdex 定义了应用响应时间的最优门槛为 T（即 Apdex 阈值，T 由性能评估人员根据预期性能要求确定），根据应用响应时间结合 T 定义了三种不同的性能表现：'
              )}
            </div>
            <div class='indentation-text'>{`● Satisfied ${this.$t('（满意）- 应用响应时间低于或等于')} T`}</div>
            <div class='indentation-text'>{`● Tolerating ${this.$t(
              '（可容忍）- 应用响应时间大于 T，但同时小于或等于'
            )} 4T`}</div>
            <div class='indentation-text'>{`● Frustrated ${this.$t('（烦躁期）- 应用响应时间大于')} 4T`}</div>
          </div>
          <div class='form-content'>
            {this.isEditing ? (
              <Form
                class='edit-config-form grid-form'
                {...{
                  props: {
                    model: this.formData,
                    rules: this.rules
                  }
                }}
                label-width={116}
                ref='editApdexForm'
              >
                {this.apdexOptionList.map(apdex => (
                  <FormItem
                    label={apdex.name}
                    property={apdex.id}
                    error-display-type='normal'
                  >
                    <Input
                      v-model={this.formData[apdex.id]}
                      class='apdex-input'
                      type='number'
                      show-controls={false}
                    >
                      <template slot='append'>
                        <div class='right-unit'>ms</div>
                      </template>
                    </Input>
                  </FormItem>
                ))}
              </Form>
            ) : (
              <div class='grid-form'>
                {this.apdexOptionList.map(apdex => (
                  <div class='display-item'>
                    <label>{apdex.name}</label>
                    <span>{this.appInfo.application_apdex_config[apdex.id] ?? '--'}</span>
                    <span class='unit'>ms</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </PanelItem>
        <PanelItem
          title={this.$t('采样配置')}
          flexDirection='column'
        >
          <div
            class='panel-intro'
            style='position:relative'
          >
            {this.$t(
              ' 根据应用的数据量情况进行设置，如果应用的trace数据量非常大，不仅影响程序的输出、网络的消耗，也需要更大的集群资源成本。 在这种情况下会考虑进行采集，注意错误的Span默认是会被采集不会被采样。'
            )}
          </div>
          <div class='form-content'>
            {this.isEditing ? (
              <Form
                class='edit-config-form'
                {...{
                  props: {
                    model: this.formData,
                    rules: this.rules
                  }
                }}
                label-width={116}
                ref='editSamplerForm'
              >
                <FormItem
                  label={this.$t('采样类型')}
                  property='sampler_type'
                  error-display-type='normal'
                >
                  <Select
                    class='sampling-type-select'
                    vModel={this.formData.sampler_type}
                    clearable={false}
                  >
                    {this.samplingTypeList.map(option => (
                      <Option
                        key={option.id}
                        id={option.id}
                        name={option.name}
                      ></Option>
                    ))}
                  </Select>
                </FormItem>
                <FormItem
                  label={this.$t('采样比例')}
                  property='sampler_percentage'
                  error-display-type='normal'
                >
                  <Input
                    v-model={this.formData.sampler_percentage}
                    class='sampling-rate-input'
                    type='number'
                    show-controls={false}
                  >
                    <template slot='append'>
                      <div class='right-unit'>%</div>
                    </template>
                  </Input>
                </FormItem>
                {/* <div class="panel-tips">
                <label>{this.$t('强调说明')}</label>
                <span>{this.$t('错误的Span一定会采集')}</span>
              </div> */}
              </Form>
            ) : (
              <div class='grid-form'>
                <div class='display-item'>
                  <label>{this.$t('采样类型')}</label>
                  <span>{this.samplingTypeMaps[this.appInfo.application_sampler_config?.sampler_type] || '--'}</span>
                </div>
                <div class='display-item'>
                  <label>{this.$t('采样比例')}</label>
                  <span>
                    {this.appInfo.application_sampler_config?.sampler_percentage
                      ? `${this.appInfo.application_sampler_config?.sampler_percentage}%`
                      : '--'}
                  </span>
                </div>
              </div>
            )}
          </div>
        </PanelItem>
        <PanelItem
          title={this.$t('实例名配置')}
          flexDirection='column'
        >
          <div
            class='panel-intro'
            style='position:relative'
          >
            {this.$t('通过实例名配置，平台将以实例名维度进行统计，所以确定实例的唯一性有助于观测数据和定位问题。')}
          </div>
          <div class='form-content'>
            <div class='instance-list'>
              <transition-group
                name={this.dragData.from !== null ? 'flip-list' : 'filp-list-none'}
                tag='ul'
              >
                {this.localInstanceList.map((instance, index) => (
                  <li
                    class='instanct-wrap'
                    key={instance.name}
                  >
                    <div class='drag-item'>
                      <div
                        class={[
                          'instance-card',
                          {
                            'active-item': index === this.drag.active,
                            'disabled-item': !this.isEditing
                          }
                        ]}
                        key={instance.value}
                        draggable={this.isEditing}
                        onDragstart={evt => this.handleDragStart(evt, index)}
                        onDragend={this.handleDragend}
                        onDrop={this.handleDrop}
                        onDragenter={() => this.handleDragEnter(index)}
                        onDragover={evt => this.handleDragOver(evt, index)}
                        onDragleave={this.handleDragLeave}
                      >
                        {this.isEditing && <span class='icon-monitor icon-mc-tuozhuai'></span>}
                        {instance.name}
                        <span
                          class='icon-monitor icon-mc-close'
                          onClick={() => this.handleDeleteInstance(index)}
                        />
                      </div>
                      {index < this.localInstanceList.length - 1 && <span class='delimiter'>:</span>}
                    </div>
                    <span class='alias-name'>{instance.alias || '--'}</span>
                  </li>
                ))}
                {this.isEditing && (
                  <li
                    key='add'
                    class='add-instance-wrap'
                  >
                    <div
                      class={[
                        'add-button',
                        { 'is-disabled': this.instanceOptionList.length === this.localInstanceList.length }
                      ]}
                      onClick={() =>
                        this.instanceOptionList.length === this.localInstanceList.length
                          ? false
                          : (this.showInstanceSelector = true)
                      }
                      v-bk-tooltips={{
                        content: this.$t('已经没有可用的维度'),
                        disabled: this.instanceOptionList.length !== this.localInstanceList.length
                      }}
                    >
                      <span class='icon-monitor icon-plus-line'></span>
                    </div>
                    {this.showInstanceSelector && (
                      <Select
                        class='instance-select'
                        ext-popover-cls='instance-select-popover'
                        searchable
                        show-on-init
                        popover-width={300}
                        onChange={v => this.handleSelectInstance(v)}
                      >
                        {this.instanceOptionList.map(option => (
                          <Option
                            key={option.id}
                            id={option.id}
                            name={option.name}
                            disabled={this.localInstanceList.some(val => val.id === option.id)}
                          >
                            <div
                              class='instance-config-option'
                              v-bk-tooltips={{
                                content: this.$t('已经添加'),
                                disabled: !this.localInstanceList.some(val => val.id === option.id)
                              }}
                            >
                              <span class='instance-name'>{option.name}</span>
                              <span class='instance-alias'>{option.alias}</span>
                            </div>
                          </Option>
                        ))}
                      </Select>
                    )}
                  </li>
                )}
              </transition-group>
            </div>
            <div class='panel-tips'>
              <label>{this.$t('样例展示')}</label>
              <span>{this.sampleStr}</span>
            </div>
          </div>
        </PanelItem>
        {/* TODO：记得翻译 */}
        <PanelItem
          title={this.$t('DB设置')}
          flexDirection='column'
        >
          <div
            class='panel-intro'
            style='position:relative'
          >
            {this.isEditing ? (
              <div class='db-config-title-container'>
                <div style='display: flex;align-items: center;margin-bottom: 12px;'>
                  <span>{this.$t('DB类型')}</span>
                  <DropdownMenu trigger='click'>
                    <Button
                      text
                      size='small'
                      slot='dropdown-trigger'
                    >
                      <div style={{ display: 'flex', alignItems: 'baseline' }}>
                        <Icon type='plus-circle' />
                        <span style='margin-left: 5px;'>{this.$t('指定DB')}</span>
                      </div>
                    </Button>

                    <ul
                      class='bk-dropdown-list'
                      slot='dropdown-content'
                    >
                      {this.appInfo.application_db_system.map(s => {
                        return (
                          <li>
                            <a
                              class={{
                                'dropdown-list-item-disabled': !!this.appInfo.application_db_config.find(
                                  option => s === option.db_system
                                )
                              }}
                              key={s}
                              href='javascript:;'
                              onClick={() => this.addDBType(s)}
                            >
                              {s}
                            </a>
                          </li>
                        );
                      })}
                    </ul>
                  </DropdownMenu>
                </div>

                <div class='card-list-container'>
                  {this.appInfo.application_db_config.map((card, index) => {
                    return (
                      <div class='db-config-card'>
                        <div
                          class={{
                            'title-bar': true,
                            'is-not-default': index > 0
                          }}
                        >
                          <span class='text'>{card.db_system || this.$t('默认')}</span>
                          {index > 0 && (
                            <Icon
                              class='close'
                              type='close'
                              onClick={() => this.deleteCurrentConfigCard(index)}
                            />
                          )}
                        </div>

                        <div class='card-container'>
                          <div>
                            <Form
                              label-width={120}
                              {...{
                                props: {
                                  model: card,
                                  rules: this.DBTypeRules[index]
                                }
                              }}
                              ref={`cardForm${index}`}
                            >
                              <FormItem
                                label={this.$t('存储方式')}
                                required
                                property='trace_mode'
                                error-display-type='normal'
                              >
                                <RadioGroup v-model={card.trace_mode}>
                                  <RadioButton value='origin'>{this.$t('原始命令')}</RadioButton>
                                  <RadioButton value='no_parameters'>{this.$t('无参数命令')}</RadioButton>
                                  <RadioButton value='closed'>{this.$t('不储存')}</RadioButton>
                                </RadioGroup>
                              </FormItem>
                              <FormItem
                                label={this.$t('启用慢语句')}
                                required={card.enabled_slow_sql}
                                property='threshold'
                                error-display-type='normal'
                              >
                                <div class='low-sql-container'>
                                  <Switcher
                                    v-model={card.enabled_slow_sql}
                                    theme='primary'
                                    size='small'
                                    onChange={() =>
                                      (this.DBTypeRules[index].threshold[0].required = card.enabled_slow_sql)
                                    }
                                  ></Switcher>
                                  <span
                                    class='text'
                                    style='margin-left: 16px;'
                                  >
                                    {this.$t('命令执行时间')}
                                  </span>
                                  <span>{'>'}</span>
                                  <Input
                                    v-model={card.threshold}
                                    behavior='simplicity'
                                    class='excution-input'
                                    type='number'
                                    min={0}
                                    onInput={() => {
                                      // 如果 card.threshold 为 falsy 值时，服务端的校验是不会通过的。（即使不启用慢语句时也是一样）
                                      // 这里手动判断一次，然后给予一个默认值。
                                      // eslint-disable-next-line no-param-reassign
                                      if (!card.threshold) card.threshold = 0;
                                    }}
                                  ></Input>
                                  <span class='text'>ms</span>
                                </div>
                              </FormItem>
                              <FormItem
                                label={this.$t('语句长度')}
                                required
                                property='length'
                                error-display-type='normal'
                              >
                                <div class='sql-length-container'>
                                  <span class='text'>{this.$t('截断')}</span>
                                  <span>{'>'}</span>
                                  <Input
                                    v-model={card.length}
                                    behavior='simplicity'
                                    class='sql-cut-input'
                                    type='number'
                                    min={0}
                                  ></Input>
                                  <span class='text'>{this.$t('字符')}</span>
                                </div>
                              </FormItem>
                            </Form>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ) : (
              <div class='db-config-card-preview'>
                {this.appInfo.application_db_config.map((item, index) => {
                  return (
                    <div
                      class='db-config-card-preview-container'
                      style={{
                        order: this.appInfo.application_db_config.length - index
                      }}
                    >
                      <div
                        class={{
                          'db-config-card-preview-title': true,
                          'is-default': index === 0
                        }}
                      >
                        {item.db_system || this.$t('默认')}
                      </div>
                      <div class='db-config-card-preview-content'>
                        <div class='row'>
                          <span class='label-text'>{this.$t('存储方式')}</span>
                          <span class='label-colons'>:</span>
                          <span class='label-value'>{this.$t(this.traceModeMapping[item.trace_mode])}</span>
                        </div>
                        <div class='row'>
                          <span class='label-text'>{this.$t('慢语句阈值')}</span>
                          <span class='label-colons'>:</span>
                          <span class='label-value'>
                            <span>{this.$t('执行时间')}</span>
                            <span style='margin: 0 5px;'>{'>'}</span>
                            <span>{item.threshold}ms</span>
                          </span>
                        </div>
                        <div class='row'>
                          <span class='label-text'>{this.$t('语句长度')}</span>
                          <span class='label-colons'>:</span>
                          <span class='label-value'>
                            <span>{this.$t('截断')}</span>
                            <span style='margin: 0 5px;'>{'>'}</span>
                            <span>{item.length}</span>
                            <span style='margin-left: 5px;'>{this.$t('字符')}</span>
                          </span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </PanelItem>
        {/* <PanelItem title={this.$t('汇聚维度')}>
        <div class="panel-intro">说明文案</div>
        <div class={['dimession-list', { 'edit-demission': this.isEditing }]}>
          <div class="dimession-row dimession-row-head">
            <span class="dimession-name">维度名</span>
            <span class="dimession-alias">别名</span>
          </div>
          {this.dimessionList.map(item => (
            <div class="dimession-row">
              <span class="dimession-name">{item.name}</span>
              <span class="dimession-alias">{item.alias}</span>
            </div>
          ))}
        </div>
      </PanelItem> */}
        <div class='header-tool'>
          {!this.isEditing && (
            <Button
              class='edit-btn'
              theme='primary'
              size='normal'
              outline
              v-authority={{ active: !this.authority }}
              onClick={() => {
                this.authority ? this.handleEditClick(true) : this.handleShowAuthorityDetail(authorityMap.MANAGE_AUTH);
              }}
            >
              {this.$t('编辑')}
            </Button>
          )}
          <div
            class='history-btn'
            v-bk-tooltips={{ content: this.$t('变更记录') }}
            onClick={() => (this.record.show = true)}
          >
            <i class='icon-monitor icon-lishijilu'></i>
          </div>
        </div>
        {this.isEditing ? (
          <div class='submit-handle'>
            <Button
              class='mr10'
              theme='primary'
              loading={this.isLoading}
              onClick={() => this.handleSubmit()}
            >
              {this.$t('保存')}
            </Button>
            <Button onClick={() => this.handleEditClick(false)}>{this.$t('取消')}</Button>
          </div>
        ) : (
          <div></div>
        )}
        {/* 操作记录弹窗 */}
        <ChangeRcord
          recordData={this.record.data}
          show={this.record.show}
          onUpdateShow={v => (this.record.show = v)}
        />

        {this.isShowLog2TracesFormItem && (
          <StrategyIpv6
            showDialog={this.selectorDialog.isShow}
            nodeType={this.formData.plugin_config.target_node_type}
            objectType={this.formData.plugin_config.target_object_type}
            checkedNodes={this.formData.plugin_config.target_nodes}
            onChange={this.handleSelectorChange}
            onCloseDialog={v => (this.selectorDialog.isShow = v)}
          ></StrategyIpv6>
        )}
      </div>
    );
  }
}
