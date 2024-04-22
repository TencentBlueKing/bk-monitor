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
      @click="curActive = index"
      @remove="handleItemRemove(item, index)"
      @set-hide="handleSetHide(item, index)"
      @set-value="data => handleSetValue(data, item, index)"
      @item-select="data => handleItemSelect(data, item, index)"
      @set-add="item.addEvent && handleSetAdd($event, item, index)"
    />
    <!-- <span class="input-blank"></span> -->
  </div>
</template>
<script>
import { deepClone, random } from 'monitor-common/utils/utils';

import SetAdd from './set-add';
import SetInput from './set-input';

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
    value: {
      type: Array,
      default() {
        return [];
      },
    },
  },
  data() {
    return {
      alarmConditionList: [],
    };
  },
  watch: {
    alarmConditionList: {
      handler() {
        this.$emit('change', deepClone(this.getValue()));
      },
      deep: true,
    },
  },
  created() {
    this.handleSetDefaultValue();
  },
  methods: {
    getDefaultMethod() {
      const key = random(10);
      return {
        list: [
          {
            id: 'gt',
            name: '>',
          },
          {
            id: 'gte',
            name: '>=',
          },
          {
            id: 'lt',
            name: '<',
          },
          {
            id: 'lte',
            name: '<=',
          },
          {
            id: 'eq',
            name: '=',
          },
          {
            id: 'neq',
            name: '!=',
          },
        ],
        value: {
          id: 'gte',
          name: '>=',
        },
        width: '32',
        'list-min-width': '30',
        'is-method': true,
        component: 'set-input',
        show: true,
        type: 'method',
        compKey: key,
        isKey: true,
      };
    },
    getDefaultValue() {
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
        'input-type': 'number',
        placeholder: this.$t('输入数字'),
        compKey: key,
      };
    },
    getDefaultCondition(isOr = false) {
      const key = random(10);
      const value = isOr ? { id: 'or', name: 'OR' } : { id: 'and', name: 'AND' };
      return {
        list: [
          {
            id: 'and',
            name: 'AND',
            show: true,
          },
          {
            id: 'or',
            name: 'OR',
            show: true,
          },
        ],
        value,
        width: '40',
        'list-min-width': '38',
        'is-condition': true,
        component: 'set-input',
        show: true,
        type: 'condition',
        compKey: key,
        unique: false,
        readonly: false,
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
      };
    },
    handleSetAdd(e, item, index) {
      e.preventDefault();
      item.show = false;
      if (this.alarmConditionList.length > 2) {
        this.alarmConditionList.splice(
          index,
          0,
          this.handleSetCondition(),
          this.getDefaultMethod(),
          this.getDefaultValue()
        );
      } else {
        this.alarmConditionList.splice(index, 0, this.getDefaultMethod(), this.getDefaultValue());
      }
      this.$nextTick().then(() => {
        const ref = this.$refs[`component-${this.alarmConditionList.length - 2}`][0];
        ref.getInput().focus();
      });
    },
    async handleItemSelect(data, item, index) {
      this.curActive = index;
      if (item.value.id !== data.id || item.value.name !== data.name) {
        item.value = { ...data };
        if (item.type === 'value') {
          this.alarmConditionList[this.alarmConditionList.length - 1].show = true;
        }
      }
    },
    handleSetHide(item, index) {
      item.show = false;
      this.alarmConditionList[index - 1].show = true;
    },
    handleSetValue(data, item) {
      data.show = true;
      item.list.unshift(data);
    },
    handleSetDefaultValue() {
      this.alarmConditionList = [];
      if (this.value.length) {
        this.value.forEach((item, index) => {
          if (index > 0) {
            this.alarmConditionList.push(this.handleSetCondition(item.condition === 'or'));
          }
          const methodItem = this.getDefaultMethod();
          methodItem.value.id = item.method;
          methodItem.value.name = methodItem.list.find(set => set.id === item.method)?.name;
          this.alarmConditionList.push(methodItem);
          const valueItem = this.getDefaultValue();
          valueItem.value.id = item.value;
          valueItem.value.name = item.value;
          valueItem.list.unshift({
            id: item.value,
            name: item.value,
          });
          this.alarmConditionList.push(valueItem);
        });
      }
      const item = this.getDefaultAdd();
      this.alarmConditionList.push(item);
      item.show = true;
    },
    handleItemRemove(item, index) {
      const nextComp = this.alarmConditionList[index + 2];
      if (nextComp.type === 'condition') {
        this.alarmConditionList.splice(index, 3);
      } else if (nextComp.type === 'add') {
        const preComp = this.alarmConditionList[index - 1];
        this.alarmConditionList.splice(preComp ? index - 1 : index, preComp ? 3 : 2);
        nextComp.show = true;
      }
      const conditionList = this.alarmConditionList.filter(set => set.type === 'condition');
      if (conditionList.length === 1) {
        const firstCondition = conditionList[0];
        firstCondition.list.forEach(set => (set.show = true));
      }
    },
    handleSetCondition(isOr = false) {
      const condition = this.getDefaultCondition(isOr);
      // 设置是否只存在OR或者AND 功能变更暂时注释
      // const conditionList = this.alarmConditionList.filter(set => set.type === 'condition')
      // if (conditionList.length > 0) {
      //     const firstCondition = conditionList[0]
      //     condition.value = { ...firstCondition.value }
      //     condition.list.forEach(set => (set.show = set.id === firstCondition.value.id))
      //     firstCondition.list.forEach(set => (set.show = set.id === firstCondition.value.id))
      // }
      return condition;
    },
    getValue() {
      const ret = [];
      if (this.alarmConditionList.length) {
        let data = {};
        this.alarmConditionList.forEach(item => {
          const { type } = item;
          if (['method', 'value', 'condition'].includes(type)) {
            if (type === 'condition') {
              ret.push({ ...data });
              data = { condition: item.value.id };
            } else {
              data[type] = item.value.id;
            }
          }
        });
        Object.keys(data).length && ret.push(data);
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
