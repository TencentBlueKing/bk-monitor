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
import { defineComponent, PropType, reactive, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { Button } from 'bkui-vue';
import { random } from 'lodash';

import { RotationSelectTypeEnum } from '../typings/common';

import ReplaceRotationTableItem, { ReplaceItemDataModel } from './replace-rotation-table-item';

import './replace-rotation-tab.scss';

export interface ItemDataModel extends ReplaceItemDataModel {
  key: number;
}

export interface ReplaceDataModel {
  id?: number;
  userGroupType: 'specified' | 'auto';
  data: ItemDataModel[];
}

export default defineComponent({
  name: 'ReplaceRotationTab',
  props: {
    data: {
      type: Object as PropType<ReplaceDataModel>,
      default: undefined
    }
  },
  emits: ['change', 'drop', 'preview'],
  setup(props, { emit }) {
    const { t } = useI18n();

    const localValue = reactive<ReplaceDataModel>({
      id: undefined,
      userGroupType: 'specified',
      data: []
    });

    watch(
      () => props.data,
      val => {
        if (val.data.length) {
          Object.assign(localValue, JSON.parse(JSON.stringify(val)));
        } else {
          localValue.data = [createDefaultItemData()];
          handleEmitData();
        }
      },
      {
        immediate: true
      }
    );

    function createDefaultItemData(): ItemDataModel {
      return {
        id: localValue.id,
        key: random(8, true),
        date: {
          type: RotationSelectTypeEnum.WorkDay,
          workTimeType: 'time_range',
          isCustom: false,
          customTab: 'duration',
          customWorkDays: [],
          periodSettings: {
            unit: 'day',
            duration: 1
          },
          value: [
            {
              key: random(8, true),
              workTime: [],
              workDays: [1, 2, 3, 4, 5]
            }
          ]
        },
        users: {
          type: localValue.userGroupType,
          groupNumber: 1,
          value: [{ key: random(8, true), value: [] }]
        }
      };
    }

    /** 切换分组类型 */
    function handleGroupTabChange(val: ReplaceDataModel['userGroupType']) {
      if (localValue.userGroupType === val) return;
      localValue.userGroupType = val;
      localValue.data.forEach(item => {
        item.users.type = val;
      });
      // 切换成自动分组需要把所有的用户组删除
      if (val === 'auto') {
        localValue.data.forEach(item => {
          const res = item.users.value.reduce((pre, cur) => {
            cur.value.forEach(user => {
              const key = `${user.id}_${user.type}`;
              if (!pre.has(key) && user.type === 'user') {
                pre.set(key, user);
              }
            });
            return pre;
          }, new Map());
          item.users.value = [{ key: item.users.value[0].key, value: Array.from(res.values()) }];
        });
      }
      handleEmitData();
    }

    function handleDataChange(val: ItemDataModel, index: number, hasPreview: boolean) {
      localValue.data[index] = val;
      handleEmitData();
      if (hasPreview) handleEmitPreview();
    }

    function handleAddItem() {
      localValue.data.push(createDefaultItemData());
    }

    function handleDelItem(index: number) {
      localValue.data.splice(index, 1);
      handleEmitData();
      handleEmitPreview();
    }

    function handleEmitDrop() {
      emit('drop');
    }

    function handleEmitPreview() {
      emit('preview');
    }

    function handleEmitData() {
      emit('change', localValue);
    }

    return {
      t,
      localValue,
      handleGroupTabChange,
      handleDataChange,
      handleAddItem,
      handleDelItem,
      handleEmitDrop,
      handleEmitData
    };
  },
  render() {
    return (
      <table
        class='replace-table-wrap-content-component'
        cellspacing='0'
        cellpadding='0'
      >
        <tr class='table-header'>
          <th class='title-content'>
            <span class='step-text'>Step1:</span>
            <span class='step-title'>{this.t('设置轮值规则')}</span>
          </th>
          <th class='title-content'>
            <div class='flex step2'>
              <span class='step-text'>Step2:</span>
              <span class='step-title'>{this.t('添加用户')}</span>
              <div class='grouped-tab flex'>
                <div
                  class={['item', this.localValue.userGroupType === 'specified' && 'active']}
                  onClick={() => this.handleGroupTabChange('specified')}
                >
                  {this.t('手动分组')}
                </div>
                <div
                  class={['item', this.localValue.userGroupType === 'auto' && 'active']}
                  onClick={() => this.handleGroupTabChange('auto')}
                >
                  {this.t('自动分组')}
                </div>
              </div>
            </div>
          </th>
        </tr>
        {this.localValue.data.map((item, index) => (
          <ReplaceRotationTableItem
            class='table-item'
            data={item}
            key={item.key}
            onChange={(val, hasPreview) => this.handleDataChange(val, index, hasPreview)}
            onDrop={this.handleEmitDrop}
          >
            {this.localValue.data.length > 1 && (
              <div
                class='delete-btn'
                onClick={() => this.handleDelItem(index)}
              >
                <i class='icon-monitor icon-mc-delete-line'></i>
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
              <i class='icon-monitor icon-plus-line add-icon'></i>
              {this.t('新增值班组')}
            </Button>
          </td>
        </tr>
      </table>
    );
  }
});
