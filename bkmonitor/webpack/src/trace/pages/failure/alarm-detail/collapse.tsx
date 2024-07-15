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
import { defineComponent, ref, watch } from 'vue';

import { AngleUpFill, RightShape } from 'bkui-vue/lib/icon';

// import { Transition } from 'bkui-vue';
import './collapse.scss';

export default defineComponent({
  props: {
    collapse: {
      type: Boolean,
      default: false,
    },
    id: {
      type: String,
      default: '',
    },
    title: {
      type: String,
      default: '',
    },
    num: {
      type: Number,
      default: 0,
    },
  },
  emits: ['changeCollapse'],
  setup(props, { emit }) {
    const isCollapse = ref(false);
    const handleToggleCollapse = () => {
      isCollapse.value = !isCollapse.value;
      emit('changeCollapse', { id: props.id, isCollapse: isCollapse.value });
    };

    watch(
      () => props.collapse,
      () => {
        isCollapse.value = props.collapse;
      }
    );

    return {
      isCollapse,
      handleToggleCollapse,
    };
  },
  render() {
    return (
      <div class='aiops-correlation-metrics'>
        <div class='correlation-metrics-collapse'>
          <div class={['correlation-metrics-collapse-head', 'correlation-metrics-collapse-head-show']}>
            <span
              class={['bk-icon bk-card-head-icon collapse-icon']}
              onClick={this.handleToggleCollapse}
            >
              {!this.isCollapse ? <AngleUpFill /> : <RightShape />}
            </span>
            <span
              class='correlation-metrics-title'
              onClick={this.handleToggleCollapse}
            >
              {this.title}
              <span class='num'>（{this.num}）</span>
            </span>
          </div>
          <div
            class={['correlation-metrics-collapse-content']}
            v-show={!this.isCollapse}
          >
            {(this.$slots as any)?.default?.()}
          </div>
        </div>
      </div>
    );
  },
});
