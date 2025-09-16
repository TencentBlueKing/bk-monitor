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

import { computed, defineComponent, onBeforeUnmount, onMounted, type PropType, type Ref, ref } from 'vue';

import { getOsCommandLabel } from '../../../../common/util';
import BklogPopover from '../../../../components/bklog-popover';
import EllipsisTagList from '../../../../components/ellipsis-tag-list';
import Content from './content';

import type { IndexSetTabList, IndexSetType } from './use-choice';
import type { Props } from 'tippy.js';

import './index.scss';

export default defineComponent({
  props: {
    height: {
      type: Number,
      default: 32,
    },
    width: {
      type: [Number, String],
      default: 400,
    },
    maxWidth: {
      type: Number,
      default: 600,
    },
    minWidth: {
      type: Number,
      default: 400,
    },
    contentWidth: {
      type: Number,
      default: 800,
    },
    textDir: {
      type: String,
      default: 'ltr',
    },
    // 索引集类型：单选-single | 联合索引-union
    activeType: {
      type: String as PropType<IndexSetType>,
      default: 'single',
    },
    // 单选-single | 联合索引-union | history-历史记录 | favorite-收藏
    activeTab: {
      type: String as PropType<IndexSetTabList>,
      default: 'single',
    },
    // 索引集值
    indexSetValue: {
      type: Array,
      default: () => [],
    },
    // 索引集列表
    indexSetList: {
      type: Array,
      default: () => [],
    },

    // 当前uid
    spaceUid: {
      type: String,
      default: '',
    },
    zIndex: {
      type: Number,
      default: 101,
    },
  },
  emits: ['type-change', 'value-change', 'auth-request'],
  setup(props, { emit }) {
    const isOpened = ref(false);
    const refRootElement: Ref<any | null> = ref(null);
    const shortcutKey = `${getOsCommandLabel()}+O`;
    const refContentObject: Ref<any | null> = ref(null);

    let unionListValue: any[] = [];

    const tippyOptions: Props = {
      hideOnClick: false,
      arrow: false,
      // #if MONITOR_APP !== 'trace'
      zIndex: props.zIndex,
      // #endif
      appendTo: document.body,
      maxWidth: 900,

      onShow: () => {
        isOpened.value = true;
        refContentObject.value?.resetUnionList();
      },
      onHide: () => {
        isOpened.value = false;

        if (props.activeTab === 'union') {
          emit('value-change', unionListValue.length ? unionListValue : props.indexSetValue, 'union');
        }
      },
    } as any;

    const rootStyle = computed(() => {
      return {
        '--indexset-root-h': `${props.height}px`,
        '--indexset-root-w': /^\d+\.?\d*$/.test(`${props.width}`) ? `${props.width}px` : props.width,
        '--indexset-root-max-w': `${props.maxWidth}px`,
        '--indexset-root-min-w': `${props.minWidth}px`,
      };
    });

    const selectedValues = computed(() =>
      props.indexSetValue
        .map(v => props.indexSetList.find((i: any) => `${i.index_set_id}` === `${v}`))
        .filter(c => c !== undefined),
    );

    const handleTabChange = (type: string) => {
      emit('type-change', type);
    };

    /**
     * 处理索引选中事件
     * @param value
     * @returns
     */
    const handleValueChange = (value: any, type: 'single' | 'union', id: number | string) => {
      // 如果是单选操作直接抛出事件
      if (['single', 'history', 'favorite'].includes(props.activeTab)) {
        emit('value-change', value, type, id);
        refRootElement.value?.hide();
        return;
      }

      // 如果是联合索引操作，暂时缓存选中结果
      // 在弹出关闭时抛出事件，触发外部事件监听
      if (props.activeTab === 'union') {
        unionListValue = value;
      }
    };

    const handleKeyDown = event => {
      // 检查是否按下了 ⌘/⌘/Ctrl + O 或 Cmd + O
      const isCtrlO = event.ctrlKey && event.key === 'o';
      const isCmdO = event.metaKey && event.key === 'o';

      if (isCtrlO || isCmdO) {
        event.preventDefault();
        if (isOpened.value) {
          refRootElement.value?.hide();
          return;
        }

        refRootElement.value?.show();
      }
    };

    onMounted(() => {
      document.addEventListener('keydown', handleKeyDown);
    });

    onBeforeUnmount(() => {
      document.removeEventListener('keydown', handleKeyDown);
      refRootElement.value?.hide();
    });

    const contentStyleVar = computed(() => {
      return {
        '--index-set-ctx-width': `${props.contentWidth}px`,
      };
    });

    const handleAuthRequest = item => {
      emit('auth-request', item);
      refRootElement.value?.hide();
    };

    return () => {
      return (
        <BklogPopover
          ref={refRootElement}
          style={rootStyle.value}
          class={[
            'bklog-v3-indexset-container',
            { 'is-opened': isOpened.value, 'is-multi': props.indexSetValue.length > 1 },
          ]}
          data-shortcut-key={shortcutKey}
          options={tippyOptions}
          {...{
            scopedSlots: {
              content: () => (
                <Content
                  ref={refContentObject}
                  style={contentStyleVar.value}
                  activeId={props.activeTab}
                  list={props.indexSetList}
                  spaceUid={props.spaceUid}
                  type={props.activeType}
                  value={props.indexSetValue}
                  zIndex={props.zIndex}
                  on-auth-request={handleAuthRequest}
                  on-type-change={handleTabChange}
                  on-value-change={handleValueChange}
                />
              ),
            },
          }}
        >
          <EllipsisTagList
            class='indexset-value-list'
            activeEllipsisCount={selectedValues.value.length > 1}
            list={selectedValues.value}
            placement='right'
            {...{
              scopedSlots: {
                item: v => (
                  <span class='index-set-value-item'>
                    <span class='index-set-name'>{v.index_set_name}</span>
                    <span class='index-set-lighten-name'>{v.lightenName}</span>
                  </span>
                ),
              },
            }}
          />
          <span class='bklog-icon bklog-arrow-down-filled-2' />
        </BklogPopover>
      );
    };
  },
});
