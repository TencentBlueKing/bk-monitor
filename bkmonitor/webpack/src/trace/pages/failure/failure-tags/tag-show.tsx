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
import { computed, defineComponent, ref } from 'vue';

import { Tag } from 'bkui-vue';

import './tag-show.scss';

export default defineComponent({
  name: 'TagShow',
  props: {
    data: {
      type: Array,
      default: () => [],
    },
    filter: {
      type: Array,
      default: () => [],
    },
    styleName: {
      type: String,
      default: '',
    },
  },
  setup() {
    const sectionRef = ref(null);
    const calculateTagCount = computed({
      get: () => {
        const domList = sectionRef.value?.children || [];
        const maxWidth = sectionRef.value?.parentNode?.clientWidth;
        let num = 0;
        let count = -1;
        for (let i = 0; i < domList.length; i++) {
          const clientWidth = domList[i]?.clientWidth;
          num = clientWidth + num + (i + 1) * 5;
          if (num >= maxWidth) {
            count = i;
            break;
          }
        }
        return count;
      },
      set: () => {},
    });
    return { calculateTagCount, sectionRef };
  },
  render() {
    const dataLen = (this.$props.data || []).length;
    if (dataLen === 0) {
      return;
    }
    const countIndex: any = this.calculateTagCount;
    const status = dataLen > countIndex;
    const list = (this.$props.data || []).slice(0, this.calculateTagCount);
    return (
      <span class='bk-common-tag-show'>
        <span
          ref='sectionRef'
          class='item-tags'
        >
          {list.map((tag: any) => (
            <Tag ext-cls={this.$props.styleName}>{tag}</Tag>
          ))}
        </span>
        {status && <span class='top-bar-tag'>+{dataLen - countIndex}</span>}
        {/* 
        <span 
            v-bk-tooltips={{ content: props.data.slice(calculateTagCount).join(','), width: 250 }}>
        </span>} */}
      </span>
    );
  },
});
