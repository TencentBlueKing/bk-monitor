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
import { type PropType, computed, defineComponent, reactive, ref, watch } from 'vue';

import { Popover } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import './week-select.scss';

interface WeekListItemModel {
  hasSetStart: boolean;
  id: number;
  isStart: boolean;
  name: string;
  Selected: boolean;
}

export default defineComponent({
  name: 'WeekSelect',
  props: {
    /** 名称 */
    label: { type: String, default: '' },
    /** 名称宽度 */
    labelWidth: { type: Number, default: 52 },
    modelValue: {
      type: Array as PropType<number[]>,
      default: () => [],
    },
  },
  emits: ['update:modelValue', 'change', 'selectEnd'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const oldValue = ref<number[]>([]);
    /** 本地数据 */
    const localValue = reactive<number[]>([]);
    /** 数据是否有变化 */
    const isChange = computed(() => {
      if (oldValue.value.length !== localValue.length) return true;
      return localValue.some((val, ind) => oldValue.value[ind] !== val);
    });
    /** 用于展示的文本 */
    const localText = computed(() =>
      localValue.map(val => weekList.value.find(item => item.id === val).name).join('、')
    );
    watch(
      () => props.modelValue,
      val => {
        localValue.splice(0, localValue.length, ...val);
      },
      {
        immediate: true,
      }
    );

    // ---------popover弹窗控制------------
    /** 控制弹窗显示隐藏 */
    const show = ref(false);
    /** 显示下拉框 */
    const handleAfterShow = () => {
      show.value = true;
      oldValue.value = [...localValue];
    };
    /** 隐藏下拉框 */
    function handleAfterHidden({ isShow }) {
      show.value = isShow;
      emitSelectEnd();
    }

    // -----------星期列表--------------
    /** 周选择器实例，用于获取宽度 */
    const weekSelectRef = ref<HTMLDivElement>();
    /** hover的周选项 */
    const hoverWeek = ref<number | string>('');
    /** 选择器下拉列表 */
    const weekList = computed<WeekListItemModel[]>(() => {
      const list = [
        { id: 1, label: t('周一') },
        { id: 2, label: t('周二') },
        { id: 3, label: t('周三') },
        { id: 4, label: t('周四') },
        { id: 5, label: t('周五') },
        { id: 6, label: t('周六') },
        { id: 7, label: t('周日') },
      ];
      return list.map(item => {
        const isStart = item.id === localValue[0];
        return {
          id: item.id,
          name: item.label,
          Selected: localValue.some(val => val === item.id),
          /** 是否时起始日 */
          isStart,
          /** 是否有设置起始日功能 */
          hasSetStart: hoverWeek.value === item.id && !isStart,
        };
      });
    });
    /**
     * 点击周列表项
     * @param week 点击的周
     */
    function handleSelectItemClick(week: WeekListItemModel) {
      // 取消勾选当前行
      if (week.Selected) {
        const ind = localValue.findIndex(item => item === week.id);
        localValue.splice(ind, 1);
      } else {
        // 勾选行
        const list = weekList.value.filter(item => item.Selected || item.id === week.id);
        const startInd = list.findIndex(item => item.isStart);
        const data = [...list.slice(startInd, list.length), ...list.slice(0, startInd)].map(item => item.id);
        localValue.splice(0, localValue.length, ...data);
      }
      handleEmitData();
    }

    /**
     * 设置起始日
     * @param e 事件源
     * @param week 设置为起始日的周
     */
    function handleSetStart(e: Event, week: WeekListItemModel) {
      const list = weekList.value.filter(item => item.Selected || item.id === week.id);
      const curInd = list.findIndex(item => item.id === week.id);
      const data = [...list.slice(curInd, list.length), ...list.slice(0, curInd)].map(item => item.id);
      localValue.splice(0, localValue.length, ...data);
      handleEmitData();
      e.stopPropagation();
    }

    function handleEmitData() {
      if (isChange.value) {
        emit('update:modelValue', localValue);
        emit('change', localValue);
      }
    }
    /** 用户选择操作结束后触发 */
    function emitSelectEnd() {
      if (isChange.value) {
        emit('selectEnd', localValue);
      }
    }

    return {
      t,
      localValue,
      localText,
      show,
      handleAfterShow,
      handleAfterHidden,
      weekSelectRef,
      weekList,
      hoverWeek,
      handleSelectItemClick,
      handleSetStart,
    };
  },
  render() {
    return (
      <div class='week-select-wrapper-component'>
        {this.label && (
          <div
            style={{ width: `${this.labelWidth}px` }}
            class='label'
          >
            {this.label}
          </div>
        )}
        <div
          ref='weekSelectRef'
          class={['week-select', this.show && 'active']}
        >
          <i class={['icon-monitor', 'arrow', 'icon-arrow-down', this.show && 'active']} />
          <Popover
            extCls='week-select-popover component'
            arrow={false}
            is-show={this.show}
            placement='bottom'
            theme='light'
            trigger='click'
            onAfterHidden={this.handleAfterHidden}
            onAfterShow={this.handleAfterShow}
          >
            {{
              content: () => (
                <div class='week-list'>
                  {this.weekList.map(item => (
                    <div
                      class={['week-item', item.Selected && 'selected']}
                      onClick={() => this.handleSelectItemClick(item)}
                      onMouseenter={() => (this.hoverWeek = item.id)}
                      onMouseleave={() => (this.hoverWeek = '')}
                    >
                      <div class='week-item-content'>
                        <span class='name'>{item.name}</span>
                        {item.isStart && <div class='start-tag'>{this.t('起始日')}</div>}
                      </div>
                      {item.Selected && !item.hasSetStart && (
                        <i class='icon-monitor icon-mc-check-small selected-icon' />
                      )}
                      {item.hasSetStart && (
                        <span
                          class='set-start-btn'
                          onClick={e => this.handleSetStart(e, item)}
                        >
                          {this.t('设为起始日')}
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              ),
              default: () => (
                <div class={{ 'week-select-text': true, placeholder: !this.localText }}>
                  {this.localText || this.t('选择')}
                </div>
              ),
            }}
          </Popover>
        </div>
      </div>
    );
  },
});
