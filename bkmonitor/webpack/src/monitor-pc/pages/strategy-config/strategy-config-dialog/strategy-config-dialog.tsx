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

import ResizeContainer from 'fta-solutions/components/resize-container/resize-container';
import AutoInput from 'fta-solutions/pages/setting/set-meal/set-meal-add/components/auto-input/auto-input';
import CustomTab from 'fta-solutions/pages/setting/set-meal/set-meal-add/components/custom-tab';
import {
  DEFAULT_MESSAGE_TMPL,
  DEFAULT_TITLE_TMPL,
} from 'fta-solutions/pages/setting/set-meal/set-meal-add/meal-content/meal-content-data';
import { getConvergeFunction, getVariables } from 'monitor-api/modules/action';
import { listActionConfig, listUserGroup } from 'monitor-api/modules/model';
import { deepClone } from 'monitor-common/utils/utils';

import MultiLabelSelect from '../../../components/multi-label-select/multi-label-select';
import TimePickerMultiple from '../../../components/time-picker-multiple/time-picker-multiple';
import {
  type IValue as IAlarmItem,
  type IAllDefense,
  actionConfigGroupList,
} from '../strategy-config-set-new/alarm-handling/alarm-handling';
import AlarmHandlingList from '../strategy-config-set-new/alarm-handling/alarm-handling-list';
import AlarmGroup from '../strategy-config-set-new/components/alarm-group';
import CommonItem from '../strategy-config-set-new/components/common-form-item';
import VerifyItem from '../strategy-config-set-new/components/verify-item';
import DetectionRules from '../strategy-config-set-new/detection-rules/detection-rules';
import { DEFAULT_TIME_RANGES } from '../strategy-config-set-new/judging-condition/judging-condition';
import { actionOption, intervalModeList, noticeOptions } from '../strategy-config-set-new/notice-config/notice-config';
import TemplateInput from '../strategy-config-set/strategy-template-input/strategy-template-input.vue';

import type { IGroupItem } from '../strategy-config-set-new/components/group-select';
import type { MetricDetail } from '../strategy-config-set-new/typings';

import './strategy-config-dialog.scss';

// 所有选项
const TYPE_MAP = {
  1: {
    title: window.i18n.tc('修改触发条件'),
    width: 480,
  },
  3: {
    title: window.i18n.tc('修改无数据告警'),
    width: 480,
  },
  5: {
    title: window.i18n.tc('修改恢复条件'),
    width: 400,
  },
  6: {
    title: window.i18n.tc('启/停策略'),
    width: 400,
  },
  7: {
    title: window.i18n.tc('删除策略'),
    width: 400,
  },
  8: {
    title: window.i18n.tc('增删目标'),
    width: 480,
  },
  10: {
    title: window.i18n.tc('修改标签'),
    width: 480,
  },
  12: {
    title: window.i18n.tc('修改生效时间段'),
    width: 480,
  },
  13: {
    title: window.i18n.tc('修改处理套餐'),
    width: 640,
  },
  14: {
    title: window.i18n.tc('修改告警组'),
    width: 480,
  },
  15: {
    title: window.i18n.tc('修改通知场景'),
    width: 640,
  },
  16: {
    title: window.i18n.tc('修改通知间隔'),
    width: 640,
  },
  17: {
    title: window.i18n.tc('修改通知模板'),
    width: 640,
  },
  18: {
    title: window.i18n.tc('修改告警风暴开关'),
    width: 480,
  },
  20: {
    title: window.i18n.tc('修改通知升级'),
    width: 480,
  },
  21: {
    title: window.i18n.tc('修改算法'),
    width: 640,
  },
};

// 通知间隔类型
const intervalModeTips = {
  standard: window.i18n.t('固定N分钟间隔进行通知'),
  increasing: window.i18n.t('按通知次数的指数递增，依次按N，2N，4N，8N,...依次类推执行，最大24小时'),
};

// 模板数据类型
const templateList = [
  { key: 'abnormal', label: window.i18n.tc('告警触发时') },
  { key: 'recovered', label: window.i18n.tc('告警恢复时') },
  { key: 'closed', label: window.i18n.tc('告警关闭时') },
];

interface IAlarmGroupList {
  id: number | string;
  name: string;
  receiver: string[];
}

interface IEvents {
  onConfirm?: () => void;
  onGetGroupList?: () => void;
  onHideDialog?: () => void;
}

interface IGroup {
  count?: number;
  id?: number;
  name?: string;
}
interface IProps {
  checkedList?: number[];
  dialogShow?: boolean;
  groupList?: IGroup[];
  loading?: boolean;
  selectMetricData?: MetricDetail[];
  setType?: number;
}

@Component
export default class StrategyConfigDialog extends tsc<IProps, IEvents> {
  @Prop({ type: Boolean, default: false }) loading: boolean;
  @Prop({ type: Array, default: () => [] }) checkedList: number[];
  @Prop({ type: Array, default: () => [] }) groupList: IGroup[];
  @Prop({ type: Boolean, default: false }) dialogShow: boolean;
  @Prop({ type: Number, default: 0 }) setType: number;
  @Prop({ type: Array, default: () => [] }) selectMetricData: MetricDetail[];

  @Ref('alarmHandlingList') alarmHandlingListRef: AlarmHandlingList;
  @Ref('detection-rules') readonly detectionRulesEl: DetectionRules;

  isLoading = false;

  /* 全局设置蓝鲸监控机器人发送图片是否开启， 如果关闭则禁用是否附带图片选项 */
  wxworkBotSendImage = false;

  data = {
    labels: [],
    alarmGroup: '',
    triggerCondition: {
      cycleOne: 5,
      count: 4,
      cycleTwo: 5,
      type: 1,
    },
    recover: {
      val: 5,
    },
    notice: {
      val: 120,
    },
    noDataAlarm: {
      cycle: 5,
    },
    openAlarmNoData: true,
    alarmNotice: true,
    triggerError: false,
    noticeGroupError: false,
    recoverAlarmError: false,
    recoverCycleError: false,
    noDataCycleError: false,
    enAbled: false,
    labelsError: false,
    upgradeError: '',
    timeRange: DEFAULT_TIME_RANGES, // 时间段
    alarmItems: [] as IAlarmItem[], // 告警处理
    userGroups: [] as number[], // 告警组
    userGroupsErr: false,
    signal: [], // 告警场景
    noticeInterval: {
      // 通知间隔
      interval_notify_mode: 'standard',
      notify_interval: 120,
    },
    noticeIntervalError: false,
    template: [
      // 模板数据
      { signal: 'abnormal', message_tmpl: DEFAULT_MESSAGE_TMPL, title_tmpl: DEFAULT_TITLE_TMPL },
      { signal: 'recovered', message_tmpl: DEFAULT_MESSAGE_TMPL, title_tmpl: DEFAULT_TITLE_TMPL },
      { signal: 'closed', message_tmpl: DEFAULT_MESSAGE_TMPL, title_tmpl: DEFAULT_TITLE_TMPL },
    ],
    chartImageEnabled: true, // 告警通知模板是否附带图片
    templateActive: 'abnormal', // 当前模板类型
    templateData: { signal: 'abnormal', message_tmpl: '', title_tmpl: '' }, // 当前模板数据
    templateError: '',
    needBizConverge: true,
    /** 通知升级 */
    upgrade_config: {
      /** 通知升级开关 */
      is_enabled: true,
      /** 通知升级间隔 */
      upgrade_interval: 1,
      /** 通知升级告警组 */
      user_groups: [],
    },
    // 检测规则数据
    detectionConfig: {
      unit: '',
      unitType: '', // 单位类型
      unitList: [],
      connector: 'and',
      data: [],
    },
  };
  triggerTypeList = [{ id: 1, name: window.i18n.tc('累计') }];
  numbersScope = {
    countMax: 5,
  };
  allAction: IGroupItem[] = []; // 套餐列表
  defenseList: IAllDefense[] = []; // 防御列表
  // 告警组
  alarmGroupList: IAlarmGroupList[] = [];
  // 自动填充所需列表
  messageTemplateList = [];

  cachInitData = {};

  type = '';
  get curItem() {
    return TYPE_MAP[this.setType] || {};
  }

  // 重置数据
  created() {
    this.cachInitData = JSON.parse(JSON.stringify(this.data));
    this.wxworkBotSendImage = !!window?.wxwork_bot_send_image;
  }

  @Watch('dialogShow')
  async handleDialogShow(v: boolean) {
    if (v) {
      this.isLoading = true;
      this.data = JSON.parse(JSON.stringify(this.cachInitData));
      if (this.setType === 13) {
        if (!this.allAction.length) {
          await this.getActionConfigList();
        }
        if (!this.defenseList.length) {
          await this.getDefenseList();
        }
      }
      if (this.setType === 14 || this.setType === 20) {
        await this.getAlarmGroupList();
      }
      if (this.setType === 17) {
        this.data.templateActive = this.data.template[0].signal;
        this.data.templateData = this.data.template[0];
        if (!this.messageTemplateList.length) {
          await this.getMessageTemplateList();
        }
      }
      this.isLoading = false;
    }
  }

  @Emit('hideDialog')
  handleHideDialog(v: boolean) {
    return v;
  }
  @Emit('confirm')
  handleConfirmEmit(params: any) {
    return params;
  }

  // 获取套餐数据
  async getActionConfigList() {
    const data = await listActionConfig().catch(() => []);
    this.allAction = actionConfigGroupList(data);
  }
  // 获取防御动作列表
  async getDefenseList() {
    const data = await getConvergeFunction().catch(() => []);
    this.defenseList = data;
  }
  // 获取告警组数据
  async getAlarmGroupList() {
    const data = await listUserGroup().catch(() => []);
    this.alarmGroupList = data.map(item => ({
      id: item.id,
      name: item.name,
      receiver: item.users?.map(rec => rec.display_name) || [],
    }));
  }
  // 获取自动填充列表
  async getMessageTemplateList() {
    const data = await getVariables().catch(() => []);
    const list = data
      .reduce((total, cur) => {
        return total.concat(cur.items);
      }, [])
      .map(item => ({
        id: item.name,
        name: item.desc,
        example: item.example,
      }));
    this.messageTemplateList = list;
  }
  /**
   *
   * @param num 数字
   * @param type 类型
   * @param prop 属性
   */
  handleFormatNumber(num, type, prop) {
    if (num) {
      let inputVal = num.toString();
      inputVal = inputVal.replace(/\./gi, '');
      this.data[type][prop] = Number.parseInt(inputVal, 10);
    }
  }

  /* 关闭弹窗 */
  handleAfterLeave() {
    this.isLoading = false;
    this.handleHideDialog(false);
  }

  // 确认
  async handleConfirm() {
    const params = await this.generationParam();
    if (params) {
      this.handleConfirmEmit(params);
      this.handleHideDialog(false);
    }
  }

  // 批量追加/替换参数
  handleClick(type: string) {
    this.type = type;
    this.handleConfirm();
  }

  // 提交参数
  async generationParam() {
    const setTypeMap = {
      0: () => (this.validateGroupList() ? false : { notice_group_list: this.data.alarmGroup }),
      1: () =>
        this.validateTriggerCondition()
          ? false
          : {
              trigger_config: {
                count: Number.parseInt(String(this.data.triggerCondition.count), 10),
                check_window: Number.parseInt(String(this.data.triggerCondition.cycleOne) as unknown as string, 10),
              },
            },
      2: () =>
        this.validateRecoveAlarmCondition()
          ? false
          : { alarm_interval: Number.parseInt(String(this.data.notice.val), 10) },
      3: () => {
        if (this.data.openAlarmNoData && this.validateNoDataAlarmCycle()) {
          return false;
        }
        return this.data.openAlarmNoData
          ? {
              no_data_config: {
                continuous: Number.parseInt(String(this.data.noDataAlarm.cycle), 10),
                is_enabled: this.data.openAlarmNoData,
              },
            }
          : { no_data_config: { is_enabled: this.data.openAlarmNoData } };
      },
      4: () => ({ send_recovery_alarm: this.data.alarmNotice }),
      5: () => (this.validateRecoveCycle() ? false : { recovery_config: { check_window: this.data.recover.val } }),
      /* 删除策略 */
      6: () => ({ is_enabled: this.data.enAbled }),
      7: () => ({ isDel: true }),
      /* 修改标签 */
      10: () => {
        if (this.validateLabelsList()) {
          return false;
        }
        // 构建类型映射的配置
        const buildTypeMap = () => {
          const labels = this.data.labels.map(path => path.replace(/^\/|\/$/g, ''));
          return {
            replace: {
              labels: {
                labels,
              },
            },
            append: {
              labels: {
                labels,
                append_keys: ['labels'],
              },
            },
          };
        };
        // 返回相应的配置
        return buildTypeMap()[this.type] ?? {};
      },
      /* 修改生效时间段 */
      12: () => {
        return {
          trigger_config: {
            uptime: {
              time_ranges: this.data.timeRange.map(range => ({
                start: range[0],
                end: range[1],
              })),
            },
          },
        };
      },
      /* 修改处理套餐 */
      13: async () => {
        const validate = await this.alarmHandlingListRef.validate();
        if (validate) {
          return {
            actions: this.data.alarmItems.map(item => ({
              ...item,
              options: {
                converge_config: {
                  ...item.options.converge_config,
                  timedelta: item.options.converge_config.timedelta * 60,
                },
              },
            })),
          };
        }
        return false;
      },
      /* 修改告警组 */
      14: () => {
        // 判断 userGroups 是否存在且非空
        if (!this.data.userGroups.length) {
          this.data.userGroupsErr = true;
          return {};
        }

        // 构建类型映射的配置
        const buildTypeMap = () => {
          const userGroups = this.data.userGroups;
          return {
            replace: {
              notice: {
                user_groups: userGroups,
              },
            },
            append: {
              notice: {
                user_groups: userGroups,
                append_keys: ['user_groups'],
              },
            },
          };
        };

        // 返回相应的配置
        return buildTypeMap()[this.type] ?? {};
      },
      /* 修改告警场景 */
      15: () => ({ notice: { signal: this.data.signal } }),
      /* 修改通知间隔 */
      16: () => {
        if (this.data.noticeInterval.notify_interval) {
          return {
            notice: {
              config: { ...this.data.noticeInterval, notify_interval: this.data.noticeInterval.notify_interval * 60 },
            },
          };
        }
        this.data.noticeIntervalError = true;
      },
      /* 修改告警通知模板 */
      17: () => {
        const templateValidate = this.data.template.some(template => {
          if (!template.title_tmpl) {
            this.handleChangeTemplate(template.signal);
          }
          return !template.title_tmpl;
        });
        if (templateValidate) {
          this.data.templateError = window.i18n.tc('必填项');
        } else {
          return {
            notice: {
              config: { template: this.data.template },
              options: { chart_image_enabled: this.data.chartImageEnabled },
            },
          };
        }
      },
      /* 修改告警风暴开关 */
      18: () => ({ notice: { options: { converge_config: { need_biz_converge: this.data.needBizConverge } } } }),
      20: () =>
        this.validUpgradeConfig() ? false : { notice: { options: { upgrade_config: this.data.upgrade_config } } },
      21: async () => {
        try {
          await this.detectionRulesEl.validate();
          return {
            algorithms: this.data.detectionConfig.data,
          };
        } catch {
          return false;
        }
      },
    };
    return setTypeMap[this.setType]?.() || {};
  }
  // 告警组校验
  validateGroupList() {
    this.data.noticeGroupError = !this.data.alarmGroup.length;
    return this.data.noticeGroupError;
  }

  // 触发条件校验
  validateTriggerCondition() {
    for (const key in this.data.triggerCondition) {
      if (!this.data.triggerCondition[key]) {
        this.data.triggerError = true;
        return true;
      }
    }
    const cycleOne = Number.parseInt(String(this.data.triggerCondition.cycleOne), 10);
    const count = Number.parseInt(String(this.data.triggerCondition.count), 10);
    if (cycleOne < count) {
      this.data.triggerError = true;
    } else {
      this.data.triggerError = false;
    }
    return this.data.triggerError;
  }

  /* 恢复条件校验 */
  validateRecoveAlarmCondition() {
    this.data.recoverAlarmError = !this.data.notice.val;
    return this.data.recoverAlarmError;
  }

  validateNoDataAlarmCycle() {
    this.data.noDataCycleError = !this.data.noDataAlarm.cycle;
    return this.data.noDataCycleError;
  }

  validateRecoveCycle() {
    this.data.recoverCycleError = !this.data.recover.val;
    return this.data.recoverCycleError;
  }

  validateLabelsList() {
    this.data.labelsError = !this.data.labels.length;
    return this.data.labelsError;
  }

  /** 校验通知升级 */
  validUpgradeConfig() {
    // eslint-disable-next-line @typescript-eslint/naming-convention
    const { is_enabled, upgrade_interval, user_groups } = this.data.upgrade_config;
    this.data.upgradeError = '';
    if (is_enabled && (upgrade_interval < 1 || user_groups.length === 0)) {
      this.data.upgradeError = this.$tc('通知升级必须填写时间间隔以及用户组');
    }
    return !!this.data.upgradeError;
  }

  // 取消
  handleCancel() {
    this.handleHideDialog(false);
  }

  // 告警组数据
  handleUserGroupChange(data) {
    this.data.userGroupsErr = false;
    this.data.userGroups = data;
  }

  // 告警场景
  handleSignalChange(v: string[], type: 'action' | 'notice') {
    const actions = actionOption.map(item => item.key);
    const notices = noticeOptions.map(item => item.key);
    const arr: string[] = JSON.parse(JSON.stringify(this.data.signal));
    let curActions = [];
    let curNotices = [];
    arr.forEach(item => {
      if (actions.includes(item)) {
        curActions.push(item);
      }
      if (notices.includes(item)) {
        curNotices.push(item);
      }
    });
    if (type === 'action') {
      curActions = v;
    } else {
      curNotices = v;
    }
    const curArr = curActions.concat(curNotices);
    this.data.signal = curArr.filter((item, index, arr) => arr.indexOf(item, 0) === index);
  }
  // 模板数据类型切换
  handleChangeTemplate(v: string) {
    this.data.templateActive = v;
    this.data.templateData = deepClone(this.data.template.find(item => item.signal === v));
  }

  // 模板数据输入
  noticeTemplateChange(tplStr: string) {
    this.data.templateData.message_tmpl = tplStr;
    this.templateChange();
  }

  // 模板数据
  templateChange() {
    this.data.templateError = '';
    this.data.template = this.data.template.map(item => {
      if (item.signal === this.data.templateActive) {
        return deepClone(this.data.templateData);
      }
      return item;
    });
  }

  /** 通知升级时间间隔 */
  handleUpgradeIntervalChange(val: string) {
    const num = Number.parseInt(val, 10);
    this.data.upgrade_config.upgrade_interval = Number.isNaN(num) ? 1 : num;
  }

  // 检测算法值更新
  handleDetectionRulesChange(v) {
    this.data.detectionConfig.data = v;
  }

  // 所有选项组件
  getAllTypeComponent() {
    switch (this.setType) {
      case 1:
        return (
          <div class='modify-trigger-condition'>
            {' '}
            {/* 修改触发条件 */}
            <i18n
              class='i18n'
              path='在{0}个周期内{1}满足{2}次检测算法触发异常告警'
            >
              <bk-input
                class='number-input w56'
                v-model={this.data.triggerCondition.cycleOne}
                behavior='simplicity'
                max={60}
                min={1}
                showControls={false}
                type='number'
                onChange={(v: number) => this.handleFormatNumber(v, 'triggerCondition', 'cycleOne')}
              />
              <bk-select
                style='width: 64px'
                v-model={this.data.triggerCondition.type}
                behavior='simplicity'
                clearable={false}
              >
                {this.triggerTypeList.map((item, index) => (
                  <bk-option
                    id={item.id}
                    key={index}
                    name={item.name}
                  />
                ))}
              </bk-select>
              <bk-input
                class='number-input w56'
                v-model={this.data.triggerCondition.count}
                behavior='simplicity'
                max={this.numbersScope.countMax}
                min={1}
                showControls={false}
                type='number'
                onChange={(v: number) => this.handleFormatNumber(v, 'triggerCondition', 'count')}
              />
            </i18n>
            {this.data.triggerError ? (
              <span class='trigger-condition-tips'>
                <i class='icon-monitor icon-mind-fill item-icon' /> {this.$t('要求: 满足次数&lt;=周期数')}
              </span>
            ) : undefined}
          </div>
        );
      case 3 /* 批量修改无数据告警 */:
        return [
          <div
            key='no-data-alarm'
            class='no-data-alarm'
          >
            <i18n
              class='i18n'
              path='{0}当数据连续丢失{1}个周期触发无数据告警'
            >
              <bk-switcher
                class='inline-switcher'
                v-model={this.data.openAlarmNoData}
                size='small'
                theme='primary'
              />
              <bk-input
                class='number-input'
                v-model={this.data.noDataAlarm.cycle}
                behavior='simplicity'
                disabled={!this.data.openAlarmNoData}
                min={1}
                showControls={false}
                type='number'
                onChange={(v: number) => this.handleFormatNumber(v, 'noDataAlarm', 'cycle')}
              />
            </i18n>
          </div>,
          this.data.noDataCycleError ? (
            <span
              key='no-data-error-msg'
              class='no-data-error-msg error-msg-font'
            >
              {' '}
              {this.$t('仅支持整数')}{' '}
            </span>
          ) : undefined,
        ];
      case 5 /* 修改恢复条件 */:
        return [
          <div
            key='modify-trigger-condition'
            class='modify-trigger-condition'
          >
            <i18n path='连续{0}个周期内不满足触发条件表示恢复'>
              <bk-input
                class='number-input'
                v-model={this.data.recover.val}
                behavior='simplicity'
                min={1}
                showControls={false}
                type='number'
                onChange={(v: number) => this.handleFormatNumber(v, 'recover', 'val')}
              />
            </i18n>
          </div>,
          this.data.recoverCycleError ? (
            <span
              key='recover-cycle-error-msg'
              class='recover-cycle-error-msg error-msg-font'
            >
              {this.$t('仅支持整数')}
            </span>
          ) : undefined,
        ];
      case 6 /* 启停策略 */:
        return (
          <div class='alarm-recover'>
            <bk-radio-group v-model={this.data.enAbled}>
              <bk-radio
                style='margin-right: 58px'
                value={true}
              >
                {this.$t('启用')}
              </bk-radio>
              <bk-radio value={false}>{this.$t('停用')}</bk-radio>
            </bk-radio-group>
          </div>
        );
      case 7 /* 删除策略 */:
        return (
          <div class='delete-strategy'>
            {this.$t('已选择 {n} 个策略，确定批量删除？', { n: this.checkedList.length })}
          </div>
        );
      case 10 /* 修改标签 */:
        return (
          <div class='from-item-wrap'>
            <div class='alarm-group-label'>
              {this.$t('标签')} <span class='asterisk'>*</span>
            </div>
            <MultiLabelSelect
              style='width: 100%; margin-bottom: 40px'
              autoGetList={true}
              behavior='simplicity'
              checkedNode={this.data.labels}
              mode='select'
              on-checkedChange={v => {
                this.data.labels = v;
              }}
              on-loading={v => {
                this.isLoading = v;
              }}
            />
            {this.data.labelsError ? (
              <span class='notice-error-msg error-msg-font'> {this.$t('选择标签')} </span>
            ) : undefined}
          </div>
        );
      case 12 /* 修改生效时间段 */:
        return (
          <div class='update-time'>
            <span class='title'>{this.$t('生效时间段')}：</span>
            <TimePickerMultiple v-model={this.data.timeRange} />
          </div>
        );
      case 13 /* 修改处理套餐 */:
        return (
          <AlarmHandlingList
            ref='alarmHandlingList'
            class='alarm-list'
            allAction={this.allAction}
            allDefense={this.defenseList}
            isSimple={true}
            value={this.data.alarmItems}
            onAddMeal={() => this.handleHideDialog(false)}
            onChange={v => (this.data.alarmItems = v)}
          />
        );
      case 14 /* 修改告警组 */:
        return (
          <div class='alarm-groups'>
            <span class='title'>{this.$t('告警组')}：</span>
            <AlarmGroup
              class='alarm-group'
              isSimple={true}
              list={this.alarmGroupList}
              showAddTip={false}
              value={this.data.userGroups}
              onAddGroup={() => this.handleHideDialog(false)}
              onChange={data => this.handleUserGroupChange(data)}
            >
              <span
                key={1}
                class='icon-monitor icon-mc-add'
              />
              <span
                key={2}
                class='add-tag-text'
              >
                {this.$t('选择告警组')}
              </span>
            </AlarmGroup>
            {this.data.userGroupsErr ? (
              <span class='alarm-groups-err-msg error-msg-font'> {this.$t('必填项')} </span>
            ) : undefined}
          </div>
        );
      case 15 /* 修改告警场景 */:
        return (
          <div class='effective-conditions-content'>
            <div class='content-item'>
              <span class='title'>{this.$t('告警阶段')}:</span>
              <span class='effective-conditions'>
                <bk-checkbox-group
                  value={this.data.signal}
                  on-change={v => this.handleSignalChange(v, 'notice')}
                >
                  {noticeOptions.map(item => (
                    <bk-checkbox
                      key={item.key}
                      value={item.key}
                    >
                      {item.text}
                    </bk-checkbox>
                  ))}
                </bk-checkbox-group>
              </span>
            </div>
            <div class='content-item'>
              <span class='title'>{this.$t('处理阶段')}:</span>
              <span class='effective-conditions'>
                <bk-checkbox-group
                  value={this.data.signal}
                  on-change={v => this.handleSignalChange(v, 'action')}
                >
                  {actionOption.map(item => (
                    <bk-checkbox
                      key={item.key}
                      value={item.key}
                    >
                      {item.text}
                    </bk-checkbox>
                  ))}
                </bk-checkbox-group>
              </span>
            </div>
          </div>
        );
      case 16 /* 修改通知间隔 */:
        return (
          <div class='notice-interval'>
            <span class='title'>{this.$t('通知间隔')}:</span>
            <span class='content'>
              <i18n
                class='content-interval'
                path='若产生相同的告警未确认或者未屏蔽,则{0}间隔{1}分钟再进行告警。'
              >
                <bk-select
                  class='select select-inline'
                  v-model={this.data.noticeInterval.interval_notify_mode}
                  behavior='simplicity'
                  clearable={false}
                  size='small'
                >
                  {intervalModeList.map(item => (
                    <bk-option
                      id={item.id}
                      key={item.id}
                      name={item.name}
                    />
                  ))}
                </bk-select>
                <bk-input
                  class='input-inline input-center'
                  v-model={this.data.noticeInterval.notify_interval}
                  behavior='simplicity'
                  showControls={false}
                  size='small'
                  type='number'
                  onFocus={() => (this.data.noticeIntervalError = false)}
                />
              </i18n>
              <span
                style={{ color: '#979ba5', marginTop: '-3px' }}
                class='icon-monitor icon-hint'
                v-bk-tooltips={{ content: intervalModeTips[this.data.noticeInterval.interval_notify_mode] }}
              />
            </span>
            {this.data.noticeIntervalError ? (
              <span class='notice-interval-err-msg error-msg-font'> {this.$t('必填项')} </span>
            ) : undefined}
          </div>
        );
      case 17 /* 修改告警通知模板 */:
        return (
          <div class='template-container'>
            <div class='wrap-top'>
              <CustomTab
                active={this.data.templateActive}
                panels={templateList}
                type={'text'}
                onChange={this.handleChangeTemplate}
              />
            </div>
            <div class='wrap-bottom'>
              <CommonItem
                class='template'
                title={this.$tc('告警标题')}
                isRequired
              >
                <VerifyItem
                  style={{ flex: 1 }}
                  errorMsg={this.data.templateError}
                >
                  <AutoInput
                    class='template-title'
                    v-model={this.data.templateData.title_tmpl}
                    tipsList={this.messageTemplateList}
                    on-change={this.templateChange}
                  />
                </VerifyItem>
              </CommonItem>
              <div
                style={{ marginTop: '7px' }}
                class='label-wrap'
              >
                <span class='label'>{this.$t('告警通知模板')}</span>
                <bk-checkbox
                  ext-cls='notice-template-checkbox'
                  v-model={this.data.chartImageEnabled}
                  v-bk-tooltips={{
                    content: this.$t('蓝鲸监控机器人发送图片全局设置已关闭'),
                    placements: ['top'],
                    disabled: this.wxworkBotSendImage,
                  }}
                  disabled={!this.wxworkBotSendImage}
                  on-change={this.templateChange}
                >
                  {this.$t('是否附带图片')}
                </bk-checkbox>
              </div>
              <ResizeContainer
                style='margin-top: 8px'
                height={215}
                minHeight={80}
                minWidth={200}
              >
                <TemplateInput
                  style='width: 100%; height: 100%;'
                  extCls={'notice-config-template-pop'}
                  defaultValue={this.data.templateData.message_tmpl}
                  triggerList={this.messageTemplateList}
                  onChange={this.noticeTemplateChange}
                />
              </ResizeContainer>
            </div>
          </div>
        );
      case 18 /* 修改告警风暴开关 */:
        return (
          <div class='alarm-storm'>
            <span class='title'>{this.$t('告警风暴')}:</span>
            <span class='content'>
              <bk-switcher
                v-model={this.data.needBizConverge}
                size='small'
                theme='primary'
              />
              <i class='icon-monitor icon-hint' />
              <span class='text'>
                {this.$t('当防御的通知汇总也产生了大量的风暴时，会进行本业务的跨策略的汇总通知。')}
              </span>
            </span>
          </div>
        );
      case 20 /** 修改通知升级 */:
        return (
          <div class='upgrade-config'>
            <div class='title'>{this.$t('通知升级')}</div>
            <div class='content'>
              <bk-switcher
                v-model={this.data.upgrade_config.is_enabled}
                size='small'
                theme='primary'
              />

              {this.data.upgrade_config.is_enabled && (
                <i18n
                  class='text'
                  path='当告警持续时长每超过{0}分种，将逐个按告警组升级通知'
                  tag='div'
                >
                  <bk-select
                    style='width: 70px'
                    class='notice-select'
                    v-model={this.data.upgrade_config.upgrade_interval}
                    behavior='simplicity'
                    placeholder={this.$t('输入')}
                    zIndex={99999}
                    allow-create
                    allow-enter
                    onChange={this.handleUpgradeIntervalChange}
                  >
                    <bk-option
                      id={1}
                      name={1}
                    />
                    <bk-option
                      id={5}
                      name={5}
                    />
                    <bk-option
                      id={10}
                      name={10}
                    />
                    <bk-option
                      id={30}
                      name={30}
                    />
                  </bk-select>
                </i18n>
              )}

              {this.data.upgrade_config.is_enabled && (
                <AlarmGroup
                  class='alarm-group'
                  v-model={this.data.upgrade_config.user_groups}
                  list={this.alarmGroupList}
                  showAddTip={false}
                  onAddGroup={() => this.handleHideDialog(false)}
                />
              )}
              {this.data.upgradeError ? (
                <span class='notice-error-msg error-msg-font'> {this.data.upgradeError} </span>
              ) : undefined}
            </div>
          </div>
        );
      case 21 /** 修改算法 */:
        return (
          <div class='detection-rules'>
            <DetectionRules
              key={+this.dialogShow}
              ref='detection-rules'
              connector={this.data.detectionConfig.connector}
              dataMode={'converge'}
              isEdit={false}
              metricData={this.selectMetricData}
              needShowUnit={true}
              unit={this.data.detectionConfig.unit}
              unitType={this.data.detectionConfig.unitType}
              onChange={this.handleDetectionRulesChange}
            />
          </div>
        );
      default:
        return '';
    }
  }

  // 底部组件
  getFooterComponent() {
    switch (this.setType) {
      case 6:
      case 7:
        return (
          <bk-button
            theme='primary'
            onClick={this.handleConfirm}
          >
            {this.$t('确认')}
          </bk-button>
        );
      case 10:
      case 14:
        return [
          <bk-button
            key='append'
            disabled={this.loading}
            theme='primary'
            onClick={() => this.handleClick('append')}
          >
            {' '}
            {this.$t('批量追加')}{' '}
          </bk-button>,
          <bk-button
            key='replace'
            disabled={this.loading}
            theme='primary'
            onClick={() => this.handleClick('replace')}
          >
            {' '}
            {this.$t('批量替换')}{' '}
          </bk-button>,
        ];
      default:
        return (
          <bk-button
            disabled={this.loading}
            theme='primary'
            onClick={this.handleConfirm}
          >
            {' '}
            {this.$t('保存')}{' '}
          </bk-button>
        );
    }
  }

  render() {
    return (
      <bk-dialog
        width={this.curItem.width}
        class='strategy-list-dialog'
        escClose={false}
        headerPosition={'left'}
        maskClose={false}
        title={this.curItem.title}
        value={this.dialogShow}
        on-after-leave={this.handleAfterLeave}
        on-confirm={this.handleConfirm}
      >
        <div
          class='strategy-dialog-wrap'
          v-bkloading={{ isLoading: this.loading || this.isLoading }}
        >
          {this.getAllTypeComponent()}
        </div>
        <div slot='footer'>
          {this.getFooterComponent()}
          <bk-button onClick={this.handleCancel}> {this.$t('取消')} </bk-button>
        </div>
      </bk-dialog>
    );
  }
}
