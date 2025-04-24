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

import { computed, defineComponent, shallowRef, useTemplateRef, watch } from 'vue';

import { $bkPopover } from 'bkui-vue';

import useUserConfig from '../../hooks/useUserConfig';
import ResidentSettingTransfer from './resident-setting-transfer';
import SettingKvSelector from './setting-kv-selector';
import TimeConsuming from './time-consuming';
import {
  ECondition,
  type IFieldItem,
  type IFilterField,
  type IWhereItem,
  RESIDENT_SETTING_EMITS,
  RESIDENT_SETTING_PROPS,
  type TGetValueFn,
} from './typing';
import { defaultWhereItem, DURATION_KEYS } from './utils';

import './resident-setting.scss';

export interface IResidentSetting {
  field: IFilterField;
  value: IWhereItem;
}

export default defineComponent({
  name: 'ResidentSetting',
  props: RESIDENT_SETTING_PROPS,
  emits: RESIDENT_SETTING_EMITS,
  setup(props, { emit }) {
    const { handleGetUserConfig, handleSetUserConfig } = useUserConfig();

    const elRef = useTemplateRef<HTMLDivElement>('el');
    const selectorRef = useTemplateRef<HTMLDivElement>('selector');
    const popoverInstance = shallowRef(null);
    const localValue = shallowRef<IResidentSetting[]>([]);
    const userConfigLoading = shallowRef(false);
    const showTransfer = shallowRef(false);

    const fieldNameMap = computed(() => {
      return props.fields.reduce((pre, cur) => {
        pre[cur.name] = cur;
        return pre;
      }, {});
    });
    const valueNameMap = computed(() => {
      return props.value.reduce((pre, cur) => {
        pre[cur.key] = cur;
        return pre;
      }, {});
    });

    watch(
      () => props.residentSettingOnlyId,
      async val => {
        const fields: IResidentSetting[] = [];
        userConfigLoading.value = true;
        const defaultConfig = (await handleGetUserConfig<string[]>(val)) || [];
        userConfigLoading.value = false;
        if (!props.isDefaultSetting) {
          for (const where of props.value) {
            if (fieldNameMap.value[where.key]) {
              fields.push({
                field: fieldNameMap.value[where.key],
                value: where,
              });
            }
          }
        } else {
          for (const key of defaultConfig.length ? defaultConfig : props.defaultResidentSetting) {
            if (fieldNameMap.value[key]) {
              fields.push({
                field: fieldNameMap.value[key],
                value: defaultWhereItem(
                  fieldNameMap.value[key] || {
                    key: fieldNameMap.value[key].name,
                    value: fieldNameMap.value[key]?.value || [],
                  }
                ),
              });
            }
          }
        }
        localValue.value = fields;
      },
      { immediate: true }
    );

    async function handleShowSelect(event: MouseEvent) {
      if (popoverInstance.value) {
        destroyPopoverInstance();
        return;
      }
      popoverInstance.value = $bkPopover({
        target: event.target,
        content: selectorRef.value,
        trigger: 'click',
        placement: 'bottom-start',
        theme: 'light common-monitor padding-0',
        arrow: false,
        boundary: 'window',
        zIndex: 998,
        padding: 0,
        offset: 5,
        onHide: () => {
          destroyPopoverInstance();
        },
      });
      popoverInstance.value.install();
      setTimeout(() => {
        popoverInstance.value?.vm?.show();
      }, 100);
      showTransfer.value = true;
    }

    function destroyPopoverInstance() {
      popoverInstance.value?.hide();
      popoverInstance.value?.close();
      popoverInstance.value = null;
      showTransfer.value = false;
    }
    function handleShowSettingTransfer(event: MouseEvent) {
      event.stopPropagation();
      handleShowSelect({
        target: elRef.value,
      } as any);
    }
    function handleCancel() {
      destroyPopoverInstance();
    }
    function handleConfirm(fields: IFilterField[]) {
      localValue.value = fields.map(item => ({
        field: item,
        value: defaultWhereItem(
          valueNameMap.value[item.name] || {
            key: item.name,
            value: [],
          }
        ),
      }));
      handleChange();
      destroyPopoverInstance();
      handleSetUserConfig(JSON.stringify(fields.map(item => item.name)), props.residentSettingOnlyId);
    }
    function handleValueChange(value: IWhereItem, index: number) {
      localValue.value[index].value = value;
      handleChange();
    }
    function handleTimeConsumingValueChange(value: number[], index: number) {
      const field = localValue.value[index].field;
      localValue.value[index].value = {
        key: field.name,
        value: value as any[],
        method: 'between',
      };
      handleChange();
    }

    function handleChange() {
      emit(
        'change',
        localValue.value.map(item => item.value)
      );
    }
    function getFieldInfo(item: IFilterField): IFieldItem {
      return {
        field: item.name,
        alias: item.alias,
        isEnableOptions: !!item?.is_option_enabled,
        methods:
          item?.supported_operations?.map(o => ({
            id: o.value,
            name: o.alias,
          })) || [],
        type: item.type,
      };
    }
    function getValueFnProxy(params: { search: string; limit: number; field: string }): any | TGetValueFn {
      return new Promise((resolve, _reject) => {
        props
          .getValueFn({
            where: [
              {
                key: params.field,
                method: 'equal',
                value: [params.search || ''],
                condition: ECondition.and,
                options: {
                  is_wildcard: true,
                },
              },
            ],
            fields: [params.field],
            limit: params.limit,
          })
          .then(data => {
            resolve(data);
          })
          .catch(() => {
            resolve({
              count: 0,
              list: [],
            });
          });
      });
    }

    return {
      localValue,
      showTransfer,
      popoverInstance,
      fieldNameMap,
      handleShowSettingTransfer,
      getFieldInfo,
      getValueFnProxy,
      handleValueChange,
      handleTimeConsumingValueChange,
      handleCancel,
      handleConfirm,
    };
  },
  render() {
    return (
      <div
        ref='el'
        class={['vue3_retrieval-filter__resident-setting-component', { 'no-data': !this.localValue.length }]}
      >
        <span
          class='left-btn'
          onClick={this.handleShowSettingTransfer}
        >
          <span class='icon-monitor icon-shezhi1' />
          <span class='setting-text'>{this.$t('设置筛选')}</span>
        </span>
        <div class='right-content'>
          {this.localValue.length ? (
            this.localValue.map((item, index) =>
              DURATION_KEYS.includes(item.field.name) ? (
                <TimeConsuming
                  key={index}
                  class='mb-4 mr-4'
                  value={item.value.value as any}
                  onChange={v => this.handleTimeConsumingValueChange(v, index)}
                />
              ) : (
                <SettingKvSelector
                  key={index}
                  class='mb-4 mr-4'
                  fieldInfo={this.getFieldInfo(item.field)}
                  getValueFn={this.getValueFnProxy}
                  value={item.value}
                  onChange={v => this.handleValueChange(v, index)}
                />
              )
            )
          ) : (
            <span class='placeholder-text'>{`（${this.$t('暂未设置常驻筛选，请点击左侧设置按钮')}）`}</span>
          )}
        </div>
        <div style='display: none;'>
          <div ref='selector'>
            <ResidentSettingTransfer
              fields={this.fields}
              show={this.showTransfer}
              value={this.localValue.map(item => item.field.name)}
              onCancel={this.handleCancel}
              onConfirm={this.handleConfirm}
            />
          </div>
        </div>
      </div>
    );
  },
});
