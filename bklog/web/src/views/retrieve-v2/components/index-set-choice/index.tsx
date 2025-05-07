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

import { computed, defineComponent, PropType, Ref, ref } from 'vue';
import BklogPopover from '../../../../components/bklog-popover';
import { getOsCommandLabel } from '../../../../common/util';
import { Props } from 'tippy.js';
import Content from './content';

import './index.scss';
import { IndexSetTabList, IndexSetType } from './use-choice';

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

    // 收藏列表
    favoriteList: {
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
  emits: ['type-change', 'value-change'],
  setup(props, { emit }) {
    const isOpened = ref(false);
    const refRootElement: Ref<any | null> = ref(null);
    const shortcutKey = `${getOsCommandLabel()}+O`;

    let unionListValue = [];

    const tippyOptions: Props = {
      hideOnClick: false,
      arrow: false,
      zIndex: props.zIndex,
      appendTo: document.body,

      onShow: () => {
        isOpened.value = true;
      },
      onHide: () => {
        isOpened.value = false;

        if (props.activeType === 'union') {
          emit('value-change', unionListValue);
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
    const handleValueChange = (value: any, type: 'single' | 'union', id: string | number) => {
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

    return () => {
      return (
        <BklogPopover
          class={[
            'bklog-v3-indexset-container',
            { 'is-opened': isOpened.value, 'is-multi': props.indexSetValue.length > 1 },
          ]}
          data-shortcut-key={shortcutKey}
          style={rootStyle.value}
          ref={refRootElement}
          options={tippyOptions}
          {...{
            scopedSlots: {
              content: () => (
                <Content
                  list={props.indexSetList}
                  type={props.activeType}
                  value={props.indexSetValue}
                  spaceUid={props.spaceUid}
                  activeId={props.activeTab}
                  zIndex={props.zIndex}
                  on-type-change={handleTabChange}
                  on-value-change={handleValueChange}
                ></Content>
              ),
            },
          }}
        >
          <bdi class='indexset-value-list'>
            {selectedValues.value.map((v: any) => (
              <span class='index-set-value-item'>
                <span class='index-set-name'>{v.index_set_name}</span>
                <span class='index-set-lighten-name'>{v.lightenName}</span>
              </span>
            ))}
          </bdi>
          <span class='bklog-icon bklog-arrow-down-filled-2'></span>
        </BklogPopover>
      );
    };
  },
});
