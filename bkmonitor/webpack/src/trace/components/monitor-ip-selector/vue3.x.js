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
import { h, onBeforeUnmount, onMounted, onUpdated, ref } from 'vue';

import { Component, merge, Vue2 } from '@blueking/ip-selector/dist/vue2.6.x.esm';

Component.props.mode.default = 'section';

export default function (options) {
  merge(options);

  return {
    name: 'bk-ip-selector',
    props: Object.assign({}, Component.props),
    emits: [...Component.emits],
    setup(props, context) {
      const rootRef = ref();

      let app = new Vue2({
        render: h => {
          return h(Component, {
            ref: 'componentRef',
            props,
          });
        },
      });
      function isPrimitive(value) {
        const type = typeof value;
        return value === null || (type !== 'object' && type !== 'function');
      }
      onMounted(() => {
        app.$mount();
        rootRef.value.appendChild(app.$el);
        for (const eventName of Component.emits) {
          app.$refs.componentRef.$on(eventName, (...agrs) => {
            context.emit(eventName, ...agrs);
          });
        }
        onUpdated(() => {
          for (const [key, value] of Object.entries(props)) {
            if (!isPrimitive(value)) continue;
            app.$refs.componentRef[key] = value;
          }
          app.$refs.componentRef.$forceUpdate();
        });
      });

      onBeforeUnmount(() => {
        app.$el.parentNode.removeChild(app.$el);
        app.$destroy();
        app = null;
      });
      return {
        rootRef,
        app,
      };
    },
    render() {
      return h('div', {
        role: 'bk-ip-selector',
        ref: 'rootRef',
      });
    },
  };
}
