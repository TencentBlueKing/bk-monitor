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

import { computed, defineComponent, Ref, ref } from 'vue';
import BklogPopover from '../../../../components/bklog-popover';
import { getOsCommandLabel } from '../../../../common/util';
import { Props } from 'tippy.js';
import Content from './content';

import './index.scss';

export default defineComponent({
  props: {
    height: {
      type: Number,
      default: 32,
    },
    width: {
      type: Number,
      default: 400,
    },
    textDir: {
      type: String,
      default: 'ltr',
    },
    // 索引集类型：单选-single | 联合索引-union
    indexSetType: {
      type: String,
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
    // 历史记录列表
    historyList: {
      type: Array,
      default: () => [],
    },
    // 收藏列表
    favoriteList: {
      type: Array,
      default: () => [],
    },
  },
  setup(props, {}) {
    const isOpened = ref(false);
    const refRootElement: Ref<HTMLElement | null> = ref(null);
    const shortcutKey = `${getOsCommandLabel()}+O`;
    const tippyOptions: Props = {
      hideOnClick: false,
      arrow: false,
      onShow: () => {
        isOpened.value = true;
      },
      onHide: () => {
        isOpened.value = false;
      },
    } as any;

    const rootStyle = computed(() => {
      return {
        '--indexset-root-h': `${props.height}px`,
        '--indexset-root-w': `${props.width}px`,
      };
    });

    const selectedValues = computed(() =>
      props.indexSetValue.map(v => props.indexSetList.find((i: any) => i.index_set_id === v)),
    );

    return () => {
      return (
        <BklogPopover
          class={['bklog-v3-indexset-container', { 'is-opened': isOpened.value }]}
          data-shortcut-key={shortcutKey}
          style={rootStyle.value}
          ref={refRootElement}
          options={tippyOptions}
          {...{
            scopedSlots: {
              content: () => <Content indexSetList={props.indexSetList}></Content>,
            },
          }}
        >
          <div class='indexset-value-list'>
            {selectedValues.value.map((v: any) => [
              <bid class='index-set-name'>{v.index_set_name}</bid>,
              <bid class='index-set-lighten-name'>{v.lightenName}</bid>,
            ])}
          </div>
          <span class='bklog-icon bklog-arrow-down-filled-2'></span>
        </BklogPopover>
      );
    };
  },
});
