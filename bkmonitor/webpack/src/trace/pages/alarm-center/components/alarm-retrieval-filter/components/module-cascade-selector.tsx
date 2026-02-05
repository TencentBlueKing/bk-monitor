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

import { defineComponent, shallowRef, watch } from 'vue';
import { triggerRef } from 'vue';
import type { PropType } from 'vue';

import { Select } from 'bkui-vue';

import spinner from '../../../../../static/img/spinner.svg';
import { useCascadeSelect } from '../hooks/use-cascade-select';
import SelectorTrigger from './selector-trigger';

import type { ICascadeData, ICascadeItem, ICascadeValue } from '../typing/typing';

import './module-cascade-selector.scss';

export default defineComponent({
  name: 'ModuleCascadeSelector',
  props: {
    value: {
      type: Array as PropType<ICascadeValue[]>,
      default: () => [],
    },
    cascades: {
      type: Array as PropType<ICascadeItem[]>,
      default: () => [],
    },
  },
  setup(props) {
    const localCascades = shallowRef<ICascadeData[]>([]);

    const { init, handleScrollEnd, handleSearch, handleOpen } = useCascadeSelect(localCascades);

    init(props.cascades, props.value);
    watch([() => props.value, () => props.cascades], () => {
      init(props.cascades, props.value);
    });

    function handleChange(item: ICascadeData, val) {
      for (const l of localCascades.value) {
        if (l.id === item.id) {
          l.value = val;
        }
      }
      triggerRef(localCascades);
    }

    return {
      localCascades,
      handleChange,
      handleOpen,
      handleSearch,
      handleScrollEnd,
    };
  },
  render() {
    return (
      <>
        {this.localCascades.map(item => (
          <Select
            key={item.id}
            class='module-selector-module-cascade-selector'
            customContent={item.loading}
            filterable={true}
            modelValue={item.value}
            multiple={true}
            popoverMinWidth={314}
            remoteMethod={val => this.handleSearch(item, val)}
            scrollLoading={item.scrollLoading}
            showAll={true}
            onChange={val => this.handleChange(item, val)}
            onScroll-end={() => this.handleScrollEnd(item)}
            onToggle={val => this.handleOpen(item, val)}
          >
            {{
              trigger: ({ selected }) => (
                <SelectorTrigger
                  active={item.isOpen}
                  defaultWidth={150}
                >
                  {{
                    top: () => <span>{item.name}</span>,
                    bottom: () => <span>{selected.map(s => s.value).join(', ')}</span>,
                  }}
                </SelectorTrigger>
              ),
              default: () =>
                !item.loading ? (
                  item.options.map(option => {
                    return (
                      <Select.Option
                        id={option.id}
                        key={option.id}
                        name={option.name}
                      />
                    );
                  })
                ) : (
                  <div style={'height: 105px; display: flex; align-items: center; justify-content: center;'}>
                    <img
                      style={'height: 24px;width: 24px;'}
                      alt='loading'
                      src={spinner}
                    />
                  </div>
                ),
            }}
          </Select>
        ))}
      </>
    );
  },
});
