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

import { defineComponent, computed } from 'vue';

export default defineComponent({
  name: 'ListBox',
  props: {
    icon: {
      type: String,
      required: true,
    },
    title: {
      type: String,
      default: '',
    },
    mark: {
      type: Boolean,
      default: false,
    },
    list: {
      type: [String, Array],
      default: '',
    },
  },
  setup(props) {
    // 计算列表数据
    const listData = computed(() => {
      if (props.list && typeof props.list === 'string') {
        return [props.list];
      }
      if (Array.isArray(props.list)) {
        return props.list;
      }
      return [];
    });

    // 判断是否显示组件
    const shouldShow = computed(() => {
      return listData.value.length || (props.mark && props.title);
    });

    return () =>
      shouldShow.value && (
        <div class='list-box-container'>
          <div class={['list-title', props.mark && 'mark']}>
            <span class={props.icon} />
            <h2 class='text'>{props.title}</h2>
          </div>
          <ul class='list-box'>
            {listData.value.map((item, index) => (
              <li
                key={`${index}-${item}`}
                class='list-item'
              >
                {item}
              </li>
            ))}
          </ul>
        </div>
      );
  },
});
