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

import { deepClone, random } from '../../../../monitor-common/utils/utils';

import { randomColor } from './color';
import CustomDatePick from './custom-date-pick';
import CustomTimeRange from './custom-time-range';
import DutyPreview, { IPreviewValue, IUserGroup } from './duty-preview';
import SimpleDayPick from './simple-day-pick';
import UserListSort, { IUserListItem } from './user-list-sort';
import { IGroupListItem } from './user-selector';

import './duty-arranges.scss';

interface IuserItem {
  // 用户组
  id: string; // 用户id
  name: string; // 用户名
  type: 'group' | 'user';
}

type TWorkType = 'daily' | 'weekly' | 'monthly' | '';
export interface IDutyItem {
  key: string;
  isExpan: boolean; // 是否展开
  title: string; // 组名
  draggable: boolean; // 是否可抓取
  subTitle: string; // 轮值时间
  id?: number; // 轮值ID(非必须)
  needRotation?: boolean; // 是否需要交接
  handoffTime?: {
    // 交接时间
    rotationType: TWorkType; // 轮值类型
    date: number; // 日期
    time: string; // 时间
  };
  effectiveReadonly?: boolean;
  effectiveTime?: string; // 生效时间
  effectiveTimeKey?: string;
  effectiveIsAutoFill?: boolean; // 是否由系统自动填充的时间
  dutyTime?: {
    // 工作时间
    workType: TWorkType; // 轮值类型
    workDays: number[]; // 日期
    workTime: string[]; // 时间
  };
  dutyUsers: {
    color: string; // 颜色
    key: string;
    users: IuserItem[];
  }[];
  backups: {
    // 代班信息
    users: {
      // 代班人员
      id: string;
      type: 'group' | 'user';
    }[];
    beginTime: string; // 开始时间
    endTime: string; // 结束时间
    excludeSettings: {
      // 被取消代班的时间
      date: string; // 日期
      time: string; // 时间
    }[];
  }[];
}

const operatorText = {
  bk_bak_operator: window.i18n.t('来自配置平台主机的备份维护人'),
  operator: window.i18n.t('来自配置平台主机的主维护人')
};

const daysZh = ['一', '二', '三', '四', '五', '六', '日'];
/* 每组头部副标题 */
const getSubtitleStr = (dutyTime: IDutyItem['dutyTime']) => {
  const isZh = ['zhCN'].includes(window.i18n.locale);
  const { workType, workDays, workTime } = dutyTime;
  if (workType === 'daily') {
    return `${window.i18n.t('轮值时间')}: ${window.i18n.t('每天')} ${workTime.join('-')}`;
  }
  if (workType === 'weekly' && !!workDays.length && !!workTime.length) {
    return `${window.i18n.t('轮值时间')}: ${window.i18n.t('每周')} ${JSON.parse(JSON.stringify(workDays))
      .sort((a, b) => Number(a) - Number(b))
      .map(item => (isZh ? daysZh[Number(item) - 1] : item))
      .join('、')} ${workTime.join('-')}`;
  }
  if (workType === 'monthly' && !!workDays.length && !!workTime.length) {
    return `${window.i18n.t('轮值时间')}: ${window.i18n.t('每月')} ${JSON.parse(JSON.stringify(workDays))
      .sort((a, b) => Number(a) - Number(b))
      .join('、')} ${workTime.join('-')}`;
  }
  return '';
};

const newDateToDateStr = () => {
  const curDate = new Date();
  const year = curDate.getFullYear();
  const month = curDate.getMonth() + 1;
  const date = curDate.getDate();
  const hours = curDate.getHours();
  const minutes = curDate.getMinutes();
  return {
    timestamp: curDate.getTime(),
    value: `${year}-${month < 10 ? `0${month}` : month}-${date < 10 ? `0${date}` : date} ${
      hours < 10 ? `0${hours}` : hours
    }:${minutes < 10 ? `0${minutes}` : minutes}`
  };
};

const defaultDutyItem = (index: number, colorIndex: number, defalutUsers: IuserItem[] = []) => ({
  key: random(8),
  isExpan: true,
  draggable: false,
  title: window.i18n.t('第 {0} 组', [index]),
  subTitle: getSubtitleStr({ workDays: [], workType: 'daily', workTime: ['00:00', '23:59'] } as any),
  needRotation: false,
  handoffTime: {
    rotationType: 'daily',
    date: 1,
    time: '00:00'
  },
  effectiveReadonly: false,
  effectiveTime: newDateToDateStr().value,
  effectiveTimeKey: random(8),
  effectiveIsAutoFill: true,
  dutyTime: {
    workType: 'daily',
    workDays: [],
    workTime: ['00:00', '23:59']
  },
  dutyUsers: [
    {
      color: randomColor(colorIndex),
      key: random(8),
      users: defalutUsers
    }
  ],
  backups: [
    {
      users: [],
      beginTime: '2022-03-11 00:00:00',
      endTime: '2022-03-11 00:00:00',
      excludeSettings: []
    }
  ]
});

const weekDaysList = [
  { name: window.i18n.tc('星期一'), id: 1 },
  { name: window.i18n.tc('星期二'), id: 2 },
  { name: window.i18n.tc('星期三'), id: 3 },
  { name: window.i18n.tc('星期四'), id: 4 },
  { name: window.i18n.tc('星期五'), id: 5 },
  { name: window.i18n.tc('星期六'), id: 6 },
  { name: window.i18n.tc('星期日'), id: 7 }
];

/* 轮值类型 */
const DUTY_TYPE = [
  { id: 'daily', name: window.i18n.tc('每天') },
  { id: 'weekly', name: window.i18n.tc('每周') },
  { id: 'monthly', name: window.i18n.tc('每月') }
];
/* 获取近七天的日期 */
const getLastDays = (max: number, start = 0): { name: string; dateObj: Date; dayTimeStamp: number }[] => {
  const dateArr = [];
  const oneDay = 24 * 60 * 60 * 1000;
  const toDay = new Date();
  for (let i = start; i < max; i++) {
    const targetDate = new Date(toDay.getTime() + i * oneDay);
    const month = targetDate.getMonth() + 1;
    const day = targetDate.getDate();
    const dateStr = `${targetDate.getFullYear()}-${month < 10 ? `0${month}` : month}-${day < 10 ? `0${day}` : day}`;
    dateArr.push({
      name: `${month}-${day}`,
      dateObj: targetDate,
      dayTimeStamp: new Date(dateStr).getTime()
    });
  }
  return dateArr;
};
/* 获取某一周期的7天*/
const getCycleDays = (cycleNumber: number) => {
  let start = 0;
  let end = 0;
  if (cycleNumber === 0) {
    end = 7;
  } else {
    start = cycleNumber * 7;
    end = (cycleNumber + 1) * 7;
  }
  return getLastDays(end, start);
};

/* 获取一天到某一周期最后一天的日期列表 */
const getTargetDays = (start: string, cycle: number): { name: string; dateObj: Date; dayTimeStamp: number }[] => {
  const startDate = new Date(start);
  const oneDay = 24 * 60 * 60 * 1000;
  const toDay = new Date();
  const targetDate = new Date(toDay.getTime() + oneDay * (cycle + 1) * 7);
  const month = targetDate.getMonth() + 1;
  const day = targetDate.getDate();
  const dateStr = `${targetDate.getFullYear()}-${month < 10 ? `0${month}` : month}-${day < 10 ? `0${day}` : day}`;
  const endDate = new Date(dateStr);
  const startTime = startDate.getTime();
  const endTime = endDate.getTime();
  const dateArr = [];
  for (let i = startTime; i < endTime; i += oneDay) {
    const dateObj = new Date(i);
    const month = dateObj.getMonth() + 1;
    const day = dateObj.getDate();
    dateArr.push({
      name: `${month}-${day}`,
      dateObj,
      dayTimeStamp: i
    });
  }
  return dateArr;
};
interface IDutyplan {
  // 生效时间之前的
  begin_time: string;
  end_time: string;
  duty_arrange_id: number;
  duty_time: {
    work_days: number[];
    work_time: string;
    work_type: TWorkType;
  }[];
  users: {
    id: string;
    display_name: string;
  }[];
}

/* 转换为参数传入后台 */
export const paramsTransform = (dutyArranges: IDutyItem[]) =>
  dutyArranges.map(item => ({
    id: item?.id,
    need_rotation: item.needRotation,
    effective_time: (() => {
      if (item.effectiveIsAutoFill) {
        const dateObj = newDateToDateStr();
        return dateObj.value;
      }
      return item.effectiveTime;
    })(),
    handoff_time: {
      rotation_type: item.handoffTime.rotationType,
      date: item.handoffTime.date,
      time: item.handoffTime.time
    },
    duty_time: [
      {
        work_type: item.dutyTime.workType,
        work_days: item.dutyTime.workDays,
        work_time: item.dutyTime.workTime.join('--')
      }
    ],
    backups: [],
    duty_users: item.dutyUsers.map(u =>
      u.users.map(user => ({
        display_name: user.name,
        type: user.type,
        id: user.id
      }))
    )
  }));
/* 后台数组转为组件数据 */
export const dutyDataTransform = (data: any[]): IDutyItem[] => {
  const dataColors = data.map(item => item.duty_users.length);
  return data.map((item, index) => {
    const effective = new Date(item.effective_time);
    const effectiveYear = effective.getFullYear();
    const effectiveMonth = effective.getMonth() + 1;
    const effectiveDay = effective.getDate();
    const effectiveHours = effective.getHours();
    const effectiveMinutes = effective.getMinutes();
    const effectiveTime = `${effectiveYear}-${effectiveMonth < 10 ? `0${effectiveMonth}` : effectiveMonth}-${
      effectiveDay < 10 ? `0${effectiveDay}` : effectiveDay
    } ${effectiveHours < 10 ? `0${effectiveHours}` : effectiveHours}:${
      effectiveMinutes < 10 ? `0${effectiveMinutes}` : effectiveMinutes
    }`;
    const effectiveTimeNum = effective.getTime();
    return {
      key: random(8),
      id: item.id,
      isExpan: false,
      draggable: false,
      title: window.i18n.t('第 {0} 组', [index + 1]),
      subTitle: getSubtitleStr({
        workDays: item.duty_time[0].work_days,
        workType: item.duty_time[0].work_type,
        workTime: item.duty_time[0].work_time.split('--')
      } as any),
      needRotation: item.need_rotation,
      handoffTime: {
        rotationType: item.handoff_time.rotation_type,
        date: item.handoff_time.date,
        time: item.handoff_time.time
      },
      effectiveReadonly: effectiveTimeNum < new Date().getTime(),
      effectiveTime,
      effectiveTimeKey: random(8),
      effectiveIsAutoFill: false,
      dutyTime: {
        workType: item.duty_time[0].work_type,
        workDays: item.duty_time[0].work_days,
        workTime: item.duty_time[0].work_time.split('--')
      },
      dutyUsers: item.duty_users.map((group, groupIndex) => ({
        color: (() => {
          let curColor = 0;
          dataColors.forEach((colorLen, colorIndex) => {
            if (colorIndex < index) {
              curColor += colorLen;
            }
          });
          curColor += groupIndex;
          return randomColor(curColor);
        })(),
        key: random(8),
        users: group.map(g => ({
          id: g.id,
          name: g.display_name,
          type: g.type
        }))
      })),
      backups: []
    } as any;
  });
};
interface IProps {
  value?: IDutyItem[]; // 轮值组
  defaultGroupList?: IGroupListItem[];
  readonly?: boolean;
  dutyPlans?: IDutyplan[]; // 生效时间
  defaultUserList?: IuserItem[]; // 开启轮值时通知对象带过来
}
interface IEvents {
  onChange?: IDutyItem[];
}
@Component
export default class DutyArranges extends tsc<IProps, IEvents> {
  @Prop({ default: () => [], type: Array }) value: IDutyItem[];
  @Prop({ default: () => [], type: Array }) defaultGroupList: IGroupListItem[];
  @Prop({ default: false, type: Boolean }) readonly: boolean;
  @Prop({ default: () => [], type: Array }) dutyPlans: IDutyplan[];
  @Prop({ default: () => [], type: Array }) defaultUserList: IuserItem[];
  /* 轮值 组 */
  dutyArranges: IDutyItem[] = [];
  /* 拖拽 */
  isDraging = false;
  dragOver: IDutyItem = null;

  /* 第几个周期 0 代表当前周 -1 代表上一周*/
  cycleNumber = 0;
  /* 预览数据 */
  previewData: IPreviewValue = {
    leisure: [],
    dateStrArr: [],
    groups: [],
    max: 1440,
    crossDayGroups: []
  };
  previewKey = random(8);

  /* 轮值预览下的统计信息 */
  userPreviewList: { name: string; id: string }[] = [];

  /* 校验 */
  errMsgList: string[] = [];
  errKey = random(8);

  /* 用于统计信息 */
  get userGroupData(): {
    display_name: string;
    id: string;
    members: { display_name: string; id: string }[];
  }[] {
    const userGroupData = [];
    this.defaultGroupList.forEach(item => {
      if (item.type === 'group') {
        item.children.forEach(child => {
          userGroupData.push(child);
        });
      }
    });
    return userGroupData;
  }

  /* 所有用户组的个数 */
  get getAllUsersLength() {
    let index = 0;
    this.dutyArranges.forEach(item => {
      index += item.dutyUsers.length;
    });
    return index;
  }

  created() {
    if (this.value.length) {
      this.dutyArranges = [...this.value];
    } else {
      if (this.dutyArranges.length) {
        this.dutyArranges.push(defaultDutyItem(1, 0) as IDutyItem);
      } else {
        this.dutyArranges.push(defaultDutyItem(1, 0, this.defaultUserList) as IDutyItem);
      }
    }
    this.setPreviewData();
  }

  /* 是否展开 */
  handleExpan(index: number, type) {
    if (type === 'expan') {
      this.dutyArranges[index].isExpan = !this.dutyArranges[index].isExpan;
    }
  }
  /* 是否交接 */
  handleNeedRotation(v: boolean, index: number) {
    this.resetEffective(index);
    if (!v) {
      this.dutyArranges[index].dutyUsers = this.dutyArranges[index].dutyUsers.filter((_item, index) => index === 0);
      this.dutyArranges[index].key = random(8);
    }
    this.setPreviewData();
  }
  /* 新增组 */
  handleAddGroup() {
    let colorIndex = 0;
    this.dutyArranges.forEach(item => {
      colorIndex += item.dutyUsers.length;
    });
    this.dutyArranges.push(defaultDutyItem(this.dutyArranges.length + 1, colorIndex) as IDutyItem);
    this.setPreviewData();
  }
  /* 进入拖拽区域 */
  handleMouseenter(index: number) {
    this.dutyArranges[index].draggable = true;
  }
  /* 离开拖拽区域 */
  handleMouseleave(index: number) {
    this.dutyArranges[index].draggable = false;
  }
  /* 拖拽开始 */
  handleDragStart(event: DragEvent, index) {
    event.stopPropagation();
    event.dataTransfer.setData('item', JSON.stringify(this.dutyArranges[index]));
    this.isDraging = true;
  }
  /* 拖拽结束 */
  handleDragEnd(event: DragEvent) {
    event.stopPropagation();
    setTimeout(() => {
      this.isDraging = false;
      this.dragOver = null;
    }, 500);
  }
  /* 拖拽到目标处，返回目标数据 */
  handleDragOver(event: DragEvent, index) {
    event.stopPropagation();
    event.preventDefault();
    this.dragOver = JSON.parse(JSON.stringify(this.dutyArranges[index]));
  }
  /* 释放至目标 */
  handleDrop(event: DragEvent) {
    event.preventDefault();
    try {
      const dragItem: IDutyItem = JSON.parse(event.dataTransfer.getData('item'));
      const dragIndex = this.dutyArranges.findIndex(item => item.key === dragItem.key); // 拖拽目标位置
      const dropIndex = this.dutyArranges.findIndex(item => item.key === this.dragOver.key); // 释放目标位置
      const tmp = this.dutyArranges.splice(dragIndex, 1);
      this.dutyArranges.splice(dropIndex, 0, tmp[0]);
      this.dragOver = null;
    } catch {
      console.warn('parse drag data error');
    }
    this.dutyArranges.forEach((item, index) => {
      item.title = window.i18n.t('第 {0} 组', [index + 1]) as string;
    });
    this.setPreviewData();
  }

  /* 删除 */
  handleDelete(index: number) {
    this.dutyArranges.splice(index, 1);
    this.dutyArranges.forEach((item, index) => {
      item.title = window.i18n.t('第 {0} 组', [index + 1]) as string;
    });
    this.setPreviewData();
  }

  /* 用户组数据 */
  handleUserListChange(v: IUserListItem[], index: number) {
    this.dutyArranges[index].dutyUsers = v.map(item => ({
      ...item,
      users: item.userList
    }));
    this.resetEffective(index);
    this.setPreviewData();
  }
  /* 工作周期 */
  handleWorkDaysChange(v: number[], index: number) {
    this.dutyArranges[index].dutyTime.workDays = v;
    this.dutyArranges[index].subTitle = getSubtitleStr(this.dutyArranges[index].dutyTime);
    this.resetEffective(index);
    this.setPreviewData();
  }
  /* 工作时间 */
  handleWorkTimeChange(v: string[], index) {
    this.dutyArranges[index].dutyTime.workTime = v;
    this.dutyArranges[index].subTitle = getSubtitleStr(this.dutyArranges[index].dutyTime);
    this.resetEffective(index);
    this.setPreviewData();
  }
  /* 交接周期 */
  handleHandOffTimeDateChange(v: number, index: number) {
    this.dutyArranges[index].handoffTime.date = v;
    this.resetEffective(index);
    this.setPreviewData();
  }
  /* 生效时间 */
  handleEffectiveTimeChange(v: string, index: number) {
    this.$nextTick(() => {
      this.dutyArranges[index].effectiveIsAutoFill = false;
      this.dutyArranges[index].effectiveTime = v;
      this.dutyArranges[index].effectiveReadonly = false;
      this.setPreviewData();
    });
  }
  /* 交接时间 */
  handleHandOffTimeChange(v: string, index: number) {
    this.resetEffective(index);
    this.setPreviewData();
  }
  /* 轮值类型 */
  handleRotationTypeChange(index: number) {
    this.dutyArranges[index].handoffTime.date = 1;
    this.resetEffective(index);
    this.setPreviewData();
  }
  /* 切换工作周期类型 */
  handleDutyTypeChange(index: number) {
    this.dutyArranges[index].subTitle = getSubtitleStr(this.dutyArranges[index].dutyTime);
    this.dutyArranges[index].dutyTime.workDays = [];
    this.dutyArranges[index].dutyTime.workTime = ['00:00', '23:59'];
    this.resetEffective(index);
    this.dutyArranges[index].key = random(8);
    this.setPreviewData();
  }

  /* 编辑轮值设置时需要将生效时间重置为当前时间 */
  resetEffective(index: number) {
    const dateObj = newDateToDateStr();
    this.dutyArranges[index].effectiveReadonly = false;
    const oldTimestamp = new Date(this.dutyArranges[index].effectiveTime).getTime();
    if (oldTimestamp < dateObj.timestamp) {
      this.dutyArranges[index].effectiveIsAutoFill = true;
      this.dutyArranges[index].effectiveTime = dateObj.value;
      this.dutyArranges[index].effectiveTimeKey = random(8);
    }
  }

  /* 校验 */
  validate() {
    return new Promise((resolve, reject) => {
      this.dutyArranges.forEach((item, index) => {
        if (item.needRotation) {
          if (item.dutyUsers.length < 2) {
            this.errMsgList[index] = window.i18n.tc('交接时需要至少两个用户组');
          } else if (!item.dutyUsers.every(u => u.users.length)) {
            this.errMsgList[index] = window.i18n.tc('每个用户组至少需要一个用户');
          } else if (!item.handoffTime.time) {
            this.errMsgList[index] = window.i18n.tc('输入交接时间');
          } else if (item.handoffTime.rotationType !== 'daily' && !item.handoffTime.date) {
            this.errMsgList[index] = window.i18n.tc('输入轮值周期');
          } else if (item.dutyTime.workType !== 'daily' && !item.dutyTime.workDays.length) {
            this.errMsgList[index] = window.i18n.tc('输入工作周期');
          } else if (!item.dutyTime.workTime) {
            this.errMsgList[index] = window.i18n.tc('输入工作时间');
          } else if (!item.effectiveTime) {
            this.errMsgList[index] = window.i18n.tc('输入生效时间');
          }
        } else {
          if (!item.dutyUsers[0].users.length) {
            this.errMsgList[index] = window.i18n.tc('输入用户');
          } else if (item.dutyTime.workType !== 'daily' && !item.dutyTime.workDays.length) {
            this.errMsgList[index] = window.i18n.tc('输入工作周期');
          } else if (!item.dutyTime.workTime) {
            this.errMsgList[index] = window.i18n.tc('输入工作时间');
          } else if (!item.effectiveTime) {
            this.errMsgList[index] = window.i18n.tc('输入生效时间');
          }
        }
        if (!item.effectiveReadonly && !item.effectiveIsAutoFill) {
          const toDayTimestamp = new Date().getTime();
          const effectiveTimestamp = new Date(item.effectiveTime).getTime();
          if (effectiveTimestamp / 60000 < Math.floor(toDayTimestamp / 60000)) {
            this.errMsgList[index] = window.i18n.tc('更新轮值设置时生效时间不能小于当前时间');
          }
        }
      });
      const validate = this.errMsgList.every(item => !item);
      this.errKey = random(8);
      if (validate) {
        resolve(true);
      } else {
        reject();
      }
    });
  }
  /* 转换轮值预览数据 */
  setPreviewData() {
    const oneDay = 24 * 60 * 60 * 1000;
    /* 获取生效时间前的轮值 */
    const dutyPlansObj: {
      [id: string]: {
        targetEffectiveTime: string;
        data: {
          dateStr: string;
          year: string;
          ranges: number[][];
          users: { id: string; name: string }[];
        }[];
      };
    } = {};
    const dutyArranges: IDutyItem[] = deepClone(this.dutyArranges);
    /* 初始化校验信息 */
    this.errMsgList = dutyArranges.map(() => '');
    this.errKey = random(8);
    const userPreviewList = [];
    /* 轮值预览下方统计信息 */
    dutyArranges.forEach(item => {
      if (item?.id) {
        dutyPlansObj[item.id] = {
          targetEffectiveTime: item.effectiveTime,
          data: []
        };
      }
      item.dutyUsers.forEach(users => {
        users.users.forEach(user => {
          if (user.type === 'group') {
            if (!userPreviewList.map(u => u.id).includes(user.id)) {
              userPreviewList.push({
                id: user.id,
                name: user.name
              });
            }
          }
        });
      });
    });
    this.userPreviewList = userPreviewList;
    /* 时间转为长度 */
    const timeToNum = (time: string): number => {
      const timeArr = time.split(':');
      const hTime = Number(timeArr[0]);
      const mTime = Number(timeArr[1]);
      return hTime * 60 + mTime;
    };
    /* 长度转为时间段  */
    const rangeToTime = (range: number[]) => {
      const hours = (num: number) => {
        const n = Math.floor(num / 60);
        return n < 10 ? `0${n}` : n;
      };
      const minutes = (num: number) => {
        const n = Math.floor(num % 60);
        return n < 10 ? `0${n}` : n;
      };
      return `${`${hours(range[0])}:${minutes(range[0])}`}-${`${hours(range[1] ? range[1] - 1 : 0)}:${minutes(
        range[1] ? range[1] - 1 : 0
      )}`}`;
    };
    const computeTimePoint = (time: string[]) => {
      const date = time[0];
      const minutes = time[1].split(':');
      const dateObj = new Date(date);
      const minutesPoint = Number(minutes[0]) * 60 + Number(minutes[1]);
      return {
        dateObj,
        dateStr: `${Number(date.slice(5, 7))}-${Number(date.slice(8, 10))}`,
        yearNum: dateObj.getTime(), // 时间戳
        minutesPoint
      };
    };

    const allDutyPlansRanges: {
      [id: string]: {
        dateStr: {
          users: any[];
          ranges: number[][];
        };
      };
    } = {};
    this.dutyPlans.forEach(item => {
      /* 当前轮值组的生效时间 */
      const effective = [
        dutyPlansObj[item.duty_arrange_id].targetEffectiveTime.slice(0, 10),
        dutyPlansObj[item.duty_arrange_id].targetEffectiveTime.slice(11, 16)
      ];
      /* 开始时间, 结束时间 */
      const start = [item.begin_time.slice(0, 10), item.begin_time.slice(11, 16)];
      let end = null;
      if (item.end_time) {
        end = [item.end_time.slice(0, 10), item.end_time.slice(11, 16)];
      } else {
        end = effective;
      }
      const effectiveObj = computeTimePoint(effective);
      const startObj = computeTimePoint(start);
      const endObj = computeTimePoint(end);
      /* 实际显示的开始时间~结束时间 */
      let relStartObj = null;
      let relEndObj = null;
      if (
        startObj.yearNum < effectiveObj.yearNum ||
        (startObj.yearNum === effectiveObj.yearNum && startObj.minutesPoint < effectiveObj.minutesPoint)
      ) {
        relStartObj = startObj;
        if (endObj.yearNum <= effectiveObj.yearNum) {
          /* 结束日期小于等生效日期 */
          if (endObj.yearNum === effectiveObj.yearNum) {
            /* 结束日期等生效日期 */
            if (endObj.minutesPoint < effectiveObj.minutesPoint) {
              relEndObj = endObj;
            } else {
              relEndObj = effectiveObj;
            }
          } else {
            relEndObj = endObj;
          }
        } else {
          relEndObj = effectiveObj;
        }
      }
      /* 获取开始时间值结束时间每天的日期 */
      const dateArr: {
        name: string;
        dateObj: Date;
        dayTimeStamp: number;
        startMintes: number;
        endMinutes: number;
      }[] = [];
      if (relStartObj && relEndObj) {
        for (let i = relStartObj.yearNum; i <= relEndObj.yearNum; i += oneDay) {
          const dateObj = new Date(i);
          const month = dateObj.getMonth() + 1;
          const day = dateObj.getDate();
          dateArr.push({
            name: `${month}-${day}`,
            dateObj,
            dayTimeStamp: i,
            startMintes: i === relStartObj.yearNum ? relStartObj.minutesPoint : null,
            endMinutes: i === relEndObj.yearNum ? relEndObj.minutesPoint : null
          });
        }
        const dutyTime = item.duty_time[0];
        const workType = dutyTime.work_type;
        const workTime = dutyTime.work_time;
        const workDays = dutyTime.work_days;
        const workTimeRange = [timeToNum(workTime.split('--')[0]), timeToNum(workTime.split('--')[1])];
        const isSkipDay = workTimeRange[0] > workTimeRange[1];
        const startDate = relStartObj.dateStr;
        const endDate = relEndObj.dateStr;
        const setAllDutyRanges = (year, dateStr: string, ranges: number[][]) => {
          if (!allDutyPlansRanges?.[item.duty_arrange_id]) {
            allDutyPlansRanges[item.duty_arrange_id] = {} as any;
          }
          if (!allDutyPlansRanges[item.duty_arrange_id]?.dateStr) {
            allDutyPlansRanges[item.duty_arrange_id][dateStr] = {
              users: item.users,
              ranges,
              year
            };
          } else {
            allDutyPlansRanges[item.duty_arrange_id][dateStr].ranges.push(...ranges);
          }
        };
        if (workType === 'daily') {
          dateArr.forEach(dateItem => {
            if (isSkipDay) {
              const oneRange = [0, workTimeRange[1] + 1];
              const twoRange = [workTimeRange[0], 1440];
              if (dateItem.name === startDate && startDate !== endDate) {
                if (dateItem.startMintes <= oneRange[0]) {
                  setAllDutyRanges(dateItem.dayTimeStamp, dateItem.name, [oneRange, twoRange]);
                } else if (dateItem.startMintes > oneRange[0] && dateItem.startMintes <= oneRange[1]) {
                  setAllDutyRanges(dateItem.dayTimeStamp, dateItem.name, [
                    [dateItem.startMintes, oneRange[1]],
                    twoRange
                  ]);
                } else if (dateItem.startMintes > oneRange[1] && dateItem.startMintes <= twoRange[0]) {
                  setAllDutyRanges(dateItem.dayTimeStamp, dateItem.name, [twoRange]);
                } else if (dateItem.startMintes > twoRange[0] && dateItem.startMintes <= twoRange[1]) {
                  setAllDutyRanges(dateItem.dayTimeStamp, dateItem.name, [[dateItem.startMintes, twoRange[1]]]);
                }
              } else if (dateItem.name === endDate) {
                if (dateItem.endMinutes > twoRange[0]) {
                  setAllDutyRanges(dateItem.dayTimeStamp, dateItem.name, [
                    oneRange,
                    [twoRange[0], dateItem.endMinutes]
                  ]);
                } else if (dateItem.endMinutes <= twoRange[0] && dateItem.endMinutes >= oneRange[1]) {
                  setAllDutyRanges(dateItem.dayTimeStamp, dateItem.name, [oneRange]);
                } else if (dateItem.endMinutes < oneRange[1] && dateItem.endMinutes) {
                  setAllDutyRanges(dateItem.dayTimeStamp, dateItem.name, [[0, dateItem.endMinutes]]);
                }
              } else {
                setAllDutyRanges(dateItem.dayTimeStamp, dateItem.name, [oneRange, twoRange]);
              }
            } else {
              if (dateItem.name === endDate) {
                if (workTimeRange[1] <= dateItem.endMinutes) {
                  setAllDutyRanges(dateItem.dayTimeStamp, dateItem.name, [[workTimeRange[0], workTimeRange[1] + 1]]);
                } else if (workTimeRange[0] < dateItem.endMinutes && workTimeRange[1] > dateItem.endMinutes) {
                  setAllDutyRanges(dateItem.dayTimeStamp, dateItem.name, [[workTimeRange[0], dateItem.endMinutes]]);
                }
              } else {
                setAllDutyRanges(dateItem.dayTimeStamp, dateItem.name, [[workTimeRange[0], workTimeRange[1] + 1]]);
              }
            }
          });
        } else if (workType === 'weekly') {
          dateArr.forEach(dateItem => {
            const day = dateItem.dateObj.getDay();
            if (workDays.includes(day === 0 ? 7 : day)) {
              if (dateItem.name === endDate) {
                if (workTimeRange[1] <= dateItem.endMinutes) {
                  setAllDutyRanges(dateItem.dayTimeStamp, dateItem.name, [[workTimeRange[0], workTimeRange[1] + 1]]);
                } else if (workTimeRange[0] < dateItem.endMinutes && workTimeRange[1] > dateItem.endMinutes) {
                  setAllDutyRanges(dateItem.dayTimeStamp, dateItem.name, [[workTimeRange[0], dateItem.endMinutes]]);
                }
              } else {
                setAllDutyRanges(dateItem.dayTimeStamp, dateItem.name, [[workTimeRange[0], workTimeRange[1] + 1]]);
              }
            }
          });
        } else if (workType === 'monthly') {
          dateArr.forEach(dateItem => {
            const date = dateItem.dateObj.getDate();
            if (workDays.includes(date)) {
              if (dateItem.name === endDate) {
                if (workTimeRange[1] <= dateItem.endMinutes) {
                  setAllDutyRanges(dateItem.dayTimeStamp, dateItem.name, [[workTimeRange[0], workTimeRange[1] + 1]]);
                } else if (workTimeRange[0] < dateItem.endMinutes && workTimeRange[1] > dateItem.endMinutes) {
                  setAllDutyRanges(dateItem.dayTimeStamp, dateItem.name, [[workTimeRange[0], dateItem.endMinutes]]);
                }
              } else {
                setAllDutyRanges(dateItem.dayTimeStamp, dateItem.name, [[workTimeRange[0], workTimeRange[1] + 1]]);
              }
            }
          });
        }
      }
    });

    /* 获取对应周期的七天 */
    const lastDays = getCycleDays(this.cycleNumber);
    const { max } = this.previewData;
    /* 当前周期的日期列表 */
    this.previewData.dateStrArr = lastDays.map(item => item.name);
    /* 生效时间转换 */
    const timeToPointObj = (
      effectiveTime: string
    ): {
      timeStamp: number;
      num: number;
    } => {
      const temp = effectiveTime.split(' ');
      const timeStamp = new Date(temp[0]).getTime();
      return {
        timeStamp,
        num: timeToNum(temp[1] as string)
      };
    };
    const computeRange = (startNum, range: number[]) => {
      if (startNum <= range[0]) {
        return range;
      }
      if (startNum > range[0] && startNum <= range[1]) {
        return [startNum, range[1]];
      }
      return null;
    };
    const computeEffectiveDate = (handoffTimeDate: number, date: Date) => {
      if (handoffTimeDate === 31) {
        const year = date.getFullYear();
        const month = date.getMonth() + 1;
        const max = new Date(year, month, 0).getDate();
        return max;
      }
      return handoffTimeDate;
    };
    /* 转换时间(未交接的情况) */
    /* 此函数返回一个数组， 每条数据包含一个日期及对应的时间段 */
    const dateTimeRange = (
      effectiveTime: string, // 示例 2022-03-11 00:00 生效时间
      timeRange: string[], // 示例 ['00:00', '23:59'] 工作时间段
      dutyType: TWorkType, // 工作周期类型
      days: number[] // 工作日期
    ): {
      dateStr: string;
      ranges: number[][];
    }[] => {
      const effectiveTimeObj = timeToPointObj(effectiveTime);
      const isHasCurDay = (day: { name: string; dateObj: Date; dayTimeStamp: number }) =>
        day.dayTimeStamp >= effectiveTimeObj.timeStamp;
      const startNum = timeToNum(timeRange[0]);
      const endNum = timeToNum(timeRange[1]);
      const dateArr = lastDays;
      const effectiveArr = effectiveTime.split(' ')[0].split('-');
      const effectiveDate = `${Number(effectiveArr[1])}-${Number(effectiveArr[2])}`;
      if (dutyType === 'daily') {
        let oneRange = [];
        let twoRange = [];
        if (startNum > endNum) {
          // 跨天
          twoRange = [startNum, max];
          oneRange = [0, endNum + 1];
        } else {
          // 不跨天
          oneRange = [startNum, endNum + 1];
        }
        return dateArr.map(item => ({
          dateStr: item.name,
          ranges: isHasCurDay(item)
            ? (() => {
                if (twoRange.length) {
                  if (effectiveDate === item.name) {
                    if (effectiveTimeObj.num <= oneRange?.[0]) {
                      return [oneRange, twoRange];
                    }
                    if (effectiveTimeObj.num > oneRange[0] && effectiveTimeObj.num <= oneRange[1]) {
                      return [[effectiveTimeObj.num, oneRange[1]], twoRange];
                    }
                    if (effectiveTimeObj.num > oneRange[1] && effectiveTimeObj.num <= twoRange[0]) {
                      return [twoRange];
                    }
                    if (effectiveTimeObj.num > twoRange[0] && effectiveTimeObj.num <= twoRange[1]) {
                      return [[effectiveTimeObj.num, twoRange[1]]];
                    }
                    return [];
                  }
                  return [oneRange, twoRange];
                }
                if (effectiveDate === item.name) {
                  const curComputeRange = computeRange(effectiveTimeObj.num, oneRange);
                  return curComputeRange ? [curComputeRange] : [];
                }
                return [oneRange];
              })()
            : []
        }));
      }
      if (dutyType === 'weekly') {
        return dateArr.map(item => {
          const day = item.dateObj.getDay();
          const curComputeRange = computeRange(effectiveTimeObj.num, [startNum, endNum + 1]);
          return {
            dateStr: item.name,
            ranges:
              days.includes(day === 0 ? 7 : day) && isHasCurDay(item)
                ? effectiveDate === item.name
                  ? curComputeRange
                    ? [curComputeRange]
                    : []
                  : [[startNum, endNum + 1]]
                : []
          };
        });
      }
      if (dutyType === 'monthly') {
        return dateArr.map(item => {
          const date = item.dateObj.getDate();
          const curComputeRange = computeRange(effectiveTimeObj.num, [startNum, endNum + 1]);
          return {
            dateStr: item.name,
            ranges:
              days.includes(date) && isHasCurDay(item)
                ? effectiveDate === item.name
                  ? curComputeRange
                    ? [curComputeRange]
                    : []
                  : [[startNum, endNum + 1]]
                : []
          };
        });
      }
      return null;
    };
    /* 时间转换为长度(交接时) */
    /* 此函数返回一个二维数据，每个数组为一个交接周期，每个交接周期包含此周期所有日期包含的时间段 */
    const handoffTimeDateTimeRange = (
      effectiveTime: string, // 示例 2022-03-11 00:00 生效时间
      timeRange: string[], // 示例 ['00:00', '23:59'] 工作时间
      dutyType: TWorkType, // 工作周期
      days: number[], // 工作日期
      rotationType: TWorkType, // 交接轮值类型,
      handoffTimeStr: string, // 交接时间,
      handoffTimeDate: number // 交接日期
    ): {
      dateStr: string;
      range: number[];
    }[][] => {
      /* 交接时间 */
      const handoffTimeNum = timeToNum(handoffTimeStr); // 交接时间点
      /* 所有交接日期合集 */
      const allHandoffTimeDate: string[] = [];
      /* 从0-当前切换的周期所有工作时间段 */
      const allCycleDatesRange: {
        dateStr: string;
        ranges: number[][];
        handoverNum?: number;
      }[] = [];
      let allCycleDays: { name: string; dateObj: Date; dayTimeStamp: number }[] = [];
      allCycleDays = getTargetDays(effectiveTime.split(' ')[0], this.cycleNumber);
      allCycleDays.forEach(item => {
        const startNum = timeToNum(timeRange[0]);
        const endNum = timeToNum(timeRange[1]);
        const effectiveTimeObj = timeToPointObj(effectiveTime);
        /* 判断当前日期是否大于生效日期 */
        const isHasCurDay = (day: { name: string; dateObj: Date; dayTimeStamp: number }) =>
          day.dayTimeStamp >= effectiveTimeObj.timeStamp;
        /* 交接时间点 */
        if (rotationType === 'daily') {
          allHandoffTimeDate.push(item.name);
        } else if (rotationType === 'weekly') {
          const day = item.dateObj.getDay();
          if ((day === 0 ? 7 : day) === handoffTimeDate) {
            allHandoffTimeDate.push(item.name);
          }
        } else if (rotationType === 'monthly') {
          const day = item.dateObj.getDate();
          const computeEffectiveDateNum = computeEffectiveDate(handoffTimeDate, item.dateObj);
          if (day === computeEffectiveDateNum) {
            allHandoffTimeDate.push(item.name);
          }
        }
        /* 工作时间段 */
        if (dutyType === 'daily') {
          let oneRange = [];
          let twoRange = [];
          if (startNum > endNum) {
            // 跨天
            oneRange = [0, endNum + 1];
            twoRange = [startNum, max];
          } else {
            // 不跨天
            oneRange = [startNum, endNum + 1];
          }
          allCycleDatesRange.push({
            dateStr: item.name,
            ranges: isHasCurDay(item)
              ? (() => {
                  if (twoRange.length) {
                    return [oneRange, twoRange];
                  }
                  return [oneRange];
                })()
              : []
          });
        } else if (dutyType === 'weekly') {
          const day = item.dateObj.getDay();
          allCycleDatesRange.push({
            dateStr: item.name,
            ranges: days.includes(day === 0 ? 7 : day) && isHasCurDay(item) ? [[startNum, endNum + 1]] : []
          });
        } else if (dutyType === 'monthly') {
          const date = item.dateObj.getDate();
          allCycleDatesRange.push({
            dateStr: item.name,
            ranges: days.includes(date) && isHasCurDay(item) ? [[startNum, endNum + 1]] : []
          });
        }
      });
      /* 计算周期 */
      const allCycleRanges: {
        dateStr: string;
        range: number[];
      }[][] = []; // 一维为一个周期， 二维为这个交接周期对应的日期与范围
      allCycleDatesRange.forEach(item => {
        const effectiveArr = effectiveTime.split(' ')[0].split('-');
        const effectiveDate = `${Number(effectiveArr[1])}-${Number(effectiveArr[2])}`;
        const effectiveTimeNum = timeToNum(effectiveTime.split(' ')?.[1] || '00:00');
        if (allHandoffTimeDate.includes(item.dateStr)) {
          // daily时 ranges 最多只有两个
          /* oneRanges与 twoRanges 的数据填入两个相邻的交接周期 */
          let oneRanges = [];
          let twoRanges = [];
          /* 判断交接时间存在无人值班的日期时直接开启下一个交接周期 */
          if (!item.ranges.length) {
            if (rotationType !== 'daily') {
              allCycleRanges.push([]);
            }
          }
          /* 跨天的情况 */
          if (item.ranges.length > 1) {
            const oneRange = item.ranges[0];
            const twoRange = item.ranges[1];
            const isStart = effectiveDate === item.dateStr;
            const startDayComputed = () => {
              if (isStart && effectiveTimeNum > (oneRange[0] || 0)) {
                twoRanges = [];
                if (effectiveTimeNum < oneRange[1] || 0) {
                  oneRanges = [[effectiveTimeNum, oneRange[1]], twoRange];
                } else if (effectiveTimeNum >= oneRange[1] && effectiveTimeNum <= twoRange[0]) {
                  oneRanges = [twoRange];
                } else if (effectiveTimeNum > twoRange[0]) {
                  oneRanges = [[effectiveTimeNum, twoRange[1]]];
                }
              }
            };
            if (handoffTimeNum <= oneRange?.[0]) {
              twoRanges = item.ranges;
              startDayComputed();
            } else if (handoffTimeNum > oneRange[0] && handoffTimeNum <= oneRange[1]) {
              oneRanges.push([oneRange[0], handoffTimeNum]);
              twoRanges.push([handoffTimeNum, oneRange[1]]);
              twoRanges.push(twoRange);
              startDayComputed();
            } else if (handoffTimeNum > oneRange[1] && handoffTimeNum <= twoRange[0]) {
              oneRanges.push(oneRange);
              twoRanges.push(twoRange);
              startDayComputed();
            } else if (handoffTimeNum > twoRange[0] && handoffTimeNum <= twoRange[1]) {
              oneRanges.push(oneRange);
              oneRanges.push([twoRange[0], handoffTimeNum]);
              twoRanges.push([handoffTimeNum, twoRange[1]]);
              startDayComputed();
            }
          } else {
            // 非跨天的情况下 直接下一个周期
            if (item.ranges.length) {
              if (handoffTimeNum <= item.ranges[0][0]) {
                if (effectiveDate === item.dateStr) {
                  if (effectiveTimeNum > item.ranges[0][0]) {
                    if (effectiveTimeNum < item.ranges[0][1]) {
                      twoRanges = [[effectiveTimeNum, item.ranges[0][1]]];
                    } else {
                      twoRanges = [];
                    }
                  } else {
                    twoRanges = item.ranges;
                  }
                } else {
                  twoRanges = item.ranges;
                }
              } else if (handoffTimeNum > item.ranges[0][0] && handoffTimeNum <= item.ranges[0][1]) {
                if (effectiveDate === item.dateStr) {
                  if (effectiveTimeNum < handoffTimeNum) {
                    /* 生效时间小于交接时间 */
                    oneRanges.push([effectiveTimeNum, handoffTimeNum]);
                    twoRanges.push([handoffTimeNum, item.ranges[0][1]]);
                  } else {
                    oneRanges.push([effectiveTimeNum, item.ranges[0][1]]);
                  }
                } else {
                  oneRanges.push([item.ranges[0][0], handoffTimeNum]);
                  twoRanges.push([handoffTimeNum, item.ranges[0][1]]);
                }
              } else {
                oneRanges = item.ranges;
                twoRanges = [];
              }
            }
          }
          if (oneRanges.length) {
            if (!allCycleRanges?.[allCycleRanges.length - 1]) {
              allCycleRanges.push([]);
            }
            allCycleRanges[allCycleRanges.length - 1].push(
              ...oneRanges.map(range => ({
                dateStr: item.dateStr,
                range
              }))
            );
          }
          if (twoRanges.length) {
            allCycleRanges.push([]);
            allCycleRanges[allCycleRanges.length - 1].push(
              ...twoRanges.map(range => ({
                dateStr: item.dateStr,
                range
              }))
            );
          }
        } else {
          if (!allCycleRanges?.[allCycleRanges.length - 1]) {
            allCycleRanges.push([]);
          }
          // eslint-disable-next-line max-len
          allCycleRanges[allCycleRanges.length - 1]?.push(
            ...item.ranges
              .filter(range => !(effectiveDate === item.dateStr && effectiveTimeNum >= range[1]))
              .map(range => ({
                dateStr: item.dateStr,
                range: (() => {
                  if (effectiveDate === item.dateStr) {
                    if (effectiveTimeNum > range[0] && effectiveTimeNum < range[1]) {
                      return [effectiveTimeNum, range[1]];
                    }
                    return range;
                  }
                  return range;
                })()
              }))
          );
        }
      });
      return allCycleRanges;
    };
    /* 轮值组 */
    this.previewData.groups = dutyArranges.map(dutyItem => {
      const { needRotation, effectiveTime, dutyTime, handoffTime } = dutyItem;
      let curDateTimeRange = [];
      let rotationDateTimeRange: {
        dateStr: string;
        range: number[];
      }[][] = [];
      if (needRotation) {
        rotationDateTimeRange = handoffTimeDateTimeRange(
          effectiveTime,
          dutyTime.workTime,
          dutyTime.workType,
          dutyTime.workDays,
          handoffTime.rotationType,
          handoffTime.time,
          handoffTime.date
        );
      } else {
        curDateTimeRange = dateTimeRange(effectiveTime, dutyTime.workTime, dutyTime.workType, dutyTime.workDays);
      }
      const dutyPlansItems = allDutyPlansRanges?.[dutyItem.id] || null;
      return {
        title: dutyItem.title,
        /* 日期列 */
        dateGroups: lastDays.map(date => {
          /* 生效时间之前的历史轮值 */
          const curDutyPlans = dutyPlansItems?.[date.name] || null;
          let plans = [];
          if (curDutyPlans) {
            plans = curDutyPlans.ranges.map(range => ({
              users: curDutyPlans.users.map(u => ({
                id: u.id,
                name: u.display_name,
                type: u.type
              })),
              color: '#ff9c00',
              range,
              time: `${date.dateObj.getFullYear()}-${
                date.dateObj.getMonth() + 1
              }-${date.dateObj.getDate()} ${rangeToTime(range)}`
            }));
          }
          if (needRotation) {
            /* 交接 */
            const arr: { cycle: number; range: number[] }[] = [];
            rotationDateTimeRange.forEach((item, index) => {
              item.forEach(d => {
                if (d.dateStr === date.name) {
                  arr.push({
                    /* index为交接周期 */
                    cycle: index,
                    range: d.range
                  });
                }
              });
            });
            const userGroups = arr.map(item => {
              let users = [];
              let color = '';
              if (item.cycle + 1 <= dutyItem.dutyUsers.length) {
                users = dutyItem.dutyUsers[item.cycle].users;
                color = dutyItem.dutyUsers[item.cycle].color;
              } else {
                /* 根据交接组的顺序填入对应的交接周期 */
                users = dutyItem.dutyUsers[item.cycle % dutyItem.dutyUsers.length].users;
                color = dutyItem.dutyUsers[item.cycle % dutyItem.dutyUsers.length].color;
              }
              return {
                users,
                color,
                range: item.range,
                time: `${date.dateObj.getFullYear()}-${
                  date.dateObj.getMonth() + 1
                }-${date.dateObj.getDate()} ${rangeToTime(item.range)}`
              };
            });
            return {
              dateStr: date,
              userGroups: [userGroups.concat(plans)]
            };
          }
          /* 不交接 */
          const userGroups = curDateTimeRange
            .find(c => c.dateStr === date.name)
            .ranges.map(r => ({
              users: dutyItem.dutyUsers[0].users,
              color: dutyItem.dutyUsers[0].color,
              range: r,
              time: `${date.dateObj.getFullYear()}-${
                date.dateObj.getMonth() + 1
              }-${date.dateObj.getDate()} ${rangeToTime(r)}`
            }));
          return {
            dateStr: date,
            userGroups: [userGroups.concat(plans)]
          };
        })
      };
    });
    const allDateItemGroup: {
      dateStr: { name: string; dateObj: Date; dayTimeStamp: number };
      ranges: number[][];
    }[] = [];
    /* 空档期 */
    lastDays.forEach(date => {
      const tempArr = [];
      this.previewData.groups.forEach(item => {
        item.dateGroups.forEach(dateItem => {
          if (dateItem.dateStr.name === date.name) {
            dateItem.userGroups.forEach(userGroup => {
              userGroup.forEach(user => {
                tempArr.push({ range: user.range });
              });
            });
          }
        });
      });
      const gapPeriod = [];
      const allRangeSort = tempArr.sort((a, b) => +a.range[0] - b.range[0]);
      const allRangeSortLen = allRangeSort.length;
      if (allRangeSortLen > 1) {
        allRangeSort.reduce((acc, cur, index) => {
          const pre = acc;
          if (pre) {
            if (index === allRangeSortLen - 1) {
              if (pre.range[1] < 1439) gapPeriod.push([cur.range[1], 1440]);
            }
            if (cur.range[0] > pre.range[1]) {
              gapPeriod.push([pre.range[1], cur.range[0]]);
            } else if (cur.range[1] < pre.range[1]) {
              return pre;
            }
          } else {
            if (cur.range[0] > 0) {
              gapPeriod.push([0, cur.range[0]]);
            }
          }
          return cur;
        }, false);
      } else {
        if (allRangeSortLen === 1) {
          const start = allRangeSort[0].range[0];
          const end = allRangeSort[0].range[1];
          gapPeriod.push([0, start]);
          if (end < 1439) gapPeriod.push([end, 1440]);
        } else {
          gapPeriod.push([0, 1440]);
        }
      }
      allDateItemGroup.push({
        dateStr: date,
        ranges: gapPeriod
      });
    });
    const leisure = allDateItemGroup.map(item => ({
      col: item.ranges.map(r => {
        const { dateObj } = item.dateStr;
        const year = dateObj.getFullYear();
        const month = dateObj.getMonth() + 1;
        const day = dateObj.getDate();
        const dateStr = `${year}-${month < 10 ? `0${month}` : month}-${day < 10 ? `0${day}` : day}`;
        return {
          range: r,
          time: `${dateStr} ${rangeToTime(r)}`
        };
      }),
      dateStr: item.dateStr.name
    }));
    /* 需要将跨天组连在一起显示(判断条件：连续两天的相邻组的颜色相同 */
    const crossDayGroups = [];
    this.previewData.groups.forEach(group => {
      const crossGroups = [];
      /* 每一组 */
      let tempPreDateGroup: IUserGroup[] = [];
      group.dateGroups.forEach((dateGroup, dateIndex) => {
        /* 每一组的每一天 */
        const curDayUserGroups = dateGroup.userGroups[0];
        const preTargetUserGroup = tempPreDateGroup.find(u => u.range[1] === 1440);
        const curTargetUserGroup = curDayUserGroups.find(u => u.range[0] === 0);
        if (preTargetUserGroup && curTargetUserGroup) {
          const notCross = curTargetUserGroup.range[0] === 0 && curTargetUserGroup.range[1] === 1440;
          if (preTargetUserGroup.color === curTargetUserGroup.color && !notCross) {
            const preTimeArr = preTargetUserGroup.time.split(' ');
            const curTimeArr = curTargetUserGroup.time.split(' ');
            const time = `${preTimeArr[0]} ${preTimeArr[1].split('-')[0]}-${curTimeArr[0]} ${
              curTimeArr[1].split('-')[1]
            }`;
            const end = dateIndex * 1440 + curTargetUserGroup.range[1];
            const start = (dateIndex - 1) * 1440 + preTargetUserGroup.range[0];
            crossGroups.push({
              time,
              range: [start, end],
              userGroup: curTargetUserGroup
            });
          }
        }
        tempPreDateGroup = curDayUserGroups;
      });
      crossDayGroups.push({
        groups: crossGroups
      });
    });
    this.previewData.crossDayGroups = crossDayGroups;
    this.previewData.leisure = leisure;
    this.previewKey = random(8);
    this.handleChange();
  }

  @Emit('change')
  handleChange() {
    return this.dutyArranges;
  }

  /* 交接时间弹出层 */
  handleHandOffTimeOpenChange(v: boolean, index: number) {
    if (!v) {
      this.dutyArranges[index].effectiveTimeKey = random(8);
    }
  }

  /* 切换周期 */
  handleCycleType(type: 'right' | 'left') {
    if (type === 'left') {
      this.cycleNumber -= 1;
    } else if (type === 'right') {
      this.cycleNumber += 1;
    }
    this.setPreviewData();
  }

  render() {
    return (
      <div class='duty-arranges-component'>
        {/* 轮值组 */}
        {!this.readonly && (
          <div class='groups'>
            <transition-group
              name={'flip-list'}
              tag='ul'
            >
              {this.dutyArranges.map((item, index) => [
                <div
                  class='group-item'
                  key={item.key}
                  draggable={item.draggable}
                  onDragstart={(event: DragEvent) => this.handleDragStart(event, index)}
                  onDragend={(event: DragEvent) => this.handleDragEnd(event)}
                  onDragover={(event: DragEvent) => this.handleDragOver(event, index)}
                  onDrop={(event: DragEvent) => this.handleDrop(event)}
                >
                  <div
                    class='header'
                    onMouseup={() => this.handleExpan(index, 'expan')}
                  >
                    <span
                      class={['icon-monitor', 'icon-mc-triangle-down', 'expan-icon', item.isExpan ? 'expan' : '']}
                    ></span>
                    <span class='title'>
                      <span
                        class='title-left'
                        onMouseup={(e: Event) => e.stopPropagation()}
                        onMouseenter={() => this.handleMouseenter(index)}
                        onMouseleave={() => this.handleMouseleave(index)}
                      >
                        <span class='icon-monitor icon-mc-tuozhuai'></span>
                      </span>
                      <span class='maintitle'>{item.title}</span>
                      <span class='subtitle'>
                        <span class='need-rotation'>
                          {window.i18n.t('是否交接')}
                          <span
                            class='need-rotation-switch'
                            onMouseup={(e: Event) => e.stopPropagation()}
                          >
                            <bk-switcher
                              v-model={item.needRotation}
                              theme='primary'
                              size='small'
                              onChange={v => this.handleNeedRotation(v, index)}
                            ></bk-switcher>
                          </span>
                        </span>
                        <span class='text'>{item.subTitle}</span>
                      </span>
                    </span>
                    <span
                      class={['icon-monitor', 'icon-mc-close', 'delete-icon']}
                      onMousedown={(e: Event) => e.stopPropagation()}
                      onClick={() => this.handleDelete(index)}
                    ></span>
                  </div>
                  <div class={['content', item.isExpan ? 'expan' : '']}>
                    {/* 用户组 */}
                    <div class='step step-1'>
                      <div class='step-title'>
                        <span class='red'>{'Step1: '}</span>
                        <span class='text'>{this.$t('添加用户')}</span>
                      </div>
                      <div class='step-content'>
                        <UserListSort
                          hasAdd={item.needRotation}
                          value={item.dutyUsers}
                          defaultGroupList={this.defaultGroupList}
                          colorIndex={this.getAllUsersLength}
                          onChange={v => this.handleUserListChange(v, index)}
                        ></UserListSort>
                      </div>
                    </div>
                    {/* 轮值类型 */}
                    <div class='step step-2'>
                      <div class='step-title'>
                        <span class='red'>{'Step2: '}</span>
                        <span class='text'>
                          {item.needRotation ? this.$t('选择交接和轮值类型') : this.$t('选择轮值类型')}
                        </span>
                      </div>
                      <div class='step-content'>
                        {item.needRotation ? (
                          /* 交接 */
                          [
                            <div class='step-content-item'>
                              <span
                                class='item-label'
                                v-en-style='width: 100px'
                              >
                                {this.$t('轮值类型')}
                              </span>
                              <span class='item-content'>
                                <span class={['duty-type', { daily: item.handoffTime.rotationType === 'daily' }]}>
                                  <bk-select
                                    v-model={item.handoffTime.rotationType}
                                    clearable={false}
                                    onChange={() => this.handleRotationTypeChange(index)}
                                  >
                                    {DUTY_TYPE.map(v => (
                                      <bk-option
                                        key={v.id}
                                        id={v.id}
                                        name={v.name}
                                      ></bk-option>
                                    ))}
                                  </bk-select>
                                </span>
                                <span class={['duty-days', { daily: item.handoffTime.rotationType === 'daily' }]}>
                                  {(() => {
                                    if (item.handoffTime.rotationType === 'daily') {
                                      return undefined;
                                    }
                                    if (item.handoffTime.rotationType === 'weekly') {
                                      return (
                                        <bk-select
                                          value={item.handoffTime.date}
                                          onChange={v => this.handleHandOffTimeDateChange(v, index)}
                                        >
                                          {weekDaysList.map(item => (
                                            <bk-option
                                              key={item.id}
                                              id={item.id}
                                              name={item.name}
                                            ></bk-option>
                                          ))}
                                        </bk-select>
                                      );
                                    }
                                    if (item.handoffTime.rotationType === 'monthly') {
                                      return (
                                        <SimpleDayPick
                                          value={item.handoffTime.date}
                                          multiple={false}
                                          onChange={v => this.handleHandOffTimeDateChange(v as number, index)}
                                        ></SimpleDayPick>
                                      );
                                    }
                                  })()}
                                </span>
                              </span>
                            </div>,
                            <div class='step-content-item mt-12'>
                              <div
                                class='item-label'
                                v-en-style='width: 100px'
                              >
                                {this.$t('交接时间')}
                              </div>
                              <div class='item-content'>
                                <bk-time-picker
                                  class='rotation-time'
                                  v-model={item.handoffTime.time}
                                  format={'HH:mm'}
                                  transfer={true}
                                  onChange={v => this.handleHandOffTimeChange(v, index)}
                                  on-open-change={v => this.handleHandOffTimeOpenChange(v, index)}
                                ></bk-time-picker>
                              </div>
                            </div>
                          ]
                        ) : (
                          /* 不交接 */
                          <div class='stemp-content-item'>
                            <span class='item-content'>
                              <bk-select
                                v-model={item.dutyTime.workType}
                                clearable={false}
                                onChange={() => this.handleDutyTypeChange(index)}
                              >
                                {DUTY_TYPE.map(v => (
                                  <bk-option
                                    key={v.id}
                                    id={v.id}
                                    name={v.name}
                                  ></bk-option>
                                ))}
                              </bk-select>
                            </span>
                          </div>
                        )}
                      </div>
                    </div>
                    {/* 时间选择 */}
                    <div class='step step-3'>
                      <div class='step-title'>
                        <span class='red'>{'Step3: '}</span>
                        <span class='text'>{this.$t('选择有效时间范围')}</span>
                      </div>
                      <div class='step-content'>
                        {item.needRotation ? (
                          /* 交接 */
                          <div class='step-content-item'>
                            <span
                              class='item-label'
                              v-en-style='width: 100px'
                            >
                              {this.$t('工作周期')}
                            </span>
                            <span class='item-content'>
                              <span class={['duty-type', { daily: item.dutyTime.workType === 'daily' }]}>
                                <bk-select
                                  v-model={item.dutyTime.workType}
                                  clearable={false}
                                  onChange={() => this.handleDutyTypeChange(index)}
                                >
                                  {DUTY_TYPE.map(v => (
                                    <bk-option
                                      key={v.id}
                                      id={v.id}
                                      name={v.name}
                                    ></bk-option>
                                  ))}
                                </bk-select>
                              </span>
                              <span class={['duty-days', { daily: item.dutyTime.workType === 'daily' }]}>
                                {(() => {
                                  if (item.dutyTime.workType === 'daily') {
                                    return undefined;
                                  }
                                  if (item.dutyTime.workType === 'weekly') {
                                    return (
                                      <bk-select
                                        value={item.dutyTime.workDays}
                                        multiple={true}
                                        onChange={v => this.handleWorkDaysChange(v, index)}
                                      >
                                        {weekDaysList.map(item => (
                                          <bk-option
                                            key={item.id}
                                            id={item.id}
                                            name={item.name}
                                          ></bk-option>
                                        ))}
                                      </bk-select>
                                    );
                                  }
                                  if (item.dutyTime.workType === 'monthly') {
                                    return (
                                      <SimpleDayPick
                                        value={item.dutyTime.workDays}
                                        onChange={v => this.handleWorkDaysChange(v as number[], index)}
                                      ></SimpleDayPick>
                                    );
                                  }
                                })()}
                              </span>
                            </span>
                          </div>
                        ) : (
                          /* 不交接 */
                          item.dutyTime.workType !== 'daily' && (
                            <div class='step-content-item'>
                              <span
                                class='item-label'
                                v-en-style='width: 100px'
                              >
                                {this.$t('工作周期')}
                              </span>
                              <span class='item-content no-rotation'>
                                {(() => {
                                  if (item.dutyTime.workType === 'weekly') {
                                    return (
                                      <bk-select
                                        value={item.dutyTime.workDays}
                                        multiple={true}
                                        onChange={v => this.handleWorkDaysChange(v, index)}
                                      >
                                        {weekDaysList.map(item => (
                                          <bk-option
                                            key={item.id}
                                            id={item.id}
                                            name={item.name}
                                          ></bk-option>
                                        ))}
                                      </bk-select>
                                    );
                                  }
                                  if (item.dutyTime.workType === 'monthly') {
                                    return (
                                      <SimpleDayPick
                                        value={item.dutyTime.workDays}
                                        onChange={v => this.handleWorkDaysChange(v as number[], index)}
                                      ></SimpleDayPick>
                                    );
                                  }
                                })()}
                              </span>
                            </div>
                          )
                        )}
                        <div class='step-content-item mt-12'>
                          <span
                            class='item-label'
                            v-en-style='width: 100px'
                          >
                            {this.$t('工作时间')}
                          </span>
                          <span class='item-content'>
                            <CustomTimeRange
                              value={item.dutyTime.workTime}
                              allowCrossDay={item.dutyTime.workType === 'daily'}
                              onChange={v => this.handleWorkTimeChange(v, index)}
                            ></CustomTimeRange>
                          </span>
                        </div>
                        {
                          <div class='step-content-item mt-12'>
                            <span
                              class='item-label'
                              v-en-style='width: 100px'
                            >
                              {this.$t('生效时间')}
                            </span>
                            <span class='item-content'>
                              <CustomDatePick
                                key={item.effectiveTimeKey}
                                value={item.effectiveTime}
                                readonly={item.effectiveReadonly}
                                readonlyTime={false}
                                onChange={v => this.handleEffectiveTimeChange(v, index)}
                              ></CustomDatePick>
                            </span>
                          </div>
                        }
                      </div>
                    </div>
                  </div>
                </div>,
                <div
                  class='err-msg'
                  key={`${index}${this.errKey}`}
                >
                  {this.errMsgList[index]}
                </div>
              ])}
            </transition-group>
          </div>
        )}
        {/* 新增按钮 */}
        {!this.readonly && (
          <div class='add-wrap'>
            <bk-button
              icon='plus'
              class='add-btn'
              onClick={this.handleAddGroup}
            >
              {this.$t('新增组')}
            </bk-button>
            <span class='icon-monitor icon-hint'></span>
            <span class='tip-msg'>
              {this.$t('电话通知的拨打顺序是按通知对象顺序依次拨打。注意用户组内无法保证顺序。')}
            </span>
          </div>
        )}
        {/* 轮值预览 */}
        <div class='preview-wrap'>
          <DutyPreview
            value={this.previewData}
            key={this.previewKey}
            onCycleType={this.handleCycleType}
          ></DutyPreview>
        </div>
        {!!this.userPreviewList.length && !this.readonly && (
          <div class='user-preivew'>
            {this.userGroupData.map(
              item =>
                this.userPreviewList.map(u => u.id).includes(item.id) && (
                  <div class='text-msg'>
                    {`${item.display_name}(${
                      ['bk_bak_operator', 'operator'].includes(item.id)
                        ? operatorText[item.id]
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
                )
            )}
          </div>
        )}
      </div>
    );
  }
}
