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

import { defineComponent, getCurrentInstance, inject, type Ref, ref } from 'vue';
import { shallowRef } from 'vue';
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';

import { Select } from 'bkui-vue';
import dayjs from 'dayjs';

import { handleTransformToTimestamp } from '../../../components/time-range/utils';
import { VariablesService } from '../../../utils/index';

import './filter-var-tag-input.scss';

export default defineComponent({
  name: 'FilterVarTagInput',
  props: {
    panel: { type: Object, default: () => null },
    multiple: { type: Boolean, default: false },
  },
  emits: ['change'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const currentInstance = getCurrentInstance();
    const startTime = inject<Ref>('startTime') || ref('');
    const endTime = inject<Ref>('endTime') || ref('');
    const startTimeMinusOneHour = dayjs
      .tz(startTime.value || undefined)
      .subtract(1, 'hour')
      .format('YYYY-MM-DD HH:mm:ss');
    const endTimeMinusOneHour = dayjs
      .tz(endTime.value || undefined)
      .add(1, 'hour')
      .format('YYYY-MM-DD HH:mm:ss');
    const timeRange = ref([startTimeMinusOneHour, endTimeMinusOneHour]);

    const localOptions = shallowRef([]);
    const localValue = ref([]);

    const localValueCheckedOptions = computed(() => {
      if (props.multiple) {
        const arr = [];
        for (const value of localValue.value) {
          const item = localOptions.value.find(item => item.id === value);
          if (item) {
            arr.push(item);
          } else {
            arr.push({ id: value, name: value });
          }
        }
        return arr;
      }
      return localOptions.value.filter(item => localValue.value === item.id);
    });
    const localCheckedFilterDict = computed(() => {
      const filterDict = {};
      props.panel.fieldsSort.reduce((total, item) => {
        const [itemKey, filterKey] = item;
        const value = props.multiple
          ? localValueCheckedOptions.value.map(opt => opt[itemKey])
          : (localValueCheckedOptions.value[0]?.[itemKey] ?? localValue.value);
        total[filterKey] = value;
        return total;
      }, filterDict);
      return filterDict;
    });

    init();

    function init() {
      handleGetOptionsList();
    }

    async function handleGetOptionsList() {
      const [startTime, endTime] = handleTransformToTimestamp(timeRange.value);
      const variablesService = new VariablesService({
        start_time: startTime,
        end_time: endTime,
      });
      const promiseList = props.panel?.targets.map(item =>
        currentInstance?.appContext.config.globalProperties?.$api[item.apiModule]
          [item.apiFunc]({
            ...variablesService.transformVariables(item.data),
            start_time: startTime,
            end_time: endTime,
          })
          .then(res => res?.data || res || [])
          .catch(err => {
            console.error(err);
            return [];
          })
      );
      const res = await Promise.all(promiseList).catch(err => {
        console.error(err);
        return [];
      });
      localOptions.value = res
        .reduce((total, list) => total.concat(list), [])
        .map(item => {
          const id = props.panel.handleCreateItemId(item);
          return {
            ...item,
            id,
            name: item.name || item.ip || item.id,
          };
        });
    }

    // function handlePaste(v) {
    //   if (props.multiple) {
    //     const SYMBOL = ';';
    //     /** 支持 空格 | 换行 | 逗号 | 分号 分割的字符串 */
    //     const valList = `${v}`.replace(/(\s+)|([,;])/g, SYMBOL)?.split(SYMBOL);
    //     const ret = [];
    //     for (const val of valList) {
    //       !localValue.value.some(v => v === val) && val !== '' && localValue.value.push(val);
    //       if (!props.list?.some(item => item.id === val)) {
    //         ret.push({
    //           id: val,
    //           name: val,
    //         });
    //       }
    //     }
    //     setTimeout(() => handleChange(localValue.value), 50);
    //     return ret;
    //   }
    //   localValue.value = [v];
    //   setTimeout(() => handleChange(localValue.value), 50);
    //   return [{ id: v, name: v }];
    // }

    function handleSelectChange(v) {
      if (props.multiple) {
        emit('change', v);
      } else {
        emit('change', v?.[0] || '');
      }
      handleChange();
    }
    function handleChange() {
      emit('change', localCheckedFilterDict.value);
    }

    return {
      localOptions,
      localValue,
      t,
      // handlePaste,
      handleSelectChange,
    };
  },
  render() {
    return (
      <span class='dashboard-panel__filter-var-tag-input'>
        {this.panel?.title && (
          <span
            class='filter-var-label'
            v-bk-tooltips={{
              content: '',
              zIndex: 9999,
              boundary: document.body,
              allowHTML: false,
            }}
          >
            {this.panel.title}
          </span>
        )}
        <Select
          v-model={this.localValue}
          allowCreate={true}
          behavior={'simplicity'}
          clearable={true}
          filterable={true}
          multiple={this.multiple}
          onChange={this.handleSelectChange}
        >
          {{
            default: () => {
              return this.localOptions.map(item => (
                <Select.Option
                  id={item.id}
                  key={item.id}
                  name={item.name}
                />
              ));
            },
          }}
        </Select>
        {/* <TagInput
          v-model={this.localValue}
          allowAutoMatch={true}
          allowCreate={true}
          clearable={true}
          list={this.list}
          pasteFn={this.handlePaste}
          placeholder={this.t('输入')}
          trigger={'focus'}
        /> */}
      </span>
    );
  },
});
