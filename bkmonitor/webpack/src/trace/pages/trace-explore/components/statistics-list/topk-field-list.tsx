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
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
 * rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
 * permit persons to whom the Software is furnished to do so, subject to the following conditions:
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

import { type PropType, defineComponent, shallowRef } from 'vue';

import { $bkPopover, Progress } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import EmptyStatus from '../../../../components/empty-status/empty-status';
import { NULL_VALUE_NAME } from '../../../../components/retrieval-filter/utils';
import { topKColorList } from '../../utils';
import { type StatisticsMode, UNIFORM_SERIES_COLOR } from './utils';

import type { ConditionChangeEvent, ITopKField } from '../../typing';

import './topk-field-list.scss';

/**
 * TopK 字段列表，弹层（top5）与侧栏（全量）两种场景共用。
 * 差异点由 mode 决定：耗时字段无 "!=" 筛选与别名子名、筛选方式为 between；
 * 数值/耗时字段进度条用统一颜色，文本字段按序取彩色列表。
 */
export default defineComponent({
  name: 'TopKFieldList',
  props: {
    list: {
      type: Array as PropType<ITopKField['list']>,
      default: () => [],
    },
    /** 当前字段名，用于筛选按钮 tooltips 与事件回传 */
    fieldName: {
      type: String,
      default: '',
    },
    mode: {
      type: String as PropType<StatisticsMode>,
      default: 'text',
    },
    /** 展示场景：弹层（top5）/ 侧栏（全量） */
    scene: {
      type: String as PropType<'popover' | 'slider'>,
      default: 'popover',
    },
    loading: {
      type: Boolean,
      default: false,
    },
  },
  emits: {
    conditionChange: (_condition: ConditionChangeEvent) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const slideOverflowPopoverInstance = shallowRef(null);

    function handleConditionChange(type: 'equal' | 'not_equal', item: ITopKField['list'][0]) {
      emit('conditionChange', {
        key: props.fieldName,
        method: props.mode === 'duration' ? 'between' : type,
        value: item.value,
      });
    }

    function topKItemMouseenter(e: MouseEvent, content: string) {
      const target = e.target as HTMLElement;
      if (target.offsetWidth < target.scrollWidth) {
        // bkui-vue 的 $Popover 类型将全部 props 声明为必填，运行时实际支持部分配置，这里用断言绕过
        slideOverflowPopoverInstance.value = $bkPopover({
          target,
          content,
          arrow: true,
          theme: 'slide-dimension-filter-overflow-tips',
        });
        slideOverflowPopoverInstance.value.install();
        setTimeout(() => {
          slideOverflowPopoverInstance.value?.show();
        }, 100);
      }
    }

    function hiddenSliderPopover() {
      slideOverflowPopoverInstance.value?.hide(0);
      slideOverflowPopoverInstance.value?.uninstall();
      slideOverflowPopoverInstance.value = null;
    }

    return { t, handleConditionChange, topKItemMouseenter, hiddenSliderPopover };
  },
  render() {
    if (this.loading)
      return (
        <div class='skeleton-wrap'>
          {new Array(5).fill(null).map((_, index) => (
            <div
              key={index}
              class='skeleton-element'
            />
          ))}
        </div>
      );
    if (!this.list.length) return <EmptyStatus type='empty' />;
    return (
      <div class='top-k-list'>
        {this.list.map((item, index) => (
          <div
            key={item.value}
            class='top-k-list-item'
          >
            <div class='filter-tools'>
              <i
                class='icon-monitor icon-a-sousuo'
                v-bk-tooltips={{
                  content: `${this.fieldName} = ${item.value || '""'}`,
                  extCls: 'statistics-top-k-item-tooltips-wrap-popover',
                  disabled: this.mode === 'duration',
                }}
                onClick={() => this.handleConditionChange('equal', item)}
              />
              {this.mode !== 'duration' && (
                <i
                  class='icon-monitor icon-sousuo-'
                  v-bk-tooltips={{
                    content: `${this.fieldName} != ${item.value || '""'}`,
                    extCls: 'statistics-top-k-item-tooltips-wrap-popover',
                  }}
                  onClick={() => this.handleConditionChange('not_equal', item)}
                />
              )}
            </div>
            <div class='progress-content'>
              <div class='info-text'>
                <span
                  class='field-name'
                  onMouseenter={e => this.topKItemMouseenter(e, item.value)}
                  onMouseleave={this.hiddenSliderPopover}
                >
                  <span>{item.alias || item.value || NULL_VALUE_NAME}</span>
                  {item.alias && this.mode !== 'duration' && <span class='sub-name'>（{item.value}）</span>}
                </span>

                <span class='counts'>
                  <span class='total'>{this.t('{0}条', [item.count])}</span>
                  <span class='progress-count'>{item.proportions}%</span>
                </span>
              </div>
              <Progress
                color={this.mode !== 'text' || this.scene === 'slider' ? UNIFORM_SERIES_COLOR : topKColorList[index]}
                percent={item.proportions}
                show-text={false}
                stroke-width={6}
              />
            </div>
          </div>
        ))}
      </div>
    );
  },
});
