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
import { computed, defineComponent, onMounted, ref, nextTick, onBeforeUnmount } from 'vue';

import interactjs from 'interactjs';

export default defineComponent({
  props: {
    width: {
      type: [String, Number],
      default: 120,
    },
    minWidth: {
      type: [String, Number],
      default: 'atuo',
    },
    resize: {
      type: Boolean,
      default: false,
    },
    customStyle: {
      type: Object,
      default: () => ({}),
    },
  },
  setup(props, { slots, emit }) {
    const cellStyle = computed(() => {
      if (['default', '100%'].includes(props.width as string)) {
        return {
          width: '100%',
          minWidth: `${props.minWidth}px`,
        };
      }
      return {
        width: `${props.width}px`,
        minWidth:
          typeof props.minWidth === 'number'
            ? Number(props.width) < Number(props.minWidth)
              ? `${props.width}px`
              : `${props.minWidth}px`
            : `${props.width}px`,
      };
    });

    const refRoot = ref();
    let interactjsInstance: any = null;

    const renderVNode = () => {
      return (
        <div
          ref={refRoot}
          style={{ ...cellStyle.value, ...props.customStyle }}
        >
          {slots.default?.()}
        </div>
      );
    };

    onMounted(() => {
      if (props.resize) {
        nextTick(() => {
          const container = refRoot.value?.closest('.bklog-result-container') as HTMLElement;
          const guideLineElement = container?.querySelector('.resize-guide-line') as HTMLElement;

          const setGuidLeft = event => {
            const client = event.client;
            const containerRect = container?.getBoundingClientRect();

            if (guideLineElement) {
              guideLineElement.style.left = `${client.x - containerRect.x}px`;
            }
          };

          interactjsInstance = interactjs(refRoot.value);
          interactjsInstance?.resizable({
            edges: { top: false, left: false, bottom: false, right: true },
            listeners: {
              start(event) {
                if (guideLineElement) {
                  // Show the guide line when resizing starts
                  guideLineElement.style.display = 'block';
                }

                document.body.classList.add('no-user-select');
                setGuidLeft(event);
              },
              move(event) {
                const { x, y } = event.target.dataset;

                Object.assign(event.target.dataset, { x, y });
                if (event.rect.width > 30) {
                  setGuidLeft(event);
                }
              },
              end(event) {
                let { x, y } = event.target.dataset;
                x = (Number.parseFloat(x) || 0) + event.deltaRect.left;
                y = (Number.parseFloat(y) || 0) + event.deltaRect.top;

                Object.assign(event.target.style, {
                  width: `${event.rect.width}px`,
                  height: `${event.rect.height}px`,
                  transform: `translate(${x}px, ${y}px)`,
                });

                if (guideLineElement) {
                  // Hide the guide line when resizing ends
                  guideLineElement.style.display = 'none';
                }

                document.body.classList.remove('no-user-select');
                emit('resize-width', event.rect.width);
              },
            },
          });
        });
      }
    });

    onBeforeUnmount(() => {
      interactjsInstance?.unset();
    });

    return { renderVNode };
  },
  render() {
    return this.renderVNode();
  },
});
