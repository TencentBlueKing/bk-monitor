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
import { type PropType, defineComponent } from 'vue';

import { Select } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import type { AiResourceOption } from '../../typings';

import './ai-resource-select.scss';

/**
 * @description 资源选择器（智能体 / 知识库 / Skill 通用）
 * 仅封装 Select 本体：本地搜索、选项渲染（名称 + 所属空间）、底部「新增」操作栏。
 * 通过具体 props 接收数据与事件，不依赖具体的 composable 实例；表单包裹由父组件负责。
 *
 * 选项接口不分页，一次返回全部可见资源，因此搜索直接交给 Select 内置的本地过滤。
 */
export default defineComponent({
  name: 'AiResourceSelect',
  props: {
    /** 下拉选项列表 */
    options: {
      type: Array as PropType<AiResourceOption[]>,
      default: () => [],
    },
    /** 是否多选（智能体单选，知识库 / Skill 多选） */
    multiple: {
      type: Boolean,
      default: false,
    },
    /** 选中值，v-model */
    modelValue: {
      type: [String, Array] as PropType<string | string[]>,
      default: '',
    },
    /** 加载中（控制自定义骨架屏，不使用 Select 内置 loading） */
    loading: {
      type: Boolean,
      default: false,
    },
    /** 底部操作栏文案，如「新增智能体」 */
    footerText: {
      type: String,
      required: true,
    },
    /** 占位提示文本 */
    placeholder: {
      type: String,
      default: '',
    },
    /** 多选展示模式：default | tag */
    multipleMode: {
      type: String as PropType<'default' | 'tag'>,
      default: 'default',
    },
    /** 选项选中样式：check | checkbox */
    selectedStyle: {
      type: String as PropType<'check' | 'checkbox'>,
      default: 'check',
    },
  },
  emits: ['update:modelValue', 'toggle'],
  setup() {
    const { t } = useI18n();

    /**
     * @description 渲染下拉面板骨架屏
     */
    const renderSelectSkeleton = () => (
      <div style='padding: 0 8px'>
        {new Array(4).fill(0).map((_, i) => (
          <div
            key={i}
            style='height: 24px; margin: 4px 0'
            class='skeleton-element'
          />
        ))}
      </div>
    );
    return { t, renderSelectSkeleton };
  },
  render() {
    return (
      <Select
        class='ai-resource-select'
        customContent={this.loading}
        loading={this.loading}
        modelValue={this.modelValue}
        multiple={this.multiple}
        multipleMode={this.multipleMode}
        noDataText={this.t('无数据')}
        placeholder={this.placeholder || this.t('请选择')}
        popoverOptions={{ extCls: 'ai-resource-select-popover' }}
        selectedStyle={this.selectedStyle}
        filterable
        onToggle={(val: boolean) => this.$emit('toggle', val)}
        onUpdate:modelValue={(val: string | string[]) => this.$emit('update:modelValue', val)}
      >
        {{
          default: () =>
            this.loading
              ? this.renderSelectSkeleton()
              : this.options.map(item => (
                  <Select.Option
                    id={item.id}
                    key={item.id}
                    name={item.name}
                  >
                    <div class='source-select-option'>
                      <span class='source-select-option-name'>{item.name}</span>
                      <span class='source-select-option-space'>{`${this.t('空间')}：${item.space_name || '--'}`}</span>
                    </div>
                  </Select.Option>
                )),
          extension: () => (
            <div class='source-select-extension'>
              <i class='icon-monitor icon-jia source-select-extension-icon' />
              <span>{this.footerText}</span>
            </div>
          ),
        }}
      </Select>
    );
  },
});
