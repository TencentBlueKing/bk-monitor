/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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

import { type PropType, computed, defineComponent } from 'vue';

import { Checkbox, Dropdown } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import './across-page-selection.scss';

/** 选择状态枚举 */
export const SelectType = {
  /** 未选择 */
  UN_SELECTED: 0,
  /** 本页全选 */
  SELECTED: 1,
  /** 半选（本页范围内部分选中） */
  HALF_SELECTED: 2,
  /** 跨页全选 */
  ALL_SELECTED: 3,
  /** 跨页半选（跨页范围内部分选中，来源为跨页全选） */
  HALF_ALL_SELECTED: 4,
} as const;

/** 选择状态类型 */
export type SelectTypeEnum = (typeof SelectType)[keyof typeof SelectType];

/**
 * 跨页选择组件
 * 支持本页全选和跨页全选两种模式，通过下拉菜单切换选择范围
 */
export default defineComponent({
  name: 'AcrossPageSelection',
  props: {
    /** 当前选择状态 */
    value: {
      type: Number as PropType<SelectTypeEnum>,
      default: SelectType.UN_SELECTED,
    },
  },
  emits: {
    /** 选择状态变更事件 */
    change: (_value: SelectTypeEnum) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();

    /** 是否为跨页全选状态 */
    const isAcrossPageSelected = computed(() => props.value === SelectType.ALL_SELECTED);
    /** 下拉菜单高亮项：将半选态映射回其来源的全选类型，使高亮与实际选择范围一致 */
    const highlightType = computed<SelectTypeEnum>(() => {
      if (props.value === SelectType.HALF_SELECTED) {
        return SelectType.SELECTED;
      }
      if (props.value === SelectType.HALF_ALL_SELECTED) {
        return SelectType.ALL_SELECTED;
      }
      return props.value;
    });

    /** 是否处于选中状态（本页全选或跨页全选） */
    const isSelected = computed(() => props.value === SelectType.ALL_SELECTED || props.value === SelectType.SELECTED);

    /** 下拉选项列表 */
    const selectList: { id: SelectTypeEnum; name: string }[] = [
      { id: SelectType.SELECTED, name: t('本页全选') },
      { id: SelectType.ALL_SELECTED, name: t('跨页全选') },
    ];

    /**
     * 处理下拉菜单选项选择
     * @param id 选择类型
     */
    const handleSelect = (id: SelectTypeEnum) => {
      emit('change', id);
    };

    /**
     * 处理 Checkbox 状态变更
     * @param value Checkbox 选中状态
     */
    const handleChangeValue = (value: boolean | number | string) => {
      if (!value) {
        emit('change', SelectType.UN_SELECTED);
        return;
      }
      // 半选态点击选中：恢复为来源全选类型（跨页半选 → 跨页全选，本页半选 → 本页全选）
      const typeToEmit = props.value === SelectType.HALF_ALL_SELECTED ? SelectType.ALL_SELECTED : SelectType.SELECTED;
      emit('change', typeToEmit);
    };

    /** 清除跨页全选状态 */
    const handleClearAcrossPageSelect = () => {
      emit('change', SelectType.UN_SELECTED);
    };

    return () => (
      <Dropdown
        popoverOptions={{
          placement: 'bottom-start',
          clickContentAutoHide: true,
          extCls: 'across-page-selection-popover',
          offset: { crossAxis: 22, mainAxis: 0 },
        }}
      >
        {{
          /** 触发器区域：包含 Checkbox 和下拉箭头 */
          default: () => (
            <div class='across-page-selection-component'>
              {isAcrossPageSelected.value ? (
                // 跨页全选状态下显示自定义选中态，点击可取消选择
                <div
                  class='across-page-across-selection-main'
                  onClick={handleClearAcrossPageSelect}
                />
              ) : (
                // 普通状态下显示 Checkbox，支持半选态
                <Checkbox
                  class={{ 'half-all-checked': props.value === SelectType.HALF_ALL_SELECTED }}
                  indeterminate={
                    props.value === SelectType.HALF_SELECTED || props.value === SelectType.HALF_ALL_SELECTED
                  }
                  modelValue={isSelected.value}
                  onChange={handleChangeValue}
                />
              )}
              <i class='icon-monitor icon-arrow-down selection-trigger' />
            </div>
          ),
          /** 下拉菜单内容：本页全选 / 跨页全选 */
          content: () => (
            <Dropdown.DropdownMenu>
              {selectList.map(item => (
                <Dropdown.DropdownItem
                  key={item.id}
                  extCls={highlightType.value === item.id ? 'list-item-active' : ''}
                  onClick={() => handleSelect(item.id)}
                >
                  {item.name}
                </Dropdown.DropdownItem>
              ))}
            </Dropdown.DropdownMenu>
          ),
        }}
      </Dropdown>
    );
  },
});
