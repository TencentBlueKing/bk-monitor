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
import { Component, Emit, Inject, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import ResizeContainer from 'fta-solutions/components/resize-container/resize-container';
import SetMealDeail from 'fta-solutions/pages/setting/set-meal-detail/set-meal-detail';
import AutoInput from 'fta-solutions/pages/setting/set-meal/set-meal-add/components/auto-input/auto-input';
import CustomTab from 'fta-solutions/pages/setting/set-meal/set-meal-add/components/custom-tab';
import {
  intervalModeTips,
  templateSignalName,
} from 'fta-solutions/pages/setting/set-meal/set-meal-add/meal-content/meal-content-data';
import SetMealAddStore from 'fta-solutions/store/modules/set-meal-add';
import { deepClone } from 'monitor-common/utils/utils';

import AIWhaleIcon from '../../../../components/ai-whale-icon/ai-whale-icon';
import TemplateInput from '../../strategy-config-set/strategy-template-input/strategy-template-input.vue';
import StrategyTemplatePreview from '../../strategy-config-set/strategy-template-preview/strategy-template-preview.vue';
import StrategyVariateList from '../../strategy-config-set/strategy-variate-list/strategy-variate-list.vue';
import AlarmGroup from '../components/alarm-group';
import CommonItem from '../components/common-form-item';
import VerifyItem from '../components/verify-item';
import NoticeItem from './notice-item';

import type GroupSelect from '../components/group-select';
import type { IGroupItem } from '../components/group-select';
import type { IAlarmGroupList } from '../strategy-config-set';
import type { ICommonItem, strategyType } from '../typings/index';

import './notice-config.scss';

// 告警触发 告警恢复 告警关闭 告警处理
export const noticeOptions = [
  { key: 'abnormal', text: window.i18n.t('告警触发时') },
  { key: 'recovered', text: window.i18n.t('告警恢复时') },
  { key: 'closed', text: window.i18n.t('告警关闭时') },
  { key: 'ack', text: window.i18n.t('告警确认时') },
];

export const actionOption = [
  { key: 'execute', text: window.i18n.t('执行前') },
  { key: 'execute_success', text: window.i18n.t('执行成功') },
  { key: 'execute_failed', text: window.i18n.t('执行失败') },
];

export const intervalModeNames = {
  standard: window.i18n.t('固定'),
  increasing: window.i18n.t('递增'),
};

export const intervalModeList = [
  { id: 'standard', name: intervalModeNames.standard },
  { id: 'increasing', name: intervalModeNames.increasing },
];

/* 包含排除选项的告警通知方式 */
export const hasExcludeNoticeWayOptions = ['recovered', 'closed', 'ack'];

export interface INoticeValue {
  config?: IAdvancedConfig; //  高级配置
  config_id?: number; // 套餐id
  signal?: string[]; // 触发信号
  user_group_list?: { id?: number; name?: string; users?: { display_name: string }[] }[];
  user_groups?: number[]; // 告警组
  options?: {
    assign_mode?: AssignModeType[];
    chart_image_enabled?: boolean;
    converge_config: {
      need_biz_converge: boolean; // 告警风暴开关
    };
    exclude_notice_ways?: {
      ack: string[];
      closed: string[];
      // 排除通知
      recovered: string[];
    };
    noise_reduce_config?: {
      /* 降噪设置 */ count: number;
      dimensions: string[];
      is_enabled: boolean;
    };
    upgrade_config?: {
      is_enabled: boolean;
      upgrade_interval: number;
      user_groups: number[];
    };
  };
}

type AssignModeType = 'by_rule' | 'only_notice';
interface IAdvancedConfig {
  interval_notify_mode: string; // "standard" 间隔模式
  notify_interval: number; // 通知间隔
  template: { message_tmpl: string; signal: string; title_tmpl: string }[];
}

interface INoticeConfigNewEvent {
  onChange?: INoticeValue;
}

interface INoticeConfigNewProps {
  alarmGroupLoading?: boolean;
  allAction?: IGroupItem[]; // 套餐列表
  dataTypeLabel?: string;
  isExecuteDisable?: boolean;
  legalDimensionList?: ICommonItem[];
  readonly?: boolean;
  strategyId?: number | string;
  userList?: IAlarmGroupList[]; // 告警组
  value?: INoticeValue;
}

@Component({
  name: 'NoticeConfigNew',
})
export default class NoticeConfigNew extends tsc<INoticeConfigNewProps, INoticeConfigNewEvent> {
  @Prop({ type: Object, default: () => ({}) }) value: INoticeValue;
  @Prop({ type: Array, default: () => [] }) allAction: IGroupItem[];
  @Prop({ type: Array, default: () => [] }) userList: IAlarmGroupList[];
  @Prop({ type: Boolean, default: false }) readonly: boolean;
  @Prop({ default: '', type: [Number, String] }) strategyId: number;
  @Prop({ default: false, type: Boolean }) isExecuteDisable: boolean;
  @Prop({ default: () => [], type: Array }) legalDimensionList: ICommonItem[];
  @Prop({ default: false, type: Boolean }) alarmGroupLoading: boolean;
  /* dataTypeLabel === time_series 才显示降噪设置 */
  @Prop({ default: '', type: String }) dataTypeLabel: string;

  @Inject('authority') authority;
  @Inject('handleShowAuthorityDetail') handleShowAuthorityDetail;
  @Inject('authorityMap') authorityMap;
  @Inject() strategyType: strategyType;

  @Ref('selectMeal') selectMealRef: GroupSelect;

  data: INoticeValue = {
    config_id: 0, // 套餐id
    user_groups: [], // 告警组
    signal: [], // 触发信号
    options: {
      converge_config: {
        need_biz_converge: true, // 告警风暴开关
      },
      exclude_notice_ways: {
        recovered: [],
        closed: [],
      },
      noise_reduce_config: {
        is_enabled: false,
        count: 10,
        dimensions: [],
      },
      upgrade_config: {
        is_enabled: false,
        user_groups: [],
        upgrade_interval: 0,
      },
      assign_mode: [],
      chart_image_enabled: true,
    },
    config: {
      // 高级配置
      interval_notify_mode: 'standard',
      notify_interval: 120,
      template: [
        { signal: 'abnormal', message_tmpl: '', title_tmpl: '' },
        { signal: 'recovered', message_tmpl: '', title_tmpl: '' },
        { signal: 'closed', message_tmpl: '', title_tmpl: '' },
      ],
    },
  };

  assignMode = {
    by_rule: false,
    only_notice: false,
  };

  templateData: {
    message_tmpl: string;
    signal: string;
    title_tmpl: string;
  } = { signal: 'abnormal', message_tmpl: '', title_tmpl: '' };
  templateActive = '';

  isShowTemplate = false;
  variateListShow = false;

  isShowDetail = false;

  expanShow = false;

  errMsg = {
    user_groups: '', // 告警组
    interval: '', // 通知间隔
    template: '', // 模板
    noise_reduce_config: '', // 降噪设置
    notice: '',
    upgrade: '', // 通知升级
  };

  /* 排除通知方式下拉是否展开 */
  excludeNoticeWaysPop = {
    recovered: false,
    closed: false,
  };

  /* 全局设置蓝鲸监控机器人发送图片是否开启， 如果关闭则禁用是否附带图片选项 */
  wxworkBotSendImage = false;

  /**
   * @description: 告警类型列表
   * @param {*}
   * @return {*}
   */
  get templateTypes() {
    return (
      this.data.config.template.map(item => ({
        key: item.signal,
        label: templateSignalName[item.signal],
      })) || []
    );
  }

  /**
   * @description: 自动填充变量列表
   * @param {*}
   * @return {*}
   */
  get getMessageTemplateList() {
    return SetMealAddStore.getMessageTemplateList;
  }

  /**
   * @description: 变量列表
   * @param {*}
   * @return {*}
   */
  get variateList() {
    return SetMealAddStore.getVariables;
  }

  // 通知方式
  get noticeWayList() {
    return SetMealAddStore.noticeWayList;
  }

  created() {
    this.wxworkBotSendImage = !!window?.wxwork_bot_send_image;
  }

  // @Watch('assignMode', { deep: true })
  handleAssignModeChange(value) {
    const assignMode = [];
    Object.keys(value).forEach(key => {
      if (value[key]) {
        assignMode.push(key);
      }
    });
    this.data.options.assign_mode = assignMode;
    this.handleChange();
  }

  // 通知方式选择
  handleCheckNoticeMode(key: string, v: boolean) {
    this.assignMode[key] = v;
    this.handleAssignModeChange(this.assignMode);
  }

  @Watch('value', { immediate: true, deep: true })
  handleValue(data: INoticeValue) {
    this.data = data;

    Object.keys(this.assignMode).forEach(key => {
      this.assignMode[key] = (data.options?.assign_mode || []).includes(key);
    });

    if (this.templateActive === '') {
      this.templateActive = data.config.template[0].signal;
      this.templateData = deepClone(data.config.template[0]);
    }
  }
  @Emit('change')
  handleChange() {
    this.clearError();
    this.data.config.template = this.data.config.template.map(item => {
      if (item.signal === this.templateActive) {
        return deepClone(this.templateData);
      }
      return item;
    });
    return this.data;
  }
  /* 监听指标已选维度变化更改降噪设置维度 */
  @Watch('legalDimensionList')
  handleLegalDimensionList(value: ICommonItem[]) {
    if (this.data.options.noise_reduce_config.dimensions.includes('all')) {
      return;
    }
    const temp = [];
    value.forEach(item => {
      if (this.data.options.noise_reduce_config.dimensions.includes(item.id as string)) {
        temp.push(item.id);
      }
    });
    this.data.options.noise_reduce_config.dimensions = temp;
    this.handleChange();
  }

  /**
   * @description: 初始化当前选中的告警类型数据（父组件调用）
   * @param {*}
   * @return {*}
   */
  templateDataInit() {
    this.templateActive = '';
    this.templateData = { signal: 'abnormal', message_tmpl: '', title_tmpl: '' };
  }

  handleUserGroup(v: number[]) {
    this.data.user_groups = v;
    this.handleChange();
  }

  handleGotoAlarmDispatch() {
    window.open(`${location.origin}${location.pathname}${location.search}#/alarm-dispatch`);
  }

  // 校验
  async validator() {
    return new Promise((resolve, reject) => {
      if (!this.data.options.assign_mode.length) {
        this.errMsg.notice = window.i18n.tc('选择通知方式');
        reject();
      }
      if (!this.data.user_groups.length && this.data.options.assign_mode.includes('only_notice')) {
        this.errMsg.user_groups = window.i18n.tc('必填项');
        reject();
      }
      if (!this.data.config.notify_interval) {
        this.errMsg.interval = window.i18n.tc('必填项');
        reject();
      }
      const templateValidate = this.data.config.template.some(template => {
        if (!template.title_tmpl) {
          this.handleChangeTemplate(template.signal);
        }
        return !template.title_tmpl;
      });
      if (templateValidate) {
        this.errMsg.template = window.i18n.tc('必填项');
        reject();
      }
      if (
        this.dataTypeLabel === 'time_series' &&
        this.data.options.noise_reduce_config.is_enabled &&
        (!this.data.options.noise_reduce_config.dimensions.length ||
          +this.data.options.noise_reduce_config.count < 1 ||
          +this.data.options.noise_reduce_config.count > 100)
      ) {
        this.errMsg.noise_reduce_config = window.i18n.tc('开启降噪设置必须设置维度且比例值为1-100之间');
        reject();
      }
      if (this.data.options.upgrade_config.is_enabled) {
        if (
          !this.data.options.upgrade_config.upgrade_interval ||
          !this.data.options.upgrade_config.user_groups.length
        ) {
          this.errMsg.upgrade = window.i18n.tc('通知升级必须填写时间间隔以及用户组');
          reject();
        }
        if (this.data.options.upgrade_config.user_groups.some(upgrade => this.data.user_groups.includes(upgrade))) {
          this.errMsg.upgrade = window.i18n.tc('通知升级的用户组不能包含第一次接收告警的用户组');
          reject();
        }
      }
      resolve(true);
    });
  }
  clearError() {
    this.errMsg = {
      user_groups: '',
      interval: '',
      template: '',
      noise_reduce_config: '',
      notice: '',
      upgrade: '',
    };
  }

  clearNoticeError() {
    this.errMsg.notice = '';
  }

  /**
   * @description: 切换告警类型
   * @param {string} v
   * @return {*}
   */
  handleChangeTemplate(v: string) {
    this.templateActive = v;
    this.templateData = deepClone(this.data.config.template.find(item => item.signal === v));
  }

  /**
   * @description: 查看模板
   * @param {*}
   * @return {*}
   */
  handleShowTemplate() {
    if (!this.templateData.message_tmpl) return;
    this.isShowTemplate = true;
  }

  /**
   * @description: 查看变量列表
   * @param {*}
   * @return {*}
   */
  handleShowVariateList() {
    this.variateListShow = true;
  }

  /**
   * @description: 模板变量输入
   * @param {string} tplStr
   * @return {*}
   */
  noticeTemplateChange(tplStr: string) {
    this.templateData.message_tmpl = tplStr;
    this.handleChange();
  }

  /**
   * @description: 告警通知及处理通知复选框输入
   * @param {string} v
   * @param {*} type
   * @return {*}
   */
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
    hasExcludeNoticeWayOptions.forEach(key => {
      (this.$refs?.[key] as any)?.hideHandler();
      if (!this.data.signal.includes(key)) {
        this.data.options.exclude_notice_ways[key] = [];
      }
    });
    this.handleChange();
  }

  /* 以下为弹层的显隐操作 */
  handleExcludeMouseenter(key) {
    if (this.data.signal.includes(key)) {
      (this.$refs?.[key] as any)?.showHandler();
    }
  }
  handleExcludeMouseleave(key) {
    if (!this.excludeNoticeWaysPop[key]) {
      (this.$refs?.[key] as any)?.hideHandler();
    }
  }
  handleExcludeToggle(v: boolean, key) {
    this.excludeNoticeWaysPop[key] = v;
    if (!v) {
      (this.$refs?.[key] as any)?.hideHandler();
    }
  }
  excludePopInit() {
    hasExcludeNoticeWayOptions.forEach(key => {
      if (!this.excludeNoticeWaysPop[key]) {
        (this.$refs?.[key] as any)?.hideHandler();
      }
    });
  }

  handleDimensionsSelected(value: string[]) {
    if (!value.length || value[value.length - 1] === 'all') {
      this.data.options.noise_reduce_config.dimensions = ['all'];
    } else {
      this.data.options.noise_reduce_config.dimensions = value.filter(id => id !== 'all');
    }
    this.handleChange();
  }

  // 在切换页面时，如果 popover 被打开不及时关闭会让该实例残留在页面上。这里进行手动清除
  hideAllPopoverInstance() {
    this.data.signal.forEach(key => {
      const ELE_POPOVER = this.$refs[key] as any;
      if (ELE_POPOVER?.instance?.state?.isVisible) {
        ELE_POPOVER?.hideHandler?.();
      }
    });
  }

  beforeDestroy() {
    this.hideAllPopoverInstance();
  }

  deactivated() {
    this.hideAllPopoverInstance();
  }

  render() {
    return (
      <div
        class={['notice-config-new-component', { readonly: this.readonly }]}
        onMousedown={() => this.excludePopInit()}
      >
        <CommonItem
          title={this.$t('告警阶段')}
          show-semicolon
        >
          <span class='effective-conditions'>
            <bk-checkbox-group
              value={this.data.signal}
              on-change={v => this.handleSignalChange(v, 'notice')}
            >
              {noticeOptions.map(item => (
                <bk-checkbox
                  key={item.key}
                  v-en-style='width: 160px'
                  disabled={this.readonly}
                  value={item.key}
                >
                  {hasExcludeNoticeWayOptions.includes(item.key) ? (
                    <bk-popover
                      ref={item.key}
                      extCls='notice-config-new-component-exclude-way-pop'
                      tippyOptions={{
                        theme: 'light',
                        trigger: 'manual',
                        hideOnClick: false,
                        distance: 10,
                      }}
                      placement='top'
                    >
                      <span
                        style={{ 'border-bottom': this.data.signal.includes(item.key) ? '1px dashed #979BA5' : 'none' }}
                        onMouseenter={() => this.handleExcludeMouseenter(item.key)}
                      >
                        {item.text}
                      </span>
                      <span
                        class='exclude-content'
                        slot='content'
                        onMouseleave={() => this.handleExcludeMouseleave(item.key)}
                      >
                        <span>{window.i18n.tc('明确排除通知方式')}</span>
                        <bk-select
                          class='exclude-select'
                          v-model={this.data.options.exclude_notice_ways[item.key]}
                          behavior='simplicity'
                          multiple
                          onToggle={v => this.handleExcludeToggle(v, item.key)}
                        >
                          {this.noticeWayList.map(way => (
                            <bk-option
                              id={way.type}
                              key={way.type}
                              name={way.label}
                            />
                          ))}
                        </bk-select>
                      </span>
                    </bk-popover>
                  ) : (
                    <span>{item.text}</span>
                  )}
                </bk-checkbox>
              ))}
            </bk-checkbox-group>
          </span>
        </CommonItem>
        <CommonItem
          title={this.$t('处理阶段')}
          show-semicolon
        >
          <span class='effective-conditions'>
            <bk-checkbox-group
              value={this.data.signal}
              on-change={v => this.handleSignalChange(v, 'action')}
            >
              {actionOption.map(item => (
                <bk-checkbox
                  key={item.key}
                  v-en-style='width: 160px'
                  disabled={this.readonly}
                  value={item.key}
                >
                  {item.text}
                </bk-checkbox>
              ))}
            </bk-checkbox-group>
          </span>
        </CommonItem>
        {/* <CommonItem title={this.$t('告警组')} show-semicolon>
          <VerifyItem errorMsg={this.errMsg.user_groups}>
            <AlarmGroup
              class="alarm-group"
              list={this.userList}
              value={this.data.user_groups}
              readonly={this.readonly}
              showAddTip={false}
              strategyId={this.strategyId}
              onChange={data => this.handleUserGroup(data)}
            ></AlarmGroup>
          </VerifyItem>
        </CommonItem> */}
        <CommonItem
          title={this.$t('通知方式')}
          show-semicolon
        >
          <VerifyItem errorMsg={this.errMsg.notice}>
            <NoticeItem
              clearError={this.clearNoticeError}
              subTitle={this.$t('可以基于不同的数据维度进行告警分派')}
              title={this.$t('基于分派规则通知')}
              value={this.assignMode.by_rule}
              onChange={v => this.handleCheckNoticeMode('by_rule', v)}
            >
              <span
                class='view-alarm'
                slot='header'
                onClick={this.handleGotoAlarmDispatch}
              >
                <span
                  class='title'
                  v-bk-overflow-tips
                >
                  {this.$t('查看分派规则')}
                </span>
                <i class='icon-monitor icon-fenxiang' />
              </span>
            </NoticeItem>
            <NoticeItem
              clearError={this.clearNoticeError}
              subTitle={this.$t('剩下的告警基于当前规则发送通知')}
              title={this.$t('默认通知')}
              value={this.assignMode.only_notice}
              onChange={v => this.handleCheckNoticeMode('only_notice', v)}
            >
              <CommonItem
                title={this.$t('告警组')}
                isRequired
                show-semicolon
              >
                <VerifyItem errorMsg={this.errMsg.user_groups}>
                  {!this.alarmGroupLoading ? (
                    <AlarmGroup
                      class='alarm-group'
                      list={this.userList}
                      readonly={this.readonly}
                      showAddTip={false}
                      strategyId={this.strategyId}
                      value={this.data.user_groups}
                      onChange={data => this.handleUserGroup(data)}
                    />
                  ) : (
                    <div class='skeleton-element alarm-group-skeleton' />
                  )}
                </VerifyItem>
              </CommonItem>
              <CommonItem
                style={{
                  alignItems: this.data.options.upgrade_config.is_enabled ? 'inherit' : 'flex-end',
                  marginBottom: this.errMsg.upgrade ? '15px' : 0,
                }}
                title={this.$t('通知升级')}
                show-semicolon
              >
                <VerifyItem errorMsg={this.errMsg.upgrade}>
                  <div class='upgrade-warp'>
                    <bk-switcher
                      v-model={this.data.options.upgrade_config.is_enabled}
                      size='small'
                      theme='primary'
                      onChange={this.clearError}
                    />
                    {this.data.options.upgrade_config.is_enabled && (
                      <i18n
                        class='text'
                        path='当告警持续时长每超过{0}分种，将逐个按告警组升级通知'
                        tag='div'
                      >
                        <bk-select
                          style='width: 78px'
                          class='notice-select'
                          v-model={this.data.options.upgrade_config.upgrade_interval}
                          behavior='simplicity'
                          placeholder={this.$t('输入')}
                          zIndex={99999}
                          allow-create
                          allow-enter
                          onChange={this.clearError}
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
                  </div>
                  {this.data.options.upgrade_config.is_enabled ? (
                    !this.alarmGroupLoading ? (
                      <AlarmGroup
                        class='alarm-group'
                        v-model={this.data.options.upgrade_config.user_groups}
                        list={this.userList}
                        readonly={this.readonly}
                        showAddTip={false}
                        strategyId={this.strategyId}
                        onChange={this.clearError}
                      />
                    ) : (
                      <div class='skeleton-element alarm-group-skeleton' />
                    )
                  ) : undefined}
                </VerifyItem>
              </CommonItem>
            </NoticeItem>
          </VerifyItem>
        </CommonItem>
        {this.advancedConfigurationComponent()}
        <SetMealDeail
          id={this.data.config_id}
          v-model={this.isShowDetail}
          strategyType={this.strategyType}
          needEditTips
        />
      </div>
    );
  }

  // 高级配置
  advancedConfigurationComponent() {
    return (
      <div class={['advanced-config', { readonly: this.readonly }]}>
        <div
          class={['expan-title', { down: this.expanShow }]}
          v-en-style='width: 180px'
          onClick={() => (this.expanShow = !this.expanShow)}
        >
          {this.$t('高级配置')} <i class='icon-monitor icon-double-down' />
        </div>
        <div class={['expan-content', { show: this.expanShow }]}>
          <CommonItem
            class='interval'
            title={this.$t('通知间隔')}
            show-semicolon
          >
            <VerifyItem errorMsg={this.errMsg.interval}>
              <span class='notice-interval'>
                <i18n
                  class='content-interval'
                  path='若产生相同的告警未确认或者未屏蔽,则{0}间隔{1}分钟再进行告警。'
                >
                  {this.readonly
                    ? [
                        <span
                          key={'intervalModeNames'}
                          class='bold'
                        >
                          {intervalModeNames[this.data.config.interval_notify_mode]}
                        </span>,
                        <span
                          key={'notify_interval'}
                          class='bold'
                        >
                          {this.data.config.notify_interval}
                        </span>,
                      ]
                    : [
                        <bk-select
                          key={'interval_notify_mode'}
                          class='select select-inline'
                          v-model={this.data.config.interval_notify_mode}
                          v-en-style='width: 100px'
                          behavior='simplicity'
                          clearable={false}
                          size='small'
                          onChange={this.handleChange}
                        >
                          {intervalModeList.map(item => (
                            <bk-option
                              id={item.id}
                              key={item.id}
                              name={item.name}
                            />
                          ))}
                        </bk-select>,
                        <bk-input
                          key={'notify_interval'}
                          class='input-inline input-center'
                          v-model={this.data.config.notify_interval}
                          behavior='simplicity'
                          size='small'
                          type='number'
                          onInput={this.handleChange}
                        />,
                      ]}
                </i18n>

                <AIWhaleIcon
                  style={{ color: '#979ba5', marginTop: '-3px' }}
                  content={this.$t('通知间隔').toString()}
                  tip={intervalModeTips[this.data.config.interval_notify_mode]}
                  type='description'
                />
              </span>
            </VerifyItem>
          </CommonItem>
          <CommonItem
            title={this.$t('告警风暴')}
            show-semicolon
          >
            <span class='alarm-storm'>
              <bk-switcher
                v-model={this.data.options.converge_config.need_biz_converge}
                disabled={this.readonly}
                size='small'
                theme='primary'
                on-change={this.handleChange}
              />
              <AIWhaleIcon
                content={this.$t('当防御的通知汇总也产生了大量的风暴时，会进行本业务的跨策略的汇总通知。').toString()}
                type='description'
              />
              <span class='text'>
                {this.$t('当防御的通知汇总也产生了大量的风暴时，会进行本业务的跨策略的汇总通知。')}
              </span>
            </span>
          </CommonItem>
          {this.dataTypeLabel === 'time_series' ? (
            <CommonItem
              title={this.$t('降噪设置')}
              show-semicolon
            >
              <VerifyItem errorMsg={this.errMsg.noise_reduce_config}>
                <span class={['noise-reduce', { mt5: !this.data.options.noise_reduce_config.is_enabled }]}>
                  <bk-switcher
                    v-model={this.data.options.noise_reduce_config.is_enabled}
                    disabled={this.readonly}
                    size='small'
                    theme='primary'
                    on-change={this.handleChange}
                  />
                  {this.data.options.noise_reduce_config.is_enabled ? (
                    <i18n
                      class='noise-content'
                      path='基于维度{0},当前策略异常告警达到比例{1}%才进行发送通知。'
                    >
                      <bk-select
                        class='select select-inline'
                        v-model={this.data.options.noise_reduce_config.dimensions}
                        v-bk-tooltips={{
                          content: this.data.options.noise_reduce_config.dimensions.join('; '),
                          trigger: 'mouseenter',
                          zIndex: 9999,
                          boundary: document.body,
                          disabled: !this.data.options.noise_reduce_config.dimensions.length,
                          allowHTML: false,
                        }}
                        behavior='simplicity'
                        clearable={false}
                        placeholder={this.$t('选择')}
                        popover-min-width={140}
                        size='small'
                        multiple
                        searchable
                        onSelected={this.handleDimensionsSelected}
                      >
                        {[{ id: 'all', name: window.i18n.tc('全部') }, ...this.legalDimensionList].map(item => (
                          <bk-option
                            id={item.id}
                            key={item.id}
                            v-bk-tooltips={{
                              content: item.id,
                              placement: 'right',
                              zIndex: 9999,
                              boundary: document.body,
                              appendTo: document.body,
                              disabled: item.id === 'all',
                              allowHTML: false,
                            }}
                            name={item.name}
                          />
                        ))}
                      </bk-select>
                      <bk-input
                        class='input-inline input-center'
                        v-model={this.data.options.noise_reduce_config.count}
                        behavior='simplicity'
                        showControls={false}
                        size='small'
                        type='number'
                        onInput={this.handleChange}
                      />
                    </i18n>
                  ) : undefined}
                </span>
              </VerifyItem>
            </CommonItem>
          ) : undefined}
          <div class='content-wrap-key1'>
            <div class='wrap-top'>
              <CustomTab
                active={this.templateActive}
                panels={this.templateTypes}
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
                  errorMsg={this.errMsg.template}
                >
                  <AutoInput
                    class='template-title'
                    v-model={this.templateData.title_tmpl}
                    readonly={this.readonly}
                    tipsList={this.getMessageTemplateList}
                    on-change={this.handleChange}
                  />
                </VerifyItem>
              </CommonItem>
              <div
                style={{ marginTop: '7px' }}
                class='label-wrap'
              >
                <span class='label'>
                  <span>{this.$t('告警通知模板')}</span>
                  <span class='need-img-check'>
                    <bk-checkbox
                      v-model={this.data.options.chart_image_enabled}
                      v-bk-tooltips={{
                        content: this.$t('蓝鲸监控机器人发送图片全局设置已关闭'),
                        placements: ['top'],
                        disabled: this.wxworkBotSendImage,
                      }}
                      disabled={!this.wxworkBotSendImage}
                      on-change={this.handleChange}
                    >
                      {this.$t('是否附带图片')}
                    </bk-checkbox>
                  </span>
                </span>
                <div class='wrap-right'>
                  <div
                    style={{ marginRight: '26px' }}
                    class={'template-btn-wrap'}
                    onClick={this.handleShowVariateList}
                  >
                    <i class='icon-monitor icon-audit' />
                    <span class='template-btn-text'>{this.$t('变量列表')}</span>
                  </div>
                  <div
                    class={['template-btn-wrap', { 'template-btn-disabled': !this.templateData.message_tmpl }]}
                    onClick={this.handleShowTemplate}
                  >
                    <i class='icon-monitor icon-audit' />
                    <span class='template-btn-text'>{this.$t('模板预览')}</span>
                  </div>
                </div>
              </div>
              {this.readonly ? (
                <div class='template-pre'>
                  <pre>{this.templateData.message_tmpl}</pre>
                </div>
              ) : (
                <ResizeContainer
                  style='margin-top: 8px'
                  height={215}
                  minHeight={80}
                  minWidth={200}
                >
                  <TemplateInput
                    style='width: 100%; height: 100%;'
                    extCls={'notice-config-template-pop'}
                    default-value={this.templateData.message_tmpl}
                    trigger-list={this.getMessageTemplateList}
                    onChange={this.noticeTemplateChange}
                  />
                </ResizeContainer>
              )}
            </div>
            <StrategyTemplatePreview
              dialogShow={this.isShowTemplate}
              template={this.templateData.message_tmpl}
              {...{ on: { 'update:dialogShow': v => (this.isShowTemplate = v) } }}
            />
            <StrategyVariateList
              dialogShow={this.variateListShow}
              {...{ on: { 'update:dialogShow': val => (this.variateListShow = val) } }}
              variate-list={this.variateList}
            />
          </div>
        </div>
      </div>
    );
  }
}
