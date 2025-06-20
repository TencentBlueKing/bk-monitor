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

import { defineComponent, shallowRef, watchEffect, type PropType } from 'vue';

import { getBkUserDisplayNameInstance, getUserComponentConfig } from 'monitor-pc/common/user-display-name';

import CollapseTag from './collapse-tags';

import type { SlotReturnValue } from 'tdesign-vue-next';

export default defineComponent({
  name: 'UserDisplayNameTag',
  props: {
    data: {
      type: Array as PropType<string[]>,
      default: () => [],
    },
    /** tag 之间的水平间距（默认为 4px），不建议另外css单独设置，计算tag宽度溢出时需要使用该值进行计算 */
    tagColGap: {
      type: Number,
      default: 4,
    },
    enableEllipsis: {
      type: Boolean,
      default: true,
    },
    ellipsisTip: {
      type: Function as PropType<(ellipsisList: string[]) => SlotReturnValue>,
    },
  },
  setup(props) {
    const userDisplayNameList = shallowRef<string[]>([]);

    // 获取负责人显示名称
    watchEffect(async () => {
      const displayNameConfig = getUserComponentConfig();
      const list = props?.data || [];
      if (list.length && displayNameConfig.apiBaseUrl && displayNameConfig.tenantId) {
        const displayNames = await getBkUserDisplayNameInstance()
          // @ts-ignore
          .getMultipleUsersDisplayName(list)
          .then(v => v?.split(',') || list)
          .catch(() => list);
        userDisplayNameList.value = displayNames;
      } else {
        userDisplayNameList.value = list;
      }
    });

    return { userDisplayNameList };
  },
  render() {
    return !this.userDisplayNameList?.length ? (
      this.$slots?.tagsEmpty?.() || <span class='user-display-name-tags__empty-text'>--</span>
    ) : (
      <CollapseTag
        class='user-display-name-tags'
        data={this.userDisplayNameList}
        ellipsisTip={this.ellipsisTip}
        enableEllipsis={this.enableEllipsis}
        tagColGap={this.tagColGap}
      >
        {{
          tagDefault: this.$slots?.tagDefault ? tag => this.$slots?.tagDefault?.(tag) : null,
        }}
      </CollapseTag>
    );
  },
});
