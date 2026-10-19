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
import { defineComponent } from 'vue';
import type { PropType } from 'vue';

import { Input, Radio } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import type { RumTimelineFilterCategoryType } from '../../typings';

import './timeline-filter-bar.scss';

/** 快捷筛选类别与文案 */
const CATEGORY_OPTIONS: { id: 'all' | Exclude<RumTimelineFilterCategoryType, 'all'>; label: string }[] = [
  { id: 'all', label: window.i18n.t('全部') },
  { id: 'action', label: window.i18n.t('动作') },
  { id: 'slow_node', label: window.i18n.t('慢节点') },
  { id: 'request', label: window.i18n.t('请求') },
  { id: 'third_party', label: window.i18n.t('第三方资源') },
  { id: 'error', label: window.i18n.t('异常') },
];

/**
 * 链路上下文列表上方的快捷筛选栏：Span 搜索与类别快捷筛选。
 * 纯展示组件，筛选状态由 useTraceContext 维护。
 */
export default defineComponent({
  name: 'TimelineFilterBar',
  props: {
    keyword: {
      type: String,
      default: '',
    },
    category: {
      type: String as PropType<RumTimelineFilterCategoryType>,
      default: 'all',
    },
  },
  emits: {
    'update:keyword': (_value: string) => true,
    'update:category': (_value: RumTimelineFilterCategoryType) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();

    return () => (
      <div class='timeline-filter-bar'>
        <Input
          class='filter-search'
          clearable={true}
          modelValue={props.keyword}
          placeholder={t('搜索 Span')}
          type='search'
          onUpdate:modelValue={value => emit('update:keyword', value as string)}
        />
        <Radio.Group
          class='filter-categories'
          modelValue={props.category}
          type='capsule'
          onChange={value => emit('update:category', value as RumTimelineFilterCategoryType)}
        >
          {CATEGORY_OPTIONS.map(option => (
            <Radio.Button
              key={option.id}
              label={option.id}
            >
              {option.label}
            </Radio.Button>
          ))}
        </Radio.Group>
      </div>
    );
  },
});
