/* eslint-disable @typescript-eslint/naming-convention */
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

import dayjs from 'dayjs';
import {
  getDataEncoding,
  instanceDiscoverKeys,
  queryBkDataToken,
  samplingOptions,
  setup,
  start,
  stop,
} from 'monitor-api/modules/apm_meta';
import { getFieldOptionValues } from 'monitor-api/modules/apm_trace';
import { deepClone, typeTools } from 'monitor-common/utils/utils';
import ChangeRcord from 'monitor-pc/components/change-record/change-record';
// import CycleInput from '../../../components/cycle-input/cycle-input';
import CycleInput from 'monitor-pc/components/cycle-input/cycle-input';
// import {
// defaultCycleOptionMicroSec,
// defaultCycleOptionMillisec,
// defaultCycleOptionMin,
// defaultCycleOptionSec
import { transformValueToMonitor } from 'monitor-pc/components/monitor-ip-selector/utils';
import { CONDITION } from 'monitor-pc/constant/constant';
import SimpleSelectInput from 'monitor-pc/pages/alarm-shield/components/simple-select-input';
import SelectMenu from 'monitor-pc/pages/strategy-config/strategy-config-set-new/components/select-menu';
import StrategyIpv6 from 'monitor-pc/pages/strategy-config/strategy-ipv6/strategy-ipv6';

import EditableFormItem from '../../../components/editable-form-item/editable-form-item';
import PanelItem from '../../../components/panel-item/panel-item';
import * as authorityMap from '../../home/authority-map';
import CustomService from './custom-service';
import {
  ETelemetryDataType,
  type IApdexConfig,
  type IAppInfo,
  type IApplicationSamplerConfig,
  type IInstanceOption,
  type ISamplingRule,
} from './type';
// } from 'monitor-pc/components/cycle-input/utils';
import type { IIpV6Value, INodeType, TargetObjectType } from 'monitor-pc/components/monitor-ip-selector/typing';

import './basic-configuration.scss';

const TIME_CONDITION_METHOD_LIST = [
  { id: 'gt', name: '>' },
  { id: 'gte', name: '>=' },
  { id: 'lt', name: '<' },
  { id: 'lte', name: '<=' },
];
const STRING_CONDITION_METHOD_LIST = [
  { id: 'eq', name: '=' },
  { id: 'gt', name: '>' },
  { id: 'gte', name: '>=' },
  { id: 'lt', name: '<' },
  { id: 'lte', name: '<=' },
  { id: 'neq', name: '!=' },
  { id: 'reg', name: 'regex' },
  { id: 'nreg', name: 'nregex' },
];
const nullOptions = {
  // 下拉选项第一为空值
  id: '',
  name: `- ${window.i18n.tc('空')} -`,
};
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

type ISamplingOption = {
  name: string;
  id: string;
  type: string;
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
    data: {},
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
    tail_conditions: [],
    plugin_config: {
      target_nodes: [],
      paths: [''],
      data_encoding: '',
      target_node_type: 'INSTANCE',
      target_object_type: 'HOST',
      bk_data_id: '',
      bk_biz_id: window.bk_biz_id,
    },
  };
  rules = {
    app_alias: [
      {
        required: true,
        message: window.i18n.tc('必填项'),
        trigger: 'blur',
      },
      {
        validator: val => !/^\s*$/.test(val),
        message: window.i18n.tc('必填项'),
        trigger: 'blur',
      },
      {
        validator: val => !/(\ud83c[\udf00-\udfff])|(\ud83d[\udc00-\ude4f\ude80-\udeff])|[\u2600-\u2B55]/g.test(val),
        message: window.i18n.tc('不能输入emoji表情'),
        trigger: 'blur',
      },
    ],
    sampler_percentage: [
      {
        required: true,
        message: window.i18n.tc('必填项'),
        trigger: 'blur',
      },
      {
        validator: val => /^(?:0|[1-9][0-9]?|100)(\.[0-9]{0,2})?$/.test(val),
        message: window.i18n.t('仅支持0-100的数字'),
        trigger: 'blur',
      },
    ],
    sampler_type: [
      {
        required: true,
        message: window.i18n.tc('必填项'),
        trigger: 'blur',
      },
    ],
    'plugin_config.target_nodes': [
      {
        validator: (val: []) => val?.length,
        message: window.i18n.tc('必填项'),
        trigger: 'change',
      },
    ],
    'plugin_config.paths': [
      {
        validator: (val: []) => val.every(item => !!item),
        message: window.i18n.tc('必填项'),
        trigger: 'blur',
      },
    ],
    'plugin_config.data_encoding': [
      {
        required: true,
        message: window.i18n.tc('必填项'),
        trigger: 'blur',
      },
    ],
  };
  apdexOptionList = [
    { id: 'apdex_default', name: window.i18n.tc('默认') },
    { id: 'apdex_http', name: window.i18n.tc('网页') },
    { id: 'apdex_rpc', name: window.i18n.tc('远程调用') },
    { id: 'apdex_db', name: window.i18n.tc('数据库') },
    { id: 'apdex_messaging', name: window.i18n.tc('消息队列') },
    { id: 'apdex_backend', name: window.i18n.tc('后台任务') },
  ];
  samplingTypeList = [
    { id: 'random', name: window.i18n.tc('随机') },
    { id: 'tail', name: window.i18n.tc('尾部采样') },
    { id: 'empty', name: window.i18n.tc('不采样') },
  ];
  samplingTypeMaps = {
    random: window.i18n.tc('随机'),
    tail: window.i18n.tc('尾部采样'),
    empty: window.i18n.tc('不采样'),
  };
  localInstanceList: IInstanceOption[] = [];
  dimessionList = [
    { name: 'kind', alias: '类型' },
    { name: 'status_code', alias: '状态码' },
    { name: 'service_name', alias: '服务名' },
  ];
  /** 拖拽数据 */
  dragData: { from: number; to: number } = {
    from: null,
    to: null,
  };
  drag = {
    active: -1,
  };
  /** 是否显示实例选择框 */
  showInstanceSelector = false;
  /** 实例配置选项列表 */
  instanceOptionList: IInstanceOption[] = [];
  selectorDialog: { isShow: boolean } = {
    isShow: false,
  };

  selectedTargetTips = {
    INSTANCE: '已选择{0}个静态主机',
    TOPO: '已动态选择{0}个节点',
    SERVICE_TEMPLATE: '已选择{0}个服务模板',
    SET_TEMPLATE: '已选择{0}个集群模板',
  };

  logAsciiList = [];
  isFetchingEncodingList = false;

  pluginIdMapping = {
    log_trace: 'Logs to Traces',
    opentelemetry: 'OpenTelemetry',
  };

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
    origin: '原始命令',
  };

  samplingRules: ISamplingRule[] = [];
  samplingRulesGroup: ISamplingRule[][] = []; // 用于渲染必采规则根据or按行排列
  samplingRuleOptions: ISamplingOption[] = [];

  samplingRuleValueMap: Record<string, { id: string; name: string }[]> = {};

  curSelectTarget = null;
  showSelectMenu = false;
  menuList = [];
  curGroupConditionIndex = -1;
  curConditionIndex = -1;
  curConditionProp = '';

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
    this.localInstanceList = [...(data.application_instance_name_config?.instance_name_composition || [])];

    if (data.application_sampler_config.sampler_type === 'tail') {
      // 尾部采样处理展示规则
      const { tail_conditions: conditions } = data.application_sampler_config;
      this.samplingRules.splice(
        0,
        this.samplingRules.length,
        ...conditions.map(item => {
          if (item.type === 'string') {
            this.getSamplingVariableValueList(item.key);
          }
          return {
            ...item,
            // biome-ignore lint/style/useExponentiationOperator: <explanation>
            value: item.type === 'time' ? Number(item.value[0] / Math.pow(10, 6)) : item.value,
          };
        })
      );
      this.handleConditionChange();
    }
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
            trigger: 'change',
          },
        ],
        threshold: [
          {
            required: item.enabled_slow_sql,
            message: '必填项',
            trigger: 'blur',
          },
        ],
        length: [
          {
            required: true,
            message: '必填项',
            trigger: 'blur',
          },
        ],
      };
    });
    this.getInstanceOptions();
    this.apdexOptionList.forEach(item => {
      this.rules[item.id] = [
        {
          required: true,
          message: window.i18n.tc('必填项'),
          trigger: 'blur',
        },
        {
          validator: val => /^[0-9]*$/.test(val),
          message: window.i18n.t('仅支持数字'),
          trigger: 'blur',
        },
      ];
    });
    this.getSamplingOptions();
    this.handleConditionChange();
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

    this.secureKey = await queryBkDataToken(this.appInfo.application_id).catch(() => '');
    return true;
  }
  /**
   * @desc 开关前置校验
   * @param { boolean } val 当前开关状态
   * @param { string } val 事件类型
   */
  handleEnablePreCheck(val: boolean, eventType: string) {
    if (!this.authority.MANAGE_AUTH) {
      this.handleShowAuthorityDetail(authorityMap.MANAGE_AUTH);
      return Promise.reject();
    }

    const { application_id: applicationId } = this.appInfo;
    return new Promise((resolve, reject) => {
      this.$bkInfo({
        title: val ? this.$t('你确认要停用？') : this.$t('你确认要启用？'),
        confirmLoading: true,

        confirmFn: async () => {
          const api = val ? stop : start;
          const isPass = await api({ application_id: applicationId, type: eventType })
            .then(() => {
              this.handleBaseInfoChange();
              return true;
            })
            .catch(() => false);
          isPass ? resolve(true) : reject();
        },
        cancelFn: () => {
          reject();
        },
      });
    });
  }
  handleEditClick(show: boolean, isSubmit = false) {
    this.isEditing = show;
    this.showInstanceSelector = !show;
    if (show) {
      if (!this.logAsciiList.length && this.isShowLog2TracesFormItem) this.fetchEncodingList();
      const { app_alias: appAlias, description, plugin_config, application_sampler_config } = this.appInfo;
      const apdexConfig = this.appInfo.application_apdex_config || {};
      const samplerConfig = Object.assign({}, application_sampler_config, {
        sampler_percentage: application_sampler_config.sampler_percentage || 0,
      });
      Object.assign(this.formData, apdexConfig, samplerConfig, {
        app_alias: appAlias,
        description,
        plugin_config,
      });
    }
    if (!isSubmit) {
      this.localInstanceList = [...(this.appInfo.application_instance_name_config?.instance_name_composition || [])];
    }
  }
  /**
   * @description: 拖拽开始
   * @param {DragEvent} evt
   * @param {number} index
   */
  handleDragStart(evt: DragEvent, index: number) {
    this.dragData.from = index;

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

      plugin_config,
      ...apdexConfig
    } = this.formData;
    Object.keys(apdexConfig).map(val => (apdexConfig[val] = Number(apdexConfig[val])));
    const instanceList = this.localInstanceList.map(item => item.name);
    const params: Record<string, any> = {
      application_id: this.appInfo.application_id,
      is_enabled: this.appInfo.is_enabled,
      app_alias: appAlias,
      description,
      application_sampler_config: {
        sampler_type: samplerType,
      },
      application_apdex_config: apdexConfig,
      application_instance_name_config: {
        instance_name_composition: instanceList,
      },
      application_db_config: this.appInfo.application_db_config,
      application_db_system: this.appInfo.application_db_system,
    };

    // 处理采样配置
    if (params.application_sampler_config.sampler_type === 'random') {
      params.application_sampler_config.sampler_percentage = Number(samplerPercentage);
    } else if (params.application_sampler_config.sampler_type === 'tail') {
      params.application_sampler_config.sampler_percentage = Number(samplerPercentage);
      params.application_sampler_config.tail_conditions = this.samplingRules
        .map(item => {
          const { key_alias, type, ...rest } = item;
          // 时间类型输入组件默认单位为秒 后端传参要求单位为纳秒
          // biome-ignore lint/style/useExponentiationOperator: <explanation>
          return { ...rest, value: type === 'time' ? [String(rest.value * Math.pow(10, 6))] : rest.value };
        })
        .filter(item => item.value.length);
    }

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
            theme: 'error',
          });
          return;
        }

        const params = this.getParams();
        this.isLoading = true;
        await setup(params)
          .then(async () => {
            this.$bkMessage({
              message: this.$t('保存成功'),
              theme: 'success',
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
      enabled_slow_sql: true,
    });
    this.DBTypeRules.push({
      trace_mode: [
        {
          required: true,
          message: '必填项',
          trigger: 'change',
        },
      ],
      threshold: [
        {
          required: true,
          message: '必填项',
          trigger: 'blur',
        },
      ],
      length: [
        {
          required: true,
          message: '必填项',
          trigger: 'blur',
        },
      ],
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
      bk_host_id: item.bk_host_id,
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

  /** 采样规则条件key值改变 */
  async handleRuleKeyChange(item: ISamplingRule, v: string, gIndex: number, index: number) {
    await this.$nextTick();
    if (!v && this.samplingRules.length > 1) this.handleDeleteKey(gIndex, index);
    item.key_alias = v;

    let id = v;
    this.samplingRuleOptions.forEach(opt => {
      if (opt.id === v || opt.name === v) {
        id = opt.id as string;
        item.type = opt.type;
      }
    });
    if (item.key !== id) {
      item.value = item.type === 'time' ? 10 : [];
    }
    item.key = id;
    if (item.type === 'string' && id && !this.samplingRuleValueMap[id]) {
      await this.getSamplingVariableValueList(id);
    }

    if (
      item.type === 'time' &&
      (item.method === '' || !TIME_CONDITION_METHOD_LIST.some(val => val.id === item.method))
    ) {
      item.method = 'gt';
    } else if (item.method === '') {
      item.method = 'eq';
    }

    this.samplingRules = this.samplingRules.slice();
    this.handleConditionChange();
  }

  /** 获取采样配置常量 */
  async getSamplingOptions() {
    await samplingOptions().then(data => {
      this.samplingTypeList = this.samplingTypeList.filter(item => (data?.sampler_types || []).includes(item.id));
      this.samplingRuleOptions = (data?.tail_sampling_options || []).map(item => {
        return {
          id: item.key,
          ...item,
        };
      });
    });
  }

  // 获取采样规则候选值列表数据
  async getSamplingVariableValueList(keyId: string) {
    const params = {
      app_name: this.appInfo.app_name,
      start_time: dayjs().add(-1, 'h').unix(),
      end_time: dayjs().unix(),
      bk_biz_id: window.bk_biz_id,
      fields: [keyId],
      // mode: 'span' // TODO
    };
    const data = await getFieldOptionValues(params).catch(() => []);
    const result = (data?.[keyId] || []).map(item => ({ name: item.text, id: item.value })) || [];
    this.samplingRuleValueMap[keyId] = result || [];
  }

  /* 弹出条件选择 */
  handleToggleCondition(e, { gIndex, index, prop }) {
    this.curSelectTarget = e.target;
    this.showSelectMenu = true;
    this.menuList = CONDITION;
    this.curGroupConditionIndex = gIndex;
    this.curConditionIndex = index;
    this.curConditionProp = prop;
  }

  /* 弹出判断方式 */
  handleToggleMethod(e, { gIndex, index, prop }) {
    this.curSelectTarget = e.target;
    this.showSelectMenu = true;
    const { key } = this.samplingRulesGroup[gIndex][index];
    const { type } = this.samplingRuleOptions.find(item => item.id === key) || { type: 'string' };
    this.menuList = this.handleGetMethodList(type as any);
    this.curGroupConditionIndex = gIndex;
    this.curConditionIndex = index;
    this.curConditionProp = prop;
    this.handleConditionChange();
  }

  handleGetMethodNameById(id: string) {
    return STRING_CONDITION_METHOD_LIST.find(item => item.id === id)?.name || '';
  }

  // value变化时触发
  async handleSamplingRuleValueChange(item, v: number | string[]) {
    await this.$nextTick();
    if (typeTools.isNumber(v)) {
      item.value = v;
    } else {
      if (item.value.includes(nullOptions.id)) {
        if ((v as any).length > 1) {
          item.value = (v as any).filter(str => str !== nullOptions.id);
        } else {
          item.value = v;
        }
      } else {
        if ((v as any).includes(nullOptions.id)) {
          item.value = [nullOptions.id];
        } else {
          item.value = v;
        }
      }
    }

    this.samplingRules = this.samplingRules.slice();
    this.handleConditionChange();
  }

  handleSamplingRuleValueUnitChange(item, v) {
    item.unit = v;
    this.samplingRules = this.samplingRules.slice();
    this.handleConditionChange();
  }

  /**
   * @description: 维度数据类型不同所需的method
   * @param {*} type 维度的数据类型
   */
  handleGetMethodList(type: 'string' | 'time') {
    if (type === 'time') {
      return TIME_CONDITION_METHOD_LIST;
    }
    return STRING_CONDITION_METHOD_LIST;
  }

  /** 选中条件下拉值 */
  handelMenuSelect(item) {
    const condition = this.samplingRulesGroup[this.curGroupConditionIndex][this.curConditionIndex];
    if (!condition) return;
    condition[this.curConditionProp] = item?.id;
    this.handleConditionChange();
  }

  /** 隐藏条件下拉选框 */
  handleMenuHidden() {
    this.curSelectTarget = null;
    this.menuList = [];
    this.showSelectMenu = false;
  }

  /**
   * @description: 添加条件
   */
  async handleAddCondition(gIndex) {
    const key = this.samplingRulesGroup[gIndex][this.samplingRulesGroup[gIndex].length - 1]?.key;
    const keyIndex = this.samplingRules.findIndex(item => item.key === key);
    this.samplingRules.splice(keyIndex + 1, 0, this.handleGetDefaultCondition('and'));

    this.handleConditionChange();
    setTimeout(() => {
      (
        this.$refs[`selectInput-${gIndex}-${this.samplingRulesGroup[gIndex].length - 1}`] as SimpleSelectInput
      ).inputWrapRef.click();
      (
        this.$refs[`selectInput-${gIndex}-${this.samplingRulesGroup[gIndex].length - 1}`] as SimpleSelectInput
      ).inputRef.focus();
    }, 100);
  }

  /** 添加默认规则 */
  handleGetDefaultCondition(condition = '') {
    return Object.assign(
      {},
      {
        key: '',
        method: '',
        value: [],
        key_alias: '',
        type: '',
      },
      condition ? { condition } : {}
    );
  }

  /* 删除条件 */
  handleDeleteKey(gIndex: number, index: number) {
    const groups = deepClone(this.samplingRulesGroup);
    const groupItem = groups[gIndex];
    const deleteList = groupItem.splice(index, 1);

    // if (!gIndex && !groupItem.length && groups.length === 1) {
    //   groups.push([this.handleGetDefaultCondition(false)]);
    // }

    if (groupItem[index]) {
      if (gIndex === 0) {
        // biome-ignore lint/performance/noDelete: <explanation>
        delete groupItem[index].condition;
      } else if (index === 0) {
        groupItem[index].condition = 'or';
      }
    }

    if (deleteList?.[0]) {
      const list = groups.reduce((prev, cur) => prev.concat(cur), []);
      if (list[0]?.condition === 'or') {
        // biome-ignore lint/performance/noDelete: <explanation>
        delete list[0].condition;
      }
      this.samplingRules.splice(0, this.samplingRules.length, ...list);
      this.handleConditionChange();
    }
  }

  /** 格式化规则列表渲染 */
  handleConditionChange() {
    this.samplingRules = this.samplingRules.map((item, index) => {
      const result = item;
      if (index && !item.condition) {
        result.condition = 'and';
      }
      return result;
    });

    let groupIndex = 0;
    const parseList = [];

    this.samplingRules.forEach(item => {
      const curIndex = item.condition === 'or' ? groupIndex + 1 : groupIndex;
      groupIndex = curIndex;
      if (!parseList[curIndex]) {
        parseList.push([]);
      }

      parseList[groupIndex].push(item);
    });
    this.samplingRulesGroup.splice(0, this.samplingRulesGroup.length, ...parseList);
  }

  /** 是否显示添加规则按钮 */
  showRuleAdd(index) {
    if (!this.samplingRules.length) return false;
    const { key, value } = this.samplingRulesGroup[index][this.samplingRulesGroup[index].length - 1];
    return key && (typeTools.isNumber(value) ? value : (value as any)?.length > 0);
  }

  /** 修改采样类型 */
  handleSamplerTypeChange() {
    if (this.formData.sampler_type === 'tail') {
      this.samplingRules = this.formData.tail_conditions || [];
      // if (!this.samplingRules.length) {
      //   this.samplingRules.push(this.handleGetDefaultCondition(false));
      //   this.handleConditionChange();
      // }
    }
  }

  /** 添加新的一行采样规则 */
  handleNewRowCondition() {
    const condition = this.samplingRules.length ? 'or' : '';
    this.samplingRules.push(this.handleGetDefaultCondition(condition));
    this.handleConditionChange();
  }

  /** 指定不储存，则不能开启慢语句 */
  handleChangeTraceMode(card) {
    if (card.trace_mode === 'closed') {
      card.enabled_slow_sql = false;
    }
  }
  /** 新增自定义服务 */
  handleAddCustomService() {
    (this.$refs.customService as InstanceType<typeof CustomService>)?.handleAddService();
  }
  /** 数据上报 */
  renderDataReporting() {
    return (
      <div class={['form-content', 'form-content-row-m16', { 'form-content-switch-edit': this.isEditing }]}>
        {this.isEditing
          ? [
              <bk-form
                key='form-data-reporting'
                class='edit-config-form'
              >
                <div
                  style='height: 20px'
                  class='item-row'
                >
                  <bk-form-item
                    label={`${this.$t('指标')}`}
                    label-width={116}
                  >
                    <bk-switcher
                      v-model={this.appInfo.is_enabled_metric}
                      v-authority={{ active: !this.authority.MANAGE_AUTH }}
                      pre-check={() =>
                        this.handleEnablePreCheck(this.appInfo.is_enabled_metric, ETelemetryDataType.metric)
                      }
                      size='small'
                      theme='primary'
                    />
                  </bk-form-item>
                  <bk-form-item
                    class='form-flex-item'
                    label={`${this.$t('日志')}`}
                    label-width={116}
                  >
                    <bk-switcher
                      v-model={this.appInfo.is_enabled_log}
                      v-authority={{ active: !this.authority.MANAGE_AUTH }}
                      pre-check={() => this.handleEnablePreCheck(this.appInfo.is_enabled_log, ETelemetryDataType.log)}
                      size='small'
                      theme='primary'
                    />
                  </bk-form-item>
                </div>
                <div
                  key='form-data-reporting'
                  style='height: 20px'
                  class='item-row'
                >
                  <bk-form-item
                    label={`${this.$t('调用链')}`}
                    label-width={116}
                  >
                    <bk-switcher
                      v-model={this.appInfo.is_enabled_trace}
                      v-authority={{ active: !this.authority.MANAGE_AUTH }}
                      pre-check={() =>
                        this.handleEnablePreCheck(this.appInfo.is_enabled_trace, ETelemetryDataType.trace)
                      }
                      size='small'
                      theme='primary'
                    />
                  </bk-form-item>
                  <bk-form-item
                    class='form-flex-item'
                    label={`${this.$t('性能分析')}`}
                    label-width={116}
                  >
                    <bk-switcher
                      v-model={this.appInfo.is_enabled_profiling}
                      v-authority={{ active: !this.authority.MANAGE_AUTH }}
                      pre-check={() =>
                        this.handleEnablePreCheck(this.appInfo.is_enabled_profiling, ETelemetryDataType.profiling)
                      }
                      size='small'
                      theme='primary'
                    />
                  </bk-form-item>
                </div>
              </bk-form>,
            ]
          : [
              <div
                key='switch-metric'
                class='item-row'
              >
                <EditableFormItem
                  formType='tag'
                  label={this.$t('指标')}
                  showEditable={false}
                  tagTheme={this.appInfo.is_enabled_metric ? 'success' : ''}
                  value={[this.appInfo.is_enabled_metric ? this.$t('已开启') : this.$t('未开启')]}
                />
                <EditableFormItem
                  formType='tag'
                  label={this.$t('日志')}
                  showEditable={false}
                  tagTheme={this.appInfo.is_enabled_log ? 'success' : ''}
                  value={[this.appInfo.is_enabled_log ? this.$t('已开启') : this.$t('未开启')]}
                />
              </div>,
              <div
                key='switch-trace'
                class='item-row'
              >
                <EditableFormItem
                  formType='tag'
                  label={this.$t('调用链')}
                  showEditable={false}
                  tagTheme={this.appInfo.is_enabled_trace ? 'success' : ''}
                  value={[this.appInfo.is_enabled_trace ? this.$t('已开启') : this.$t('未开启')]}
                />
                <EditableFormItem
                  formType='tag'
                  label={this.$t('性能分析')}
                  showEditable={false}
                  tagTheme={this.appInfo.is_enabled_profiling ? 'success' : ''}
                  value={[this.appInfo.is_enabled_profiling ? this.$t('已开启') : this.$t('未开启')]}
                />
              </div>,
            ]}
      </div>
    );
  }
  /** 渲染基础信息 */
  renderBaseInfo() {
    return (
      <div class={['form-content', 'form-content-row-m12', { 'form-content-edit': this.isEditing }]}>
        {this.isEditing
          ? [
              <div
                key='base_app_name'
                class='item-row'
              >
                <EditableFormItem
                  formType='input'
                  label={this.$t('应用名')}
                  showEditable={false}
                  value={this.appInfo.app_name}
                />
                <EditableFormItem
                  authority={this.authority.MANAGE_AUTH}
                  formType='password'
                  label='Token'
                  showEditable={false}
                  updateValue={() => this.handleUpdateValue()}
                  value={this.secureKey}
                />
              </div>,
              <bk-form
                key='edit-base-info-form'
                class='edit-config-form'
                {...{
                  props: {
                    model: this.formData,
                    rules: this.rules,
                  },
                }}
                ref='editInfoForm'
                label-width={116}
              >
                <bk-form-item
                  error-display-type='normal'
                  label={this.$t('应用别名')}
                  property='app_alias'
                  required
                >
                  <bk-input
                    class='alias-name-input'
                    v-model={this.formData.app_alias}
                  />
                </bk-form-item>
                <bk-form-item
                  label={this.$t('描述')}
                  property='description'
                >
                  <bk-input
                    class='description-input'
                    v-model={this.formData.description}
                    maxlength='100'
                    type='textarea'
                    show-word-limit
                  />
                </bk-form-item>
              </bk-form>,
            ]
          : [
              <div
                key={'base-info-app-name'}
                class='item-row'
              >
                <EditableFormItem
                  formType='input'
                  label={this.$t('应用名')}
                  showEditable={false}
                  value={this.appInfo.app_name}
                />
                <EditableFormItem
                  authority={this.authority.MANAGE_AUTH}
                  authorityName={authorityMap.MANAGE_AUTH}
                  formType='input'
                  label={this.$t('应用别名')}
                  showEditable={false}
                  value={this.appInfo.app_alias}
                />
              </div>,
              <div
                key='base-info-create_user'
                class='item-row'
              >
                <EditableFormItem
                  formType='custom'
                  label={this.$t('创建人')}
                  showEditable={false}
                  value={this.appInfo.create_user}
                >
                  <template slot='custom'>
                    <span class='text-content'>
                      {this.appInfo.create_user ? <bk-user-display-name user-id={this.appInfo.create_user} /> : '--'}
                    </span>
                  </template>
                </EditableFormItem>
                <EditableFormItem
                  authority={this.authority.MANAGE_AUTH}
                  authorityName={authorityMap.MANAGE_AUTH}
                  formType='input'
                  label={this.$t('描述')}
                  showEditable={false}
                  value={this.appInfo.description}
                />
              </div>,
              <div
                key='base-info-create_time'
                class='item-row'
              >
                <EditableFormItem
                  formType='input'
                  label={this.$t('创建时间')}
                  showEditable={false}
                  value={this.appInfo.create_time}
                />
                <EditableFormItem
                  authority={this.authority.MANAGE_AUTH}
                  formType='password'
                  label='Token'
                  showEditable={false}
                  updateValue={() => this.handleUpdateValue()}
                  value={this.secureKey}
                />
              </div>,
            ]}
      </div>
    );
  }
  /** 渲染Apdex设置 */
  renderApdex() {
    return [
      <div
        key='apdex-text'
        style='position:relative'
        class='panel-intro'
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
      </div>,
      <div
        key='apdex-form'
        class='form-content'
      >
        {this.isEditing ? (
          <bk-form
            class='edit-config-form grid-form'
            {...{
              props: {
                model: this.formData,
                rules: this.rules,
              },
            }}
            ref='editApdexForm'
            label-width={116}
          >
            {this.apdexOptionList.map(apdex => (
              <bk-form-item
                key={apdex.id}
                error-display-type='normal'
                label={apdex.name}
                property={apdex.id}
              >
                <bk-input
                  class='apdex-input'
                  v-model={this.formData[apdex.id]}
                  show-controls={false}
                  type='number'
                >
                  <template slot='append'>
                    <div class='right-unit'>ms</div>
                  </template>
                </bk-input>
              </bk-form-item>
            ))}
          </bk-form>
        ) : (
          <div class='grid-form'>
            {this.apdexOptionList.map(apdex => (
              <div
                key={apdex.id}
                class='display-item'
              >
                <label for={apdex.id}>{apdex.name}</label>
                <span>{this.appInfo.application_apdex_config[apdex.id] ?? '--'}</span>
                <span class='unit'>ms</span>
              </div>
            ))}
          </div>
        )}
      </div>,
    ];
  }
  render() {
    return (
      <div class='conf-content base-info-wrap'>
        <PanelItem title={this.$t('基础信息')}>{this.renderBaseInfo()}</PanelItem>
        <PanelItem title={this.$t('数据上报')}>{this.renderDataReporting()}</PanelItem>
        {this.isShowLog2TracesFormItem && (
          <PanelItem
            flexDirection='column'
            title='Logs to Traces'
          >
            <div class='form-content'>
              {this.isEditing
                ? [
                    <bk-form
                      key='editLog2TracesForm'
                      class='edit-config-form'
                      {...{
                        props: {
                          model: this.formData,
                          rules: this.rules,
                        },
                      }}
                      ref='editInfoForm'
                      label-width={116}
                    >
                      <bk-form-item
                        error-display-type='normal'
                        label={this.$t('采集目标')}
                        property='plugin_config.target_nodes'
                        required
                      >
                        <div style='display: flex;align-items: center;'>
                          <bk-button
                            class='btn-target-collect'
                            icon='plus'
                            theme='default'
                            onClick={() => (this.selectorDialog.isShow = true)}
                          >
                            {this.$t('选择目标')}
                          </bk-button>
                          {this.formData.plugin_config.target_nodes.length > 0 && (
                            <i18n
                              style='margin-left: 8px;'
                              path={this.selectedTargetTips[this.formData.plugin_config.target_node_type]}
                            >
                              <span style='color: #4e99ff;'>{this.formData.plugin_config.target_nodes.length}</span>
                            </i18n>
                          )}
                        </div>
                      </bk-form-item>
                      <bk-form-item
                        error-display-type='normal'
                        label={this.$t('日志路径')}
                        property='plugin_config.paths'
                        required
                      >
                        {this.formData.plugin_config.paths.map((path, index) => (
                          <div key={`log_path_${index}`}>
                            <div
                              style={{
                                display: 'flex',
                                alignItems: 'center',
                                marginBottom:
                                  index > 0 && index < this.formData.plugin_config.paths.length - 1 && '20px',
                              }}
                            >
                              <bk-input
                                style='width: 490px;'
                                v-model={this.formData.plugin_config.paths[index]}
                                placeholder={this.$t('请输入')}
                              />
                              <bk-icon
                                class='log-path-icon log-path-icon-plus'
                                type='plus-circle-shape'
                                onClick={() => this.formData.plugin_config.paths.push('')}
                              />
                              <bk-icon
                                class={{
                                  'log-path-icon': true,
                                  'log-path-icon-minus': true,
                                  disabled: this.formData.plugin_config.paths.length <= 1,
                                }}
                                type='minus-circle-shape'
                                onClick={() =>
                                  this.formData.plugin_config.paths.length > 1 &&
                                  this.formData.plugin_config.paths.splice(index, 1)
                                }
                              />
                            </div>
                            {index === 0 && (
                              <div class='log-path-hint'>{this.$t('日志文件为绝对路径，可使用通配符')}</div>
                            )}
                          </div>
                        ))}
                      </bk-form-item>
                      <bk-form-item
                        error-display-type='normal'
                        label={this.$t('日志字符集')}
                        property='plugin_config.data_encoding'
                        required
                      >
                        <bk-select
                          style='width: 490px;'
                          v-model={this.formData.plugin_config.data_encoding}
                          disabled={this.isFetchingEncodingList}
                        >
                          {this.logAsciiList.map(item => (
                            <bk-option
                              id={item.id}
                              key={item.id}
                              name={item.name}
                            />
                          ))}
                        </bk-select>
                      </bk-form-item>
                    </bk-form>,
                  ]
                : [
                    <div
                      key='collection-target'
                      class='item-row'
                    >
                      <EditableFormItem
                        value={this.$t(this.selectedTargetTips[this.appInfo?.plugin_config?.target_node_type], [
                          this.appInfo?.plugin_config?.target_nodes?.length || 0,
                        ])}
                        authority={this.authority.MANAGE_AUTH}
                        authorityName={authorityMap.MANAGE_AUTH}
                        formType='input'
                        label={this.$t('采集目标')}
                        showEditable={false}
                      />
                    </div>,
                    <div
                      key='collection-log-path'
                      class='item-row'
                    >
                      <div class='log-path-item-row'>
                        <div class='label'>{this.$t('日志路径')}</div>
                        <div class='value-container'>
                          {this.appInfo.plugin_config.paths.map(path => (
                            <div
                              key={path}
                              class='value'
                            >
                              {path}
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>,
                    <div
                      key='collection-data_encoding'
                      class='item-row'
                    >
                      <EditableFormItem
                        authority={this.authority.MANAGE_AUTH}
                        authorityName={authorityMap.MANAGE_AUTH}
                        formType='input'
                        label={this.$t('日志字符集')}
                        showEditable={false}
                        value={this.appInfo.plugin_config.data_encoding}
                      />
                    </div>,
                  ]}
              <div class='item-row' />
            </div>
          </PanelItem>
        )}
        <PanelItem
          class='tips-panel-item'
          flexDirection='column'
          title={this.$t('Apdex设置')}
        >
          <div
            style='position:relative'
            class='panel-intro'
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
              <bk-form
                class='edit-config-form grid-form'
                {...{
                  props: {
                    model: this.formData,
                    rules: this.rules,
                  },
                }}
                ref='editApdexForm'
                label-width={116}
              >
                {this.apdexOptionList.map(apdex => (
                  <bk-form-item
                    key={apdex.id}
                    error-display-type='normal'
                    label={apdex.name}
                    property={apdex.id}
                  >
                    <bk-input
                      class='apdex-input'
                      v-model={this.formData[apdex.id]}
                      show-controls={false}
                      type='number'
                    >
                      <template slot='append'>
                        <div class='right-unit'>ms</div>
                      </template>
                    </bk-input>
                  </bk-form-item>
                ))}
              </bk-form>
            ) : (
              <div class='grid-form'>
                {this.apdexOptionList.map(apdex => (
                  <div
                    key={apdex.name}
                    class='display-item'
                  >
                    <label for={apdex.id}>{apdex.name}</label>
                    <span>{this.appInfo.application_apdex_config[apdex.id] ?? '--'}</span>
                    <span class='unit'>ms</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </PanelItem>
        <PanelItem
          class='tips-panel-item'
          flexDirection='column'
          title={this.$t('采样配置')}
        >
          <div
            style='position:relative'
            class='panel-intro'
          >
            {this.$t(
              ' 根据应用的数据量情况进行设置，如果应用的trace数据量非常大，不仅影响程序的输出、网络的消耗，也需要更大的集群资源成本。 在这种情况下会考虑进行采集，注意错误的Span默认是会被采集不会被采样。'
            )}
          </div>
          <div class='form-content'>
            {this.isEditing ? (
              <bk-form
                class={['edit-config-form', { 'form-content-edit': this.isEditing }]}
                {...{
                  props: {
                    model: this.formData,
                    rules: this.rules,
                  },
                }}
                ref='editSamplerForm'
                label-width={116}
              >
                <bk-form-item
                  error-display-type='normal'
                  label={this.$t('采样类型')}
                  property='sampler_type'
                >
                  <bk-select
                    class='sampling-type-select'
                    vModel={this.formData.sampler_type}
                    clearable={false}
                    onChange={this.handleSamplerTypeChange}
                  >
                    {this.samplingTypeList.map(option => (
                      <bk-option
                        id={option.id}
                        key={option.id}
                        name={option.name}
                      />
                    ))}
                  </bk-select>
                  {this.formData.sampler_type === 'tail' && (
                    <i class='icon-monitor icon-hint sampling-hint'>
                      <span>
                        {this.$t('单个 trace 中 30 分钟没有 span 上报，会自动结束；单个 trace 最大时长 1 天')}
                      </span>
                    </i>
                  )}
                </bk-form-item>
                {this.formData.sampler_type !== 'empty' ? (
                  <bk-form-item
                    error-display-type='normal'
                    label={this.$t('采样比例')}
                    property='sampler_percentage'
                  >
                    <bk-input
                      class='sampling-rate-input'
                      v-model={this.formData.sampler_percentage}
                      show-controls={false}
                      type='number'
                    >
                      <template slot='append'>
                        <div class='right-unit'>%</div>
                      </template>
                    </bk-input>
                    <i class='icon-monitor icon-hint sampling-hint'>
                      <span>{this.$t('对非必采的部分按TraceID进行采样')}</span>
                    </i>
                  </bk-form-item>
                ) : (
                  ''
                )}
                {this.formData.sampler_type === 'tail' ? (
                  <bk-form-item
                    class='sampling-rule-form-item'
                    label={this.$t('必采规则')}
                    property='sampler_rules'
                  >
                    <div style='position:relative;'>
                      {this.samplingRulesGroup.length > 1 ? (
                        <div class='sampling-rule-brackets'>
                          <div class='or-condition'>OR</div>
                        </div>
                      ) : (
                        ''
                      )}
                      {this.samplingRulesGroup.map((group, gIndex) => (
                        <div
                          key={`sampling_${gIndex}`}
                          class='sampling-rule-item'
                        >
                          {group.map((item, index) => [
                            item.condition && item.key && index > 0 ? (
                              <input
                                key={`condition-${index}-${item.key}`}
                                style={{ display: item.condition ? 'block' : 'none' }}
                                class='condition-item-condition'
                                value={item.condition.toLocaleUpperCase()}
                                readonly
                              />
                            ) : undefined,
                            <SimpleSelectInput
                              key={`selectInput-${gIndex}-${index}`}
                              ref={`selectInput-${gIndex}-${index}`}
                              v-bk-tooltips={{
                                content: item.key,
                                trigger: 'mouseenter',
                                zIndex: 9999,
                                disabled: !item.key,
                                boundary: document.body,
                                allowHTML: false,
                              }}
                              list={this.samplingRuleOptions}
                              placeholder={window.i18n.t('请输入') as string}
                              value={item.key_alias}
                              onChange={v => this.handleRuleKeyChange(item, v, gIndex, index)}
                              onNullBlur={() => this.handleDeleteKey(gIndex, index)}
                            >
                              <div
                                class='extension'
                                slot='extension'
                                on-click={() => this.handleDeleteKey(gIndex, index)}
                              >
                                <i class='icon-monitor icon-chahao' />
                                <span>{this.$t('删除')}</span>
                              </div>
                            </SimpleSelectInput>,
                            item.key_alias
                              ? [
                                  <span
                                    key={`method-${index}-${item.key}`}
                                    class='condition-item-method'
                                    on-click={e => this.handleToggleMethod(e, { gIndex, index, prop: 'method' })}
                                  >
                                    {this.handleGetMethodNameById(item.method)}
                                  </span>,
                                  item.type === 'time' ? (
                                    // <CycleInput
                                    //   class='form-interval'
                                    //   v-model={item.value}
                                    //   needAuto={false}
                                    //   options={this.cycleInputOptions}
                                    //   defaultUnit={'ms'}
                                    //   onUnitChange={(v: string) => this.handleSamplingRuleValueUnitChange(item, v)}
                                    //   onChange={(v: number) => this.handleSamplingRuleValueChange(item, v)}
                                    // />
                                    <CycleInput
                                      key='condition-form-interval'
                                      class='form-interval'
                                      v-model={item.value}
                                      minSec={1}
                                      needAuto={false}
                                      onChange={(v: number) => this.handleSamplingRuleValueChange(item, v)}
                                    />
                                  ) : (
                                    <bk-tag-input
                                      key={`value-${gIndex}-${index}-${item.key}-${JSON.stringify(
                                        this.samplingRuleValueMap[item.key] || []
                                      )}`}
                                      class='condition-item-value'
                                      list={
                                        this.samplingRuleValueMap[item.key] ? this.samplingRuleValueMap[item.key] : []
                                      }
                                      trigger='focus'
                                      value={item.value}
                                      allow-auto-match
                                      allow-create
                                      has-delete-icon
                                      // paste-fn={v => this.handlePaste(v, item)}
                                      on-change={(v: string[]) => this.handleSamplingRuleValueChange(item, v)}
                                    />
                                  ),
                                ]
                              : undefined,
                          ])}
                          <span
                            style={{ display: this.showRuleAdd(gIndex) ? 'flex' : 'none' }}
                            class='condition-add'
                            on-click={() => this.handleAddCondition(gIndex)}
                          >
                            <i class='bk-icon icon-plus' />
                          </span>
                        </div>
                      ))}
                    </div>
                    <bk-button
                      class='add-rule-btn'
                      icon='plus'
                      size='small'
                      theme='primary'
                      outline
                      text
                      on-click={() => this.handleNewRowCondition()}
                    >
                      {this.$t('添加规则')}
                    </bk-button>
                  </bk-form-item>
                ) : (
                  ''
                )}
                {/* <div class="panel-tips">
                <label>{this.$t('强调说明')}</label>
                <span>{this.$t('错误的Span一定会采集')}</span>
              </div> */}
              </bk-form>
            ) : (
              <div class='grid-form'>
                <div class='display-item'>
                  <label for=''>{this.$t('采样类型')}</label>
                  <span>{this.samplingTypeMaps[this.appInfo.application_sampler_config?.sampler_type] || '--'}</span>
                </div>
                {this.appInfo.application_sampler_config.sampler_type !== 'empty' ? (
                  <div class='display-item'>
                    <label for=''>{this.$t('采样比例')}</label>
                    <span>
                      {this.appInfo.application_sampler_config?.sampler_percentage
                        ? `${this.appInfo.application_sampler_config?.sampler_percentage}%`
                        : '--'}
                    </span>
                  </div>
                ) : (
                  ''
                )}
                {this.appInfo.application_sampler_config.sampler_type === 'tail' ? (
                  <div class='display-item sampling-rules-item'>
                    <label for=''>{this.$t('必采规则')}</label>
                    <div class='sampling-rules'>
                      {this.samplingRulesGroup.length > 1 ? (
                        <div class='sampling-rule-brackets'>
                          <div class='or-condition'>OR</div>
                        </div>
                      ) : (
                        ''
                      )}
                      {this.samplingRulesGroup.map((group, index) => (
                        <div
                          key={`group_${index}`}
                          class='rule-item'
                        >
                          {group
                            .filter(item => !!item.key_alias)
                            .map((item, index) => (
                              <span
                                key={`condition-item-${item.method}`}
                                class='condition-item'
                              >
                                {index && item.condition ? (
                                  <span class='and-condition'>{item.condition.toLocaleUpperCase()}</span>
                                ) : (
                                  ''
                                )}
                                <span>{item.key_alias}</span>
                                <span class='method'>{this.handleGetMethodNameById(item.method)}</span>
                                <span>{item.type === 'string' ? item.value.join(',') : `${item.value}s`}</span>
                              </span>
                            ))}
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  ''
                )}
              </div>
            )}
          </div>
        </PanelItem>
        <PanelItem
          class='tips-panel-item'
          flexDirection='column'
          title={this.$t('实例名配置')}
        >
          <div
            style='position:relative'
            class='panel-intro'
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
                    key={instance.name}
                    class='instanct-wrap'
                  >
                    <div class='drag-item'>
                      <div
                        key={instance.value}
                        class={[
                          'instance-card',
                          {
                            'active-item': index === this.drag.active,
                            'disabled-item': !this.isEditing,
                          },
                        ]}
                        draggable={this.isEditing}
                        onDragend={this.handleDragend}
                        onDragenter={() => this.handleDragEnter(index)}
                        onDragleave={this.handleDragLeave}
                        onDragover={evt => this.handleDragOver(evt, index)}
                        onDragstart={evt => this.handleDragStart(evt, index)}
                        onDrop={this.handleDrop}
                      >
                        {this.isEditing && <span class='icon-monitor icon-mc-tuozhuai' />}
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
                        { 'is-disabled': this.instanceOptionList.length === this.localInstanceList.length },
                      ]}
                      v-bk-tooltips={{
                        content: this.$t('已经没有可用的维度'),
                        disabled: this.instanceOptionList.length !== this.localInstanceList.length,
                        allowHTML: false,
                      }}
                      onClick={() =>
                        this.instanceOptionList.length === this.localInstanceList.length
                          ? false
                          : (this.showInstanceSelector = true)
                      }
                    >
                      <span class='icon-monitor icon-plus-line' />
                    </div>
                    {this.showInstanceSelector && (
                      <bk-select
                        class='instance-select'
                        ext-popover-cls='instance-select-popover'
                        popover-width={300}
                        searchable
                        show-on-init
                        onChange={v => this.handleSelectInstance(v)}
                      >
                        {this.instanceOptionList.map(option => (
                          <bk-option
                            id={option.id}
                            key={option.id}
                            disabled={this.localInstanceList.some(val => val.id === option.id)}
                            name={option.name}
                          >
                            <div
                              class='instance-config-option'
                              v-bk-tooltips={{
                                content: this.$t('已经添加'),
                                disabled: !this.localInstanceList.some(val => val.id === option.id),
                                allowHTML: false,
                              }}
                            >
                              <span class='instance-name'>{option.name}</span>
                              <span class='instance-alias'>{option.alias}</span>
                            </div>
                          </bk-option>
                        ))}
                      </bk-select>
                    )}
                    {this.isEditing && this.localInstanceList.length === 0 && (
                      <span class='add-instance-wrap-tips'>
                        <i class='bk-icon icon-info' />
                        <span>{this.$t('至少需要一个字段')}</span>
                      </span>
                    )}
                  </li>
                )}
              </transition-group>
            </div>
            <div class='panel-tips'>
              <label for=''>{this.$t('样例展示')}</label>
              <span>{this.sampleStr}</span>
            </div>
          </div>
        </PanelItem>
        {/* TODO：记得翻译 */}
        <PanelItem
          flexDirection='column'
          title={this.$t('DB设置')}
        >
          <div
            style='position:relative; margin-bottom: 8px'
            class='panel-intro form-content'
          >
            {this.isEditing ? (
              <div class='db-config-title-container'>
                <div style='display: flex;align-items: center;margin-bottom: 12px;'>
                  <span style='margin-right: 12px'>{this.$t('DB类型')}</span>
                  <bk-dropdown-menu trigger='click'>
                    <bk-button
                      slot='dropdown-trigger'
                      size='small'
                      text
                    >
                      <div style={{ display: 'flex', alignItems: 'baseline' }}>
                        <bk-icon
                          style='margin-right: 5px;'
                          type='plus-circle'
                        />
                        <span>{this.$t('指定DB')}</span>
                      </div>
                    </bk-button>

                    <ul
                      class='bk-dropdown-list'
                      slot='dropdown-content'
                    >
                      {this.appInfo.application_db_system.map(s => {
                        return (
                          <li key={s}>
                            <a
                              key={s}
                              class={{
                                'dropdown-list-item-disabled': !!this.appInfo.application_db_config.find(
                                  option => s === option.db_system
                                ),
                              }}
                              href='javascript:;'
                              onClick={() => this.addDBType(s)}
                            >
                              {s}
                            </a>
                          </li>
                        );
                      })}
                    </ul>
                  </bk-dropdown-menu>
                </div>

                <div class='card-list-container'>
                  {this.appInfo.application_db_config.map((card, index) => {
                    return (
                      <div
                        key={`${card.db_system}_${index}`}
                        class='db-config-card'
                      >
                        <div
                          class={{
                            'title-bar': true,
                            'is-not-default': index > 0,
                          }}
                        >
                          <span class='text'>{card.db_system || this.$t('默认')}</span>
                          {index > 0 && (
                            <bk-icon
                              class='close'
                              type='close'
                              onClick={() => this.deleteCurrentConfigCard(index)}
                            />
                          )}
                        </div>

                        <div class='card-container'>
                          <div>
                            <bk-form
                              label-width={82}
                              {...{
                                props: {
                                  model: card,
                                  rules: this.DBTypeRules[index],
                                },
                              }}
                              ref={`cardForm${index}`}
                            >
                              <bk-form-item
                                error-display-type='normal'
                                label={this.$t('存储方式')}
                                property='trace_mode'
                                required
                              >
                                <bk-radio-group
                                  v-model={card.trace_mode}
                                  onChange={this.handleChangeTraceMode.bind(this, card)}
                                >
                                  <bk-radio-button value='origin'>{this.$t('原始命令')}</bk-radio-button>
                                  <bk-radio-button value='no_parameters'>{this.$t('无参数命令')}</bk-radio-button>
                                  <bk-radio-button value='closed'>{this.$t('不储存')}</bk-radio-button>
                                </bk-radio-group>
                              </bk-form-item>
                              <bk-form-item
                                error-display-type='normal'
                                label={this.$t('启用慢语句')}
                                property='threshold'
                                required={card.enabled_slow_sql}
                              >
                                <div class='low-sql-container'>
                                  <bk-switcher
                                    v-model={card.enabled_slow_sql}
                                    disabled={card.trace_mode === 'closed'}
                                    size='small'
                                    theme='primary'
                                    onChange={() => {
                                      this.DBTypeRules[index].threshold[0].required = card.enabled_slow_sql;
                                    }}
                                  />
                                  <span
                                    style='margin-left: 16px;'
                                    class='text'
                                  >
                                    {this.$t('命令执行时间')}
                                  </span>
                                  <span>{'>'}</span>
                                  <bk-input
                                    class='excution-input'
                                    v-model={card.threshold}
                                    behavior='simplicity'
                                    disabled={card.trace_mode === 'closed'}
                                    min={0}
                                    type='number'
                                    onInput={() => {
                                      // 如果 card.threshold 为 falsy 值时，服务端的校验是不会通过的。（即使不启用慢语句时也是一样）
                                      // 这里手动判断一次，然后给予一个默认值。

                                      if (!card.threshold) card.threshold = 0;
                                    }}
                                  />
                                  <span class='text'>ms</span>
                                </div>
                              </bk-form-item>
                              <bk-form-item
                                error-display-type='normal'
                                label={this.$t('语句长度')}
                                property='length'
                                required
                              >
                                <div class='sql-length-container'>
                                  <span class='text'>{this.$t('截断')}</span>
                                  <span>{'>'}</span>
                                  <bk-input
                                    class='sql-cut-input'
                                    v-model={card.length}
                                    behavior='simplicity'
                                    min={0}
                                    type='number'
                                  />
                                  <span class='text'>{this.$t('字符')}</span>
                                </div>
                              </bk-form-item>
                            </bk-form>
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
                      key={item.db_system + index}
                      style={{
                        order: this.appInfo.application_db_config.length - index,
                      }}
                      class='db-config-card-preview-container'
                    >
                      <div
                        class={{
                          'db-config-card-preview-title': true,
                          'is-default': index === 0,
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
        <PanelItem
          class={'custom-service-panel-item pb-24'}
          flexDirection='column'
          title={this.$t('自定义服务')}
        >
          <div
            class='custom-service-add'
            slot='headerTool'
          >
            <i
              class='icon-monitor icon-mc-plus-fill'
              onClick={this.handleAddCustomService}
            />
            <span onClick={this.handleAddCustomService}>{this.$t('新增')}</span>
          </div>
          <CustomService
            ref='customService'
            style={this.isEditing ? { marginBottom: '30px' } : {}}
            data={this.appInfo}
          />
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
          <div
            class='history-btn'
            v-bk-tooltips={{ content: this.$t('变更记录'), allowHTML: false }}
            onClick={() => (this.record.show = true)}
          >
            <i class='icon-monitor icon-lishijilu' />
          </div>
          {!this.isEditing && (
            <bk-button
              class={['edit-btn', { 'edit-btn-no-authority': !this.authority.MANAGE_AUTH }]}
              v-authority={{ active: !this.authority.MANAGE_AUTH }}
              size='normal'
              theme='primary'
              outline
              onClick={() => {
                this.authority.MANAGE_AUTH
                  ? this.handleEditClick(true)
                  : this.handleShowAuthorityDetail(authorityMap.MANAGE_AUTH);
              }}
            >
              {this.$t('编辑')}
            </bk-button>
          )}
        </div>
        {this.isEditing ? (
          <div class='submit-handle'>
            <bk-button
              class='mr10'
              loading={this.isLoading}
              theme='primary'
              onClick={() => this.handleSubmit()}
            >
              {this.$t('保存')}
            </bk-button>
            <bk-button onClick={() => this.handleEditClick(false)}>{this.$t('取消')}</bk-button>
          </div>
        ) : (
          <div />
        )}
        {/* 操作记录弹窗 */}
        <ChangeRcord
          recordData={this.record.data}
          show={this.record.show}
          onUpdateShow={v => (this.record.show = v)}
        />

        {this.isShowLog2TracesFormItem && (
          <StrategyIpv6
            checkedNodes={this.formData.plugin_config.target_nodes}
            nodeType={this.formData.plugin_config.target_node_type}
            objectType={this.formData.plugin_config.target_object_type}
            showDialog={this.selectorDialog.isShow}
            onChange={this.handleSelectorChange}
            onCloseDialog={v => (this.selectorDialog.isShow = v)}
          />
        )}

        <SelectMenu
          list={this.menuList}
          min-width={60}
          show={this.showSelectMenu}
          target={this.curSelectTarget}
          on-on-hidden={() => this.handleMenuHidden()}
          on-on-select={item => this.handelMenuSelect(item)}
        />
      </div>
    );
  }
}
