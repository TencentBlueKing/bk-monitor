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
import { computed, defineComponent, inject, PropType, reactive, Ref, TransitionGroup, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import { Button, Input, Select } from 'bkui-vue';
import { random } from 'lodash';
import { isEn } from 'monitor-pc/i18n/i18n';

import MemberSelect, { TagItemModel } from '../../../components/member-select/member-select';
import { RotationSelectTypeEnum } from '../typings/common';
import { validTimeOverlap } from '../utils';
import CalendarSelect from './calendar-select';
import DataTimeSelect from './data-time-select';
import FormItem from './form-item';
import TimeTagPicker from './time-tag-picker';
import WeekSelect from './week-select';

import './replace-rotation-table-item.scss';
type CustomTabType = 'classes' | 'duration';
type WorkTimeType = 'datetime_range' | 'time_range';
export interface ReplaceRotationDateModel {
  key: number;
  workDays?: number[];
  workTime: string[][];
}
export interface ReplaceRotationUsersModel {
  groupNumber?: number;
  groupType: 'auto' | 'specified';
  value: { key: number; value: { type: 'group' | 'user'; id: string }[]; orderIndex: number }[];
}

export interface ReplaceItemDataModel {
  id?: number;
  date: {
    type: RotationSelectTypeEnum;
    /** 每周、每月：时间范围/起止时间 */
    workTimeType: WorkTimeType;
    /** 是否是自定义轮值类型 */
    isCustom: boolean;
    /** 自定义：指定时长/指定班次 */
    customTab: CustomTabType;
    /** 自定义轮值有效日期 */
    customWorkDays: number[];
    /** 单班时长 */
    periodSettings: { unit: 'day' | 'hour'; duration: number };
    value: ReplaceRotationDateModel[];
  };
  users: ReplaceRotationUsersModel;
}

export default defineComponent({
  name: 'ReplaceRotationTableItem',
  props: {
    data: {
      type: Object as PropType<ReplaceItemDataModel>,
      default: undefined,
    },
  },
  emits: ['change', 'drop'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const colorList = inject<{ value: string[]; setValue: (val: string[]) => void }>('colorList');

    const defaultGroup = inject<Ref<any[]>>('defaultGroup');
    const labelWidth = computed(() => (isEn ? 110 : 70));

    const rotationTypeList: { label: string; value: RotationSelectTypeEnum }[] = [
      { label: t('每天'), value: RotationSelectTypeEnum.Daily },
      { label: t('每周'), value: RotationSelectTypeEnum.Weekly },
      { label: t('每月'), value: RotationSelectTypeEnum.Monthly },
      { label: t('每工作日(周一至周五)'), value: RotationSelectTypeEnum.WorkDay },
      { label: t('每周末(周六、周日)'), value: RotationSelectTypeEnum.Weekend },
      { label: t('自定义'), value: RotationSelectTypeEnum.Custom },
    ];

    const localValue = reactive<ReplaceItemDataModel>({
      id: undefined,
      date: {
        type: RotationSelectTypeEnum.WorkDay,
        workTimeType: 'time_range',
        isCustom: false,
        customTab: 'duration',
        customWorkDays: [],
        periodSettings: {
          unit: 'day',
          duration: 1,
        },
        value: [createDefaultDate(RotationSelectTypeEnum.WorkDay)],
      },
      users: {
        groupType: 'specified',
        groupNumber: 1,
        value: [{ key: random(8, true), value: [], orderIndex: 0 }],
      },
    });

    /** 轮值类型 */
    const rotationSelectType = computed({
      get() {
        return localValue.date.isCustom ? RotationSelectTypeEnum.Custom : localValue.date.type;
      },
      set(val: RotationSelectTypeEnum) {
        localValue.date.workTimeType = 'time_range';
        localValue.date.customTab = 'duration';
        if (val === RotationSelectTypeEnum.Custom) {
          localValue.date.isCustom = true;
          localValue.date.type = RotationSelectTypeEnum.Weekly;
        } else {
          localValue.date.isCustom = false;
          localValue.date.type = val;
          localValue.date.customWorkDays = [];
        }
        localValue.date.value = [createDefaultDate(val)];
        handleEmitData();
      },
    });

    watch(
      () => props.data,
      val => {
        if (val) {
          Object.assign(localValue, val);
        }
      },
      {
        immediate: true,
      }
    );

    function createDefaultDate(type: RotationSelectTypeEnum): ReplaceRotationDateModel {
      let days = [];
      switch (type) {
        case RotationSelectTypeEnum.WorkDay:
          days = [1, 2, 3, 4, 5];
          break;
        case RotationSelectTypeEnum.Weekend:
          days = [6, 7];
          break;
        case RotationSelectTypeEnum.Daily:
          days = [1, 2, 3, 4, 5, 6, 7];
          break;
        case RotationSelectTypeEnum.Monthly:
        case RotationSelectTypeEnum.Weekly:
        case RotationSelectTypeEnum.Custom:
          days = [];
          break;
      }

      return {
        key: random(8, true),
        workTime: [],
        workDays: days,
      };
    }

    /**
     * 新增/删除单班时间项
     */
    function handleClassesItemChange(type: 'add' | 'del', ind = 1) {
      if (type === 'add') {
        localValue.date.value.push(createDefaultDate(localValue.date.type));
      } else {
        localValue.date.value.splice(ind, 1);
        handleEmitData();
      }
    }

    /**
     * 轮值类型为每周和每月时渲染的内容
     * @param rotationType 轮值类型
     * @returns 渲染的内容
     */
    function weekAndMonthClasses(rotationType: RotationSelectTypeEnum.Monthly | RotationSelectTypeEnum.Weekly) {
      const val = localValue.date.value;

      /**
       * 时间范围和起止时间类型切换
       * @param type 切换的类型
       */
      function handleDateTypeChange(type: WorkTimeType) {
        localValue.date.workTimeType = type;
        localValue.date.value = [createDefaultDate(localValue.date.type)];
        handleEmitData();
      }

      /**
       * 渲染时间范围类型的单班时间项
       * @param item 数据
       * @param ind 索引
       */
      function renderTimeRangeItem(item: ReplaceRotationDateModel, ind: number) {
        return [
          rotationType === RotationSelectTypeEnum.Weekly ? (
            <WeekSelect
              class='mr8'
              v-model={item.workDays}
              label={val.length > 1 ? t('第 {num} 班', { num: ind + 1 }) : ''}
              onSelectEnd={handleEmitData}
            />
          ) : (
            <CalendarSelect
              class='mr8'
              v-model={item.workDays}
              label={val.length > 1 ? t('第 {num} 班', { num: ind + 1 }) : ''}
              hasStart
              onSelectEnd={handleEmitData}
            />
          ),
          <TimeTagPicker
            v-model={item.workTime}
            onChange={handleEmitData}
          />,
          val.length > 1 && (
            <i
              class='icon-monitor icon-mc-delete-line del-icon'
              onClick={() => handleClassesItemChange('del', ind)}
            />
          ),
        ];
      }
      function dataTimeSelectChange(val: string[], item: ReplaceRotationDateModel, type: 'end' | 'start') {
        if (type === 'start') {
          item.workTime[0] = val;
        } else {
          item.workTime[1] = val;
        }
        if (item.workTime[0] && item.workTime[1]) handleEmitData();
      }
      /**
       * 渲染起止时间类型的单班时间项
       * @param item 数据
       * @param ind 索引
       */
      function renderDateTimeRangeItem(item: ReplaceRotationDateModel, ind: number) {
        return [
          <DataTimeSelect
            label={val.length > 1 ? t('第 {num} 班', { num: ind + 1 }) : ''}
            modelValue={item.workTime[0]}
            type={rotationType === RotationSelectTypeEnum.Weekly ? 'week' : 'calendar'}
            onChange={val => dataTimeSelectChange(val, item, 'start')}
          />,
          <span class='separator-to'>{t('至')}</span>,
          <DataTimeSelect
            modelValue={item.workTime[1]}
            type={rotationType === RotationSelectTypeEnum.Weekly ? 'week' : 'calendar'}
            onChange={val => dataTimeSelectChange(val, item, 'end')}
          />,
          val.length > 1 && (
            <i
              class='icon-monitor icon-mc-delete-line del-icon'
              onClick={() => handleClassesItemChange('del', ind)}
            />
          ),
        ];
      }

      return [
        <FormItem
          label=''
          labelWidth={labelWidth.value}
        >
          <div class='tab-list'>
            <div
              class={['tab-list-item', localValue.date.workTimeType === 'time_range' && 'active']}
              onClick={() => handleDateTypeChange('time_range')}
            >
              {t('时间范围')}
            </div>
            <div
              class={['tab-list-item', localValue.date.workTimeType === 'datetime_range' && 'active']}
              onClick={() => handleDateTypeChange('datetime_range')}
            >
              {t('起止时间')}
            </div>
          </div>
        </FormItem>,
        <FormItem
          label={t('单班时间')}
          labelWidth={labelWidth.value}
        >
          <div class='classes-list'>
            {val.map((item, ind) => [
              <div
                key={item.key}
                class='classes-item'
              >
                {localValue.date.workTimeType === 'time_range'
                  ? renderTimeRangeItem(item, ind)
                  : renderDateTimeRangeItem(item, ind)}
              </div>,
              validTimeOverlap(item.workTime) && <p class='err-msg'>{t('时间段重复')}</p>,
            ])}
            <Button
              class='add-btn'
              theme='primary'
              text
              onClick={() => handleClassesItemChange('add')}
            >
              <i class='icon-monitor icon-plus-line add-icon'></i>
              {t('新增值班')}
            </Button>
          </div>
        </FormItem>,
      ];
    }
    /**
     * 轮值类型为自定义时渲染的内容
     * @param rotationType 轮值类型
     * @returns 渲染的内容
     */
    function customClasses() {
      const { value } = localValue.date;
      function handleTypeChange(type: CustomTabType) {
        localValue.date.customTab = type;
        type === 'duration' && (localValue.date.value = [value[0]]);
        handleEmitData();
      }
      function handleDateTypeChange() {
        localValue.date.customWorkDays = [];
        handleEmitData();
      }
      function handleDurationChange(duration: number) {
        localValue.date.periodSettings.duration = duration || 1;
        handleEmitData();
      }

      return [
        <FormItem
          class='expiration-date-form-item'
          label={t('有效日期')}
          labelWidth={labelWidth.value}
        >
          <Select
            class='date-type-select'
            v-model={localValue.date.type}
            clearable={false}
            onChange={handleDateTypeChange}
          >
            <Select.Option
              label={t('按周')}
              value={RotationSelectTypeEnum.Weekly}
            />
            <Select.Option
              label={t('按月')}
              value={RotationSelectTypeEnum.Monthly}
            />
          </Select>
          {localValue.date.type === RotationSelectTypeEnum.Weekly && (
            <WeekSelect
              v-model={localValue.date.customWorkDays}
              onSelectEnd={handleEmitData}
            />
          )}
          {localValue.date.type === RotationSelectTypeEnum.Monthly && (
            <CalendarSelect
              class='date-value-select'
              v-model={localValue.date.customWorkDays}
              onSelectEnd={handleEmitData}
            />
          )}
        </FormItem>,
        <FormItem
          label=''
          labelWidth={labelWidth.value}
        >
          <div class='tab-list'>
            <div
              class={['tab-list-item', 'duration', localValue.date.customTab === 'duration' && 'active']}
              onClick={() => handleTypeChange('duration')}
            >
              {t('指定时长')}
            </div>
            <div
              class={['tab-list-item', 'classes', localValue.date.customTab === 'classes' && 'active']}
              onClick={() => handleTypeChange('classes')}
            >
              {t('指定班次')}
            </div>
          </div>
        </FormItem>,

        localValue.date.customTab === 'duration' && (
          <FormItem
            class='classes-duration-form-item'
            label={t('单班时长')}
            labelWidth={labelWidth.value}
          >
            <Input
              v-model={localValue.date.periodSettings.duration}
              min={1}
              type='number'
              onChange={handleDurationChange}
            />
            <Select
              v-model={localValue.date.periodSettings.unit}
              clearable={false}
              onChange={handleEmitData}
            >
              {/* <Select.Option
                label={t('小时')}
                value='hour'
              /> */}
              <Select.Option
                label={t('天')}
                value='day'
              />
            </Select>
          </FormItem>
        ),
        <FormItem
          label={localValue.date.customTab === 'duration' ? t('有效时间') : t('单班时间')}
          labelWidth={labelWidth.value}
        >
          <div class='classes-list'>
            {value.map((item, ind) => [
              <div
                key={item.key}
                class='classes-item'
              >
                <TimeTagPicker
                  v-model={item.workTime}
                  label={value.length > 1 ? t('第 {num} 班', { num: ind + 1 }) : ''}
                  onChange={handleEmitData}
                />
                {value.length > 1 && (
                  <i
                    class='icon-monitor icon-mc-delete-line del-icon'
                    onClick={() => handleClassesItemChange('del', ind)}
                  />
                )}
              </div>,
              validTimeOverlap(item.workTime) && <p class='err-msg'>{t('时间段重复')}</p>,
            ])}
            {localValue.date.customTab === 'classes' && (
              <Button
                class='add-btn'
                theme='primary'
                text
                onClick={() => handleClassesItemChange('add')}
              >
                <i class='icon-monitor icon-plus-line add-icon'></i>
                {t('新增值班')}
              </Button>
            )}
          </div>
        </FormItem>,
      ];
    }
    /**
     * 渲染不同轮值类型下的单班时间
     */
    function renderClassesContent() {
      switch (rotationSelectType.value) {
        /** 工作日 */
        case RotationSelectTypeEnum.WorkDay:
        /** 周末 */
        case RotationSelectTypeEnum.Weekend:
        /** 每天 */
        case RotationSelectTypeEnum.Daily: {
          const val = localValue.date.value;
          return (
            <FormItem
              label={t('单班时间')}
              labelWidth={labelWidth.value}
            >
              <div class='classes-list'>
                {val.map((item, ind) => [
                  <div class='classes-item'>
                    <TimeTagPicker
                      key={item.key}
                      v-model={item.workTime}
                      label={val.length > 1 ? t('第 {num} 班', { num: ind + 1 }) : ''}
                      onChange={handleEmitData}
                    />
                    {val.length > 1 && (
                      <i
                        class='icon-monitor icon-mc-delete-line del-icon'
                        onClick={() => handleClassesItemChange('del', ind)}
                      />
                    )}
                  </div>,
                  validTimeOverlap(item.workTime) && <p class='err-msg'>{t('时间段重复')}</p>,
                ])}
                <Button
                  class='add-btn'
                  theme='primary'
                  text
                  onClick={() => handleClassesItemChange('add')}
                >
                  <i class='icon-monitor icon-plus-line add-icon' />
                  {t('新增值班')}
                </Button>
              </div>
            </FormItem>
          );
        }
        /** 每周 */
        case RotationSelectTypeEnum.Weekly:
        /** 每月 */
        case RotationSelectTypeEnum.Monthly:
          return weekAndMonthClasses(rotationSelectType.value);
        /** 自定义 */
        case RotationSelectTypeEnum.Custom:
          return customClasses();
      }
    }

    // ---------用户组----------

    /** 切换分组类型 */
    function handleGroupTabChange(val: ReplaceRotationUsersModel['groupType']) {
      if (localValue.users.groupType === val) return;
      localValue.users.groupType = val;
      // 切换成自动分组需要把所有人员聚合并去重
      if (val === 'auto') {
        const res = localValue.users.value.reduce((pre, cur) => {
          cur.value.forEach(user => {
            const key = `${user.id}_${user.type}`;
            if (!pre.has(key)) {
              pre.set(key, user);
            }
          });
          return pre;
        }, new Map());
        localValue.users.value = [
          { key: localValue.users.value[0].key, value: Array.from(res.values()), orderIndex: 0 },
        ];
      }
      handleEmitData();
    }

    function handleAddUserGroup() {
      localValue.users.value.push({ key: random(8, true), value: [], orderIndex: 0 });
      handleEmitData();
    }
    function handleDelUserGroup(ind: number) {
      localValue.users.value.splice(ind, 1);
      handleEmitData();
    }
    function handMemberSelectChange(ind: number, val: ReplaceRotationUsersModel['value'][0]['value']) {
      localValue.users.value[ind].value = val;
      handleEmitData();
    }

    /**
     * 自动分组人员tag模板
     * @param data 人员数据
     * @param index 人员索引
     * @returns 模板
     */
    function autoGroupTagTpl(data: TagItemModel, index: number) {
      function handleCloseTag(e: Event) {
        e.stopPropagation();
        localValue.users.value[0].value.splice(index, 1);
        handleEmitData();
      }
      return [
        <div
          style={{ 'background-color': colorList.value[getOrderIndex(index)] }}
          class='auto-group-tag-color'
        ></div>,
        <span class='icon-monitor icon-mc-tuozhuai'></span>,
        <span class='user-name'>{data?.username}</span>,
        <span
          class='icon-monitor icon-mc-close'
          onClick={e => handleCloseTag(e)}
        ></span>,
      ];
    }

    /**
     * 根据索引获取颜色
     * @param index
     * @returns
     */
    function getOrderIndex(index: number) {
      const { groupType } = localValue.users;
      if (groupType === 'auto') {
        const { orderIndex } = localValue.users.value[0];
        return orderIndex + index;
      }
      return localValue.users.value[index].orderIndex;
    }

    /** 唯一拖拽id */
    const dragUid = random(8, true);
    function handleDragstart(e: DragEvent, index: number) {
      e.dataTransfer.setData('index', String(index));
      e.dataTransfer.setData('uid', String(dragUid));
    }
    function handleDragover(e: DragEvent) {
      e.preventDefault();
    }
    function handleDrop(e: DragEvent, endIndex: number) {
      const uid = Number(e.dataTransfer.getData('uid'));
      // 不进行跨组件拖拽
      if (dragUid !== uid) return;
      const startIndex = Number(e.dataTransfer.getData('index'));
      const startUser = localValue.users.value[startIndex];
      const endUser = localValue.users.value[endIndex];
      localValue.users.value.splice(startIndex, 1);
      localValue.users.value.splice(endIndex, 0, startUser);
      setColorList(startUser.orderIndex, endUser.orderIndex);
      handleEmitDrop();
    }

    /**
     * 自动分组人员拖拽
     * @param startIndex 起始索引
     * @param endIndex 结束索引
     */
    function handleAutoGroupDrop(startIndex: number, endIndex: number) {
      setColorList(getOrderIndex(startIndex), getOrderIndex(endIndex));
      handleEmitDrop();
    }

    // 修改颜色轮盘
    function setColorList(startIndex: number, endIndex: number) {
      const newColorList = [...colorList.value];
      const color = newColorList[startIndex];
      newColorList.splice(startIndex, 1);
      newColorList.splice(endIndex, 0, color);
      colorList.setValue(newColorList);
    }

    function handleEmitDrop() {
      emit('drop');
    }

    function handleEmitData() {
      emit('change', localValue);
    }

    return {
      t,
      labelWidth,
      colorList,
      defaultGroup,
      rotationTypeList,
      localValue,
      rotationSelectType,
      getOrderIndex,
      renderClassesContent,
      autoGroupTagTpl,
      handleAddUserGroup,
      handleDelUserGroup,
      handMemberSelectChange,
      handleDragstart,
      handleDragover,
      handleDrop,
      handleAutoGroupDrop,
      handleEmitDrop,
      handleEmitData,
      handleGroupTabChange,
    };
  },
  render() {
    return (
      <tr class='replace-rotation-table-item-component'>
        <td class='step-wrapper replace-rotation'>
          <FormItem
            label={this.t('轮值类型')}
            labelWidth={this.labelWidth}
          >
            <Select
              v-model={this.rotationSelectType}
              clearable={false}
            >
              {this.rotationTypeList.map(item => (
                <Select.Option
                  id={item.value}
                  key={item.value}
                  name={item.label}
                ></Select.Option>
              ))}
            </Select>
          </FormItem>

          {this.renderClassesContent()}
        </td>
        <td class='step-wrapper replace-rotation'>
          <div class='user-panel-wrap'>
            <div class='group-tab flex'>
              <div
                class={['item', this.localValue.users.groupType === 'specified' && 'active']}
                onClick={() => this.handleGroupTabChange('specified')}
              >
                {this.t('手动分组')}
              </div>
              <div
                class={['item', this.localValue.users.groupType === 'auto' && 'active']}
                onClick={() => this.handleGroupTabChange('auto')}
              >
                {this.t('自动分组')}
              </div>
            </div>
            {this.localValue.users.groupType === 'specified' ? (
              // 手动分组
              <div class='specified-group-wrap'>
                <TransitionGroup name={'flip-list'}>
                  {this.localValue.users.value.map((item, ind) => (
                    <div
                      key={item.key}
                      class='specified-group-item'
                      draggable
                      onDragover={e => this.handleDragover(e)}
                      onDragstart={e => this.handleDragstart(e, ind)}
                      onDrop={e => this.handleDrop(e, ind)}
                    >
                      <MemberSelect
                        v-model={item.value}
                        defaultGroup={this.defaultGroup}
                        hasDefaultGroup={true}
                        showType='avatar'
                        onSelectEnd={val => this.handMemberSelectChange(ind, val)}
                      >
                        {{
                          prefix: () => (
                            <div
                              style={{ 'border-left-color': this.colorList.value[this.getOrderIndex(ind)] }}
                              class='member-select-prefix'
                            >
                              <span class='icon-monitor icon-mc-tuozhuai'></span>
                            </div>
                          ),
                        }}
                      </MemberSelect>
                      {this.localValue.users.value.length > 1 && (
                        <i
                          class='icon-monitor icon-mc-delete-line del-icon'
                          onClick={() => this.handleDelUserGroup(ind)}
                        ></i>
                      )}
                    </div>
                  ))}
                </TransitionGroup>
                <Button
                  class='add-btn'
                  theme='primary'
                  text
                  onClick={this.handleAddUserGroup}
                >
                  <i class='icon-monitor icon-plus-line add-icon' />
                  {this.t('添加用户组')}
                </Button>
              </div>
            ) : (
              // 自动分组
              <div
                class='auto-group-wrap'
                v-show={this.localValue.users.groupType === 'auto'}
              >
                <FormItem
                  label={this.t('轮值人员')}
                  labelWidth={this.labelWidth}
                >
                  <MemberSelect
                    v-model={this.localValue.users.value[0].value}
                    defaultGroup={this.defaultGroup}
                    hasDefaultGroup={true}
                    showType='tag'
                    tagTpl={this.autoGroupTagTpl}
                    onDrop={this.handleAutoGroupDrop}
                    onSelectEnd={val => this.handMemberSelectChange(0, val)}
                  />
                </FormItem>
                <FormItem
                  label={this.t('单次值班')}
                  labelWidth={this.labelWidth}
                >
                  <Input
                    style='width: 200px'
                    v-model={this.localValue.users.groupNumber}
                    min={1}
                    suffix={this.t('人')}
                    type='number'
                    onChange={this.handleEmitData}
                  />
                </FormItem>
              </div>
            )}
          </div>
        </td>
        {this.$slots.default?.()}
      </tr>
    );
  },
});
