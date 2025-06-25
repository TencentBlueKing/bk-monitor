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
import { computed, defineComponent, shallowRef, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import { Button, Checkbox, Dialog, Input } from 'bkui-vue';

import { useAlarmCenterStore } from '../../../../store/modules/alarm-center';

import type { QuickFilterItem } from '../../typings';
import type { PropType } from 'vue';

import './setting-dialog.scss';

export type SelectType = 'dimension' | 'field';

export default defineComponent({
  name: 'SettingDialog',
  props: {
    show: {
      type: Boolean,
      default: false,
    },
    fieldList: {
      type: Array as PropType<Omit<QuickFilterItem, 'children'>[]>,
      default: () => [],
    },
    dimensionList: {
      type: Array as PropType<Omit<QuickFilterItem, 'children'>[]>,
      default: () => [],
    },
    settingValue: {
      type: Array as PropType<string[]>,
      default: () => [],
    },
  },
  emits: ['update:show'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const alarmStore = useAlarmCenterStore();
    const localSelectValue = shallowRef<string[]>([]);

    watch(
      () => props.show,
      value => {
        if (value) {
          localSelectValue.value = [...props.settingValue];
        }
      }
    );

    const selectType = shallowRef<SelectType>('field');
    const types = shallowRef<{ id: SelectType; name: string }[]>([
      { id: 'field', name: t('字段') },
      { id: 'dimension', name: t('维度') },
    ]);
    const handleTypeChange = (type: SelectType) => {
      selectType.value = type;
    };

    const searchValue = shallowRef('');
    const handleSearch = (value: string) => {
      searchValue.value = value;
    };

    const showList = computed(() => {
      const list = selectType.value === 'field' ? props.fieldList : props.dimensionList;
      return list.filter(item => item.name.includes(searchValue.value));
    });

    const handleCheckChange = (item: Omit<QuickFilterItem, 'children'>, checked: boolean) => {
      if (checked) {
        localSelectValue.value.push(item.id);
      } else {
        localSelectValue.value = localSelectValue.value.filter(id => id !== item.id);
      }
    };

    const handleShowChange = (value: boolean) => {
      if (!value) {
        searchValue.value = '';
        selectType.value = 'field';
      }
      emit('update:show', value);
    };

    return {
      t,
      alarmStore,
      types,
      selectType,
      searchValue,
      showList,
      localSelectValue,
      handleShowChange,
      handleTypeChange,
      handleSearch,
      handleCheckChange,
    };
  },
  render() {
    return (
      <Dialog
        width={960}
        class='alarm-analysis-setting-dialog'
        isShow={this.show}
        quickClose
        onUpdate:isShow={this.handleShowChange}
      >
        {{
          header: () => <div class='title'>{this.t('告警分析设置')}</div>,
          default: (
            <div class='content'>
              <div class='field-select-wrap'>
                {this.alarmStore.alarmType === 'alert' && (
                  <Button.ButtonGroup class='select-button-group'>
                    {this.types.map(item => (
                      <Button
                        key={item.id}
                        selected={this.selectType === item.id}
                        onClick={() => this.handleTypeChange(item.id)}
                      >
                        {item.name}
                      </Button>
                    ))}
                  </Button.ButtonGroup>
                )}

                <Input
                  class='search-input'
                  modelValue={this.searchValue}
                  type='search'
                  clearable
                  onClear={() => this.handleSearch('')}
                  onInput={this.handleSearch}
                />

                {/* <Checkbox.Group
                  class='select-check-box-group'
                  modelValue={this.selectType === 'field' ? this.fieldSelectList : this.dimensionSelectList}
                  onChange={this.handleCheckChange}
                ></Checkbox.Group> */}
                <div class='select-group-wrap'>
                  {this.showList.map(item => (
                    <Checkbox
                      key={item.id}
                      label={item.id}
                      modelValue={this.localSelectValue.includes(item.id)}
                      onChange={checked => this.handleCheckChange(item, checked)}
                    >
                      {item.name}
                    </Checkbox>
                  ))}
                </div>
              </div>
              <div class='selected-list' />
            </div>
          ),
        }}
      </Dialog>
    );
  },
});
