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

import tippy from 'tippy.js';
import { useI18n } from 'vue-i18n';

import useUserConfig from '../../hooks/useUserConfig';
import ResidentSettingTransfer from './resident-setting-transfer';
import SettingKvInput from './setting-kv-input';
import SettingKvSelector from './setting-kv-selector';
import TimeConsuming from './time-consuming';
import {
  type IFieldItem,
  type IFilterField,
  type IWhereItem,
  type TGetValueFn,
  ECondition,
  EMethod,
  RESIDENT_SETTING_EMITS,
  RESIDENT_SETTING_PROPS,
} from './typing';
import { defaultWhereItem, DURATION_KEYS, EXISTS_KEYS, INPUT_TAG_KEYS } from './utils';

import './resident-setting.scss';
import 'tippy.js/dist/tippy.css';

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
    const { t } = useI18n();

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

    watch(
      () => props.residentSettingOnlyId,
      async val => {
        const fields: IResidentSetting[] = [];
        userConfigLoading.value = true;
        const defaultConfig = (await handleGetUserConfig<string[]>(val)) || [];
        userConfigLoading.value = false;
        const valueNameMap = getValueNameMap();
        const pushFields = (config: string[]) => {
          for (const key of config) {
            if (fieldNameMap.value[key]) {
              fields.push({
                field: fieldNameMap.value[key],
                value: defaultWhereItem(
                  valueNameMap[key] || {
                    key: fieldNameMap.value[key]?.name,
                    value: valueNameMap[key]?.value || [],
                    method: fieldNameMap.value[key]?.supported_operations?.[0]?.value || EMethod.eq,
                  }
                ),
              });
            }
          }
        };
        if (!props.isDefaultSetting && props.value?.length) {
          for (const where of props.value) {
            if (fieldNameMap.value[where.key]) {
              fields.push({
                field: fieldNameMap.value[where.key],
                value: where,
              });
            }
          }
        } else {
          pushFields(defaultConfig.length ? defaultConfig : props.defaultResidentSetting);
        }
        localValue.value = fields;
      },
      { immediate: true }
    );

    watch(
      () => props.value,
      () => {
        if (!props.value?.length) {
          localValue.value = localValue.value.map(item => ({
            ...item,
            value: {
              ...item.value,
              value: [],
            },
          }));
        }
      }
    );

    function getValueNameMap() {
      return props.value.reduce((pre, cur) => {
        pre[cur.key] = cur;
        return pre;
      }, {});
    }

    async function handleShowSelect(event: MouseEvent) {
      if (popoverInstance.value) {
        destroyPopoverInstance();
        return;
      }
      popoverInstance.value = tippy(event.target as any, {
        content: selectorRef.value,
        trigger: 'click',
        placement: 'bottom-start',
        theme: 'light common-monitor padding-0',
        arrow: false,
        appendTo: document.body,
        zIndex: 998,
        maxWidth: 638,
        offset: [0, 4],
        interactive: true,
        onHidden: () => {
          destroyPopoverInstance();
        },
      });
      popoverInstance.value?.show();
      showTransfer.value = true;
    }

    function destroyPopoverInstance() {
      popoverInstance.value?.hide();
      popoverInstance.value?.destroy();
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
      const valueNameMap = getValueNameMap();
      localValue.value = fields.map(item => ({
        field: item,
        value: defaultWhereItem(
          valueNameMap[item.name] || {
            key: item.name,
            value: [],
            method: fieldNameMap.value[item.name]?.supported_operations?.[0]?.value || EMethod.eq,
          }
        ),
      }));
      handleChange();
      destroyPopoverInstance();
      handleSetUserConfig(JSON.stringify(fields.map(item => item.name)));
    }
    function handleValueChange(value: IWhereItem, index: number) {
      localValue.value[index].value = value;
      handleChange();
    }
    // function handleTimeConsumingValueChange(value: number[], index: number) {
    //   const field = localValue.value[index].field;
    //   localValue.value[index].value = {
    //     key: field.name,
    //     value: value as any[],
    //     method: 'between',
    //   };
    //   handleChange();
    // }

    function handleChange() {
      emit(
        'change',
        localValue.value
          .filter(item => {
            return EXISTS_KEYS.includes(item.value.method) ? item?.value?.key : item?.value?.value?.length;
          })
          .map(item => item.value)
      );
    }
    function getFieldInfo(item: IFilterField): IFieldItem {
      return {
        field: item.name,
        alias: item.alias,
        isEnableOptions: !!item?.isEnableOptions,
        methods:
          item?.supported_operations?.map(o => ({
            id: o.value,
            name: o.alias,
          })) || [],
        type: item.type,
      };
    }
    /**
     * 获取通配符操作符
     * @param field - 字段名称
     * @param isSearch - 是否为搜索模式,默认为 false
     * @returns 返回操作符字符串
     * @description 根据字段名称和搜索模式获取对应的通配符操作符:
     * - 非搜索模式下返回字段对应的 method 值或默认值 'equal'
     * - 搜索模式下根据 supported_operations 匹配 wildcard_operator,若无匹配则返回第一个支持的操作符或默认值 'equal'
     */
    function getWildcardOperator(field: string, isSearch = false) {
      let operator = '';
      const tempLocalValue = localValue.value.find(item => item.field.name === field);
      if (!tempLocalValue) {
        return 'equal';
      }
      if (!isSearch) {
        operator = tempLocalValue.value?.method || 'equal';
        return operator;
      }
      for (const m of tempLocalValue.field?.supported_operations || []) {
        if (tempLocalValue.value?.method === m.value) {
          operator = m?.wildcard_operator;
          break;
        }
      }
      if (!operator) {
        operator = tempLocalValue.field?.supported_operations?.[0]?.wildcard_operator || 'equal';
      }
      return operator;
    }
    /**
     * 代理获取值的函数，用于处理搜索查询并返回结果
     * @param params 查询参数对象
     * @param params.search 搜索关键字
     * @param params.limit 限制返回结果数量
     * @param params.field 查询字段名称
     * @returns 返回Promise，解析为查询结果数据
     * @description 该函数将搜索参数转换为查询条件，通过props.getValueFn执行查询
     * 支持通配符搜索，并在发生错误时返回空结果集
     */
    function getValueFnProxy(params: { field: string; limit: number; search: string }): any | TGetValueFn {
      return new Promise((resolve, _reject) => {
        props
          .getValueFn({
            where: params.search
              ? [
                  {
                    key: params.field,
                    method: getWildcardOperator(params.field, !!params.search),
                    value: [params.search],
                    condition: ECondition.and,
                    options: {
                      is_wildcard: true,
                    },
                  },
                ]
              : [],
            fields: [params.field],
            limit: params.limit,
            isInit__: params?.isInit__ || false,
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
      // handleTimeConsumingValueChange,
      handleCancel,
      handleConfirm,
      t,
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
          <span class='setting-text'>{this.t('设置筛选')}</span>
        </span>
        <div class='right-content'>
          {this.localValue.length ? (
            this.localValue.map((item, index) => {
              if (DURATION_KEYS.includes(item.field.name)) {
                return (
                  <TimeConsuming
                    key={item.field.name}
                    class='mb-4 mr-4'
                    fieldInfo={this.getFieldInfo(item.field)}
                    value={item.value}
                    onChange={v => this.handleValueChange(v, index)}
                  />
                );
              }
              if (INPUT_TAG_KEYS.includes(item.field.name)) {
                return (
                  <SettingKvInput
                    key={item.field.name}
                    class='mb-4 mr-4'
                    fieldInfo={this.getFieldInfo(item.field)}
                    value={item.value}
                    onChange={v => this.handleValueChange(v, index)}
                  />
                );
              }
              return (
                <SettingKvSelector
                  key={item.field.name}
                  class='mb-4 mr-4'
                  fieldInfo={this.getFieldInfo(item.field)}
                  getValueFn={this.getValueFnProxy}
                  value={item.value}
                  onChange={v => this.handleValueChange(v, index)}
                />
              );
            })
          ) : (
            <span class='placeholder-text'>{`（${this.t('暂未设置常驻筛选，请点击左侧设置按钮')}）`}</span>
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
