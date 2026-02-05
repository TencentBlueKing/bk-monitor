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

import { defineComponent, useTemplateRef } from 'vue';
import { shallowRef } from 'vue';

import { useDebounceFn } from '@vueuse/core';
import { Input } from 'bkui-vue';
import { useI18n } from 'vue-i18n';
import { useTippy } from 'vue-tippy';

import { useModuleSelect } from '../hooks/use-module-select';
import ModuleCascadeSelector from './module-cascade-selector';
import SelectorTrigger from './selector-trigger';

import type { IModuleListItem } from '../typing/typing';

import './alarm-module-selector.scss';

export default defineComponent({
  name: 'AlarmModuleSelector',
  setup() {
    const { t } = useI18n();
    const wrapRef = useTemplateRef('wrapRef');

    let popInstance = null;
    const showPop = shallowRef(false);

    const { searchValue, searchModuleList } = useModuleSelect();
    const curOption = shallowRef<IModuleListItem>(null);

    const handleDebounceSearchChange = useDebounceFn(handleSearchChange, 300);

    function handleClick(event: MouseEvent) {
      handleShowPop(event.currentTarget);
    }

    function handleShowPop(target) {
      searchValue.value = '';
      popInstance = useTippy(target, {
        content: () => wrapRef.value,
        trigger: 'click',
        interactive: true,
        theme: 'light common-monitor',
        arrow: false,
        placement: 'bottom-start',
        appendTo: () => document.body,
        onHidden: () => {
          handlePopHidden();
        },
        hideOnClick: true,
        offset: [0, 5],
        maxWidth: 'none',
      });
      popInstance?.show?.();
      showPop.value = true;
    }
    function handlePopHidden() {
      popInstance?.hide();
      popInstance?.destroy?.();
      showPop.value = false;
    }

    function handleSearchChange(val: string) {
      searchValue.value = val;
    }

    function handleSelectModule(item: IModuleListItem) {
      curOption.value = item;
      handlePopHidden();
    }

    return {
      searchValue,
      searchModuleList,
      curOption,
      showPop,
      handleDebounceSearchChange,
      handleClick,
      handleSelectModule,
      t,
    };
  },
  render() {
    return (
      <>
        <SelectorTrigger
          active={this.showPop}
          click={this.handleClick}
          defaultWidth={102}
          hasRightSplit={true}
        >
          {{
            top: () => <span>{this.t('告警模块')}</span>,
            bottom: () => <span>{this.curOption?.name || this.t('全部')}</span>,
          }}
        </SelectorTrigger>
        <div style={{ display: 'none' }}>
          <div
            ref='wrapRef'
            class='alarm-module-selector-popover-content'
          >
            <div class='all-option'>
              <span class='icon-monitor icon-All' />
              <span>{this.t('全部')}</span>
            </div>
            <div class='split-line' />
            <div class='search-input'>
              <Input
                behavior={'simplicity'}
                modelValue={this.searchValue}
                placeholder={this.t('请输入关键字或标签')}
                onInput={this.handleDebounceSearchChange}
              >
                {{
                  prefix: () => <span class='icon-monitor icon-mc-search' />,
                }}
              </Input>
            </div>
            <div class='list-wrap'>
              {this.searchModuleList.map(module => (
                <div
                  key={module.id}
                  class='list-wrap-item'
                >
                  <div class='list-wrap-item-father'>{module.name}</div>
                  {module.children.map(item => (
                    <div
                      key={item.id}
                      class='list-wrap-item-child'
                      onClick={() => this.handleSelectModule(item)}
                    >
                      {item.name}
                    </div>
                  ))}
                </div>
              ))}
            </div>
          </div>
        </div>
        <ModuleCascadeSelector cascades={this.curOption?.cascade || []} />
      </>
    );
  },
});
