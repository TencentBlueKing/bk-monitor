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

import { computed, defineComponent, shallowRef, watch } from 'vue';

import { promiseTimeout } from '@vueuse/core';

import { type IFilterItem, KV_TAG_EMITS, KV_TAG_PROPS, NOT_TYPE_METHODS } from './typing';
import { NULL_VALUE_NAME } from './utils';

import './kv-tag.scss';

export default defineComponent({
  name: 'KvTag',
  props: KV_TAG_PROPS,
  emits: KV_TAG_EMITS,
  setup(props, { emit }) {
    const localValue = shallowRef<IFilterItem>(null);
    const hideCount = shallowRef(0);
    const isSetting = shallowRef(false);
    const groupRelation = shallowRef('OR');

    const isHide = computed(() => {
      if (typeof localValue.value?.hide === 'boolean') {
        return localValue.value.hide;
      }
      return false;
    });
    const tipContent = computed(
      () =>
        `<div style="max-width: 600px;">${props.value.key.id} ${props.value.method.name} ${props.value.value.map(v => v.id).join(' OR ')}<div>`
    );

    watch(
      () => props.value,
      val => {
        if (val && JSON.stringify(localValue.value || {}) !== JSON.stringify(val)) {
          const localValueT = structuredClone(val);
          let count = 0;
          const valueT = [];
          for (const item of val.value) {
            if (count === 3) {
              break;
            }
            count += 1;
            valueT.push({
              ...item,
              name: nameStr(item),
            });
          }
          localValue.value = {
            ...localValueT,
            value: valueT,
          };
          hideCount.value = val.value.length - 3;
          groupRelation.value = val?.options?.group_relation || 'OR';
          flickerTag(!!val?.isSetting);
        }
      },
      { immediate: true }
    );

    async function flickerTag($isSetting: boolean) {
      if ($isSetting) {
        isSetting.value = true;
        await promiseTimeout(200);
        isSetting.value = false;
        await promiseTimeout(200);
        isSetting.value = true;
        await promiseTimeout(200);
        isSetting.value = false;
      } else {
        isSetting.value = false;
      }
    }
    function handleDelete(event: MouseEvent) {
      event.stopPropagation();
      emit('delete');
    }
    function handleClickComponent(event) {
      emit('update', event);
    }
    function handleHide(event: MouseEvent) {
      event.stopPropagation();
      emit('hide');
    }

    function nameStr(item: { id: string; name: string }) {
      if (item.id === '') {
        return NULL_VALUE_NAME;
      }
      if (item.name) {
        return item?.name?.length > 20 ? `${item.name.slice(0, 20)}...` : item.name;
      }
    }

    return {
      localValue,
      tipContent,
      isSetting,
      isHide,
      hideCount,
      groupRelation,
      handleClickComponent,
      handleHide,
      handleDelete,
    };
  },
  render() {
    return this.localValue ? (
      <div
        class='vue3_retrieval-filter__kv-tag-component'
        onClick={this.handleClickComponent}
      >
        <div
          class={['retrieval-filter__kv-tag-component-wrap', { 'yellow-bg': this.isSetting }]}
          v-bk-tooltips={{
            delay: [300, 0],
            allowHTML: true,
            content: (
              <div style='max-width: 600px; word-break: break-all; word-wrap: break-word; white-space: normal'>
                {`${this.value.key.id} ${this.value.method.id} ${this.value.value.map(v => v.id).join(` ${this.groupRelation || 'OR'} `)}`}
              </div>
            ),
          }}
        >
          <div class='key-wrap'>
            <span class='key-name'>{`${this.localValue.key.name} (${this.localValue.key.id})`}</span>
            <span class={['key-method', { 'red-text': NOT_TYPE_METHODS.includes(this.localValue.method.id) }]}>
              {this.localValue.method.name}
            </span>
          </div>
          <div class={['value-wrap', { 'hide-value': this.isHide }]}>
            {this.$slots?.value ? (
              this.$slots.value()
            ) : (
              <>
                {this.localValue.value.map((item, index) => [
                  index > 0 && (
                    <span
                      key={`${index}_condition`}
                      class='value-condition'
                    >
                      {this.groupRelation}
                    </span>
                  ),
                  <span
                    key={`${index}_key`}
                    class='value-name'
                  >
                    {['string', 'number'].includes(typeof item.name) ? item.name : NULL_VALUE_NAME}
                  </span>,
                ])}
                {this.hideCount > 0 && <span class='value-condition'>{`+${this.hideCount}`}</span>}
              </>
            )}
          </div>
          <div class='btn-wrap'>
            <div
              class='hide-btn'
              onClick={this.handleHide}
            >
              {this.isHide ? (
                <span class='icon-monitor icon-mc-invisible' />
              ) : (
                <span class='icon-monitor icon-guanchazhong' />
              )}
            </div>
            <div
              class='delete-btn'
              onClick={this.handleDelete}
            >
              <span class='icon-monitor icon-mc-close-fill' />
            </div>
          </div>
        </div>
      </div>
    ) : undefined;
  },
});
