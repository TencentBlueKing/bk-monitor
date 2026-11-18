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
import { computed, defineComponent } from 'vue';
import type { PropType } from 'vue';

import { Checkbox, Input, Radio } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import { RumTimelineFilterCategoryEnum, RumTimelineSortEnum } from '../../constants';

import type { RumTimelineFilterCategoryType, RumTimelineSortType } from '../../typings';

import './timeline-filter-bar.scss';

/** 快捷筛选类别与文案，顺序即胶囊按钮的展示顺序 */
const CATEGORY_OPTIONS: { id: RumTimelineFilterCategoryType; label: string }[] = [
  { id: RumTimelineFilterCategoryEnum.ALL, label: window.i18n.t('全部') },
  { id: RumTimelineFilterCategoryEnum.ACTION, label: window.i18n.t('动作') },
  { id: RumTimelineFilterCategoryEnum.SLOW_NODE, label: window.i18n.t('慢节点') },
  { id: RumTimelineFilterCategoryEnum.REQUEST, label: window.i18n.t('请求') },
  { id: RumTimelineFilterCategoryEnum.ERROR, label: window.i18n.t('错误') },
  { id: RumTimelineFilterCategoryEnum.THIRD_PARTY, label: window.i18n.t('第三方资源') },
];

/**
 * 链路上下文列表上方的快捷筛选栏：Span 搜索与类别快捷筛选。
 * 纯展示组件，筛选状态由 useTraceContext 维护。
 */
export default defineComponent({
  name: 'TimelineFilterBar',
  props: {
    /** 检索维度：会话时间轴可排序与折叠 View，会话内 View 的链路上下文只有一张卡片，不展示这两项 */
    scope: {
      type: String as PropType<'session' | 'view'>,
      required: true,
    },
    /** 时间轴总耗时，取接口 duration 格式化后的文案，为空时不展示 */
    durationText: {
      type: String,
      default: '',
    },
    keyword: {
      type: String,
      default: '',
    },
    category: {
      type: String as PropType<RumTimelineFilterCategoryType>,
      default: RumTimelineFilterCategoryEnum.ALL,
    },
    /** 排序方向：正序 / 倒序，排序结果由 useTraceContext 提供 */
    sort: {
      type: String as PropType<RumTimelineSortType>,
      default: RumTimelineSortEnum.ASC,
    },
    /** 是否折叠中间的 View，折叠结果由 useTraceContext 提供 */
    collapseMiddle: {
      type: Boolean,
      default: false,
    },
  },
  emits: {
    'update:keyword': (_value: string) => true,
    'update:category': (_value: RumTimelineFilterCategoryType) => true,
    'update:sort': (_value: RumTimelineSortType) => true,
    'update:collapseMiddle': (_value: boolean) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    /** 单 View 的链路上下文只有一张卡片，排序与折叠 View 无意义 */
    const showViewTools = computed(() => props.scope === 'session');

    return () => (
      <div class='timeline-filter-bar'>
        <div class='timeline-filter-bar-header'>
          <div class='timeline-title'>{t('会话事件时间轴')}</div>
          {props.durationText ? <div class='timeline-duration'>{props.durationText}</div> : null}
          {showViewTools.value ? (
            <div class='timeline-header-tools'>
              <div
                class={{ 'sort-btn': true, active: props.sort === RumTimelineSortEnum.ASC }}
                onClick={() => emit('update:sort', RumTimelineSortEnum.ASC)}
              >
                <i class='icon-monitor icon-paixu-xia sort-icon' />
                <span>{t('正序')}</span>
              </div>
              <div
                class={{ 'sort-btn': true, active: props.sort === RumTimelineSortEnum.DESC }}
                onClick={() => emit('update:sort', RumTimelineSortEnum.DESC)}
              >
                <i class='icon-monitor icon-paixu-shang sort-icon' />
                <span>{t('倒序')}</span>
              </div>

              <Checkbox
                class='collapse-middle-view'
                modelValue={props.collapseMiddle}
                onChange={value => emit('update:collapseMiddle', Boolean(value))}
              >
                {t('折叠中间 View')}
              </Checkbox>
            </div>
          ) : null}
        </div>
        <div class='timeline-filter-bar-body'>
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
      </div>
    );
  },
});
