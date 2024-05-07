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
  <div
    :tabindex="1"
    @blur="handleSelectBlur"
  >
    <div
      class="select-node"
      :class="{ 'hight-lignt': listShow }"
      @click="handleSelectChange"
      @mouseenter="handleClearIconShow"
      @mouseleave="handleClearIconClose"
    >
      <span
        v-if="!value"
        class="default-text"
        >{{ placeholder }}</span
      >
      <span v-else>{{ value }}</span>
      <div
        class="focus"
        :class="{ transform: listShow }"
      >
        <i class="bk-select-angle bk-icon icon-angle-down" />
      </div>
      <i
        v-if="iconShow"
        class="bk-icon icon-close-circle-shape clear"
        @click.stop="handleClearValue"
      />
    </div>
    <div
      v-show="listShow"
      class="select-node-content"
    >
      <slot />
    </div>
  </div>
</template>

<script>
export default {
  name: 'SelectInputTemplate',
  props: {
    placeholder: {
      type: String,
      default() {
        return this.$t('选择');
      },
    },
    value: {
      type: String,
      default: '',
    },
  },
  data() {
    return {
      listShow: false,
      iconShow: false,
    };
  },
  methods: {
    handleSelectChange() {
      this.listShow = !this.listShow;
    },
    handleSelectBlur() {
      this.listShow = false;
    },
    // clear-icon显示
    handleClearIconShow() {
      this.iconShow = !!this.value;
    },
    // clear-icon关闭
    handleClearIconClose() {
      this.iconShow = false;
    },
    // clear-icon事件
    handleClearValue() {
      this.$emit('clear', this.value);
      this.iconShow = false;
    },
  },
};
</script>

<style lang="scss" scoped>
.select-node {
  width: 380px;
  height: 32px;
  background: #fff;
  border: 1px solid #c4c6cc;
  border-radius: 2px;
  padding: 0 8px 0 10px;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
  cursor: pointer;

  .default-text {
    color: #c4c6cc;
  }
}

.select-node-content {
  position: absolute;
  top: 34px;
  left: 126px;
  background: #fff;
  border: 1px solid #dcdee5;
  border-radius: 2px;
  box-shadow: 0 3px 6px 0 rgba(49, 50, 56, 0.15);
  width: 380px;
  max-height: 760px;
  z-index: 2;
}

.focus {
  display: flex;
  align-items: center;
  position: relative;
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.clear {
  position: absolute;
  top: 9px;
  right: 8px;
  color: #c4c6cc;
  background: #fff;

  &:hover {
    color: #979ba5;
  }
}

.transform {
  transform: rotate(-180deg);
}

.hight-lignt {
  border: 1px solid #3a84ff;
  box-shadow: 0 0 4px rgba(58, 132, 255, 0.4);
}
</style>
