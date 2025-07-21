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
import { Component, Ref } from 'vue-property-decorator';
import { modifiers, Component as tsc } from 'vue-tsx-support';

import {
  deleteCalendar,
  editCalendar,
  getParentItemList,
  getTimeZone,
  listCalendar,
} from 'monitor-api/modules/calendar';

import CustomSelect from '../../components/custom-select/custom-select';
import CalendarAddInput from './calendar-add-input';
import CalendarList from './calendar-list';
import CalendarInfo from './components/calendar-info/calendar-info';
import { type ICalendarListItem, type ICalendarTypeListItem, type IOptionsItem, Z_INDEX } from './types';

import './calendar.scss';

/** 预览 preview / 事项列表 list */
type ItabId = 'list' | 'preview';
interface ITabListItem {
  id: ItabId;
  name: string;
}
/**
 * 日历服务
 */
@Component
export default class Calendar extends tsc<object> {
  @Ref() calendarListRef: CalendarList;
  @Ref() calendarAddInputRef: CalendarAddInput;
  loading = false;
  /** 预览 preview / 事项列表 list */
  activeTab: ItabId = 'list';
  tabList: ITabListItem[] = [
    {
      id: 'preview',
      name: window.i18n.t('预览').toString(),
    },
    {
      id: 'list',
      name: window.i18n.t('事项列表').toString(),
    },
  ];

  /** 策兰日历列表渲染数据 */
  calendarList: ICalendarTypeListItem[] = [
    {
      title: window.i18n.t('日历列表').toString(),
      list: [],
    },
    {
      title: window.i18n.t('内置日历').toString(),
      list: [],
    },
  ];

  /** 时区可选项数据 */
  timeZoneOptions: IOptionsItem[] = [];

  /** 全部的日历列表 */
  calendarListTotal: IOptionsItem[] = [];

  tableList = [];

  /** 当前编辑日历的id */
  editId = null;
  /** 编辑的名称 */
  editName = '';

  /** 删除日历的数据 */
  curCalendarInfo = {
    show: false,
    id: null /** 日历id */,
    scheduleCount: 0 /** 日程数 */,
    selectedId: null /** 选中的日历 */,
  };

  /** 是否需要合并日历 */
  get mergeable() {
    return !!this.curCalendarInfo.scheduleCount;
  }

  get mergeableCalendarList() {
    return this.calendarList.reduce((total, item) => {
      const list = item.list.filter(set => set.id !== this.curCalendarInfo.id);
      total = [...total, ...list];
      return total;
    }, []);
  }

  /** 选中的日历id */
  get checkedCalendarIds() {
    return this.calendarList.reduce((total, item) => {
      item.list.forEach(set => {
        set.checked && total.push(set.id);
      });
      return total;
    }, []);
  }

  /** 内置日历的ids */
  get defaultCalendarIds(): number[] {
    return this.calendarList[1].list.map(item => item.id as number);
  }

  async created() {
    this.loading = true;
    await this.getCalendarList();
    await this.calendarListRef.getTableList();
    await this.getTimeZone();
    this.loading = false;
  }

  /**
   * 获取时区列表数据
   */
  async getTimeZone() {
    const data = await getTimeZone().catch(() => []);
    this.timeZoneOptions = data.map(item => ({
      id: item.time_zone,
      name: item.name,
    }));
    return data;
  }

  /**
   * 获取日历列表 包括自定义、内置日历
   */
  async getCalendarList() {
    const params = {
      page: 1,
      page_size: 1000,
    };
    const data = await listCalendar(params).catch(() => null);
    if (data) {
      const customList = [];
      const defaultList = [];
      data.data.forEach(item => {
        if (item.classify === 'custom') {
          customList.push({
            id: item.id,
            name: item.name,
            checked: true,
            color: item.deep_color,
          });
        } else {
          defaultList.push({
            id: item.id,
            name: item.name,
            checked: true,
            color: item.deep_color,
          });
        }
      });
      this.calendarList[0].list = customList;
      this.calendarList[1].list = defaultList;
      this.calendarListTotal = [...customList].map(item => ({
        id: item.id,
        name: item.name,
      }));
    }
  }

  /**
   * 选中日历
   */
  async handleCheckedCalendar() {
    await this.$nextTick();
    this.calendarListRef.getTableList(true);
  }

  /**
   * 隐藏新增日历输入框
   * @param key refs key
   */
  handleHideAddPopover(key: string) {
    const popover = this.$refs[key] as any;
    popover?.instance?.hide?.();
  }

  /**
   * 新增日历成功
   * @param key refs key
   */
  handleAddConfirm(key: string) {
    this.handleHideAddPopover(key);
    this.getCalendarList();
  }

  /** 展开后输入框自动获取焦点 */
  handleShowAdd() {
    this.calendarAddInputRef.focus();
  }

  /**
   * 显示要删除的日历
   * @param item 日历数据
   */
  async handleShowDeleteCalendar(item: ICalendarListItem) {
    const res = await getParentItemList({ calendar_ids: item.id }).catch(() => false);
    if (res) {
      this.curCalendarInfo.id = item.id;
      this.curCalendarInfo.scheduleCount = res.total;
      this.curCalendarInfo.show = true;
    }
  }

  /** 合并日历 */
  async handleMergeCalendar() {
    await this.$nextTick();
    this.curCalendarInfo.selectedId = '';
  }
  /**
   * 删除日历
   * @param id 日历id
   */
  async handleDeleteCalendar() {
    const res = await deleteCalendar({ id: this.curCalendarInfo.id })
      .then(() => true)
      .catch(() => false);
    if (res) {
      this.curCalendarInfo.show = false;
      this.$bkMessage({ message: this.$t('删除成功'), theme: 'success' });
      this.getCalendarList();
      !!this.curCalendarInfo.scheduleCount && this.calendarListRef.getTableList();
    }
  }

  /**
   * 激活日历名称的编辑状态
   * @param item
   * @param flag
   * @returns
   */
  async handleShowEditName(item: ICalendarListItem, flag: boolean) {
    if (!flag) return;
    this.editId = item.id;
    this.editName = item.name;
    await this.$nextTick();
    const key = `input-key-${item.id}`;
    const input = this.$refs[key] as any;
    input.focus();
  }

  /**
   * 提交编辑的名称
   * @param item
   * @returns
   */
  async handleEditSubmit(item: ICalendarListItem) {
    if (item.name === this.editName.trim()) {
      this.editId = null;
      return;
    }
    const res = await editCalendar({ id: this.editId, name: this.editName })
      .then(() => true)
      .catch(() => false);
    if (res) {
      await this.getCalendarList();
      this.$bkMessage({ theme: 'success', message: this.$t('修改成功') });
    }
    this.editId = null;
  }

  render() {
    return (
      <div
        class='calendar-wrapper'
        v-bkloading={{ isLoading: this.loading, zIndex: 1 }}
      >
        <div class='calendar-left'>
          {/* 日历列表 */}
          <div>
            {this.calendarList.map((item, index) => {
              const key = `add-popover-${index}`;
              return (
                <div class='calendar-list-wrap'>
                  <div class='calendar-list-title'>
                    <span>{item.title}</span>
                    {!index && (
                      <bk-popover
                        ref={key}
                        offset='-30,0'
                        placement='bottom-start'
                        theme='light'
                        trigger='click'
                        z-index={Z_INDEX}
                        onShow={this.handleShowAdd}
                      >
                        <i class='icon-monitor icon-mc-add' />
                        <div
                          class='calendar-add-popover-content'
                          slot='content'
                        >
                          <div class='add-title'>{this.$t('新建日历')}</div>
                          <CalendarAddInput
                            ref='calendarAddInputRef'
                            onCancel={() => this.handleHideAddPopover(key)}
                            onConfirm={() => this.handleAddConfirm(key)}
                          />
                        </div>
                      </bk-popover>
                    )}
                  </div>
                  <div class='calendar-list'>
                    {item.list.map(set => (
                      <div class='calendar-list-item'>
                        <span class='calendar-list-item-left'>
                          <bk-checkbox
                            style={{ '--color': set.color }}
                            class={['calendar-checkedbox', set.color ? 'color-theme' : '']}
                            v-model={set.checked}
                            onChange={this.handleCheckedCalendar}
                          />
                          <span class='calendar-name'>
                            {this.editId === set.id ? (
                              <input
                                ref={`input-key-${set.id}`}
                                class='calendar-name-input'
                                v-model={this.editName}
                                onBlur={() => this.handleEditSubmit(set)}
                                onKeydown={modifiers.enter(() => this.handleEditSubmit(set))}
                              />
                            ) : (
                              <span class={['calendar-name-text', { editable: !index }]}>
                                <span
                                  class='name'
                                  title={set.name}
                                >
                                  {set.name}
                                </span>
                                <i
                                  class='icon-monitor icon-bianji'
                                  onClick={() => this.handleShowEditName(set, !index)}
                                />
                              </span>
                            )}
                          </span>
                        </span>
                        {!index && (
                          <i
                            class='icon-monitor icon-mc-delete-line delete-icon'
                            onClick={() => this.handleShowDeleteCalendar(set)}
                          />
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
          {/* <div class="date-panel">
            <DatePanel></DatePanel>
          </div> */}
        </div>
        <div class='calendar-right'>
          {/* <bk-radio-group class="calendar-radio-group" v-model={this.activeTab}>
            {
              this.tabList.map(tab => (
                <bk-radio-button value={ tab.id }>
                  { tab.name }
                </bk-radio-button>
              ))
            }
          </bk-radio-group> */}
          <div class='calendar-right-content'>
            <keep-alive>
              {
                // 事项列表
                this.activeTab === 'list' && (
                  <CalendarList
                    ref='calendarListRef'
                    calendarList={this.calendarListTotal}
                    checkedCalendarIds={this.checkedCalendarIds}
                    defaultCalendarIds={this.defaultCalendarIds}
                    timeZoneList={this.timeZoneOptions}
                    onUpdateCalendarList={this.getCalendarList}
                  />
                )
              }
            </keep-alive>
          </div>
        </div>
        <CalendarInfo
          v-model={this.curCalendarInfo.show}
          infoTitle={this.$tc('确定删除该日历？')}
        >
          {this.curCalendarInfo.scheduleCount ? (
            <i18n
              slot='infoDesc'
              path='当前日历下包含{0}个日程，删除日历和其下所有日程'
            >
              <span class='calendar-info-schedule'>{this.curCalendarInfo.scheduleCount}</span>
            </i18n>
          ) : (
            <span slot='infoDesc'>{this.$t('当前日历没有相关日程')}</span>
          )}
          <div
            class='calendar-info-btn-groups'
            slot='buttonGroup'
          >
            <bk-button
              theme='primary'
              onClick={this.handleDeleteCalendar}
            >
              {this.$tc(this.curCalendarInfo.scheduleCount ? '删除全部' : '确认')}
            </bk-button>
            {false && this.mergeable && (
              <CustomSelect
                v-model={this.curCalendarInfo.selectedId}
                popover-min-width={10}
                searchable={false}
                onSelected={this.handleMergeCalendar}
              >
                <bk-button
                  class='merge-btn'
                  slot='target'
                >
                  {this.$tc('合并到日历')}
                  <i class='icon-monitor icon-arrow-down' />
                </bk-button>
                {this.mergeableCalendarList.map(opt => (
                  <bk-option
                    id={opt.id}
                    name={opt.name}
                  />
                ))}
              </CustomSelect>
            )}
          </div>
        </CalendarInfo>
      </div>
    );
  }
}
