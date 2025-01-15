<!--
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
-->
<template>
  <div class="strategy-set-input">
    <component
      :is="item.component"
      v-for="(item, index) in alarmConditionList"
      v-show="item.show"
      :key="item.type + '-' + item.compKey"
      :ref="'component-' + index"
      :list="item.list"
      v-bind="item"
      @click="handleChange(index)"
      @remove="handleItemRemove(item, index)"
      @set-hide="handleSetHide(item, index)"
      @item-select="data => handleItemSelect(data, item, index)"
      @set-add="item.addEvent && handleSetAdd($event, item, index)"
      @set-value="data => handleSetValue(data, item, index)"
    />
    <!-- <span class="input-blank"></span> -->
  </div>
</template>
<script>
import { deepClone, random } from 'monitor-common/utils/utils';
import { createNamespacedHelpers } from 'vuex';

import { CONDITION_METHOD_LIST } from '../../../../constant/constant';
import SetAdd from './set-add';
import SetInput from './set-input';

const { mapActions, mapGetters, mapMutations } = createNamespacedHelpers('strategy-config');

export default {
  name: 'StrategyConditionInput',
  components: {
    SetInput,
    SetAdd,
  },
  props: {
    dimensionList: {
      type: Array,
      default() {
        return [];
      },
    },
    conditions: {
      type: Array,
      default() {
        return [];
      },
    },
    // 系统事件无result_table_id，非必须
    resultTableId: {
      type: [String, Number],
      required: false,
    },
    metricField: {
      type: [String, Number],
      required: true,
    },
    field: {
      type: [String, Number],
      required: false,
    },
    bizId: {
      type: [String, Number],
      required: true,
    },
    typeId: {
      type: [String, Number],
      required: true,
    },
    dataTypeLabel: {
      type: String,
      required: true,
    },
    dataSourceLabel: {
      type: String,
      required: true,
    },
    // 条件列表
    methodList: {
      type: Array,
      default: () => CONDITION_METHOD_LIST, // 默认全量的method
    },
    // 日志关键字不需要过滤method
    needFilterMethod: {
      type: Boolean,
      default: true,
    },
  },
  data() {
    return {
      alarmConditionList: [],
      curActive: 0,
    };
  },
  computed: {
    ...mapGetters(['dimensionsValueMap']),
    isReadOnly() {
      return false;
      //   return this.typeId === 'uptimecheck' && this.metricField !== 'task_duration'
      //     && !(this.dataTypeLabel === 'event' && this.dataSourceLabel === 'custom')
    },
    curComp() {
      return this.alarmConditionList[this.curActive];
    },
    nextComp() {
      return this.alarmConditionList[this.curActive + 1];
    },
    preComp() {
      return this.alarmConditionList[this.curActive - 1];
    },
    isAllowCreate() {
      return true;
      // 拨测服务时候不允许自动创建tag
      //   return this.typeId !== 'uptimecheck'
    },
    getConditions() {
      // 兼容后端返回number类型,导致无法正确展示条件名称
      return this.conditions.map(item => ({
        ...item,
        value: Array.isArray(item.value) ? (item.value = item.value.map(v => `${v}`)) : `${item.value}`,
      }));
    },
  },
  async created() {
    const len = this.getConditions.length;
    const alarmList = [];
    if (len > 0) {
      this.SET_LOADING(true);
      const promiseList = this.getConditions.map(async (item, index) => {
        const list = [];
        const keyList = Object.keys(item);
        const addItem = this.getDefaultAdd();
        addItem.show = false;
        list.push(addItem);
        if (keyList.includes('condition') && index > 0) {
          const conditionItem = this.getDefaultCondition();
          conditionItem.value.id = item.condition;
          conditionItem.value.name = item.condition.toLocaleUpperCase();
          list.push(conditionItem);
        }
        const keyItem = this.getDefaultKey();
        keyItem.value.id = item.key;
        const keyItemVal = this.dimensionList.find(set => set.id === item.key);
        keyItem.value.name = keyItemVal ? keyItemVal.name : item.key;
        list.push(keyItem);
        if (this.dataTypeLabel !== 'log' && keyItem.value.id && !this.dimensionsValueMap[keyItem.value.id]) {
          const params = {
            bk_biz_id: this.bizId,
            type: 'dimension',
            params: {
              data_source_label: this.dataSourceLabel,
              data_type_label: this.dataTypeLabel,
              field: keyItem.value.id,
              metric_field: this.metricField,
              result_table_id: this.resultTableId,
              where: [],
            },
          };
          await this.getVariableValueList(params);
        }
        const dimensionRes = this.dimensionList.find(dim => dim.id === item.key);
        const methodItem = this.getDefaultMethod(dimensionRes);
        // const methodItem = this.getDefaultMethod(keyItemVal)
        const setMethod = methodItem.list.find(set => set.id === item.method);
        methodItem.value.id = item.method;
        methodItem.value.name = setMethod ? setMethod.name : item.method;
        list.push(methodItem);
        const valueItem = this.getDefaultValue();
        // valueItem.value.id = item['value'] + ''
        // valueItem.value.name = (item['value_name'] || item['value']) + ''
        const val = item.value || '';
        valueItem.value = val ? (Array.isArray(val) ? val : [val]) : [];
        valueItem.list = this.dimensionsValueMap[keyItem.value.id] || [];
        // valueItem.value.name = (item['value_name'] || item['value']) + ''
        list.push(valueItem);
        alarmList[index] = list;
      });
      await Promise.all(promiseList).catch(e => console.log(e));
      this.alarmConditionList = alarmList.reduce((pre, cur) => pre.concat(cur), []);
      this.alarmConditionList = this.alarmConditionList.map((item, index) => {
        if (item.addType && item.addType === 'character' && index > 0) {
          item.addType = 'common';
        }
        return item;
      });
      this.SET_LOADING(false);
    }
    if (!this.isReadOnly) {
      const item = this.getDefaultAdd();
      this.alarmConditionList.push(item);
      item.show = true;
    }
  },
  methods: {
    ...mapActions(['getVariableValueList']),
    ...mapMutations(['SET_LOADING']),
    handleChange(index) {
      this.curActive = index;
    },
    getDefaultKey() {
      const key = random(10);
      return {
        list: this.dimensionList,
        value: {
          id: '',
          name: '',
        },
        component: 'set-input',
        show: true,
        type: 'key',
        'is-key': true,
        compKey: key,
        readonly: this.isReadOnly,
      };
    },
    handleMethList(list, type) {
      if (!this.needFilterMethod) return list;
      // type为number时, method会多四个
      const typeIsNumberMap = [
        { id: 'gt', name: '>' },
        { id: 'gte', name: '>=' },
        { id: 'lt', name: '<' },
        { id: 'lte', name: '<=' },
      ];
      const res = deepClone(list);
      typeIsNumberMap.forEach(item => {
        if (type === 'number') {
          const findRes = list.find(set => set.id === item.id);
          if (!findRes) res.unshift(deepClone(item));
        } else if (type === 'string') {
          const index = res.findIndex(set => set.id === item.id);
          if (index > -1) res.splice(index, 1);
        }
      });
      return res;
    },
    getDefaultMethod(data) {
      let list = this.methodList;
      if (data?.type === 'number') {
        list = this.handleMethList(this.methodList, 'number');
      } else if (!data || !('type' in data) || data?.type === 'string') {
        list = this.handleMethList(this.methodList, 'string');
      }
      const key = random(10);
      return {
        list,
        value: { ...list[0] },
        width: '32',
        'list-min-width': '30',
        'is-method': true,
        component: 'set-input',
        show: true,
        type: 'method',
        compKey: key,
        readonly: this.isReadOnly,
      };
    },
    getDefaultOldValue() {
      const key = random(10);
      return {
        list: [],
        value: {
          id: '',
          name: '',
        },
        component: 'set-input',
        show: true,
        type: 'value',
        compKey: key,
        readonly: this.isReadOnly,
      };
    },
    getDefaultValue() {
      const key = random(10);
      return {
        list: [],
        value: [],
        component: 'set-input',
        show: true,
        type: 'value',
        compKey: key,
        multiple: true,
        readonly: this.isReadOnly,
        allowCreate: this.isAllowCreate,
        allowAutoMatch: this.isAllowCreate,
      };
    },
    getDefaultCondition() {
      const key = random(10);
      return {
        list: [
          {
            id: 'and',
            name: 'AND',
          },
          {
            id: 'or',
            name: 'OR',
          },
        ],
        value: {
          id: 'and',
          name: 'AND',
        },
        width: '40',
        'list-min-width': '38',
        'is-condition': true,
        component: 'set-input',
        show: true,
        type: 'condition',
        compKey: key,
        readonly: this.isReadOnly,
      };
    },
    getDefaultAdd() {
      const key = random(10);
      return {
        component: 'set-add',
        show: false,
        addEvent: true,
        type: 'add',
        compKey: key,
        addDesc: this.$t('（对数据进行筛选过滤）'),
        addType: this.alarmConditionList.length > 1 ? 'common' : 'character',
      };
    },
    handleSetAdd(e, item, index) {
      e.preventDefault();
      item.show = false;
      if (!this.alarmConditionList[index + 1]) {
        this.alarmConditionList.push(this.getDefaultKey());
      }
      this.alarmConditionList[index + 1].show = true;
      this.$nextTick().then(() => {
        this.curActive = index + 1;
        const ref = this.$refs[`component-${index + 1}`][0];
        ref.getInput().focus();
        ref.handleSetClick();
      });
    },
    async handleItemSelect(data, item, index) {
      this.curActive = index;
      if (item.value.id !== data.id || item.value.name !== data.name) {
        item.value = { ...data };
        if (item.type === 'key') {
          if (this.dataTypeLabel !== 'log' && !this.dimensionsValueMap[data.id]) {
            this.SET_LOADING(true);
            const params = {
              bk_biz_id: this.bizId,
              type: 'dimension',
              params: {
                data_source_label: this.dataSourceLabel,
                data_type_label: this.dataTypeLabel,
                field: item.value.id,
                metric_field: this.metricField,
                result_table_id: this.resultTableId,
                where: [],
              },
            };
            await this.getVariableValueList(params);
            this.SET_LOADING(false);
          }
          if (!this.nextComp) {
            if (this.preComp.type === 'add' && index > 2) {
              this.alarmConditionList.splice(index, 0, this.getDefaultCondition());
            }
            this.alarmConditionList.push(this.getDefaultMethod(data));
            this.alarmConditionList.push(this.getDefaultValue());
          }
          const appendValue = this.alarmConditionList.slice(index).find(set => set.type === 'value');
          if (this.dataTypeLabel !== 'log') {
            appendValue.value = [];
            appendValue.list = this.dimensionsValueMap[item.value.id] || [];
            // 更新对应method
            const preValueIndex = index - 2;
            const prevValue = this.alarmConditionList[preValueIndex];
            if (!(preValueIndex > 0 && prevValue?.type === 'value')) {
              // 将method恢复对应的维度默认值
              const nextComp = this.alarmConditionList[index + 1];
              const newMethod = this.getDefaultMethod(data);
              nextComp.list = newMethod.list;
              nextComp.value = newMethod.value;
              nextComp.compKey = newMethod.compKey;
              this.$emit('on-set-value', this.getValue());
            }
          }
        } else if (item.type === 'value') {
          if (!this.nextComp && !this.isReadOnly) {
            const add = this.getDefaultAdd();
            add.show = true;
            this.alarmConditionList.push(add);
          }
        }
      }
      this.$emit('on-item-select', this.getValue());
    },
    handleSetHide(item, index) {
      item.show = false;
      this.alarmConditionList[index - 1].show = true;
    },
    handleSetValue(data, item, index) {
      const { value, list } = item;
      const dataLen = data.length;
      const valueLen = value.length;
      let diffId = '';
      this.handleChange(index);
      if (dataLen === 0) {
        item.value = data;
      } else {
        if (dataLen > valueLen) {
          diffId = data.find(id => !value.some(val => val === id));
        } else {
          diffId = value.find(id => !data.some(val => val === id));
        }
        if (diffId && !list.some(item => item.id === diffId)) {
          item.list.unshift({ id: diffId, name: diffId });
        }
      }
      item.value = data;
      if (!this.nextComp && !this.isReadOnly) {
        const add = this.getDefaultAdd();
        add.show = true;
        this.alarmConditionList.push(add);
      }
      this.$emit('on-set-value', this.getValue());
    },
    handleItemRemove(item, index) {
      this.curActive = index;
      if (this.preComp) {
        const preType = this.preComp.type;
        if (preType === 'condition') {
          const apendComp = this.alarmConditionList[index + 3];
          if (apendComp && apendComp.type === 'add') {
            this.alarmConditionList.splice(index - 1, 5);
          } else {
            this.alarmConditionList.splice(index - 1, 4);
          }
          const farComp = this.alarmConditionList[index - 2];
          if (farComp && farComp.type === 'add') {
            farComp.show = true;
          }
        } else if (preType === 'add') {
          const apendComp = this.alarmConditionList[index + 3];
          if (apendComp && apendComp.type === 'add') {
            this.alarmConditionList.splice(index, 5);
            if (this.alarmConditionList.length === 1) {
              this.preComp.show = true;
            }
          } else {
            this.alarmConditionList.splice(index, 3);
            this.preComp.show = true;
          }
        }
      }

      const len = this.alarmConditionList.length;
      this.alarmConditionList = this.alarmConditionList.map((item, index) => {
        if (index > 0 && item.addType && index !== len - 1) {
          item.show = false;
        }
        return item;
      });
      this.$emit('on-remove-item', this.getValue());
    },
    getValue() {
      const ret = [];
      if (this.alarmConditionList.length) {
        let data = {};
        let valueType = 'string';
        this.alarmConditionList.forEach(item => {
          const { type } = item;
          if (['key', 'method', 'value', 'condition'].includes(type)) {
            if (type === 'condition') {
              ret.push({ ...data });
              data = {};
              data[type] = item.value.id;
            } else if (type === 'key') {
              valueType =
                typeof item.value.type === 'undefined'
                  ? this.dimensionList?.find(set => set.id === item.value.id)?.type || 'string'
                  : item.value.type;
              data[type] = data[type] || item.value.id;
            } else if (type === 'value') {
              data[type] =
                data[type] ||
                (Array.isArray(item.value)
                  ? item.value
                      .map(v => (valueType === 'number' ? Number(v) : String(v).trim()))
                      .filter(v => v !== Number.NaN)
                  : item.value);
            } else {
              data[type] = data[type] || item.value.id;
            }
          }
        });
        Object.keys(data).length > 2 && ret.push(data);
      }
      return ret;
    },
  },
};
</script>
<style lang="scss" scoped>
.strategy-set-input {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  width: 100%;
  font-size: 12px;
  color: #63656e;

  .input-blank {
    box-sizing: border-box;
    flex: 1;
    height: 32px;
    margin-top: 2px;
    margin-right: 2px;
    background: #fafbfd;
    border: 1px solid #f0f1f5;
    border-radius: 2px;
  }
}
</style>
