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
import { type PropType, defineComponent, reactive, watch } from 'vue';

import { Button } from 'bkui-vue';
import { random } from 'lodash';
import { useI18n } from 'vue-i18n';

import { RotationSelectTypeEnum } from '../typings/common';
import ReplaceRotationTableItem, { type ReplaceItemDataModel } from './replace-rotation-table-item';

import './replace-rotation-tab.scss';

export interface ReplaceDataModel extends ReplaceItemDataModel {
  key: number;
}

export default defineComponent({
  name: 'ReplaceRotationTab',
  props: {
    data: {
      type: Object as PropType<ReplaceDataModel[]>,
      default: undefined,
    },
  },
  emits: ['change', 'drop'],
  setup(props, { emit }) {
    const { t } = useI18n();

    const localValue = reactive<ReplaceDataModel[]>([]);

    watch(
      () => props.data,
      val => {
        if (val.length) {
          localValue.splice(0, localValue.length, ...val);
        } else {
          localValue.splice(0, localValue.length, createDefaultItemData());
        }
      },
      {
        immediate: true,
      }
    );

    function createDefaultItemData(): ReplaceDataModel {
      return {
        id: undefined,
        key: random(8, true),
        date: {
          type: RotationSelectTypeEnum.Daily,
          workTimeType: 'time_range',
          isCustom: false,
          customTab: 'duration',
          customWorkDays: [],
          periodSettings: {
            unit: 'day',
            duration: 1,
          },
          value: [
            {
              key: random(8, true),
              workTime: [],
              workDays: [1, 2, 3, 4, 5],
            },
          ],
        },
        users: {
          groupType: 'specified',
          groupNumber: 1,
          value: [{ key: random(8, true), value: [], orderIndex: 0 }],
        },
      };
    }

    function handleDataChange(val: ReplaceDataModel, index: number) {
      localValue.splice(index, 1, val);
      handleEmitData();
    }

    function handleAddItem() {
      localValue.push(createDefaultItemData());
      handleEmitData();
    }

    function handleDelItem(index: number) {
      localValue.splice(index, 1);
      handleEmitData();
    }

    function handleEmitDrop() {
      emit('drop');
    }

    function handleEmitData() {
      emit('change', localValue);
    }

    return {
      t,
      localValue,
      handleDataChange,
      handleAddItem,
      handleDelItem,
      handleEmitDrop,
      handleEmitData,
    };
  },
  render() {
    return (
      <table
        class='replace-table-wrap-content-component'
        cellpadding='0'
        cellspacing='0'
      >
        <tr class='table-header'>
          <th class='title-content'>
            <span class='step-text'>Step1:</span>
            <span class='step-title'>{this.t('设置轮值规则')}</span>
          </th>
          <th class='title-content'>
            <div class='flex step2'>
              <span class='step-text'>Step2:</span>
              <span class='step-title'>{this.t('添加轮值人员')}</span>
            </div>
          </th>
        </tr>
        {this.localValue.map((item, index) => (
          <ReplaceRotationTableItem
            key={item.key}
            class='table-item'
            data={item}
            onChange={val => this.handleDataChange(val, index)}
            onDrop={this.handleEmitDrop}
          >
            {this.localValue.length > 1 && (
              <div
                class='delete-btn'
                onClick={() => this.handleDelItem(index)}
              >
                <i class='icon-monitor icon-mc-delete-line' />
              </div>
            )}
          </ReplaceRotationTableItem>
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
