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
import { type PropType, type Ref, defineComponent, inject, reactive, watch } from 'vue';

import { Button, DatePicker, Select } from 'bkui-vue';
import { random } from 'lodash';
import { useI18n } from 'vue-i18n';

import MemberSelect from '../../../components/member-select/member-select';
import { RotationSelectTypeEnum, WeekDataList } from '../typings/common';
import { validTimeOverlap } from '../utils';
import CalendarSelect from './calendar-select';
import FormItem from './form-item';
import TimeTagPicker from './time-tag-picker';

import './fixed-rotation-tab.scss';

export interface FixedDataModel {
  id?: number;
  key: number;
  orderIndex: number;
  users: { id: string; type: 'group' | 'user' }[];
  workDateRange: [];
  workDays: (number | string)[];
  workTime: string[][];
  type:
    | RotationSelectTypeEnum.Daily
    | RotationSelectTypeEnum.DateRange
    | RotationSelectTypeEnum.Monthly
    | RotationSelectTypeEnum.Weekly;
}

export default defineComponent({
  name: 'FixedRotationTab',
  props: {
    data: {
      type: Array as PropType<FixedDataModel[]>,
      default: () => [],
    },
  },
  emits: ['change'],
  setup(props, { emit }) {
    // --------公共------------
    const { t } = useI18n();
    const defaultGroup = inject<Ref<any[]>>('defaultGroup');
    const colorList = inject<{ setValue: (val: string[]) => void; value: string[] }>('colorList');

    const typeList = [
      { label: t('每天'), value: RotationSelectTypeEnum.Daily },
      { label: t('按周'), value: RotationSelectTypeEnum.Weekly },
      { label: t('按月'), value: RotationSelectTypeEnum.Monthly },
      { label: t('指定时间'), value: RotationSelectTypeEnum.DateRange },
    ];
    function createDefaultData(): FixedDataModel {
      return {
        id: undefined,
        key: random(8, true),
        type: RotationSelectTypeEnum.Weekly,
        workDays: [1],
        orderIndex: 0,
        workDateRange: [],
        workTime: [],
        users: [],
      };
    }

    // ---------数据----------
    const localValue = reactive<FixedDataModel[]>([]);
    watch(
      () => props.data,
      val => {
        if (val.length) {
          localValue.splice(0, localValue.length, ...val);
        } else {
          localValue.splice(0, localValue.length, createDefaultData());
        }
      },
      {
        immediate: true,
      }
    );
    const handleDateTypeChange = (item: FixedDataModel) => {
      if (item.type !== RotationSelectTypeEnum.DateRange) {
        item.workDays = [1];
      } else {
        item.workDateRange = [];
      }
      handleEmitData();
    };
    function handleAddItem() {
      localValue.push(createDefaultData());
      handleEmitData();
    }
    function handleDelItem(ind: number) {
      localValue.splice(ind, 1);
      handleEmitData();
    }
    function handleUserChange(val: FixedDataModel['users'], item: FixedDataModel) {
      item.users = val;
      handleEmitData();
    }
    function handleEmitData() {
      emit('change', localValue);
    }

    return {
      t,
      colorList,
      defaultGroup,
      localValue,
      typeList,
      handleUserChange,
      handleDateTypeChange,
      handleAddItem,
      handleDelItem,
      handleEmitData,
    };
  },
  render() {
    return (
      <table
        class='fixed-table-wrap-content-component'
        cellpadding='0'
        cellspacing='0'
      >
        <tr class='table-header'>
          <th class='title-content'>
            <span class='step-text'>Step1:</span>
            <span class='step-title'>{this.t('设计值班时间')}</span>
          </th>
          <th class='title-content'>
            <span class='step-text'>Step2:</span>
            <span class='step-title'>{this.t('添加轮值人员')}</span>
          </th>
        </tr>

        {this.localValue.map((item, ind) => (
          <tr
            key={item.key}
            class='table-item'
          >
            <td class='date-setting-content'>
              <FormItem
                class='work-time-rang-form-item'
                label={this.t('工作时间范围')}
                labelWidth={92}
              >
                <Select
                  class='date-type-select'
                  v-model={item.type}
                  clearable={false}
                  onChange={() => this.handleDateTypeChange(item)}
                >
                  {this.typeList.map(type => (
                    <Select.Option
                      label={type.label}
                      value={type.value}
                    />
                  ))}
                </Select>
                {item.type === RotationSelectTypeEnum.Weekly && (
                  <Select
                    class='date-value-select'
                    v-model={item.workDays}
                    clearable={false}
                    multiple
                    onToggle={this.handleEmitData}
                  >
                    {WeekDataList.map(week => (
                      <Select.Option
                        label={week.label}
                        value={week.id}
                      />
                    ))}
                  </Select>
                )}
                {item.type === RotationSelectTypeEnum.Monthly && (
                  <CalendarSelect
                    class='date-value-select'
                    v-model={item.workDays}
                    onSelectEnd={this.handleEmitData}
                  />
                )}
                {item.type === RotationSelectTypeEnum.DateRange && (
                  <DatePicker
                    class='date-value-select'
                    v-model={item.workDateRange}
                    appendToBody={true}
                    format='yyyy-MM-dd'
                    placeholder={`${this.t('如')}: 2019-01-30 至 2019-01-30`}
                    type='daterange'
                    clearable
                    onChange={this.handleEmitData}
                  />
                )}
              </FormItem>
              <FormItem
                label={this.t('工作时间')}
                labelWidth={92}
              >
                <TimeTagPicker
                  v-model={item.workTime}
                  onChange={this.handleEmitData}
                />
                {validTimeOverlap(item.workTime) && <p class='err-msg'>{this.t('时间段重复')}</p>}
              </FormItem>
            </td>
            <td class='user-setting-content'>
              <MemberSelect
                v-model={item.users}
                defaultGroup={this.defaultGroup}
                hasDefaultGroup={true}
                showType='avatar'
                onSelectEnd={val => this.handleUserChange(val, item)}
              >
                {{
                  prefix: () => (
                    <div
                      style={{ 'border-left-color': this.colorList.value[item.orderIndex] }}
                      class='member-select-prefix'
                    />
                  ),
                }}
              </MemberSelect>
            </td>
            {this.localValue.length > 1 && (
              <div
                class='delete-btn'
                onClick={() => this.handleDelItem(ind)}
              >
                <i class='icon-monitor icon-mc-delete-line' />
              </div>
            )}
          </tr>
        ))}
        <tr class='table-footer'>
          <td
            class='footer-content'
            colspan={2}
          >
            <Button
              theme='primary'
              text
              onClick={this.handleAddItem}
            >
              <i class='icon-monitor icon-plus-line add-icon' />
              {this.t('新增值班组')}
            </Button>
          </td>
        </tr>
      </table>
    );
  },
});
