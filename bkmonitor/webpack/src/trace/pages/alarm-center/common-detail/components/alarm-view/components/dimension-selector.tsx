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

import { type PropType, computed, defineComponent, shallowRef } from 'vue';

import { Checkbox, Input } from 'bkui-vue';
import EmptyStatus from 'trace/components/empty-status/empty-status';
import OverflowTips from 'trace/directive/overflow-tips';
import { useI18n } from 'vue-i18n';

import './dimension-selector.scss';

export default defineComponent({
  name: 'DimensionSelector',
  props: {
    dimensions: {
      type: Array as PropType<{ id: string; name: string }[]>,
      default: () => [],
    },
    isMulti: {
      type: Boolean,
      default: false,
    },
    selected: {
      type: Array as PropType<string[]>,
      default: () => [],
    },
    loading: {
      type: Boolean,
      default: false,
    },
  },
  emits: {
    multiChange: (_val: boolean) => true,
    change: (_val: string[]) => true,
  },
  directive: {
    OverflowTips,
  },
  setup(props, { emit }) {
    const { t } = useI18n();

    const searchValue = shallowRef('');

    const filteredDimensions = computed(() => {
      if (!searchValue.value) {
        return props.dimensions;
      }
      return props.dimensions.filter(
        item => item.name.includes(searchValue.value) || item.id.includes(searchValue.value)
      );
    });

    const handleMultiChange = (val: boolean) => {
      emit('multiChange', val);
    };

    const handleSelect = (item: { id: string; name: string }) => {
      emit('change', [item.id]);
    };

    const handleCheck = (val: boolean, item: { id: string; name: string }) => {
      if (val) {
        emit('change', Array.from(new Set([...props.selected, item.id])));
      } else {
        emit(
          'change',
          props.selected.filter(id => id !== item.id)
        );
      }
    };

    const handleSearch = (val: string) => {
      searchValue.value = val;
    };

    return {
      searchValue,
      filteredDimensions,
      t,
      handleMultiChange,
      handleSelect,
      handleCheck,
      handleSearch,
    };
  },
  render() {
    return (
      <div class='dimension-analysis-dimension-selector'>
        <div class='header-title'>
          <span class='title'>{this.t('维度分析')}</span>
          <Checkbox
            modelValue={this.isMulti}
            onChange={this.handleMultiChange}
          >
            {this.t('多选')}
          </Checkbox>
        </div>
        <div class='search-wrap'>
          <Input
            clearable={true}
            modelValue={this.searchValue}
            placeholder={`${this.t('搜索')} ${this.t('维度')}`}
            type='search'
            onUpdate:modelValue={this.handleSearch}
          />
        </div>
        <div class='dimension-list'>
          {this.loading ? (
            new Array(8).fill(null).map((_, index) => {
              return (
                <div
                  key={index}
                  style={{ padding: '0 8px' }}
                  class='dimension-list-item'
                >
                  <div
                    style={{ height: '22px' }}
                    class='skeleton-element'
                  />
                </div>
              );
            })
          ) : this.filteredDimensions.length ? (
            this.filteredDimensions.map((item, index) => (
              <div
                key={index}
                class={[
                  'dimension-list-item',
                  this.isMulti ? 'multi-type' : 'single-type',
                  {
                    active: this.selected.includes(item.id),
                  },
                ]}
                onClick={() => {
                  if (!this.isMulti) {
                    this.handleSelect(item);
                  }
                }}
              >
                {this.isMulti ? (
                  <>
                    <Checkbox
                      modelValue={this.selected.includes(item.id)}
                      onChange={v => this.handleCheck(v, item)}
                    >
                      <span v-overflow-tips>{item.name}</span>
                    </Checkbox>
                    {/* {index > 5 && (
                    <span
                      class='suspicious-tag'
                      v-bk-tooltips={{
                        content: <div>可疑可疑</div>,
                      }}
                    >
                      <span>{this.t('可疑')}</span>
                    </span>
                  )} */}
                  </>
                ) : (
                  <>
                    <span
                      class='item-label'
                      v-overflow-tips
                    >
                      {item.name}
                    </span>
                    {/* {index > 5 && (
                    <span
                      class='suspicious-tag'
                      v-bk-tooltips={{
                        content: <div>可疑可疑</div>,
                      }}
                    >
                      <span>{this.t('可疑')}</span>
                    </span>
                  )} */}
                  </>
                )}
              </div>
            ))
          ) : (
            <EmptyStatus
              type={this.searchValue ? 'search-empty' : 'empty'}
              onOperation={val => {
                if (val === 'clear-filter') {
                  this.handleSearch('');
                }
              }}
            />
          )}
        </div>
      </div>
    );
  },
});
