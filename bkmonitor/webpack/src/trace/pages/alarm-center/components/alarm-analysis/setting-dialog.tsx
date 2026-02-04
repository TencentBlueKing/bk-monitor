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
import { computed, defineComponent, shallowRef, TransitionGroup, watch } from 'vue';
import type { PropType } from 'vue';

import { useThrottleFn } from '@vueuse/core';
import { Button, Checkbox, Dialog, Input } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import EmptyStatus from '../../../../components/empty-status/empty-status';
import { useAlarmCenterStore } from '../../../../store/modules/alarm-center';

import type { QuickFilterItem } from '../../typings';

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
    selectValue: {
      type: Array as PropType<string[]>,
      default: () => [],
    },
  },
  emits: ['update:show', 'selectValueChange'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const alarmStore = useAlarmCenterStore();
    const localSelectValue = shallowRef<string[]>([]);

    watch(
      () => props.show,
      value => {
        if (value) {
          localSelectValue.value = [...props.selectValue];
        }
      }
    );

    const localSelectValueList = computed(() => {
      const list = [...props.fieldList, ...props.dimensionList];
      return localSelectValue.value.map(id => list.find(item => item.id === id) || { id, name: id });
    });

    /** 字段，维度类别 */
    const selectType = shallowRef<SelectType>('field');
    const types = shallowRef<{ id: SelectType; name: string }[]>([
      { id: 'field', name: t('字段') },
      { id: 'dimension', name: t('维度') },
    ]);
    const handleTypeChange = (type: SelectType) => {
      selectType.value = type;
    };

    /** 搜索 */
    const searchValue = shallowRef('');
    const handleSearch = (value: string) => {
      searchValue.value = value;
    };
    /** 搜索结果列表 */
    const searchResultList = computed(() => {
      const list = selectType.value === 'field' ? props.fieldList : props.dimensionList;
      return list.filter(item => item.name.includes(searchValue.value));
    });

    const handleCheckChange = (item: Omit<QuickFilterItem, 'children'>, checked: boolean) => {
      if (checked) {
        localSelectValue.value = [...localSelectValue.value, item.id];
      } else {
        localSelectValue.value = localSelectValue.value.filter(id => id !== item.id);
      }
    };

    const handleDeleteItem = (index: number) => {
      localSelectValue.value = localSelectValue.value.filter((_id, i) => i !== index);
    };

    const handleClearSelect = () => {
      localSelectValue.value = [];
    };

    const handleShowChange = (value: boolean) => {
      if (!value) {
        searchValue.value = '';
        selectType.value = 'field';
      }
      emit('update:show', value);
    };

    /** 拖拽的字段 */
    const draggingField = shallowRef('');
    /** 目标字段 */
    const targetField = shallowRef('');

    /** 变更拖拽对象和目标对象位置 */
    const transformFieldItemPosition = () => {
      if (!draggingField.value || !targetField.value || targetField.value === draggingField.value) {
        return;
      }
      const list = [...localSelectValue.value];
      const targetIndex = list.indexOf(targetField.value);
      const sourceIndex = list.indexOf(draggingField.value);
      if (sourceIndex > targetIndex) {
        list.splice(sourceIndex, 1);
        list.splice(targetIndex, 0, draggingField.value);
      } else {
        list.splice(targetIndex + 1, 0, draggingField.value);
        list.splice(sourceIndex, 1);
      }
      localSelectValue.value = list;
    };

    const throttleTransformFieldItemPosition = useThrottleFn(transformFieldItemPosition, 300);
    /**
     * @description 源对象开始进入目标对象范围内触发, 记录目标对象
     *
     */
    function handleDragover(e: DragEvent, field: string) {
      targetField.value = field;
      dragPreventDefault(e);
      throttleTransformFieldItemPosition();
    }
    /**
     * @description 源对象拖动结束时触发
     *
     */
    function handleDragend(e: DragEvent) {
      console.log('dragend', targetField.value, draggingField.value);
      transformFieldItemPosition();
      const target = e.target as HTMLElement;
      const dragDom = target.closest('.target-item');
      if (dragDom) {
        dragDom?.classList.remove('dragging');
        // @ts-expect-error
        dragDom.draggable = false;
      }
      draggingField.value = '';
      targetField.value = '';
    }

    /**
     * @description 源对象开始被拖动时触发，记录当前拖拽的key值
     *
     */
    function handleDragstart(e: DragEvent, field: string) {
      draggingField.value = field;
      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData('text/plain', field);
      // @ts-expect-error
      e.target.closest('.target-item').classList.add('dragging');
    }

    /**
     * @description drag 操作句柄鼠标 按下/松开 触发回调事件
     *
     */
    function dragHandleMouseOperation(e: MouseEvent, draggable) {
      // @ts-expect-error
      e.target.closest('.target-item').draggable = draggable;
    }

    /**
     * @description 阻止默认事件
     */
    function dragPreventDefault(e) {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
    }

    function handleConfirm() {
      emit('selectValueChange', localSelectValue.value);
    }

    return {
      t,
      alarmStore,
      types,
      selectType,
      searchValue,
      searchResultList,
      localSelectValue,
      localSelectValueList,
      handleShowChange,
      handleTypeChange,
      handleSearch,
      handleCheckChange,
      handleDeleteItem,
      handleClearSelect,
      dragPreventDefault,
      handleDragstart,
      handleDragover,
      handleDragend,
      dragHandleMouseOperation,
      handleConfirm,
    };
  },
  render() {
    return (
      <Dialog
        width={960}
        class='alarm-analysis-setting-dialog'
        v-slots={{
          header: () => <div class='title'>{this.t('告警分析设置')}</div>,
          default: () => (
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
                  placeholder={this.$t('搜索 字段名称')}
                  type='search'
                  clearable
                  onClear={() => this.handleSearch('')}
                  onInput={this.handleSearch}
                />
                {this.searchResultList.length ? (
                  <div class='select-group-wrap'>
                    {this.searchResultList.map(item => (
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
                ) : (
                  <EmptyStatus type='empty' />
                )}
              </div>
              <div
                class='right-panel'
                onDragenter={this.dragPreventDefault}
                onDragover={this.dragPreventDefault}
              >
                <div class='header'>
                  <i18n-t
                    keypath='已选 {0} 项'
                    tag='span'
                  >
                    <span class='selected-count'>{this.localSelectValue.length}</span>
                  </i18n-t>
                  <span
                    class='clear-btn'
                    onClick={this.handleClearSelect}
                  >
                    {this.$t('清空')}
                  </span>
                </div>
                {this.localSelectValueList.length ? (
                  <TransitionGroup
                    class='selected-list'
                    name='drag'
                    tag='ul'
                  >
                    {this.localSelectValueList.map((field, index) => {
                      return (
                        <li
                          key={field.id}
                          class='list-item target-item'
                          onDragend={this.handleDragend}
                          onDragover={e => this.handleDragover(e, field.id)}
                          onDragstart={e => this.handleDragstart(e, field.id)}
                        >
                          <div class='list-item-left'>
                            <i
                              class='icon-monitor icon-mc-tuozhuai'
                              onMousedown={e => this.dragHandleMouseOperation(e, true)}
                              onMouseup={e => this.dragHandleMouseOperation(e, false)}
                            />
                            <span
                              class='item-label'
                              v-overflow-tips
                            >
                              {field.name}
                            </span>
                          </div>
                          <i
                            class='icon-monitor icon-mc-close'
                            onClick={() => this.handleDeleteItem(index)}
                          />
                        </li>
                      );
                    })}
                  </TransitionGroup>
                ) : (
                  <EmptyStatus
                    textMap={{ empty: this.$t('暂无选中项') }}
                    type='empty'
                  />
                )}
              </div>
            </div>
          ),
        }}
        isShow={this.show}
        quickClose
        onConfirm={this.handleConfirm}
        onUpdate:isShow={this.handleShowChange}
      />
    );
  },
});
