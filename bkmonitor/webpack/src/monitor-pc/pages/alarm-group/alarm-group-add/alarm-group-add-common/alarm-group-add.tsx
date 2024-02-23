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
import { VNode } from 'vue';
import { Component, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import Schema, { ErrorList, Rules, ValidateSource } from 'async-validator';

import CustomTab, {
  IPanels
} from '../../../../../fta-solutions/pages/setting/set-meal/set-meal-add/components/custom-tab';
import NoticeModeNew, {
  INoticeWayValue,
  robot
} from '../../../../../fta-solutions/pages/setting/set-meal/set-meal-add/components/notice-mode';
import {
  defaultAddTimeRange,
  executionNotifyConfigChange,
  getNotifyConfig,
  timeRangeValidate,
  timeTransform
} from '../../../../../fta-solutions/pages/setting/set-meal/set-meal-add/meal-content/meal-content-data';
import SetMealAddStore from '../../../../../fta-solutions/store/modules/set-meal-add';
import { getReceiver } from '../../../../../monitor-api/modules/notice_group';
import { getBkchatGroup } from '../../../../../monitor-api/modules/user_groups';
import { deepClone, random } from '../../../../../monitor-common/utils/utils';
// import TimezoneSelect from '../../../../components/timezone-select/timezone-select';
import { SET_NAV_ROUTE_LIST } from '../../../../store/modules/app';
import { createUserGroup, retrieveUserGroup, updateUserGroup } from '../../.././../../monitor-api/modules/model';
import { IDutyItem } from '../../duty-arranges/duty-arranges';
import RotationConfig from '../../rotation/rotation-config';
import MemberSelector from '../member-selector';

import './alarm-group-add.scss';

const { i18n } = window;

type TGroupType = 'monitor' | 'fta';
type NoticeType = 'alert_notice' | 'action_notice'; // 告警通知及执行通知
const ALERT_NOTICE = 'alert_notice';
const ACTION_NOTICE = 'action_notice';

interface IAlert {
  time_range?: string[]; // 时间段
  notify_config?: INoticeWayValue[]; // 通知方式
  key?: string; // 随机数生成的key
}

interface IAlarmGroupAdd {
  groupId?: number;
  fromRoute?: string;
  type?: TGroupType;
}

type TRouterName = 'alarm-group' | 'strategy-config-edit' | 'strategy-config-add';
type TRouterNameMap = { [key in TRouterName]: Function };

interface IFormData {
  name: string;
  bizId: string;
  users: string[];
  mention_list: { id: string; type: string }[];
  desc: string;
  alert_notice: IAlert[]; // 告警通知
  action_notice: IAlert[]; // 执行通知
  needDuty?: boolean;
  channels: string[];
  timezone: string;
}
interface IUserItem {
  id: string; // 用户id
  name: string; // 用户名
  type: 'group' | 'user';
}
// 注册路由钩子
Component.registerHooks(['beforeRouteEnter']);

// 群提醒人 需要有一个默认值
const mentListDefaultItem = {
  id: 'all',
  display_name: window.i18n.t('内部通知人'),
  logo: '',
  type: 'group',
  members: [],
  username: 'all'
};
@Component({
  components: { MemberSelector }
})
export default class AlarmGroupAdd extends tsc<IAlarmGroupAdd> {
  @Prop({ default: 'monitor', type: String, validator: (val: TGroupType) => ['monitor', 'fta'].includes(val) })
  type: TGroupType;
  @Prop({ default: null, type: Number }) groupId: number;
  @Prop({ default: '', type: String }) fromRoute: string; // 进入前路由名称

  @Ref('alertNotice') alertNoticeRef: NoticeModeNew;
  @Ref('actionNotice') actionNoticeRef: NoticeModeNew;
  // @Ref('dutyArranges') dutyArrangesRef: DutyArranges;
  @Ref('rotationConfig') rotationConfigRef: RotationConfig;

  loading = false;
  isShowOverInput = false;
  loadingSvg = require('../../../../static/images/svg/spinner.svg'); // eslint-disable-line

  errorsMsg: { [field: string]: string } = {};

  // 表单数据
  formData: IFormData = {
    channels: [],
    name: '',
    bizId: '',
    users: [],
    mention_list: [{ id: mentListDefaultItem.id, type: mentListDefaultItem.type }],
    desc: '',
    timezone: '',
    [ALERT_NOTICE]: [
      // 初始告警通知数据
      {
        time_range: ['00:00', '23:59'],
        notify_config: [
          // 通知方式
          { level: 1, notice_ways: [] },
          { level: 2, notice_ways: [] },
          { level: 3, notice_ways: [] }
        ],
        key: random(10)
      }
    ],
    [ACTION_NOTICE]: [
      // 初始处理通知数据
      {
        time_range: ['00:00', '23:59'],
        notify_config: [
          // 通知方式
          { phase: 3, notice_ways: [] },
          { phase: 2, notice_ways: [] },
          { phase: 1, notice_ways: [] }
        ],
        key: random(10)
      }
    ],
    needDuty: false
  };
  formRules: Rules = {
    name: { required: true, message: i18n.tc('输入告警组名称') },
    users: {
      validator: (rule, list) => (this.formData.needDuty ? true : !!list?.length),
      message: i18n.tc('选择告警人员')
    }
  };
  bizIdLIst = [];
  channels: string[] = ['user'];
  alertTypeList = [
    { id: 'user', name: this.$t('内部通知对象'), selected: true, icon: 'icon-mc-internal-user', show: true },
    { id: 'wxwork-bot', name: this.$t('群机器人'), selected: false, icon: 'icon-mc-robot', show: true },
    { id: 'bkchat', name: this.$t('蓝鲸信息流'), selected: false, icon: 'icon-inform-circle', show: true }
  ];

  // 用户组数据
  defaultGroupList = [];
  // 群提醒人 列表
  mentionGroupList = [];
  // 人员选择器 中 群提醒人 选中项
  selectedMentionList = ['all'];
  // 所有接收者数据
  allRecerverData = [];
  operatorText = {
    bk_bak_operator: i18n.t('来自配置平台主机的备份维护人'),
    operator: i18n.t('来自配置平台主机的主维护人')
  };

  alertActive = ''; // 当前选中的tab选项
  actionActive = '';
  alertNewkey = ''; // 用于新增时间段的样式处理
  actionNewKey = '';
  alertData: IAlert = {}; // 告警通知数据
  actionData: IAlert = {}; // 处理通知数据
  // 用key去管理子组件中的数据更新
  refreshKey = {
    alertKey: false,
    actionKey: false
  };

  /* 轮值数据 */
  dutyArranges: IDutyItem[] = [];
  dutyPlans = [];
  dutyUserList: IUserItem[] = []; // 选中过的用户详细数据
  defaultUserList: IUserItem[] = []; // 切换轮值时默认用户
  bkchatList = [];

  /* 轮值数据 ---- 新 */
  rotationData = {
    dutyArranges: [],
    dutyNotice: {
      plan_notice: { enabled: false, days: 7, chat_ids: [''], type: 'weekly', date: 1, time: '00:00' },
      personal_notice: { enabled: false, hours_ago: 168, duty_rules: [] }
    },
    rendreKey: random(8)
  };

  pageTitle = '';

  get memberSelectorKey(): string {
    return `${random(8)}-${this.defaultGroupList.length}`;
  }

  get mentionMemberSelectorKey(): string {
    return `${random(8)}-${this.mentionGroupList.length}`;
  }

  // 告警通知
  get alertTimePanels(): IPanels[] {
    return (
      this.formData.alert_notice
        .map(item => ({
          key: item.key,
          timeValue: item.time_range
        }))
        .sort(
          (a, b) =>
            (timeTransform(a.timeValue[0], false, true) as number) -
            (timeTransform(b.timeValue[0], false, true) as number)
        ) || []
    );
  }

  // 执行通知
  get actionTimePanels(): IPanels[] {
    return (
      this.formData.action_notice
        .map(item => ({
          key: item.key,
          timeValue: item.time_range
        }))
        .sort(
          (a, b) =>
            (timeTransform(a.timeValue[0], false, true) as number) -
            (timeTransform(b.timeValue[0], false, true) as number)
        ) || []
    );
  }

  // 通知方式
  get noticeWayList() {
    const { noticeWayList } = SetMealAddStore;
    this.setNoticeWayVisible(noticeWayList);
    if (noticeWayList.find(item => item.channel === 'bkchat')) {
      this.getBkchatList(); // 查询bkchat下拉选项
    }
    return noticeWayList;
  }

  async created() {
    this.updateNavData(this.groupId ? this.$tc('编辑') : this.$tc('新增告警组'));
    this.formData.bizId = this.$store.getters.bizId;
    this.formData.timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    this.bizIdLIst = this.$store.getters.bizList;
    this.alertActive = this.formData.alert_notice[0].key;
    this.alertData = this.formData.alert_notice[0];
    this.actionActive = this.formData.action_notice[0].key;
    this.actionData = this.formData.action_notice[0];
    await this.getReceiverGroup();
    this.loading = true;
    await SetMealAddStore.getNoticeWay();
    if (this.groupId) {
      await this.getGroupDetail();
    } else {
      // 新增的情况如果通知方式里有群机器人，则通知方式默认选择 内部通知对象和群机器人
      if (this.noticeWayList.find(way => way.channel === robot.wxworkBot)) {
        this.channels = ['user', 'wxwork-bot'];
        this.alertTypeList[1].selected = true;
      }
      this.loading = false;
    }
    this.refreshKey.alertKey = true;
    this.refreshKey.actionKey = true;
  }

  @Watch('formData.users')
  usersChange(users: string[]) {
    if (users.length) {
      this.errorsMsg.users = '';
    }
  }

  /** 更新面包屑 */
  updateNavData(name = '') {
    if (!name) return;
    const routeList = [];
    routeList.push({
      name,
      id: ''
    });
    this.$store.commit(`app/${SET_NAV_ROUTE_LIST}`, routeList);
  }

  setNoticeWayVisible(noticeWayList) {
    const noticeArr = [...new Set(noticeWayList.map(notice => notice.channel))];
    this.alertTypeList.forEach(type => {
      type.show = noticeArr.includes(type.id);
    });
  }

  /**
   * @description: 获取告警组详情接口
   * @param {*}
   * @return {*}
   */
  async getGroupDetail() {
    this.loading = true;
    await retrieveUserGroup(this.groupId)
      .then(data => {
        const {
          name,
          desc,
          channels,
          timezone,
          bk_biz_id: bizId,
          alert_notice: alertNotice,
          action_notice: actionNotice,
          need_duty: needDuty,
          // 选中的 群提醒人 列表
          mention_list: mentionList
        } = data;
        // this.type === 'monitor' && this.$store.commit('app/SET_NAV_TITLE', `${this.$t('编辑')} - #${id} ${name}`);
        this.updateNavData(`${this.$t('编辑')} ${name}`);
        this.pageTitle = `#${this.groupId} ${name}`;
        this.formData.name = name;
        this.formData.desc = desc;
        this.formData.bizId = bizId;
        this.formData.timezone = timezone || Intl.DateTimeFormat().resolvedOptions().timeZone;
        this.formData.channels = channels || ['user'];
        this.channels = channels || ['user'];
        // 通知类型回显
        this.alertTypeList.forEach(item => {
          item.selected = this.channels.includes(item.id);
        });
        if (needDuty) {
          // this.dutyArranges = dutyDataTransform(data.duty_arranges);
          this.dutyPlans = data.duty_plans;
          this.rotationData.dutyArranges = data.duty_rules;
          if (data.duty_notice?.personal_notice) {
            this.rotationData.dutyNotice.personal_notice = data.duty_notice.personal_notice;
          }
          if (data.duty_notice?.plan_notice) {
            this.rotationData.dutyNotice.plan_notice = data.duty_notice.plan_notice;
          }
          this.rotationData.rendreKey = random(8);
        } else {
          const users = [];
          data.duty_arranges.forEach(item => {
            item.users && users.push(...item.users);
          });
          this.formData.users = users.map(item => item.id);
        }
        this.formData.needDuty = needDuty;
        // 以下为通知方式回填
        if (alertNotice) {
          this.formData.alert_notice = alertNotice.map((item, index) => ({
            time_range: item.time_range.split('--').map(time => time.slice(0, 5)),
            notify_config: getNotifyConfig(item.notify_config),
            key: index === 0 ? this.formData.alert_notice[0].key : random(10)
          }));
        }
        if (actionNotice) {
          this.formData.action_notice = actionNotice.map((item, index) => ({
            time_range: item.time_range.split('--').map(time => time.slice(0, 5)),
            notify_config: getNotifyConfig(item.notify_config),
            key: index === 0 ? this.formData.action_notice[0].key : random(10)
          }));
        }
        this.alertActive = this.formData.alert_notice[0].key;
        this.alertData = this.formData.alert_notice[0];
        this.actionActive = this.formData.action_notice[0].key;
        this.actionData = this.formData.action_notice[0];
        // 如果后端有返回 mention_list 且有值，就将选中值替换，否则使用默认。
        if (Array.isArray(mentionList)) {
          this.selectedMentionList = mentionList.map(item => item.id);
          this.formData.mention_list = mentionList;
        } else {
          this.selectedMentionList = [];
          this.formData.mention_list = [];
        }
      })
      .finally(() => (this.loading = false));
  }

  /**
   * @description: 获取通知对象数据
   * @param {*}
   * @return {*}
   */
  async getReceiverGroup() {
    this.isShowOverInput = true;
    await getReceiver()
      .then(data => {
        this.allRecerverData = data;
        const groupData = data.find(item => item.id === 'group');
        groupData.type = 'group';
        groupData.children.map(item => (item.username = item.id));
        this.defaultGroupList.push(groupData);
        // 群提醒人 需要有一个固定选项。
        const mentionList = deepClone(groupData);
        mentionList.children.unshift(mentListDefaultItem);
        this.mentionGroupList.push(mentionList);
      })
      .finally(() => {
        this.isShowOverInput = false;
      });
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

  /**
   * @description: 处理接收人参数
   * @param {*}
   * @return {*}
   */
  handleNoticeReceiver() {
    const result = [];
    const groupMap = new Map();
    this.allRecerverData.forEach(item => {
      const isGroup = item.type === 'group';
      isGroup &&
        item.children.forEach(chil => {
          groupMap.set(chil.id, chil);
        });
    });
    this.formData.users.forEach(id => {
      const isGroup = groupMap.has(id);
      result.push({
        display_name: isGroup ? groupMap.get(id)?.display_name : id,
        logo: '',
        id,
        type: isGroup ? 'group' : 'user',
        members: isGroup ? groupMap.get(id)?.members : undefined
      });
    });
    return result;
  }

  /**
   * 收集群提醒人信息
   */
  handleMentionReceiver() {
    const result = [];
    const groupMap = new Map();
    this.allRecerverData.forEach(item => {
      const isGroup = item.type === 'group';
      isGroup &&
        item.children.forEach(chil => {
          groupMap.set(chil.id, chil);
        });
    });
    this.selectedMentionList.forEach(id => {
      const isGroup = groupMap.has(id);
      let type = isGroup ? 'group' : 'user';
      // 特殊处理 内部通知人 的情况
      if (id === 'all') type = 'group';
      result.push({
        id,
        type
      });
    });
    return result;
  }

  // 通知方式校验
  noticeValidate() {
    return new Promise((resolve, reject) => {
      const validate = [ALERT_NOTICE, ACTION_NOTICE].every((type: NoticeType) => {
        const allNoticeValidator = this.formData[type].some(noticeItem => {
          const isPass = noticeItem.notify_config.every(item => {
            if (!item.notice_ways?.length) return false;
            return true;
          });
          if (!isPass) {
            this.handleChangeTimeRang(noticeItem.key as string, type);
          }
          return !isPass;
        });
        this.$nextTick(() => {
          const refs = {
            [ALERT_NOTICE]: this.alertNoticeRef,
            [ACTION_NOTICE]: this.actionNoticeRef
          };
          refs[type].validator();
        });
        return !allNoticeValidator;
      });
      if (validate) {
        resolve(true);
      } else {
        reject();
      }
    });
  }

  // 校验
  validate(): Promise<boolean | ErrorList> {
    return new Promise((resolve, reject) => {
      const valueMap: ValidateSource = {};
      const newRules = {
        ...this.formRules
      };
      // 没有选择内部通知对象的情况，不需要加入对users的校验
      if (!this.channels.includes('user')) {
        newRules.users && delete newRules.users;
      }
      Object.keys(newRules).forEach(key => {
        valueMap[key] = this.formData[key];
      });
      const validator = new Schema(newRules);
      this.errorsMsg = {};
      validator.validate(valueMap, {}, (errors: any[]) => {
        if (!errors) {
          resolve(true);
        } else {
          errors.forEach(item => {
            this.$set(this.errorsMsg, item.field, item.message);
          });
          reject({ errors });
        }
      });
    });
  }

  // 保存通知方式的参数
  noticeParams(type: NoticeType) {
    const params = this.formData[type].map(item => ({
      time_range: item.time_range.map(time => `${time}:00`).join('--'),
      notify_config: item.notify_config.map(item => ({
        ...item,
        notice_ways: item.notice_ways.map(way => {
          const obj = {
            ...way
          };
          if (way.receivers) {
            // 使用 .trim() 移除字符串两端的换行符和其他空白字符，然后基于换行符或逗号分割字符串
            const receivers =
              typeof way.receivers === 'string'
                ? way.receivers
                    .trim()
                    .split(/\s*[\n,]+\s*/)
                    .filter(Boolean)
                : way.receivers;

            obj.receivers = receivers;
          }
          return obj;
        })
      }))
    }));
    return params;
  }

  /**
   * @description: 提交操作
   * @param {*}
   * @return {*}
   */
  async handleSubmit() {
    const res = await this.validate().catch(err => console.log(err));
    const noticeRes = await this.noticeValidate().catch(() => false);
    const dutyValidate = !this.formData.needDuty || (await this.rotationConfigRef.validate().catch(() => false));
    if (!(res && noticeRes && dutyValidate)) return;
    const { name, desc, needDuty } = this.formData;
    const params: any = {
      name,
      desc,
      // timezone: this.formData.timezone,
      need_duty: needDuty,
      duty_arranges: needDuty
        ? // ? paramsTransform(this.dutyArranges)
          undefined
        : [
            {
              duty_type: 'always',
              work_time: 'always',
              users: this.handleNoticeReceiver()
            }
          ],
      duty_rules: needDuty ? this.rotationData.dutyArranges : undefined,
      duty_notice: needDuty
        ? {
            ...this.rotationData.dutyNotice,
            plan_notice: this.rotationData.dutyNotice.plan_notice.enabled
              ? this.rotationData.dutyNotice.plan_notice
              : undefined,
            personal_notice: this.rotationData.dutyNotice.personal_notice.enabled
              ? this.rotationData.dutyNotice.personal_notice
              : undefined
          }
        : undefined,
      alert_notice: this.noticeParams(ALERT_NOTICE),
      action_notice: this.noticeParams(ACTION_NOTICE),
      // 有些项可能会被删掉，这里做一次处理
      mention_list: this.handleMentionReceiver()
    };
    // 新增参数channels
    params.channels = this.channels;
    const api = this.groupId ? params => updateUserGroup(this.groupId, params) : createUserGroup;
    this.loading = true;
    api(params)
      .then(data => {
        this.$bkMessage({ theme: 'success', message: this.groupId ? this.$t('编辑成功') : this.$t('创建成功') });
        this.handleRouterTo(data);
      })
      .finally(() => (this.loading = false));
  }

  /**
   * @description: 处理路由跳转
   * @param {*} data
   * @return {*}
   */
  handleRouterTo({ id }: { id: string }) {
    const routerMap: TRouterNameMap = {
      'alarm-group': () => {
        this.$router.push({
          name: 'alarm-group',
          params: {
            needReflesh: true
          }
        });
      },
      'strategy-config-edit': () => {
        this.$router.replace({
          name: 'strategy-config-edit',
          params: {
            alarmGroupId: id,
            id: this.$route.params.strategyId
          }
        });
      },
      'strategy-config-add': () => {
        this.$router.replace({
          name: 'strategy-config-add',
          params: {
            alarmGroupId: id
          }
        });
      }
    };
    const fn = routerMap[this.fromRoute];
    fn
      ? fn()
      : (() => {
          if (window.history.length > 1) {
            this.$router.back();
          } else {
            this.$router.push({
              name: 'alarm-group'
            });
          }
        })();
  }

  /**
   * @description: 取消操作
   * @param {*}
   * @return {*}
   */
  handleCancel() {
    if (window.history.length > 1) {
      this.$router.back();
    } else {
      this.$router.push({
        name: 'alarm-group'
      });
    }
  }

  // 添加时间段
  handleAddTimeRang(type: NoticeType) {
    let copyData: IAlert = {};
    const defaultTimeRanges = defaultAddTimeRange(
      this.formData[type].map(item => item.time_range),
      true
    );
    if (!defaultTimeRanges.length) {
      this.$bkMessage({
        theme: 'warning',
        message: window.i18n.tc('时间段重叠了')
      });
      return;
    }
    const noticeData = { [ALERT_NOTICE]: this.alertData, [ACTION_NOTICE]: this.actionData };
    copyData = deepClone(noticeData[type]);
    copyData.key = random(10);
    copyData.time_range = defaultTimeRanges[defaultTimeRanges.length - 1] as string[];
    this.formData[type].push(copyData);
    switch (type) {
      case ALERT_NOTICE:
        this.$nextTick(() => {
          this.alertNewkey = copyData.key;
          this.refreshKey.alertKey = true;
        });
        break;
      case ACTION_NOTICE:
        this.$nextTick(() => {
          this.actionNewKey = copyData.key;
          this.refreshKey.actionKey = true;
        });
        break;
    }
  }
  /* 切换时间段 */
  handleChangeTimeRang(v: string, type: NoticeType) {
    switch (type) {
      case ALERT_NOTICE:
        this.alertActive = v;
        this.alertData = this.formData.alert_notice.find(item => item.key === v);
        this.refreshKey.alertKey = true;
        break;
      case ACTION_NOTICE:
        this.actionActive = v;
        this.actionData = this.formData.action_notice.find(item => item.key === v);
        this.refreshKey.actionKey = true;
        break;
    }
  }
  /* 删除时间段 */
  handleDelTimeRang(v: string, type: NoticeType) {
    const index = this.formData[type].findIndex(item => item.key === v);
    this.formData[type].splice(index, 1);
  }
  /* 编辑时间段 */
  handleEditTimeRang(v: { value: string[]; key: string }, type: NoticeType) {
    const noticeData = { [ALERT_NOTICE]: this.alertData, [ACTION_NOTICE]: this.actionData };
    const curTimeRange = deepClone(noticeData[type].time_range);
    if (
      !timeRangeValidate(
        this.formData[type].filter(item => item.key !== v.key).map(item => item.time_range),
        v.value
      )
    ) {
      this.$bkMessage({
        theme: 'warning',
        message: window.i18n.tc('时间段重叠了')
      });
      noticeData[type].time_range = curTimeRange;
      this.handleNoticeChange(type);
      return;
    }
    noticeData[type].time_range = v.value;
    this.handleNoticeChange(type);
    // 时间段校验
  }
  /* 编辑通知方式 */
  noticeConfigChange(v: INoticeWayValue[], type: NoticeType) {
    switch (type) {
      case ALERT_NOTICE:
        this.alertData.notify_config = v;
        break;
      case ACTION_NOTICE:
        this.actionData.notify_config = executionNotifyConfigChange(v, false);
        break;
    }
    this.handleNoticeChange(type);
  }
  /* 整理数据 */
  handleNoticeChange(type: NoticeType) {
    const noticeData = { [ALERT_NOTICE]: this.alertData, [ACTION_NOTICE]: this.actionData };
    const noticeActive = { [ALERT_NOTICE]: this.alertActive, [ACTION_NOTICE]: this.actionActive };
    this.formData[type] = this.formData[type].map(item => {
      if (item.key === noticeActive[type]) {
        return deepClone(noticeData[type]);
      }
      return item;
    });
  }

  handleDutyArranges(v) {
    this.dutyArranges = v;
  }
  /* 点击开启轮值 */
  handleCheckNeedDuty() {
    return new Promise<void>(resolve => {
      if (!this.formData.needDuty) {
        this.defaultUserList = this.dutyUserList.filter(item => this.formData.users.includes(item.id as any));
      }
      resolve();
    });
  }
  /* 切换通知对象 (直接通知/轮值) */
  handleAlertMethodChange(val) {
    this.formData.needDuty = val;
    this.handleCheckNeedDuty();
    this.refreshKey.alertKey = true;
    this.refreshKey.actionKey = true;
  }

  /* 新增时默认通知用户传至轮值组件 */
  handleSelectUser(user) {
    if (this.dutyUserList.map(item => item.id).includes(user.username)) return;
    this.dutyUserList.push({
      id: user.username,
      name: user.display_name,
      type: user.type || 'user'
    });
  }
  handleSelectMentionUser(user) {
    if (this.formData.mention_list.map(item => item.id).includes(user.username)) return;
    this.formData.mention_list.push({
      id: user.id,
      type: user.type
    });
  }
  /* 选择通知类型 */
  handleSelectAlertType(item) {
    const { id, selected } = item;
    const selectedArray = this.alertTypeList.filter(item => item.selected === true) || [];
    const { length: arrayLength } = selectedArray;
    // 当前只选了一种通知类型，并且当前点击对象就是该类型时不处理
    if (arrayLength === 1 && selectedArray[0].id === id) return;
    item.selected = !selected;
    this.channels = this.alertTypeList.filter(item => item.selected).map(item => item.id);
    this.refreshKey.alertKey = true;
    this.refreshKey.actionKey = true;
    // 群机器人 项需要做特殊处理,在编辑页手动选中时需要添加相应的默认值。
    if (id === 'wxwork-bot' && selected) {
      if (this.selectedMentionList.length === 0) {
        this.selectedMentionList = ['all'];
        this.formData.mention_list = [{ id: mentListDefaultItem.id, type: mentListDefaultItem.type }];
      }
    }
  }

  render(): VNode {
    return (
      <div
        class='alarm-group-add-wrap'
        title={!!this.groupId ? this.pageTitle : ''}
        v-bkloading={{ isLoading: this.loading }}
      >
        <bk-form label-width={this.$store.getters.lang === 'en' ? 150 : 100}>
          <bk-form-item label={this.$t('所属')}>
            <bk-select
              class='width-508'
              clearable={false}
              readonly
              v-model={this.formData.bizId}
              placeholder={this.$t('输入所属空间')}
            >
              {this.bizIdLIst.map(opt => (
                <bk-option
                  key={opt.id}
                  id={opt.id}
                  name={opt.text}
                ></bk-option>
              ))}
            </bk-select>
          </bk-form-item>
          <bk-form-item
            label={this.$t('告警组名称')}
            required
            property='name'
          >
            <div class='input-item width-508'>
              <bk-input
                v-model={this.formData.name}
                onFocus={() => (this.errorsMsg.name = '')}
              ></bk-input>
              {this.errorsMsg.name && <div class='error-msg'>{this.errorsMsg.name}</div>}
            </div>
          </bk-form-item>
          {/* <bk-form-item
            label={this.$t('时区')}
            required
            property='name'
          >
            <div class='width-508'>
              <TimezoneSelect
                value={this.formData.timezone}
                onChange={v => (this.formData.timezone = v)}
              ></TimezoneSelect>
            </div>
          </bk-form-item> */}
          {/* <bk-form-item label={this.$t('开启轮值')}>*/}
          {/*  <div class="input-duty">*/}
          {/*    <bk-switcher v-model={this.formData.needDuty}*/}
          {/*      pre-check={this.handleCheckNeedDuty}*/}
          {/*      theme="primary"></bk-switcher>*/}
          {/*    <span class="icon-monitor icon-hint"*/}
          {/*      v-bk-tooltips={{*/}
          {/*        placements: ['top'],*/}
          {/*        content: window.i18n.t('轮值功能，可以按不同的时段分配不同的值班成员')*/}
          {/*      }}></span>*/}
          {/*  </div>*/}
          {/* </bk-form-item>*/}
          <bk-form-item
            label={this.$t('通知类型')}
            required
            property='alert_type'
          >
            <div class='alert-type'>
              {this.alertTypeList.map(
                item =>
                  item.show && (
                    <div
                      class={[
                        'type-card',
                        item.selected && 'selected-card',
                        this.channels.length === 1 && 'select-disabled'
                      ]}
                      onClick={() => this.handleSelectAlertType(item)}
                    >
                      <i class={['icon-monitor', item.icon, item.selected && 'selected-icon', 'type-icon']} />
                      <div class='card-name'>{item.name}</div>
                    </div>
                  )
              )}
            </div>
          </bk-form-item>
          {this.channels.includes('user') && (
            <bk-form-item
              label={this.$t('通知对象')}
              required
              property='users'
            >
              <div class='item-container'>
                {this.isShowOverInput && (
                  <div class='over-input'>
                    <img
                      alt=''
                      src={this.loadingSvg}
                      class='status-loading'
                    />
                  </div>
                )}
                <div class='input-item'>
                  <bk-radio-group
                    class='radio-group'
                    v-model={this.formData.needDuty}
                    on-change={this.handleAlertMethodChange}
                  >
                    <bk-radio-button
                      value={false}
                      class='radio-button'
                    >
                      {this.$t('直接通知')}
                    </bk-radio-button>
                    <bk-radio-button
                      value={true}
                      class='radio-button'
                    >
                      {this.$t('轮值')}
                    </bk-radio-button>
                  </bk-radio-group>
                  {!this.formData.needDuty && (
                    <member-selector
                      class='user-selector'
                      key={this.memberSelectorKey}
                      v-model={this.formData.users}
                      group-list={this.defaultGroupList}
                      on-select-user={this.handleSelectUser}
                    />
                  )}
                  {!this.formData.needDuty && this.errorsMsg.users && (
                    <div class='error-msg'>{this.errorsMsg.users}</div>
                  )}
                </div>
                {this.handleNoticeReceiver().map(item =>
                  item.type === 'group' ? (
                    <div class='text-msg'>
                      {`${item.display_name}(${
                        ['bk_bak_operator', 'operator'].includes(item.id)
                          ? this.operatorText[item.id]
                          : this.$t('来自配置平台')
                      })`}
                      {!['bk_bak_operator', 'operator'].includes(item.id) ? (
                        item.members.length ? (
                          <span>
                            {'，'}
                            {this.$t('当前成员')} {item.members.map(m => `${m.id}(${m.display_name})`).join('; ')}
                          </span>
                        ) : (
                          <span>
                            {'，'}
                            {this.$t('当前成员')}
                            {`(${this.$t('空')})`}
                          </span>
                        )
                      ) : undefined}
                    </div>
                  ) : undefined
                )}
                {/* <div class="text-tip">*/}
                {/*  <span class="icon-monitor icon-hint"></span>*/}
                {/*  {this.$t('电话语音通知，拨打的顺序是按通知对象顺序依次拨打，用户组内无法保证顺序')}*/}
                {/* </div>*/}
                {!this.formData.needDuty && (
                  <div class='directly-text-tip'>
                    {this.$t('处理套餐中使用了电话语音通知，拨打的顺序是按通知对象顺序依次拨打，用户组内无法保证顺序')}
                  </div>
                )}
              </div>
            </bk-form-item>
          )}
          {this.formData.needDuty && (
            <bk-form-item
              label={this.$t('轮值设置')}
              required
            >
              {/* <div class='item-duty'>
                <DutyArranges
                  ref='dutyArranges'
                  value={this.dutyArranges}
                  dutyPlans={this.dutyPlans}
                  defaultGroupList={this.defaultGroupList}
                  defaultUserList={this.defaultUserList}
                  onChange={this.handleDutyArranges}
                ></DutyArranges>
              </div> */}
              <RotationConfig
                ref={'rotationConfig'}
                defaultGroupList={this.defaultGroupList}
                dutyArranges={this.rotationData.dutyArranges}
                dutyNotice={this.rotationData.dutyNotice}
                rendreKey={this.rotationData.rendreKey}
                alarmGroupId={this.groupId}
                dutyPlans={this.dutyPlans}
                onDutyChange={v => (this.rotationData.dutyArranges = v)}
                onNoticeChange={v => (this.rotationData.dutyNotice = v)}
              ></RotationConfig>
            </bk-form-item>
          )}
          {this.channels.includes('wxwork-bot') && (
            <bk-form-item label={this.$t('群提醒人')}>
              <member-selector
                class='mention-user-selector'
                key={this.mentionMemberSelectorKey}
                v-model={this.selectedMentionList}
                group-list={this.mentionGroupList}
                on-select-user={this.handleSelectMentionUser}
              />
            </bk-form-item>
          )}
          <bk-form-item
            label={this.$t('通知方式')}
            required
          >
            <div class='notice-wrap'>
              <div class='title'>{this.$t('告警阶段')}</div>
              <div class='content-wrap-key1'>
                <CustomTab
                  panels={this.alertTimePanels}
                  active={this.alertActive}
                  type={'period'}
                  newKey={this.alertNewkey}
                  timeStyleType={1}
                  minIsMinute={true}
                  onAdd={() => this.handleAddTimeRang(ALERT_NOTICE)}
                  onChange={v => this.handleChangeTimeRang(v, ALERT_NOTICE)}
                  onDel={v => this.handleDelTimeRang(v, ALERT_NOTICE)}
                  onTimeChange={v => this.handleEditTimeRang(v, ALERT_NOTICE)}
                ></CustomTab>
                <div class='wrap-bottom'>
                  <span class='bottom-title'>{this.$t('每个告警级别至少选择一种通知方式')}</span>
                  <NoticeModeNew
                    class='notice-mode'
                    ref='alertNotice'
                    noticeWay={this.noticeWayList}
                    notifyConfig={this.alertData.notify_config}
                    channels={this.channels}
                    bkchatList={this.bkchatList}
                    showHeader={false}
                    showlevelMark={true}
                    refreshKey={this.refreshKey.alertKey}
                    onChange={v => this.noticeConfigChange(v, ALERT_NOTICE)}
                    onRefreshKeyChange={() => (this.refreshKey.alertKey = false)}
                  ></NoticeModeNew>
                </div>
              </div>
              <div
                class='title'
                style={{ marginTop: '16px' }}
              >
                {this.$t('执行通知')}
                <span class='title-tip'>
                  {this.$t('当告警策略配置了告警处理，可以通过如下的通知方式获取到执行处理套餐的结果')}。
                </span>
              </div>
              <div class='content-wrap-key1'>
                <CustomTab
                  panels={this.actionTimePanels}
                  active={this.actionActive}
                  type={'period'}
                  newKey={this.actionNewKey}
                  timeStyleType={1}
                  minIsMinute={true}
                  onAdd={() => this.handleAddTimeRang(ACTION_NOTICE)}
                  onChange={v => this.handleChangeTimeRang(v, ACTION_NOTICE)}
                  onDel={v => this.handleDelTimeRang(v, ACTION_NOTICE)}
                  onTimeChange={v => this.handleEditTimeRang(v, ACTION_NOTICE)}
                ></CustomTab>
                <div class='wrap-bottom'>
                  <span class='bottom-title'>{this.$t('每个执行阶段至少选择一种通知方式')}</span>
                  <NoticeModeNew
                    class='notice-mode'
                    ref='actionNotice'
                    noticeWay={this.noticeWayList}
                    notifyConfig={executionNotifyConfigChange(this.actionData?.notify_config)}
                    channels={this.channels}
                    bkchatList={this.bkchatList}
                    type={1}
                    refreshKey={this.refreshKey.actionKey}
                    onChange={v => this.noticeConfigChange(v, ACTION_NOTICE)}
                    onRefreshKeyChange={() => (this.refreshKey.actionKey = false)}
                  ></NoticeModeNew>
                </div>
              </div>
            </div>
          </bk-form-item>
          <bk-form-item label={this.$t('说明')}>
            <bk-input
              class='input-desc'
              type='textarea'
              maxlength={100}
              v-model={this.formData.desc}
              placeholder={this.$t('输入')}
            ></bk-input>
          </bk-form-item>
        </bk-form>
        <div class='footer'>
          <bk-button
            theme='primary'
            title={this.$t('提交')}
            onClick={this.handleSubmit}
          >
            {this.$t('提交')}
          </bk-button>
          <bk-button
            theme='default'
            title={this.$t('取消')}
            onClick={this.handleCancel}
          >
            {this.$t('取消')}
          </bk-button>
        </div>
      </div>
    );
  }
}
