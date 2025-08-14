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
import { type PropType, type Ref, defineComponent, inject, ref, watch } from 'vue';

import './failure-menu.scss';

interface ITabItem {
  label: string;
  name: string;
}

export default defineComponent({
  name: 'FailureMenu',
  props: {
    active: {
      type: String,
      default: '',
    },
    tabList: {
      type: Array as PropType<Array<ITabItem>>,
      default: () => [],
    },
    width: {
      type: String,
      default: '100%',
    },
    top: {
      type: Number,
      default: -15,
    },
  },
  emits: ['change'],
  setup(props, { emit }) {
    const activeName = ref<string>(props.active);
    const playLoading = inject<Ref<boolean>>('playLoading');
    watch(
      () => props.active,
      (val: string) => {
        activeName.value = val;
      }
    );
    const handleActive = (name: string) => {
      if (activeName.value === name) {
        return;
      }
      activeName.value = name;
      emit('change', name);
    };
    return {
      activeName,
      handleActive,
      playLoading,
    };
  },
  render() {
    return (
      <div class='failure-menu'>
        {this.playLoading && (
          <div
            style={{ width: this.$props.width, top: `${this.$props.top}px` }}
            class='loading-mask'
          />
        )}
        <ul class='detail-tab-content'>
          {this.tabList.map(item => (
            <li
              class={{ active: this.activeName === item.name }}
              onClick={this.handleActive.bind(this, item.name)}
            >
              {item.label}
            </li>
          ))}
        </ul>
      </div>
    );
  },
});
