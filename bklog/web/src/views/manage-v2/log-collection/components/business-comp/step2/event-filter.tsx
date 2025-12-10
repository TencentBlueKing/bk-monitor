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

import { defineComponent, computed, type PropType } from 'vue';

import useLocale from '@/hooks/use-locale';

import './event-filter.scss';

/**
 * 事件类型
 */
export type EventType = 'winlog_event_id' | 'winlog_level' | 'winlog_source' | 'winlog_content';

/**
 * 事件过滤项接口
 */
export interface IEventFilterItem {
  type: EventType;
  list: string[];
  isCorrect: boolean;
}

/**
 * 事件选项接口
 */
interface IEventOption {
  id: EventType;
  name: string;
  isSelect: boolean;
}

export default defineComponent({
  name: 'EventFilter',
  props: {
    data: {
      type: Array as PropType<IEventFilterItem[]>,
      default: () => [] as IEventFilterItem[],
    },
  },

  emits: ['change'],

  setup(props, { emit }) {
    const { t } = useLocale();
    const selectEventList: IEventOption[] = [
      {
        id: 'winlog_event_id',
        name: t('事件ID'),
        isSelect: false,
      },
      {
        id: 'winlog_level',
        name: t('级别'),
        isSelect: false,
      },
      {
        id: 'winlog_source',
        name: t('事件来源'),
        isSelect: false,
      },
      {
        id: 'winlog_content',
        name: t('事件内容'),
        isSelect: false,
      },
    ];

    const maxLength = selectEventList.length;
    /**
     * 已经选中的类型
     */
    const chooseList = computed(() => props.data.map(item => item.type));
    const isDisabled = (id: EventType): boolean => {
      return chooseList.value.includes(id);
    };
    /**
     * 新增
     */
    const handleAdd = (): void => {
      const noChooseList = selectEventList.filter(val => !chooseList.value.includes(val.id));
      if (noChooseList.length === 0) return;
      const data: IEventFilterItem[] = [
        {
          type: noChooseList[0].id,
          list: [],
          isCorrect: true,
        },
      ];
      const list = [...props.data, ...data];
      emit('change', list);
    };
    /**
     * 删除
     * @param item - 要删除的事件过滤项
     */
    const handleDel = (item: IEventFilterItem): void => {
      const data = props.data.filter(val => val.type !== item.type);
      emit('change', data);
    };
    const renderItem = (item: IEventFilterItem) => (
      <div class='event-filter-item'>
        <bk-select
          class='event-filter-select'
          clearable={false}
          value={item.type}
          on-selected={(val: EventType) => {
            item.type = val;
            emit('change', props.data);
          }}
        >
          {selectEventList.map(option => (
            <bk-option
              id={option.id}
              key={option.id}
              disabled={isDisabled(option.id)}
              name={option.name}
            />
          ))}
        </bk-select>
        <bk-tag-input
          class='event-filter-tag-input'
          allow-auto-match={true}
          allow-create={true}
          has-delete-icon={true}
          value={item.list}
          free-paste
          on-change={(val: string[]) => {
            item.list = val;
            emit('change', props.data);
          }}
        />
        <div class='item-tool'>
          <span
            class={{
              'bk-icon icon-plus-circle-shape icons': true,
              disabled: props.data.length >= maxLength,
            }}
            on-Click={handleAdd}
          />
          <span
            class={{
              'bk-icon icon-minus-circle-shape icons': true,
              disabled: props.data.length <= 1,
            }}
            on-Click={() => handleDel(item)}
          />
        </div>
      </div>
    );
    return () => <div class='event-filter-main'>{(props.data || []).map(item => renderItem(item))}</div>;
  },
});
