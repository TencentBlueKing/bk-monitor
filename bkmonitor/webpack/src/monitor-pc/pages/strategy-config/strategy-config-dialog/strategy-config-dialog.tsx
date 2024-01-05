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

import ResizeContainer from '../../../../fta-solutions/components/resize-container/resize-container';
import AutoInput from '../../../../fta-solutions/pages/setting/set-meal/set-meal-add/components/auto-input/auto-input';
import CustomTab from '../../../../fta-solutions/pages/setting/set-meal/set-meal-add/components/custom-tab';
import {
  DEFAULT_MESSAGE_TMPL,
  DEFAULT_TITLE_TMPL
} from '../../../../fta-solutions/pages/setting/set-meal/set-meal-add/meal-content/meal-content-data';
import { getConvergeFunction, getVariables } from '../../../../monitor-api/modules/action';
import { listActionConfig, listUserGroup } from '../../../../monitor-api/modules/model';
import { deepClone } from '../../../../monitor-common/utils/utils';
import MultiLabelSelect from '../../../components/multi-label-select/multi-label-select';
import TimePickerMultiple from '../../../components/time-picker-multiple/time-picker-multiple';
import TemplateInput from '../strategy-config-set/strategy-template-input/strategy-template-input.vue';
import {
  actionConfigGroupList,
  IAllDefense,
  IValue as IAlarmItem
} from '../strategy-config-set-new/alarm-handling/alarm-handling';
import AlarmHandlingList from '../strategy-config-set-new/alarm-handling/alarm-handling-list';
import AlarmGroup from '../strategy-config-set-new/components/alarm-group';
import CommonItem from '../strategy-config-set-new/components/common-form-item';
import { IGroupItem } from '../strategy-config-set-new/components/group-select';
import VerifyItem from '../strategy-config-set-new/components/verify-item';
import { DEFAULT_TIME_RANGES } from '../strategy-config-set-new/judging-condition/judging-condition';
import { actionOption, intervalModeList, noticeOptions } from '../strategy-config-set-new/notice-config/notice-config';

import './strategy-config-dialog.scss';

// 所有选项
const TYPE_MAP = {
  1: {
    title: window.i18n.tc('修改触发条件'),
    width: 480
  },
  3: {
    title: window.i18n.tc('修改无数据告警'),
    width: 480
  },
  5: {
    title: window.i18n.tc('修改恢复条件'),
    width: 400
  },
  6: {
    title: window.i18n.tc('启/停策略'),
    width: 400
  },
  7: {
    title: window.i18n.tc('删除策略'),
    width: 400
  },
  8: {
    title: window.i18n.tc('增删目标'),
    width: 480
  },
  10: {
    title: window.i18n.tc('修改标签'),
    width: 480
  },
  12: {
    title: window.i18n.tc('修改生效时间段'),
    width: 480
  },
  13: {
    title: window.i18n.tc('修改处理套餐'),
    width: 640
  },
  14: {
    title: window.i18n.tc('修改告警组'),
    width: 480
  },
  15: {
    title: window.i18n.tc('修改通知场景'),
    width: 640
  },
  16: {
    title: window.i18n.tc('修改通知间隔'),
    width: 640
  },
  17: {
    title: window.i18n.tc('修改通知模板'),
    width: 640
  },
  18: {
    title: window.i18n.tc('修改告警风暴开关'),
    width: 480
  }
};

// 通知间隔类型
const intervalModeTips = {
  standard: window.i18n.t('固定N分钟间隔进行通知'),
  increasing: window.i18n.t('按通知次数的指数递增，依次按N，2N，4N，8N,...依次类推执行，最大24小时')
};

// 模板数据类型
const templateList = [
  { key: 'abnormal', label: window.i18n.tc('告警触发时') },
  { key: 'recovered', label: window.i18n.tc('告警恢复时') },
  { key: 'closed', label: window.i18n.tc('告警关闭时') }
];

interface IAlarmGroupList {
  id: number | string;
  name: string;
  receiver: string[];
}

interface IGroup {
  count?: number;
  name?: string;
  id?: number;
}

interface IProps {
  loading?: boolean;
  checkedList?: number[];
  groupList?: IGroup[];
  dialogShow?: boolean;
  setType?: number;
}
interface IEvents {
  onGetGroupList?: void;
  onConfirm?: void;
  onHideDialog?: void;
}

@Component
export default class StrategyConfigDialog extends tsc<IProps, IEvents> {
  @Prop({ type: Boolean, default: false }) loading: boolean;
  @Prop({ type: Array, default: () => [] }) checkedList: number[];
  @Prop({ type: Array, default: () => [] }) groupList: IGroup[];
  @Prop({ type: Boolean, default: false }) dialogShow: boolean;
  @Prop({ type: Number, default: 0 }) setType: number;

  @Ref('alarmHandlingList') alarmHandlingListRef: AlarmHandlingList;

  isLoading = false;
  data = {
    labels: [],
    alarmGroup: '',
    triggerCondition: {
      cycleOne: 5,
      count: 4,
      cycleTwo: 5,
      type: 1
    },
    recover: {
      val: 5
    },
    notice: {
      val: 120
    },
    noDataAlarm: {
      cycle: 5
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
    timeRange: DEFAULT_TIME_RANGES, // 时间段
    alarmItems: [] as IAlarmItem[], // 告警处理
    userGroups: [] as number[], // 告警组
    userGroupsErr: false,
    signal: [], // 告警场景
    noticeInterval: {
      // 通知间隔
      interval_notify_mode: 'standard',
      notify_interval: 120
    },
    noticeIntervalError: false,
    template: [
      // 模板数据
      { signal: 'abnormal', message_tmpl: DEFAULT_MESSAGE_TMPL, title_tmpl: DEFAULT_TITLE_TMPL },
      { signal: 'recovered', message_tmpl: DEFAULT_MESSAGE_TMPL, title_tmpl: DEFAULT_TITLE_TMPL },
      { signal: 'closed', message_tmpl: DEFAULT_MESSAGE_TMPL, title_tmpl: DEFAULT_TITLE_TMPL }
    ],
    templateActive: 'abnormal', // 当前模板类型
    templateData: { signal: 'abnormal', message_tmpl: '', title_tmpl: '' }, // 当前模板数据
    templateError: '',
    needBizConverge: true
  };
  triggerTypeList = [{ id: 1, name: window.i18n.tc('累计') }];
  numbersScope = {
    countMax: 5
  };
  allAction: IGroupItem[] = []; // 套餐列表
  defenseList: IAllDefense[] = []; // 防御列表
  // 告警组
  alarmGroupList: IAlarmGroupList[] = [];
  // 自动填充所需列表
  messageTemplateList = [];

  cachInitData = {};

  get curItem() {
    return TYPE_MAP[this.setType] || {};
  }

  // 重置数据
  created() {
    this.cachInitData = JSON.parse(JSON.stringify(this.data));
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
      if (this.setType === 14 && !this.alarmGroupList.length) {
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
      receiver: item.users?.map(rec => rec.display_name) || []
    }));
  }
  // 获取自动填充列表
  async getMessageTemplateList() {
    const data = await getVariables().catch(() => []);
    const list = data
      .reduce((total, cur) => {
        total = total.concat(cur.items);
        return total;
      }, [])
      .map(item => ({
        id: item.name,
        name: item.desc,
        example: item.example
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
      this.data[type][prop] = parseInt(inputVal, 10);
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

  // 提交参数
  async generationParam() {
    const setTypeMap = {
      0: () => (this.validateGroupList() ? false : { notice_group_list: this.data.alarmGroup }),
      1: () =>
        this.validateTriggerCondition()
          ? false
          : {
              trigger_config: {
                count: parseInt(String(this.data.triggerCondition.count), 10),
                check_window: parseInt(String(this.data.triggerCondition.cycleOne) as unknown as string, 10)
              }
            },
      2: () =>
        this.validateRecoveAlarmCondition() ? false : { alarm_interval: parseInt(String(this.data.notice.val), 10) },
      3: () => {
        if (this.data.openAlarmNoData && this.validateNoDataAlarmCycle()) {
          return false;
        }
        return this.data.openAlarmNoData
          ? {
              no_data_config: {
                continuous: parseInt(String(this.data.noDataAlarm.cycle), 10),
                is_enabled: this.data.openAlarmNoData
              }
            }
          : { no_data_config: { is_enabled: this.data.openAlarmNoData } };
      },
      4: () => ({ send_recovery_alarm: this.data.alarmNotice }),
      5: () => (this.validateRecoveCycle() ? false : { recovery_config: { check_window: this.data.recover.val } }),
      /* 删除策略 */
      6: () => ({ is_enabled: this.data.enAbled }),
      7: () => ({ isDel: true }),
      /* 修改标签 */
      10: () => (this.validateLabelsList() ? false : { labels: this.data.labels }),
      /* 修改生效时间段 */
      12: () => {
        return {
          trigger_config: {
            uptime: {
              time_ranges: this.data.timeRange.map(range => ({
                start: range[0],
                end: range[1]
              }))
            }
          }
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
                  timedelta: item.options.converge_config.timedelta * 60
                }
              }
            }))
          };
        }
        return false;
      },
      /* 修改告警组 */
      14: () => {
        if (this.data.userGroups.length) {
          return {
            notice: {
              user_groups: this.data.userGroups
            }
          };
        }
        this.data.userGroupsErr = true;
      },
      /* 修改告警场景 */
      15: () => ({ notice: { signal: this.data.signal } }),
      /* 修改通知间隔 */
      16: () => {
        if (this.data.noticeInterval.notify_interval) {
          return {
            notice: {
              config: { ...this.data.noticeInterval, notify_interval: this.data.noticeInterval.notify_interval * 60 }
            }
          };
        }
        this.data.noticeIntervalError = true;
      },
      /* 修改告警通知模板 */
      17: () => {
        const templateValidate = this.data.template.some(template => {
          if (!Boolean(template.title_tmpl)) {
            this.handleChangeTemplate(template.signal);
          }
          return !Boolean(template.title_tmpl);
        });
        if (templateValidate) {
          this.data.templateError = window.i18n.tc('必填项');
        } else {
          return { notice: { config: { template: this.data.template } } };
        }
      },
      /* 修改告警风暴开关 */
      18: () => ({ notice: { options: { converge_config: { need_biz_converge: this.data.needBizConverge } } } })
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
    const cycleOne = parseInt(String(this.data.triggerCondition.cycleOne), 10);
    const count = parseInt(String(this.data.triggerCondition.count), 10);
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
                behavior='simplicity'
                onChange={(v: number) => this.handleFormatNumber(v, 'triggerCondition', 'cycleOne')}
                class='number-input w56'
                type='number'
                showControls={false}
                min={1}
                max={60}
                v-model={this.data.triggerCondition.cycleOne}
              ></bk-input>
              <bk-select
                behavior='simplicity'
                style='width: 64px'
                clearable={false}
                v-model={this.data.triggerCondition.type}
              >
                {this.triggerTypeList.map((item, index) => (
                  <bk-option
                    key={index}
                    id={item.id}
                    name={item.name}
                  ></bk-option>
                ))}
              </bk-select>
              <bk-input
                behavior='simplicity'
                onChange={(v: number) => this.handleFormatNumber(v, 'triggerCondition', 'count')}
                class='number-input w56'
                type='number'
                showControls={false}
                min={1}
                max={this.numbersScope.countMax}
                v-model={this.data.triggerCondition.count}
              ></bk-input>
            </i18n>
            {this.data.triggerError ? (
              <span class='trigger-condition-tips'>
                <i class='icon-monitor icon-mind-fill item-icon'></i> {this.$t('要求: 满足次数&lt;=周期数')}
              </span>
            ) : undefined}
          </div>
        );
      case 3 /* 批量修改无数据告警 */:
        return [
          <div class='no-data-alarm'>
            <i18n
              class='i18n'
              path='{0}当数据连续丢失{1}个周期触发无数据告警'
            >
              <bk-switcher
                class='inline-switcher'
                v-model={this.data.openAlarmNoData}
                size='small'
                theme='primary'
              ></bk-switcher>
              <bk-input
                behavior='simplicity'
                disabled={!this.data.openAlarmNoData}
                onChange={(v: number) => this.handleFormatNumber(v, 'noDataAlarm', 'cycle')}
                class='number-input'
                type='number'
                showControls={false}
                min={1}
                v-model={this.data.noDataAlarm.cycle}
              ></bk-input>
            </i18n>
          </div>,
          this.data.noDataCycleError ? (
            <span class='no-data-error-msg error-msg-font'> {this.$t('仅支持整数')} </span>
          ) : undefined
        ];
      case 5 /* 修改恢复条件 */:
        return [
          <div class='modify-trigger-condition'>
            <i18n path='连续{0}个周期内不满足触发条件表示恢复'>
              <bk-input
                behavior='simplicity'
                onChange={(v: number) => this.handleFormatNumber(v, 'recover', 'val')}
                class='number-input'
                type='number'
                showControls={false}
                min={1}
                v-model={this.data.recover.val}
              ></bk-input>
            </i18n>
          </div>,
          this.data.recoverCycleError ? (
            <span class='recover-cycle-error-msg error-msg-font'>{this.$t('仅支持整数')}</span>
          ) : undefined
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
              mode='select'
              behavior='simplicity'
              autoGetList={true}
              checkedNode={this.data.labels}
              on-loading={v => (this.isLoading = v)}
              on-checkedChange={v => (this.data.labels = v)}
            ></MultiLabelSelect>
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
            class='alarm-list'
            ref='alarmHandlingList'
            value={this.data.alarmItems}
            allAction={this.allAction}
            allDefense={this.defenseList}
            isSimple={true}
            onChange={v => (this.data.alarmItems = v)}
            onAddMeal={() => this.handleHideDialog(false)}
          ></AlarmHandlingList>
        );
      case 14 /* 修改告警组 */:
        return (
          <div class='alarm-groups'>
            <span class='title'>{this.$t('告警组')}：</span>
            <AlarmGroup
              class='alarm-group'
              list={this.alarmGroupList}
              value={this.data.userGroups}
              showAddTip={false}
              isSimple={true}
              onChange={data => this.handleUserGroupChange(data)}
              onAddGroup={() => this.handleHideDialog(false)}
            ></AlarmGroup>
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
                    <bk-checkbox value={item.key}>{item.text}</bk-checkbox>
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
                    <bk-checkbox value={item.key}>{item.text}</bk-checkbox>
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
                path='若产生相同的告警未确认或者未屏蔽,则{0}间隔{1}分钟再进行告警。'
                class='content-interval'
              >
                <bk-select
                  class='select select-inline'
                  clearable={false}
                  behavior='simplicity'
                  size='small'
                  v-model={this.data.noticeInterval.interval_notify_mode}
                >
                  {intervalModeList.map(item => (
                    <bk-option
                      key={item.id}
                      id={item.id}
                      name={item.name}
                    ></bk-option>
                  ))}
                </bk-select>
                <bk-input
                  class='input-inline input-center'
                  behavior='simplicity'
                  v-model={this.data.noticeInterval.notify_interval}
                  showControls={false}
                  type='number'
                  size='small'
                  onFocus={() => (this.data.noticeIntervalError = false)}
                ></bk-input>
              </i18n>
              <span
                class='icon-monitor icon-hint'
                v-bk-tooltips={{ content: intervalModeTips[this.data.noticeInterval.interval_notify_mode] }}
                style={{ color: '#979ba5', marginTop: '-3px' }}
              ></span>
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
                panels={templateList}
                active={this.data.templateActive}
                type={'text'}
                onChange={this.handleChangeTemplate}
              ></CustomTab>
            </div>
            <div class='wrap-bottom'>
              <CommonItem
                title={this.$tc('告警标题')}
                class='template'
                isRequired
              >
                <VerifyItem
                  errorMsg={this.data.templateError}
                  style={{ flex: 1 }}
                >
                  <AutoInput
                    class='template-title'
                    tipsList={this.messageTemplateList}
                    v-model={this.data.templateData.title_tmpl}
                    on-change={this.templateChange}
                  ></AutoInput>
                </VerifyItem>
              </CommonItem>
              <div
                class='label-wrap'
                style={{ marginTop: '7px' }}
              >
                <span class='label'>{this.$t('告警通知模板')}</span>
              </div>
              <ResizeContainer
                style='margin-top: 8px'
                height={215}
                minHeight={80}
                minWidth={200}
              >
                <TemplateInput
                  extCls={'notice-config-template-pop'}
                  defaultValue={this.data.templateData.message_tmpl}
                  triggerList={this.messageTemplateList}
                  onChange={this.noticeTemplateChange}
                  style='width: 100%; height: 100%;'
                ></TemplateInput>
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
                theme='primary'
                size='small'
              ></bk-switcher>
              <i class='icon-monitor icon-hint'></i>
              <span class='text'>
                {this.$t('当防御的通知汇总也产生了大量的风暴时，会进行本业务的跨策略的汇总通知。')}
              </span>
            </span>
          </div>
        );
      default:
        return '';
    }
  }

  render() {
    return (
      <bk-dialog
        class='strategy-list-dialog'
        title={this.curItem.title}
        width={this.curItem.width}
        escClose={false}
        value={this.dialogShow}
        maskClose={false}
        headerPosition={'left'}
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
          {this.setType === 6 || this.setType === 7 ? (
            <bk-button
              theme='primary'
              onClick={this.handleConfirm}
            >
              {this.$t('确认')}
            </bk-button>
          ) : (
            <bk-button
              theme='primary'
              onClick={this.handleConfirm}
              disabled={this.loading}
            >
              {' '}
              {this.$t('保存')}{' '}
            </bk-button>
          )}
          <bk-button onClick={this.handleCancel}> {this.$t('取消')} </bk-button>
        </div>
      </bk-dialog>
    );
  }
}
