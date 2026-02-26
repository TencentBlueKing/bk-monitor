/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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

import { type PropType, computed, defineComponent, shallowRef, watch } from 'vue';

import { Input } from 'bkui-vue';
import EmptyStatus, { type EmptyStatusOperationType } from 'trace/components/empty-status/empty-status';

import type { IIndexSet } from './typing';

import './index-set-selector-pop-simple.scss';

export default defineComponent({
  name: 'IndexSetSelectorPopSimple',
  props: {
    list: {
      type: Array as PropType<IIndexSet[]>,
      default: () => [],
    },
    id: {
      type: [Number, String] as PropType<number | string>,
      default: '',
    },
    show: {
      type: Boolean,
      default: false,
    },
  },
  emits: {
    select: (_indexSetId: number | string) => true,
  },
  setup(props, { emit }) {
    const searchValue = shallowRef('');

    const filterList = computed(() => {
      const filterValue = searchValue.value.toLocaleLowerCase();
      return props.list.filter(item => item.index_set_name.toLocaleLowerCase().includes(filterValue));
    });

    watch(
      () => props.show,
      show => {
        if (show) {
          searchValue.value = '';
        }
      }
    );

    const handleSearchValueChange = (val: string) => {
      searchValue.value = val;
    };

    const handleSelect = (indexSetId: number | string) => {
      emit('select', indexSetId);
    };

    const handleOperation = (type: EmptyStatusOperationType) => {
      if (type === 'clear-filter') {
        handleSearchValueChange('');
      }
    };

    return {
      filterList,
      searchValue,
      handleSearchValueChange,
      handleSelect,
      handleOperation,
    };
  },

  render() {
    return (
      <div class='alarm-log-index-set-selector-pop-simple'>
        <div class='search-wrap'>
          <Input
            behavior='simplicity'
            modelValue={this.searchValue}
            clearable
            onChange={this.handleSearchValueChange}
            onClear={() => {
              this.handleSearchValueChange('');
            }}
            onInput={this.handleSearchValueChange}
          >
            {{
              prefix: () => {
                return <span class='icon-monitor icon-mc-search' />;
              },
            }}
          </Input>
        </div>
        <div class='list-wrap'>
          {this.filterList.length ? (
            this.filterList.map(item => (
              <div
                key={item.index_set_id}
                class={['list-item', { active: item.index_set_id === this.id }]}
                onClick={() => this.handleSelect(item.index_set_id)}
              >
                {item.index_set_name}
              </div>
            ))
          ) : (
            <EmptyStatus
              type={this.searchValue ? 'search-empty' : 'empty'}
              onOperation={this.handleOperation}
            />
          )}
        </div>
      </div>
    );
  },
});
