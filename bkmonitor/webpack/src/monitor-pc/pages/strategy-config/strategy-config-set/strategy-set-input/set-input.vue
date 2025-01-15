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
  <div class="set-input-wrapper">
    <div
      v-if="!multiple"
      ref="input"
      class="set-input"
      :class="{
        'is-condition': isCondition || isMethod,
        'is-method': isMethod,
        'input-placeholder': !inputValue.length && !(select[displayKey] + '').length,
      }"
      :style="{ 'min-width': width + 'px' }"
      :data-placeholder="placeholder"
      :contenteditable="!readonly"
      @input="handleInputChange"
      @click.stop="!readonly && handleSetClick($event)"
      @keyup.enter="handleSetEnter"
      @blur="handleSetBlur"
    />
    <div
      v-else
      class="set-tag"
    >
      <bk-tag-input
        trigger="focus"
        class="set-tag-select"
        :placeholder="$t('输入')"
        :value="value"
        :list="list"
        :disabled="readonly"
        :allow-create="allowCreate"
        :allow-auto-match="allowAutoMatch"
        :paste-fn="handlePaste"
        @change="handleTagChange"
      />
    </div>
    <div
      v-if="!multiple"
      style="display: none"
    >
      <slot name="list">
        <div
          ref="setList"
          class="set-list-wrapper"
        >
          <ul
            class="set-list"
            :style="{ 'min-width': listMinWidth + 'px' }"
          >
            <li
              v-for="(item, index) in filterList"
              v-show="unique ? !(+unique ^ +item.show) : item.show"
              :key="index"
              class="set-list-item"
              :class="{ 'is-condition': isCondition || isMethod }"
              data-set-item="setListItem"
              :data-item-index="index"
              @mousedown="handleSetItemClick($event, item)"
            >
              {{ item[displayKey] }}
            </li>
          </ul>
          <div
            v-if="isKey && (select[displayKey] + '').length"
            class="set-remove"
            @mousedown="handleRemoveClick"
          >
            <i
              class="icon-monitor icon-chahao"
              :class="{ 'set-remove-icon': !isMethod }"
            />
            {{ !isMethod ? $t('删除') : '' }}
          </div>
        </div>
      </slot>
    </div>
  </div>
</template>
<script>
export default {
  name: 'SetInput',
  props: {
    inputType: {
      type: String,
      default: 'text',
      validator(v) {
        return ['text', 'number'].includes(v);
      },
    },
    list: {
      type: Array,
      required: true,
    },
    isKey: Boolean,
    isCondition: Boolean,
    isMethod: Boolean,
    defaultFocus: Boolean,
    placeholder: {
      type: String,
      default() {
        return this.$t('选择值');
      },
    },
    value: {
      type: [Object, Array],
      required: true,
    },
    listMinWidth: {
      type: [String, Number],
      default: 98,
    },
    width: {
      type: [String, Number],
      default: 100,
    },
    idKey: {
      type: String,
      default: 'id',
    },
    displayKey: {
      type: String,
      default: 'name',
    },
    unique: Boolean,
    readonly: {
      type: Boolean,
      default: false,
    },
    // 是否只允许选择
    onlySelect: {
      type: Boolean,
      default: true,
    },
    // 是否多选
    multiple: {
      type: Boolean,
      default: false,
    },
    allowCreate: {
      type: Boolean,
      default: true,
    },
    allowAutoMatch: {
      type: Boolean,
      default: true,
    },
  },
  data() {
    return {
      popoverInstance: null,
      unWatch: null,
      filterList: [],
      isItemClick: false,
      select: {
        id: '',
        name: '',
      },
      inputValue: '',
    };
  },
  watch: {
    value: {
      handler(v) {
        this.select = Object.assign(
          {
            [this.idKey]: '',
            [this.displayKey]: '',
          },
          this.select,
          v
        );
      },
      immediate: true,
      deep: true,
    },
    list: {
      handler() {
        this.filterList = this.list || [];
        this.filterList.forEach(item => {
          item.show = item.show !== undefined ? !!item.show : true;
        });
      },
      immediate: true,
    },
  },
  created() {
    this.unWatch = this.$watch('inputValue', this.handleSelectChange);
  },
  mounted() {
    if (this.defaultFocus) {
      this.$refs.input.focus();
    }
    this.inputValue = this.select[this.displayKey];
    this.handleSetInputValue(this.inputValue);
  },
  beforeDestroy() {
    this.unWatch?.();
    if (this.popoverInstance) {
      this.popoverInstance.hide();
      this.popoverInstance.destroy();
      this.popoverInstance = null;
    }
  },
  methods: {
    initPopover() {
      this.popoverInstance = this.$bkPopover(this.$refs.input, {
        content: this.$refs.setList,
        arrow: false,
        trigger: 'manul',
        placement: 'bottom-start',
        theme: 'light set-input-list',
        maxWidth: 520,
        duration: [200, 0],
        distance: 2,
        onHidden: () => {
          // this.popoverInstance.destroy()
          // this.popoverInstance = null
        },
      });
    },
    handlePaste(v) {
      const data = `${v}`.replace(/\s/gim, '');
      const valList = Array.from(new Set(`${data}`.split(',').map(v => v.trim())));
      const ret = [];
      valList.forEach(val => {
        // eslint-disable-next-line vue/no-mutating-props
        !this.value.some(v => v === val) && val !== '' && this.value.push(val);
        if (!this.list.some(item => item.id === val)) {
          ret.push({
            id: val,
            name: val,
            show: true,
          });
        }
      });
      this.handleTagChange(this.value);
      return ret;
    },
    handleTagChange(tags) {
      this.$emit('set-value', tags);
    },
    handleSetClick() {
      this.handleSetInputValue('');
      this.inputValue = '';
      if (!this.popoverInstance) {
        this.initPopover();
      }
      const hasSelect = `${this.select[this.displayKey]}`.length > 0;
      if (this.unique) {
        const hasList = this.list.some(set => set.show);
        if ((!hasList && hasSelect) || hasList) {
          this.$nextTick().then(() => {
            this.popoverInstance.show(100);
          });
        }
      } else {
        const hasList = this.list.length > 0;
        if ((!hasList && hasSelect && this.isKey) || hasList > 0) {
          this.$nextTick().then(() => {
            this.popoverInstance.show(100);
          });
        }
      }
    },
    handleSetItemClick(e, data) {
      if (this.select[this.idKey] && this.unique) {
        const selectItem = this.list.find(set => set[this.idKey] === this.select[this.idKey]);
        if (selectItem) {
          selectItem.show = true;
        }
      }
      this.select = { ...data };
      this.handleSetInputValue(data[this.displayKey]);
      this.isItemClick = true;
      this.inputValue = data[this.displayKey];
      if (this.unique) {
        data.show = false;
      }
      this.popoverInstance.hide(100);
      this.$emit('item-select', { ...data });
    },
    handleRemoveClick() {
      if (this.select[this.idKey] && this.unique) {
        const item = this.list.find(set => set[this.idKey] === this.select[this.idKey]);
        if (item) {
          item.show = true;
        }
      }
      this.$emit('remove');
    },
    handleInputChange(e) {
      this.inputValue = e.target.innerText;
      this.$emit('change', e, e.target.innerText);
    },
    handleSetInputValue(v) {
      if (this.$refs.input) {
        this.$refs.input.innerText = v;
      } else {
        this.$nextTick().then(() => {
          if (this.$refs.input) {
            this.$refs.input.innerText = v;
          }
        });
      }
    },
    handleSelectChange(v) {
      this.filterList = this.list.filter(item => `${item[this.displayKey]}`.indexOf(v) !== -1);
      if (!this.filterList.length) {
        this.popoverInstance?.hide(100);
      } else if (
        !this.isItemClick &&
        this.popoverInstance &&
        !this.popoverInstance.state.isVisible &&
        this.list.length
      ) {
        this.popoverInstance?.show(100);
      }
    },
    handleSetEnter(e) {
      this.handleSetBlur(e);
    },
    handleSetBlur() {
      this.inputValue = `${this.inputValue}`;
      if (!this.inputValue.trim()) {
        if (this.select[this.displayKey]) {
          this.inputValue = this.select[this.displayKey];
          this.handleSetInputValue(this.inputValue);
        } else if (this.isKey) {
          this.$emit('set-hide');
        }
      } else {
        if (this.inputValue !== this.select[this.displayKey]) {
          const item = this.list.find(set => set[this.displayKey] === this.inputValue.trim());
          if (item) {
            this.select = { ...item };
            if (this.unique) {
              item.show = false;
              const selectItem = this.list.find(set => set[this.displayKey] === this.select[this.idKey]);
              selectItem && (selectItem.show = true);
            }
            this.$emit('item-select', { ...item });
          } else {
            if (this.isMethod || this.isCondition) {
              this.inputValue = this.select[this.displayKey];
              this.handleSetInputValue(this.inputValue);
              return;
            }
            if (this.onlySelect && this.isKey) {
              this.inputValue = this.select[this.displayKey];
              this.handleSetInputValue(this.inputValue);
              return;
            }
            const text = this.inputValue.trim();
            if (this.inputType === 'number' && isNaN(text)) {
              this.inputValue = this.select[this.displayKey];
              this.handleSetInputValue(this.inputValue);
              return;
            }
            this.select = { id: this.inputValue.trim(), name: this.inputValue.trim(), show: true };
            this.$emit('set-value', { id: this.inputValue.trim(), name: this.inputValue.trim() });
            this.$emit('item-select', { id: this.inputValue.trim(), name: this.inputValue.trim() });
          }
        }
      }
      this.isItemClick = false;
    },
    getInput() {
      return this.$refs.input;
    },
  },
};
</script>
<style lang="scss" scoped>
.set-input-wrapper {
  .set-input {
    box-sizing: border-box;
    display: flex;
    align-items: center;
    min-height: 32px;
    line-height: 30px;
    min-width: 32px;
    border: 1px solid #c4c6cc;
    border-radius: 2px;
    padding: 0 12px;
    margin-right: 2px;
    margin-top: 2px;

    &.input-placeholder {
      &:before {
        content: attr(data-placeholder);
        color: #c4c6cc;
      }
    }

    &.is-condition {
      text-align: center;
      justify-content: center;
      padding: 0 5px;

      /* stylelint-disable-next-line declaration-no-important */
      color: #3a84ff !important;
    }

    &.is-method {
      /* stylelint-disable-next-line declaration-no-important */
      color: #ff9c01 !important;
      padding: 0 5px;
      font-weight: bold;
    }

    &:hover {
      border-color: #979ba5;
      color: #63656e;
      cursor: pointer;
    }

    &:focus {
      border-color: #3a84ff;
    }
  }

  .set-tag {
    display: flex;
    margin: 2px 2px 0 0;
    min-width: 120px;
    align-items: center;
    min-height: 32px;

    &-select {
      flex: 1;
      min-height: 32px;
    }
  }
}
</style>
<style lang="scss">
.set-input-list-theme {
  padding: 0;
  pointer-events: all;
  border-radius: 0;

  /* stylelint-disable-next-line declaration-no-important */
  box-shadow: none !important;
  font-size: 12px;
  color: #63656e;

  .set-list-wrapper {
    display: flex;
    flex-direction: column;
    border: 1px solid #dcdee5;
    border-radius: 2px;
    background-color: #fff;

    .set-list {
      display: flex;
      flex-direction: column;
      padding: 6px 0;
      min-width: 98px;
      box-sizing: border-box;
      max-height: 210px;
      overflow: auto;

      &-item {
        flex: 0 0 32px;
        display: flex;
        align-items: center;
        padding: 0 15px;

        &.is-condition {
          justify-content: center;
          padding: 0 5px;
        }

        &:hover {
          background-color: #e1ecff;
          color: #3a84ff;
          cursor: pointer;
        }
      }
    }

    .set-remove {
      flex: 0 0 32px;
      border-top: 1px solid #dcdee5;
      display: flex;
      align-items: center;
      background-color: #fafbfd;
      padding: 0 15px;
      cursor: pointer;

      &-icon {
        margin-right: 4px;
      }
    }
  }
}
</style>
