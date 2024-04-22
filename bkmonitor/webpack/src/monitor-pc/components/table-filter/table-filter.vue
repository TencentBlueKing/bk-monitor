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
  <article v-show="false">
    <div
      ref="labelMenuWrapper"
      class="label-menu-wrapper"
    >
      <ul
        v-if="filterType === 'checkbox'"
        class="label-menu-list"
      >
        <!-- <li class="item" v-for="(item, index) in label.list" :key="index" @click="handleSelectLabel(item)"> -->
        <li
          v-for="(item, index) in label.list"
          :key="index"
          class="item"
          @click="handleSelectCheckbox(item)"
        >
          <!-- <bk-checkbox :value="item.value" :true-value="item.checked" :false-value="item.cancel"></bk-checkbox> -->
          <bk-checkbox
            :checked="item.checked"
            :true-value="true"
            :false-value="false"
          />
          <span class="name">{{ item.name }}</span>
        </li>
      </ul>
      <bk-radio-group
        v-else-if="filterType === 'radio'"
        v-model="radio.value"
        class="radio-group"
      >
        <bk-radio
          v-for="(item, index) in radioList"
          :key="index + 'radio'"
          ext-cls="radio-item"
          :value="item"
          :checked="item === radio.value"
        >
          {{ item }}
        </bk-radio>
      </bk-radio-group>
      <div class="footer">
        <div class="btn-group">
          <span
            class="monitor-btn"
            @click="handleLabelChange"
          >
            {{ $t('确定') }}
          </span>
          <span
            class="monitor-btn"
            @click="handleResetLable"
          >
            {{ $t('重置') }}
          </span>
        </div>
      </div>
    </div>
  </article>
</template>
<script>
export default {
  name: 'TableFilter',
  props: {
    show: {
      type: Boolean,
      default: false,
    },
    target: null,
    radioList: {
      type: Array,
      default: () => [],
    },
    // 菜单列表
    menuList: {
      type: Array,
      default: () => [],
    },
    // 筛选列表类型 多选/单选
    filterType: {
      type: String,
      default: 'checkbox',
      validator: val => ['checkbox', 'radio'].includes(val),
    },
    value: {
      type: [String, Array],
      default: '',
    },
  },
  data() {
    return {
      label: {
        list: [],
        instance: null,
        values: [],
        selectedLabels: [],
        isFilter: false,
      },
      tippyOptions: {
        trigger: 'manual',
        arrow: false,
        theme: 'light common-monitor',
        maxWidth: 280,
        offset: '-1, -11',
        sticky: true,
        duration: [275, 0],
        interactive: true,
      },
      radio: {
        value: '',
        tempVal: '',
        isFilter: false,
      },
    };
  },
  computed: {
    labelKeyword() {
      return this.label.list.filter(item => item.checked).map(item => item.id);
    },
  },
  watch: {
    show(v) {
      if (!v && this.label.instance) {
        this.label.instance.hide();
      } else if (v && this.label.instance) {
        this.label.instance.show(100);
      } else if (v && !this.label.instance) {
        this.handleShow();
      }
      if (v) {
        this.genreationSelectorList();
        if (this.filterType === 'checkbox' && this.value && this.value.length) {
          this.label.isFilter = true;
        } else if (this.type === 'radio' && this.value) {
          this.radio.isFilter = true;
        }
      }
    },
    labelKeyword(v) {
      this.$emit('selected', v);
    },
    menuList() {
      this.genreationSelectorList();
      this.handleUpdateChecked();
    },
  },
  created() {
    this.tippyOptions = Object.assign(this.tippyOptions, this.options);
    this.genreationSelectorList();
  },
  deactivated() {
    this.handleDestroy();
  },
  beforeDestroy() {
    this.handleDestroy();
  },
  methods: {
    // 销毁
    handleDestroy() {
      this.label.instance?.destroy();
      this.label.instance = null;
      this.$emit('hide', false);
    },
    // 设置正反选
    // handleSelectLabel (item) {
    //     item.value = item.value === item.id ? null : item.id
    // },
    // 设置正反选
    handleSelectCheckbox(item) {
      item.checked = !item.checked;
    },
    handleShow() {
      this.label.instance = this.$bkPopover(this.target, {
        content: this.$refs.labelMenuWrapper,
        onHidden: () => {
          this.filterType === 'checkbox' && this.handleUpdateChecked();
          this.filterType === 'radio' && this.handleUpdateRadio();
          this.handleDestroy();
        },
        ...this.tippyOptions,
      });
      this.label.instance?.show(100);
    },
    /**
     * 确定筛选
     */
    handleLabelChange() {
      this.label.instance.hide(100);
      if (this.filterType === 'radio') {
        this.radio.isFilter = true;
        this.radio.tempVal = this.radio.value;
        this.$emit('confirm', this.radio.value);
        this.$emit('hide', false);
        return;
      }
      this.label.isFilter = true;
      if (this.labelKeyword.length) {
        this.label.selectedLabels = this.labelKeyword;
        this.$emit('confirm', this.label.selectedLabels);
      }
      this.$emit('hide', false);
    },
    /**
     * 重置以勾选的选项，如果重置前发生过筛选则抛出reset事件
     */
    handleResetLable() {
      this.label.instance.hide(100);
      if (this.filterType === 'radio') {
        this.radio.value = '';
        if (this.radio.isFilter) {
          this.radio.isFilter = false;
          this.$emit('reset', '');
        }
      } else {
        this.label.list.forEach(item => {
          item.checked = false;
        });
        this.label.selectedLabels = [];
        if (this.label.isFilter) {
          this.label.isFilter = false;
          this.$emit('reset', '');
        }
      }
      this.$emit('hide', false);
    },
    handleUpdateChecked() {
      const list = this.label.selectedLabels.length ? this.label.selectedLabels : [];
      this.label.list.forEach(item => {
        if (list.includes(item.id)) {
          item.value = item.id;
        } else {
          item.value = null;
        }
      });
    },
    /**
     * 处理下拉菜单的数据格式
     */
    genreationSelectorList() {
      this.label.list = this.menuList.map(item => ({
        name: item.name,
        id: item.id,
        checked: this.value.includes(item.id),
      }));
    },
    // 更新radio值
    handleUpdateRadio() {
      this.radio.tempVal !== this.radio.value && (this.radio.value = this.radio.tempVal);
      !this.radio.isFilter && (this.radio.value = '');
    },
  },
};
</script>
<style lang="scss" scoped>
.label-menu-wrapper {
  background-color: #fff;
  .radio-group {
    display: flex;
    flex-direction: column;
    padding: 6px 0;
    max-height: 250px;
    overflow-y: auto;
    .radio-item {
      display: flex;
      align-items: center;
      height: 32px;
      padding: 0 10px;
      font-size: 12px;
      flex-shrink: 0;
      &:hover {
        color: #3a84ff;
        background: #e1ecff;
      }
    }
  }
  .label-menu-list {
    display: flex;
    flex-direction: column;
    border-radius: 2px;
    padding: 6px 0;
    max-height: 250px;
    overflow-y: auto;
    .item {
      display: flex;
      align-items: center;
      height: 32px;
      min-height: 32px;
      padding: 0 10px;
      color: #63656e;
      cursor: pointer;
      .name {
        margin-left: 6px;
      }
      &:hover {
        background: #e1ecff;
        color: #3a84ff;
      }
    }
  }
  .footer {
    display: flex;
    justify-content: center;
    height: 29px;
    border-top: solid 2px #f0f1f5;
    .btn-group {
      display: flex;
      justify-content: space-between;
      align-items: center;
      width: 70px;
      height: 100%;
      .monitor-btn {
        color: #3a84ff;
        cursor: pointer;
        &:hover {
          color: #699df4;
        }
      }
    }
  }
}
</style>
