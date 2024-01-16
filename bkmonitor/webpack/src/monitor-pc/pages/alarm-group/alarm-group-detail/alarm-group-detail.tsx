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
import { Component, Emit, Model, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import NoticeModeNew, {
  INoticeWayValue
} from '../../../../fta-solutions/pages/setting/set-meal/set-meal-add/components/notice-mode';
import {
  executionNotifyConfigChange,
  getNotifyConfig
} from '../../../../fta-solutions/pages/setting/set-meal/set-meal-add/meal-content/meal-content-data';
import { getNoticeWay } from '../../../../monitor-api/modules/notice_group';
import { getBkchatGroup, previewUserGroupPlan } from '../../../../monitor-api/modules/user_groups';
import { random } from '../../../../monitor-common/utils/utils';
import HistoryDialog from '../../../components/history-dialog/history-dialog';
import { listDutyRule, retrieveUserGroup } from '../.././../../monitor-api/modules/model';
import RotationPreview from '../rotation/rotation-preview';
import { getCalendarOfNum, setPreviewDataOfServer } from '../rotation/utils';

import './alarm-group-detail.scss';

const ALERT_NOTICE = 'alert_notice';
const ACTION_NOTICE = 'action_notice';

export interface IAlarmGroupDeatail {
  id: number | string;
  show?: boolean;
  customEdit?: boolean;
}
interface IEvent {
  onShowChange?: boolean;
  onEditGroup?: string | number;
}
interface IFormData {
  channels: string[];
  name: string;
  bizId: string;
  desc: string;
  users: any[];
  needDuty?: boolean;
  mention_list: any[];
}

interface IAlert {
  time_range?: string;
  notify_config?: INoticeWayValue[];
  key?: string;
}
interface INotice {
  [ALERT_NOTICE]: IAlert[]; // 所有通知方式数据
  [ACTION_NOTICE]: IAlert[];
  alertData: IAlert; // 当前通知方式数据
  actionData: IAlert;
  alertActive: string; // 当前通知方式选项
  actionActive: string;
}

const noticeTypeMap = {
  weekly: window.i18n.t('每周'),
  monthly: window.i18n.t('每月')
};

@Component
export default class AlarmGroupDetial extends tsc<IAlarmGroupDeatail, IEvent> {
  @Prop({ type: [String, Number], default: 0 }) id: number | string;
  @Prop({ type: Boolean, default: false }) customEdit: boolean;
  @Model('showChange', { default: false, type: Boolean }) show: boolean;

  loading = false;

  detailData = {
    createUser: '',
    createTime: '',
    updateUser: '',
    updateTime: ''
  };
  formData: IFormData = {
    channels: ['user'],
    name: '',
    bizId: '',
    desc: '',
    users: [],
    needDuty: false,
    mention_list: []
  };
  channels: string[] = ['user'];
  bkchatList = [];

  // 通知方式数据
  notice: INotice = {
    [ALERT_NOTICE]: [],
    [ACTION_NOTICE]: [],
    alertData: {},
    actionData: {},
    alertActive: '',
    actionActive: ''
  };
  noticeWayList = [];

  /* 轮值数据 */
  // dutyArranges: IDutyItem[] = [];
  dutyPlans = [];
  dutyArrangesKey = random(8);
  refreshKey = {
    alertKey: false,
    actionKey: false
  };

  /* 是否可编辑 */
  editAllowed = false;

  receiverList = [];

  /* 轮值数据 --- 新 */
  previewData = [];
  previewLoading = false;
  dutyList = [];

  /* 值班通知设置  */
  dutyNotice = {
    plan_notice: {
      enabled: false,
      chat_ids: ['apsojgldjgngmfmdkgjfhdhsjfkdjfld'],
      days: 7,
      type: 'weekly',
      date: 1,
      time: '00:00'
    },
    personal_notice: {
      enabled: false,
      hours_ago: 0,
      duty_rules: []
    }
  };

  get title() {
    return `${this.$t('告警组详情')} - #${this.id} ${this.formData.name}`;
  }
  get bizName() {
    let name = '';
    // 筛选出所属空间
    if (+this.formData.bizId === 0) {
      name = this.$tc('全业务');
    } else {
      const bizItem = this.$store.getters.bizList.filter(item => +this.formData.bizId === +item.id);
      name = bizItem[0].text;
    }
    return name;
  }

  get historyList() {
    return [
      { label: this.$t('创建人'), value: this.detailData.createUser || '--' },
      { label: this.$t('创建时间'), value: this.detailData.createTime || '--' },
      { label: this.$t('最近更新人'), value: this.detailData.updateUser || '--' },
      { label: this.$t('修改时间'), value: this.detailData.updateTime || '--' }
    ];
  }

  @Watch('show')
  showChange(val: boolean) {
    if (val) {
      this.getDetailInfo();
    }
  }

  /**
   * @description: 获取告警组详情
   * @param {*}
   * @return {*}
   */
  async getDetailInfo() {
    this.loading = true;
    await this.getNoticeWay();
    retrieveUserGroup(this.id)
      .then(data => {
        const {
          name,
          desc,
          channels,
          bk_biz_id: bizId,
          create_time: createTime,
          create_user: createUser,
          update_time: updateTime,
          update_user: updateUser,
          need_duty: needDuty,
          edit_allowed: editAllowed,
          // 群提醒人 列表
          mention_list: mentionList
        } = data;
        this.formData.name = name;
        this.formData.desc = desc;
        this.formData.bizId = bizId;
        this.formData.needDuty = needDuty;
        this.formData.channels = channels || ['user'];
        // 无论是否对 mention_list 赋值，都要先清空数组，不然界面会保留上一次的数据。
        this.formData.mention_list.length = 0;
        if (Array.isArray(mentionList) && mentionList.length) {
          this.formData.mention_list = mentionList;
        }
        this.channels = channels || ['user'];
        const users = [];
        this.dutyNotice.plan_notice.enabled = false;
        this.dutyNotice.personal_notice.enabled = false;
        if (needDuty) {
          // this.dutyArranges = dutyDataTransform(data.duty_arranges);
          this.dutyPlans = data.duty_plans;
          this.getPreviewData(data.duty_rules);
          if (data.duty_notice?.plan_notice?.enabled) {
            this.dutyNotice.plan_notice = data.duty_notice.plan_notice;
          }
          if (data.duty_notice?.personal_notice?.enabled) {
            this.dutyNotice.personal_notice = data.duty_notice.personal_notice;
          }
        } else {
          data.duty_arranges.forEach(item => {
            item.users && users.push(...item.users);
          });
        }
        this.formData.users = users;
        this.detailData.createTime = createTime;
        this.detailData.createUser = createUser;
        this.detailData.updateTime = updateTime;
        this.detailData.updateUser = updateUser;
        this.getNoticeData(data);
        this.dutyArrangesKey = random(8);
        this.editAllowed = editAllowed;
      })
      .finally(() => {
        this.refreshKey.alertKey = true;
        this.refreshKey.actionKey = true;
        this.loading = false;
      });
  }

  async getPreviewData(list) {
    const dutyList = [];
    const allDutyList = (await listDutyRule().catch(() => [])) as any;
    const sets = new Set(list);
    allDutyList.forEach(item => {
      if (sets.has(item.id)) {
        item.isCheck = true;
        dutyList.push(item);
      }
    });
    this.dutyList = list
      .map(l => {
        const temp = dutyList.find(d => String(d.id) === String(l));
        return temp;
      })
      .filter(l => !!l);
    const startTime = getCalendarOfNum()[0];
    const beginTime = `${startTime.year}-${startTime.month}-${startTime.day} 00:00:00`;
    const params = {
      source_type: 'DB',
      id: this.id,
      days: 7,
      begin_time: beginTime
      // config: {
      //   duty_rules: list
      // }
    };
    const data = await previewUserGroupPlan(params).catch(() => []);
    this.previewData = setPreviewDataOfServer(data, this.dutyList);
  }
  async handleStartTimeChange(startTime) {
    const params = {
      source_type: 'DB',
      id: this.id,
      days: 7,
      begin_time: startTime
      // config: {
      //   duty_rules: this.dutyList.map(d => d.id)
      // }
    };
    this.previewLoading = true;
    const data = await previewUserGroupPlan(params).catch(() => []);
    this.previewLoading = false;
    this.previewData = setPreviewDataOfServer(data, this.dutyList);
  }

  /**
   *
   * @param data 通知方式数据
   * @description: 获取通知方式数据
   */
  getNoticeData(data: any) {
    this.notice = {
      [ALERT_NOTICE]: [],
      [ACTION_NOTICE]: [],
      alertData: {},
      actionData: {},
      alertActive: '',
      actionActive: ''
    };
    const { action_notice: actionNotice, alert_notice: alertNotice } = data;
    if (actionNotice?.length) {
      this.notice[ACTION_NOTICE] = actionNotice.map(item => ({
        ...item,
        time_range: item.time_range
          .split('--')
          .map(time => time.slice(0, 5))
          .join('--'),
        notify_config: getNotifyConfig(item.notify_config),
        key: random(10)
      }));
      this.notice.actionActive = this.notice[ACTION_NOTICE][0].key;
      [this.notice.actionData] = this.notice[ACTION_NOTICE];
    }
    if (alertNotice?.length) {
      this.notice[ALERT_NOTICE] = alertNotice.map(item => ({
        ...item,
        time_range: item.time_range
          .split('--')
          .map(time => time.slice(0, 5))
          .join('--'),
        notify_config: getNotifyConfig(item.notify_config),
        key: random(10)
      }));
      this.notice.alertActive = this.notice[ALERT_NOTICE][0].key;
      [this.notice.alertData] = this.notice[ALERT_NOTICE];
    }
  }

  // 获取通知方式数据表格
  async getNoticeWay() {
    if (this.noticeWayList.length) return;
    const data = await getNoticeWay().catch(() => []);
    this.noticeWayList = data.map(item => ({
      type: item.type,
      label: item.label,
      icon: item.icon,
      tip: item.type === 'wxwork-bot' ? window.i18n.t('获取群ID方法', { name: item.name }) : undefined,
      channel: item.channel
    }));
    if (this.noticeWayList.find(item => item.channel === 'bkchat')) {
      await this.getBkchatList(); // 查询bkchat下拉选项
    }
    this.refreshKey.alertKey = true;
    this.refreshKey.actionKey = true;
  }

  async getBkchatList() {
    try {
      await getBkchatGroup().then(res => {
        this.bkchatList = res;
        this.refreshKey.alertKey = true;
        this.refreshKey.actionKey = true;
      });
    } catch (e) {
      console.log(e);
    }
  }

  @Emit('showChange')
  emitIsShow(val: boolean) {
    return val;
  }
  @Emit('editGroup')
  handleEditGroup(): number | string {
    this.emitIsShow(false);
    return this.id;
  }

  /**
   * @description: 编辑告警组
   * @param {*}
   * @return {*}
   */
  handleEdit() {
    if (this.customEdit) {
      this.handleEditGroup();
      return;
    }
    this.emitIsShow(false);
    this.$router.push({
      name: 'alarm-group-edit',
      params: {
        id: `${this.id}`
      }
    });
  }

  /**
   * 前端特殊处理 群提醒人 的 display_name 。
   * @param display_name
   * @returns
   */
  getMappingDisplayName(display_name) {
    const mapping = {
      all: this.$t('内部通知人')
    };
    return mapping[display_name] || display_name;
  }

  render() {
    return (
      <bk-sideslider
        class='alarm-group-detail-wrap'
        {...{ on: { 'update:isShow': this.emitIsShow } }}
        width={960}
        quick-close={true}
        is-show={this.show}
      >
        <div
          class='alarm-detail-header'
          slot='header'
        >
          {this.loading ? (
            <span class='header-name'>{this.$t('加载中...')}</span>
          ) : (
            <span
              class='header-name'
              title={this.title}
            >
              {this.title}
            </span>
          )}
          <bk-button
            class={['header-edit', { disabled: !this.editAllowed }]}
            theme={this.editAllowed ? 'primary' : 'default'}
            outline={this.editAllowed}
            disabled={!this.editAllowed}
            onClick={this.handleEdit}
          >
            {this.$t('编辑')}
          </bk-button>
          <HistoryDialog
            style='margin: 0 24px 0 8px'
            list={this.historyList}
          />
        </div>
        <div
          slot='content'
          v-bkloading={{ isLoading: this.loading }}
          class='alarm-details'
        >
          <div class='alarm-details-col'>
            <div
              class='alarm-details-label'
              v-en-class='en-lang'
            >
              {this.$t('所属')}
            </div>
            <div class='alarm-details-item'>{this.bizName}</div>
          </div>
          <div class='alarm-details-col'>
            <div
              class='alarm-details-label'
              v-en-class='en-lang'
            >
              {this.$t('告警组名称')}
            </div>
            <div class='alarm-details-item alarm-details-content'>{this.formData.name}</div>
          </div>
          <div
            class='alarm-details-col text-top'
            style='margin-bottom: 14px'
          >
            <div
              class='alarm-details-label alarm-details-person-label'
              v-en-class='en-lang'
            >
              {this.$t('通知对象')}
            </div>
            <div class='alarm-details-item alarm-details-person'>
              {(() => {
                if (this.formData.needDuty) {
                  return (
                    <div class='duty-wrap'>
                      {/* <DutyArranges
                    value={this.dutyArranges}
                    readonly={true}
                    key={this.dutyArrangesKey}
                    dutyPlans={this.dutyPlans}
                  ></DutyArranges> */}
                      <RotationPreview
                        v-bkloading={{ isLoading: this.previewLoading }}
                        value={this.previewData}
                        dutyPlans={this.dutyPlans}
                        alarmGroupId={this.id}
                        onStartTimeChange={this.handleStartTimeChange}
                      ></RotationPreview>
                      {/* 值班通知设置 */}
                      {this.dutyNotice.plan_notice.enabled && (
                        <div class='duty-notice'>
                          <div class='mt-16'>{this.$t('排班表发送')}</div>
                          <div class='mt-16'>
                            <span class='notice-label'>{this.$t('发送时间')}</span>
                            <span>
                              <span>{noticeTypeMap[this.dutyNotice.plan_notice.type]}</span>
                              <span class='mr-8'>{this.dutyNotice.plan_notice.date}</span>
                              <span>{this.dutyNotice.plan_notice.time}</span>
                            </span>
                          </div>
                          <div class='mt-16'>
                            <span class='notice-label'>{this.$t('发送内容')}</span>
                            <span>
                              <i18n path={'近{0}天的排班结果'}>{this.dutyNotice.plan_notice.days}</i18n>
                            </span>
                          </div>
                          <div class='mt-16'>
                            <span class='notice-label'>{this.$t('企业微信群ID')}</span>
                            <span>{this.dutyNotice.plan_notice.chat_ids.join(',')}</span>
                          </div>
                        </div>
                      )}
                      {this.dutyNotice.personal_notice.enabled && (
                        <div class='duty-notice'>
                          <div class='mt-16'>{this.$t('个人轮值通知')}</div>
                          <div class='mt-16'>
                            <i18n
                              class='notice-label'
                              path={'值班开始前{0}天收到通知'}
                            >
                              {this.dutyNotice.personal_notice.hours_ago / 24}
                            </i18n>
                          </div>
                          <div class='mt-16'>
                            <span class='notice-label'>{this.$t('指定轮值规则')}</span>
                            <span>{this.dutyList.map(item => item.name).join(',')}</span>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                }
                if (this.formData.users?.length) {
                  return this.formData.users.map(item => (
                    <div
                      class='person-box'
                      key={item.id}
                    >
                      <div class='person-image'>
                        {[
                          item.logo ? (
                            <img
                              src={item.logo}
                              alt=''
                            />
                          ) : undefined,
                          !item.logo && item.type === 'group' ? (
                            <i class='icon-monitor icon-mc-user-group no-img' />
                          ) : undefined,
                          !item.logo && item.type === 'user' ? (
                            <i class='icon-monitor icon-mc-user-one no-img' />
                          ) : undefined
                        ]}
                      </div>
                      <span class='person-name'>
                        {item.id}
                        {`(${item.display_name})`}
                      </span>
                    </div>
                  ));
                }
                return '--';
              })()}
            </div>
          </div>
          {!!this.formData.mention_list.length && (
            <div
              class='alarm-details-col text-top'
              style='margin-bottom: 14px'
            >
              <div
                class='alarm-details-label alarm-details-person-label'
                v-en-class='en-lang'
              >
                {this.$t('群提醒人')}
              </div>

              <div class='alarm-details-item alarm-details-person'>
                {this.formData.mention_list.map(item => (
                  <div
                    class='person-box'
                    key={item.id}
                  >
                    <div class='person-image'>
                      {[
                        item.logo ? (
                          <img
                            src={item.logo}
                            alt=''
                          />
                        ) : undefined,
                        !item.logo && item.type === 'group' ? (
                          <i class='icon-monitor icon-mc-user-group no-img' />
                        ) : undefined,
                        !item.logo && item.type === 'user' ? (
                          <i class='icon-monitor icon-mc-user-one no-img' />
                        ) : undefined
                      ]}
                    </div>
                    <span class='person-name'>
                      {item.id}
                      {`(${this.getMappingDisplayName(item.display_name)})`}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
          {!!this.notice[ALERT_NOTICE].length && !!this.notice[ACTION_NOTICE].length && (
            <div class='alarm-details-col text-top'>
              <div
                class='alarm-details-label alarm-details-des-label'
                v-en-class='en-lang'
              >
                {this.$t('通知方式')}
              </div>
              <div class='alarm-details-item notice'>
                <div class='notice-title'>{this.$t('告警阶段')}</div>
                <div class='notice-item-wrap'>
                  <bk-tab
                    active={this.notice.alertActive}
                    labelHeight={42}
                    on-tab-change={(v: string) => {
                      this.notice.alertActive = v;
                      this.notice.alertData = this.notice[ALERT_NOTICE].find(item => item.key === v);
                      this.refreshKey.alertKey = true;
                    }}
                  >
                    {this.notice[ALERT_NOTICE].map(item => ({
                      key: item.key,
                      label: item.time_range.replace('--', '-')
                    })).map(item => (
                      <bk-tab-panel
                        key={item.key}
                        name={item.key}
                        label={item.label}
                      ></bk-tab-panel>
                    ))}
                  </bk-tab>
                  <div class='notice-item-content'>
                    <NoticeModeNew
                      noticeWay={this.noticeWayList}
                      notifyConfig={this.notice.alertData.notify_config}
                      refreshKey={this.refreshKey.alertKey}
                      channels={this.channels}
                      bkchatList={this.bkchatList}
                      readonly={true}
                      onRefreshKeyChange={() => (this.refreshKey.alertKey = false)}
                    ></NoticeModeNew>
                  </div>
                </div>
                <div
                  class='notice-title'
                  style={{ marginTop: '16px' }}
                >
                  {this.$t('执行通知')}
                </div>
                <div class='notice-item-wrap'>
                  <bk-tab
                    active={this.notice.actionActive}
                    labelHeight={42}
                    on-tab-change={(v: string) => {
                      this.notice.actionActive = v;
                      this.notice.actionData = this.notice[ACTION_NOTICE].find(item => item.key === v);
                      this.refreshKey.actionKey = true;
                    }}
                  >
                    {this.notice[ACTION_NOTICE].map(item => ({
                      key: item.key,
                      label: item.time_range.replace('--', '-')
                    })).map(item => (
                      <bk-tab-panel
                        key={item.key}
                        name={item.key}
                        label={item.label}
                      ></bk-tab-panel>
                    ))}
                  </bk-tab>
                  <div class='notice-item-content'>
                    <NoticeModeNew
                      noticeWay={this.noticeWayList}
                      type={1}
                      refreshKey={this.refreshKey.actionKey}
                      channels={this.channels}
                      bkchatList={this.bkchatList}
                      notifyConfig={executionNotifyConfigChange(this.notice.actionData.notify_config)}
                      readonly={true}
                      onRefreshKeyChange={() => (this.refreshKey.actionKey = false)}
                    ></NoticeModeNew>
                  </div>
                </div>
              </div>
            </div>
          )}
          <span></span>
          <div class='alarm-details-col text-top'>
            <div
              class='alarm-details-label alarm-details-des-label'
              v-en-class='en-lang'
            >
              {this.$t('说明')}
            </div>
            <div class='alarm-details-item'>
              <pre style='margin: 0; white-space: pre-wrap;'>{this.formData.desc || '--'}</pre>
            </div>
          </div>
        </div>
      </bk-sideslider>
    );
  }
}
