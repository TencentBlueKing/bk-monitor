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
import { type PropType, computed, defineComponent, shallowRef } from 'vue';

import { Select } from 'bkui-vue';

import './panel-source-selector.scss';

export interface IPanelSourceOption {
  id: string;
  name: string;
}

/**
 * 告警详情各 tab 筛选条上方的数据源下拉，触发器形如「应用：xxx」「数据ID：xxx」，
 * 与「Tracing 检索」「事件检索」页顶栏的选择器保持一致的交互与视觉。
 */
export default defineComponent({
  name: 'PanelSourceSelector',
  props: {
    /** 触发器前缀文案，如「应用」「数据ID」 */
    label: {
      type: String,
      default: '',
    },
    value: {
      type: String,
      default: '',
    },
    list: {
      type: Array as PropType<IPanelSourceOption[]>,
      default: () => [],
    },
    loading: {
      type: Boolean,
      default: false,
    },
    placeholder: {
      type: String,
      default: '',
    },
  },
  emits: {
    change: (_value: string) => true,
  },
  setup(props, { emit }) {
    const isExpand = shallowRef(false);

    /**
     * 列表接口不一定包含告警自身关联的那一项（例如 APM 告警的数据源 builtin 不在
     * get_data_source_config 的返回里），补进去保证当前值可见、切走后还能切回来。
     */
    const displayList = computed<IPanelSourceOption[]>(() => {
      if (!props.value || props.list.some(item => item.id === props.value)) return props.list;
      return [{ id: props.value, name: props.value }, ...props.list];
    });

    const currentName = computed(() => displayList.value.find(item => item.id === props.value)?.name || props.value);

    const handleSelect = (value: string) => {
      if (value !== props.value) {
        emit('change', value);
      }
    };

    const handleToggle = (val: boolean) => {
      isExpand.value = val;
    };

    return {
      isExpand,
      displayList,
      currentName,
      handleSelect,
      handleToggle,
    };
  },
  render() {
    if (this.loading) {
      return <div class='skeleton-element panel-source-selector-loading' />;
    }
    return (
      <Select
        class='panel-source-selector'
        clearable={false}
        modelValue={this.value}
        popoverOptions={{ extCls: 'panel-source-selector-popover' }}
        searchPlaceholder={this.placeholder}
        filterable
        onSelect={this.handleSelect}
        onToggle={this.handleToggle}
      >
        {{
          trigger: () => (
            <div class={['panel-source-selector-trigger', { active: this.isExpand }]}>
              <span class='source-label'>{this.label}：</span>
              <span
                class='source-name'
                v-overflow-tips
              >
                {this.currentName}
              </span>
              <span class={['icon-monitor', 'icon-mc-arrow-down', { expand: this.isExpand }]} />
            </div>
          ),
          default: () =>
            this.displayList.map(item => (
              <Select.Option
                id={item.id}
                key={item.id}
                name={item.name}
              />
            )),
        }}
      </Select>
    );
  },
});
