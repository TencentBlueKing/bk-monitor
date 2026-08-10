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

import { type PropType, defineComponent, onMounted, shallowRef, useTemplateRef } from 'vue';

import { Cascader } from 'bkui-vue';

import type { IFieldItem, TGetValueFn } from './typing';

import './cascade-selector.scss';

/**
 * 级联选择器组件（基于 bkui-vue Cascader）
 * 用于业务拓扑等树形结构字段的值选择，支持多选、搜索、浮动模式。
 */
export default defineComponent({
  name: 'CascadeSelector',
  props: {
    modelValue: {
      type: Array as PropType<(number | string | string[])[]>,
      default: () => [],
    },
    fieldInfo: {
      type: Object as PropType<IFieldItem>,
      default: () => null,
    },
    getValueFn: {
      type: Function as PropType<TGetValueFn>,
      default: () =>
        Promise.resolve({
          count: 0,
          list: [],
        }),
    },
  },
  emits: {
    'update:modelValue': (_value: string[][]) => true,
    toggle: (_value: boolean) => true,
  },
  setup(props, { emit }) {
    /** 级联组件实例引用，用于自动展开面板 */
    const cascaderRef = useTemplateRef<InstanceType<typeof Cascader>>('cascader');
    /** 级联数据列表（下拉选项） */
    const list = shallowRef([]);
    /** 选中值变化时同步给父组件 */
    const handleValueChange = val => {
      emit('update:modelValue', val);
    };

    // 挂载即请求级联数据填充选项，并自动展开级联面板（点击 .bk-cascader-name 触发），免去用户手动展开
    onMounted(async () => {
      const res = await props.getValueFn({
        search: '',
        field: props.fieldInfo.field,
      });

      list.value = res.list;
      setTimeout(() => {
        cascaderRef.value?.popover?.show?.();
      }, 200);
    });

    /** 下拉展开/收起时加载数据 */
    const handleToggle = (val: boolean) => {
      emit('toggle', val);
    };

    return {
      list,

      handleValueChange,
      handleToggle,
    };
  },
  render() {
    return (
      <Cascader
        ref='cascader'
        class='retrieval-filter-cascade-selector'
        popoverOptions={{
          boundary: 'parent',
        }}
        checkAnyLevel={true}
        list={this.list}
        modelValue={this.modelValue}
        trigger='click'
        filterable
        floatMode
        multiple
        onToggle={this.handleToggle}
        onUpdate:modelValue={this.handleValueChange}
      />
    );
  },
});
