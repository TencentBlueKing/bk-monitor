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

import { useApplicationStore } from '@/app/state/domains/application-store';
import { defineComponent, ref, computed, watch, nextTick } from 'vue';
import { RecycleScroller } from 'vue-virtual-scroller';


import { SPACE_TYPE_MAP } from '../../../app/state/constant';

import './list.scss';

export enum ETagsType {
  BCS = 'bcs',
  BKCC = 'bkcc',
  BKCI = 'bkci',
  BKSAAS = 'bksaas',
  MONITOR = 'monitor',
}

export interface ITagsItem {
  id: string;
  name: string;
  type: ETagsType;
}

export interface IListItem {
  id: number | string;
  name: string;
  space_code?: string;
  space_type_id?: string;
  space_id?: string;
  tags?: ITagsItem[];
  children?: IListItem[];
  is_hidden_tag?: boolean;
  space_uid?: string;
  type?: string;
  commonListLength?: number; // 用于标识常用业务列表的长度
}

export type ThemeType = 'dark' | 'light';

// 骨架屏行数，按列表可视高度 240px / 行高 32px 铺满
const SKELETON_ROW_COUNT = 7;
const ITEM_HEIGHT = 32;

// const DEFAULT_BIZ_ID = 'DEFAULT_BIZ_ID';

export default defineComponent({
  name: 'BizList',
  props: {
    checked: {
      type: [Number, String],
      default: undefined,
      required: true, // 强制要求传递
    },
    canSetDefaultSpace: {
      type: Boolean,
      default: true,
    },
    list: {
      type: Array as () => IListItem[],
      default: () => [],
    },
    theme: {
      type: String as () => ThemeType,
      default: 'dark',
      validator: (val: string) => ['dark', 'light'].includes(val),
    },
    commonList: {
      type: Array as () => IListItem[],
      default: () => [],
    },
    selectedIndex: {
      type: Number,
      default: -1,
    },
    selectableItems: {
      type: Array as () => IListItem[],
      default: () => [],
    },
    loading: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['handleClickOutSide', 'handleClickMenuItem', 'openDialog'],
  setup(props, { emit }) {
    const store = useApplicationStore();
    const scrollerRef = ref<{ scrollToItem?: (index: number) => void } | null>(null);
    const defaultSpace = ref<IListItem | null>(null); // 当前弹窗中选中的业务
    const isSetBizIdDefault = ref(true); // 设为默认or取消默认
    const defaultBizId = computed(() => store.defaultBizId); // 当前默认业务ID

    // 点击设置/取消默认
    const handleDefaultBizIdDialog = (e: MouseEvent, data: IListItem, isSetDefault: boolean) => {
      e.stopPropagation();
      defaultSpace.value = null;
      setTimeout(() => {
        defaultSpace.value = data;
        isSetBizIdDefault.value = isSetDefault;
        emit('openDialog', defaultSpace.value, isSetBizIdDefault.value); // 打开弹窗
        emit('handleClickOutSide'); // 关闭下拉框
      });
    };

    // 选中业务项时触发
    const handleSelected = (item: IListItem) => {
      emit('handleClickMenuItem', item);
    };

    // 常用分组的分隔线落在常用列表最后一项上，不依赖它前面是否还有置顶结果
    const isLastCommonItem = (item: IListItem) => {
      if (!props.commonList.length || item.type === 'group-title') {
        return false;
      }
      const last = props.commonList[props.commonList.length - 1];
      return item.id === last.id && item.space_uid === last.space_uid;
    };

    // 判断当前项是否被键盘选中
    const isKeyboardSelected = (item: IListItem) => {
      if (props.selectedIndex < 0 || item.type === 'group-title') {
        return false;
      }
      // 找到当前项在 selectableItems 中的索引
      const selectableIndex = props.selectableItems.findIndex(
        selectableItem => selectableItem.id === item.id && selectableItem.space_uid === item.space_uid,
      );
      return selectableIndex === props.selectedIndex;
    };

    const scrollerItems = computed(() =>
      props.list.map((item, index) => ({
        ...item,
        rowKey: `${index}-${item.space_uid || item.id || item.name}`,
      })),
    );

    watch(
      () => props.selectedIndex,
      index => {
        if (index < 0) {
          return;
        }
        const selected = props.selectableItems[index];
        const listIndex = props.list.findIndex(
          item => item.id === selected?.id && item.space_uid === selected?.space_uid,
        );
        if (listIndex < 0) {
          return;
        }
        nextTick(() => scrollerRef.value?.scrollToItem?.(listIndex));
      },
    );

    // 空间列表加载中的骨架占位，避免只渲染首屏预加载的单个空间造成误解
    const renderSkeleton = () => (
      <div class='list-skeleton'>
        {Array.from({ length: SKELETON_ROW_COUNT }).map((_, index) => (
          <div
            key={index}
            class='list-skeleton-item'
          >
            <span class='list-skeleton-bar' />
          </div>
        ))}
      </div>
    );

    // 渲染函数
    return () => (
      <div class={['biz-list-wrap', props.theme]}>
        {props.loading ? (
          renderSkeleton()
        ) : props.list.length > 0 ? (
          <RecycleScroller
            ref={scrollerRef}
            class='list-scroller'
            items={scrollerItems.value}
            itemSize={ITEM_HEIGHT}
            keyField='rowKey'
            v-slots={{
              default: ({ item, index }: { item: IListItem & { rowKey: string }; index: number }) => (
              <div
                key={item.rowKey}
                class={['list-group', props.theme]}
              >
                <div
                  data-id={item.id}
                  data-space-uid={item.space_uid}
                  class={[
                    item.type === 'group-title' ? 'list-group-title' : 'list-item',
                    props.theme,
                    { checked: item.space_uid === props.checked },
                    { 'keyboard-selected': isKeyboardSelected(item) },
                    isLastCommonItem(item) ? 'last-common-item' : '',
                  ]}
                  onClick={() => handleSelected(item)}
                >
                  <span class='list-item-left'>
                    <span class='list-item-name'>{item.name}</span>
                    <span class={['list-item-id', props.theme]}>
                      {item.type !== 'group-title' ? `(#${item.space_id})` : ''}
                    </span>
                    {props.canSetDefaultSpace && defaultBizId.value && Number(defaultBizId.value) === item.id && (
                      <span class='item-default-icon'>
                        <span class='item-default-text'>默认</span>
                      </span>
                    )}
                  </span>
                  {!item.is_hidden_tag && (
                    <span class='list-item-right'>
                      {item.tags?.map?.(tag => (
                        <span
                          key={tag.id}
                          style={{ ...SPACE_TYPE_MAP[tag.id]?.[props.theme] }}
                          class='list-item-tag'
                        >
                          {SPACE_TYPE_MAP[tag.id]?.name}
                        </span>
                      ))}
                    </span>
                  )}
                  {props.canSetDefaultSpace && item.type !== 'group-title' && (
                    <div class='set-default-button'>
                      {defaultBizId.value && Number(defaultBizId.value) === Number(item.id) ? (
                        <div
                          class={`btn-style-${props.theme} remove`}
                          onClick={e => handleDefaultBizIdDialog(e as MouseEvent, item, false)}
                        >
                          取消默认
                        </div>
                      ) : (
                        <div
                          class={`btn-style-${props.theme}`}
                          onClick={e => handleDefaultBizIdDialog(e as MouseEvent, item, true)}
                        >
                          设为默认
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
              ),
            }}
          />
        ) : (
          <div class='list-empty'>无匹配结果</div>
        )}
      </div>
    );
  },
});
