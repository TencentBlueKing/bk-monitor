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

import { type PropType, defineComponent, onMounted, onUnmounted, ref } from 'vue';

import { Loading } from 'bkui-vue';

import './simple-list.scss';

interface IDataItem {
  duration: string;
  id: string;
  isError: boolean;
  startTime: string;
}

const TRACE_TABLE_ROW_HEIGHT = 60; // trace 表格行高

export default defineComponent({
  name: 'TraceSimpleList',
  props: {
    data: {
      type: Array as PropType<IDataItem[]>,
      defaut: () => [],
    },
    selectedId: {
      type: String,
      default: '',
    },
    loading: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['change', 'loadMore'],
  setup(props, { emit }) {
    const listRef = ref<HTMLDivElement>();
    const isInitialScroll = ref(true);

    onMounted(() => {
      setTimeout(() => {
        const index = props.data.findIndex(item => item.id === props.selectedId);
        listRef.value.scrollTo({
          top: index * TRACE_TABLE_ROW_HEIGHT,
        });
        listRef.value?.addEventListener('scroll', onScroll);
      });
    });

    onUnmounted(() => {
      listRef.value?.removeEventListener('scroll', onScroll);
    });

    function onScroll() {
      if (isInitialScroll.value) {
        isInitialScroll.value = false;
        return;
      }

      const { scrollTop, scrollHeight, clientHeight } = listRef.value;
      if (scrollTop + clientHeight >= scrollHeight) {
        emit('loadMore');
      }
    }

    return {
      listRef,
    };
  },
  render() {
    return (
      <div class='trace-simple-list'>
        <div class='head'>Trace ID</div>
        <ul ref='listRef'>
          {this.data.map((item, index) => (
            <li
              class={`${this.selectedId === item.id ? 'selected' : ''}`}
              onClick={() => this.$emit('change', item.id, index)}
            >
              <div class='trace-id'>{item.id}</div>
              <div>
                <span class='duration'>{item.duration}</span>
                <span class='time'>{item.startTime}</span>
                {item.isError && <span class='icon-monitor icon-mind-fill' />}
              </div>
            </li>
          ))}
        </ul>
        <Loading
          class='list-loading'
          loading={this.loading}
        />
      </div>
    );
  },
});
