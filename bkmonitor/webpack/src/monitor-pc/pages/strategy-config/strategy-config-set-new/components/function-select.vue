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
  <span
    :class="[
      'function-select-wrap',
      {
        'is-readonly': readonly
      }
    ]"
  >
    <span
      data-type="func"
      class="func-label"
    >{{ $t('函数') }}</span>
    <!-- <span
      data-type="func"
      :contenteditable="!readonly"
      :data-placeholder="placeholder"
      :placeholder="placeholder"
      @click="handleAddFunc('init-add')"
      ref="target-init-add"
      class="init-add">
    </span> -->
    <span
      class="init-add"
      data-type="func"
      v-show="!localValue.length"
      @click="handleAddFunc('init-add')"
    >
      <bk-input
        :placeholder="placeholder"
        :readonly="readonly"
        class="init-add-input"
        ref="target-init-add"
      />
    </span>
    <!-- 方法 -->
    <span
      data-type="func"
      v-for="(item, index) in localValue"
      :key="item.id"
      :ref="`target-${item.id}`"
      class="func-item"
    >
      <span
        @click="handleAddFunc(item.id, item, index)"
        :class="['is-hover', { 'is-readonly': readonly }]"
      >{{
        item.name
      }}</span>
      <span class="brackets">&nbsp;(&nbsp;</span>
      <span
        class="params-item"
        v-for="(set, i) in item.params"
        :key="i"
      >
        <!-- 参数 -->
        <span
          :class="['params-text', 'is-hover', { 'is-readonly': readonly }]"
          v-show="!set.contenteditable"
          @click.stop="handleFuncParams(set, i)"
        >{{ set.value }}</span>
        <input
          v-show="set.contenteditable"
          v-model="set.value"
          :ref="`input-${set.parentId}-${set.name}`"
          :data-focus="set.contenteditable"
          :class="['params-input', { 'is-edit': set.contenteditable }]"
          @blur="handleFuncParamsBlur(set, index, i)"
        ><span v-if="i !== item.params.length - 1">,&nbsp;</span>
      </span>
      <span class="brackets">&nbsp;)&nbsp;</span>
    </span>
    <span
      data-type="func"
      class="func-add-btn"
      v-show="localValue.length"
      @click="handleAddFunc('Add')"
      ref="target-Add"
    >
      <span class="icon-monitor icon-mc-add" />
    </span>
    <select-menu
      :show="showSelectMenu"
      :target="curSelectTarget"
      :list="menuList"
      :need-delete="isNeedDelete"
      @on-delete="handleMenuDelete"
      @on-select="handelMenuSelect"
      @on-hidden="handleMenuHidden"
    />
  </span>
</template>
<script lang="ts">
import { Component, Emit, Model, Prop, Ref, Vue, Watch } from 'vue-property-decorator';


import { deepClone } from '../../../../../monitor-common/utils/utils';
import SelectMenu from '../components/select-menu.vue';
import { IFuncListItem, IFuncLocalParamsItem, IFuncLocalValue, IFuncValueItem, IIdNameItem } from '../type';

@Component({
  name: 'function-select',
  components: {
    SelectMenu
  }
})
export default class FunctionSelect extends Vue {
  @Model('valueChange', { default: () => [], type: Array }) private readonly value!: IFuncValueItem[];

  @Prop({ default: window.i18n.t('选择'), type: String }) private readonly placeholder: string;
  @Prop({ default: false, type: Boolean }) private readonly readonly: boolean;

  @Ref('target-init-add') private readonly initAddRef: bkInput;

  private localValue: IFuncLocalValue[] = [];
  // 函数可选列表
  //   private funcList: any = []

  // 后端提供可选列表
  private funcList: IFuncListItem[] = [
    {
      id: 1,
      name: 'Top',
      params: [
        {
          name: 'top',
          default: 5,
          list: [1, 2, 3, 4, '5']
        }
      ]
    },
    {
      id: 2,
      name: 'Bottom',
      params: [
        {
          name: 'bot1',
          default: 1,
          list: [1, 2, 3, 4, 5]
        },
        {
          name: 'bot2',
          default: 2,
          list: [1, 2, 3]
        }
      ]
    },
    {
      id: 3,
      name: 'left',
      params: [
        {
          name: 'left1',
          default: 1,
          list: [1, 2, 3, 4, 5]
        },
        {
          name: 'left2',
          default: 2,
          list: [1, 2, 3]
        }
      ]
    },
    {
      id: 4,
      name: 'right',
      params: [
        {
          name: 'right1',
          default: 1,
          list: [1, 2, 3, 4, 5]
        },
        {
          name: 'righddfft',
          default: 2,
          list: [1, 2, 3]
        }
      ]
    },
    {
      id: 5,
      name: 'test',
      params: [
        {
          name: 'testf1df',
          default: 1,
          list: [1, 2, 3, 4, 5]
        },
        {
          name: 'test1',
          default: 2,
          list: [1, 2, 3]
        }
      ]
    },
    {
      id: 6,
      name: 'rig2as22ht',
      params: [
        {
          name: 'rig223fdht1',
          default: 1,
          list: [1, 2, 3, 4, 5]
        },
        {
          name: 'rig444ht',
          default: 2,
          list: [1, 2, 3]
        }
      ]
    },
    {
      id: 7,
      name: 'righdddfdft',
      params: [
        {
          name: 'rigaaffht1',
          default: 1,
          list: [1, 2, 3, 4, 5]
        },
        {
          name: 'rifdddfght',
          default: 2,
          list: [1, 2, 3]
        }
      ]
    }
  ];

  // 对应函数的参数可选列表
  private paramsList: IIdNameItem[] = [];

  // 菜单类型
  private menuType: 'function' | 'parmams' = 'function';

  // 菜单展示目标元素
  private curSelectTarget: any = null;
  // 选中的函数
  private curSelectFunction: IFuncLocalValue = null;
  private curSelectFunctionIndex: number = null;
  // 选中的参数
  private curSelectParams: IFuncLocalParamsItem = null;
  private curSelectParamsIndex: number = null;
  // 菜单展示
  private showSelectMenu = false;

  private get menuList() {
    // 函数
    if (this.menuType === 'function') {
      if (this.curSelectFunction) return [];
      if (this.showSelectMenu) {
        return this.funcList.filter(item => !this.localValue.some(set => set.id === item.id));
      }
      return [];
    }
    // 参数
    return this.paramsList;
  }

  private get isNeedDelete() {
    return !!this.curSelectFunction;
  }

  private mounted() {
    this.curSelectTarget = this.initAddRef.$el;
    // setTimeout(() => {
    // this.funcList = this.funcListTemp
    // }, 3000)
  }

  @Watch('value', { immediate: true, deep: true })
  private watchValueChange(v) {
    this.transformValueToLocal(v);
  }

  @Watch('funcList')
  private watchFuncListChange(list) {
    if (list.length) {
      this.value.length && this.transformValueToLocal(this.value);
    }
  }

  @Emit('change')
  @Emit('valueChange')
  private emitValueChange() {
    const temp = this.transformValue(this.localValue);
    return temp;
  }

  @Emit('delete-func')
  private emitFunctionDelete(value, index) {
    value = this.transformValue(value);
    return { value, index };
  }

  @Emit('add-func')
  private emitFunctionAdd(value) {
    value = this.transformValue([value]);
    return value;
  }

  @Emit('replace-func')
  private emitReplaceFunc(newValue, oldValue) {
    newValue = this.transformValue([newValue]);
    oldValue = this.transformValue([oldValue]);
    return { newValue, oldValue };
  }

  @Emit('blur-params')
  private emitBlurParams(value, parentIndex, index) {
    this.emitValueChange();
    return { value, parentIndex, index };
  }

  /**
   * 新增修改函数
   */
  private handleAddFunc(target: string | number, funcItem: any = null, funcIndex: number = null) {
    if (this.readonly) return;
    this.curSelectFunction = funcItem;
    this.curSelectFunctionIndex = funcIndex;
    this.menuType = 'function';
    const temp: bkInput | HTMLElement | HTMLElement[] = this.$refs[`target-${target}`];
    this.curSelectTarget = Array.isArray(temp) ? temp[0] : temp.$el || temp;
    this.showSelectMenu = true;
  }

  /**
   * 菜单隐藏
   */
  private handleMenuHidden() {
    this.showSelectMenu = false;
  }

  /**
   * 菜单选中
   */
  private handelMenuSelect({ id, index }) {
    // 函数
    if (this.menuType === 'function') {
      let func = this.funcList.find(item => item.id === id);
      func = deepClone(func);
      func.params.map((item) => {
        this.$set(item, 'value', item.default);
        item.parentId = func.id;
        item.list = item.list.map(item => ({
          id: item,
          name: item
        }));
        this.$set(item, 'contenteditable', false);
        return item;
      });
      if (this.curSelectFunction) {
        this.emitReplaceFunc(deepClone(func), deepClone(this.localValue[this.curSelectFunctionIndex]));
        this.localValue[this.curSelectFunctionIndex] = func;
        this.curSelectFunction = null;
        this.curSelectFunctionIndex = null;
        this.emitValueChange();
      } else {
        this.localValue.push(func);
        this.emitFunctionAdd(func);
        this.emitValueChange();
      }
    } else {
      const newVal = this.curSelectParams.list[index].id;
      if (this.curSelectParams.value !== newVal) {
        this.curSelectParams.value = newVal;
        this.emitValueChange();
      }
    }
  }

  /**
   * 菜单删除
   */
  private handleMenuDelete() {
    // 函数
    if (this.menuType === 'function') {
      const delFunc = this.localValue.splice(this.curSelectFunctionIndex, 1);
      this.emitFunctionDelete(delFunc, this.curSelectFunctionIndex);
    }
    this.emitValueChange();
  }

  /**
   * 参数修改
   */
  private handleFuncParams(item, i) {
    if (this.readonly) return;
    this.curSelectFunction = null;
    item.contenteditable = true;
    this.curSelectParams = item;
    this.curSelectParamsIndex = i;
    this.$nextTick(() => {
      const input = this.$refs[`input-${item.parentId}-${item.name}`];
      this.curSelectTarget = input[0];
      this.curSelectTarget.focus();
      this.menuType = 'parmams';
      this.paramsList = item.list;
      this.showSelectMenu = true;
    });
  }

  /**
   * 参数输入失焦点
   */
  private handleFuncParamsBlur(item, parentIndex, index) {
    if (this.readonly) return;
    this.$nextTick(() => {
      item.contenteditable = false;
      this.emitBlurParams(item.value, parentIndex, index);
    });
  }

  /**
   * 转换外部所需value格式
   */
  private transformValue(value) {
    const temp = value.map(func => ({
      id: func.id,
      name: func.name,
      params: func.params.map(par => ({
        name: par.name,
        value: par.value
      }))
    }));
    return temp;
  }
  /**
   * 转换为内部value格式
   */
  private transformValueToLocal(value) {
    value = deepClone(value);
    if (!this.funcList.length) return (this.localValue = []);
    const temp = value.map((func) => {
      const resFunc = this.funcList.find(f => f.id === func.id);
      const params = func.params.map((par) => {
        const resPar = resFunc.params.find(p => p.name === par.name);
        par.contenteditable = false;
        par.default = resPar.default;
        par.parentId = resFunc.id;
        par.list = resPar.list.map(li => ({ id: li, name: li }));
        return par;
      });
      return {
        id: func.id,
        name: func.name,
        params
      };
    });
    this.localValue = temp;
  }
}
</script>
<style lang="scss">
.function-select-wrap {
  display: flex;
  flex-wrap: wrap;
  padding-left: 1px;

  .func-label {
    display: inline-block;
    height: 32px;
    padding: 0 16px;
    margin-left: -1px;
    font-size: 12px;
    font-weight: 400;
    line-height: 32px;
    color: #313238;
    text-align: left;
    background: #dcdee5;
    border: 1px solid #dcdee5;
  }

  .func-item,
  .init-add {
    display: inline-block;
    min-width: 50px;
    height: 32px;
    margin-bottom: 2px;
    margin-left: -1px;
    border: 1px solid #dcdee5;

    :deep(.bk-form-input) {
      border: 0;
    }
  }

  .func-item {
    display: flex;
    align-items: center;
    padding: 0 10px;

    .is-edit {
      display: inline-block;
    }

    .params-item {
      display: inline-block;
      height: 100%;

      .params-text {
        display: inline-block;
        height: 100%;
        line-height: 30px;
      }
    }

    .params-input {
      height: 100%;
      border: 0;
      outline: none;
    }

    /* stylelint-disable-next-line no-duplicate-selectors */
    .is-edit {
      width: 50px;
    }

    &:hover {
      cursor: pointer;

      .is-hover {
        color: #3a84ff;
      }
    }
  }

  .init-add {
    width: 93px;
    overflow: hidden;
    font-size: 12px;
    font-weight: 400;
    line-height: 30px;
    color: #c4c6cc;
    text-align: left;
    white-space: nowrap;
    // &:empty:before {
    //   content: attr(placeholder);
    //   color: #c4c6cc;
    // }
    // &:focus {
    //   content: none;
    // }
  }

  .func-add-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    margin-left: -1px;
    cursor: pointer;
    border: 1px solid #dcdee5;

    &:hover {
      color: #3a84ff;
    }

    .icon-mc-add {
      display: inline-block;
      width: 24px;
      height: 24px;
      font-size: 24px;
    }
  }
}

.is-readonly {
  /* stylelint-disable-next-line no-duplicate-selectors */
  .func-item {
    &:hover {
      cursor: default;

      .is-hover {
        color: #3a84ff;
      }

      .is-readonly {
        color: #313238;
      }
    }
  }

  /* stylelint-disable-next-line no-duplicate-selectors */
  .func-add-btn {
    cursor: default;
  }
}
</style>
<style lang="scss">
.cycle-list-wrapper-theme {
  width: 100%;
  padding: 0;
  border-radius: 0;
  box-shadow: 0 0 6px rgba(204, 204, 204, .3);
}
</style>
