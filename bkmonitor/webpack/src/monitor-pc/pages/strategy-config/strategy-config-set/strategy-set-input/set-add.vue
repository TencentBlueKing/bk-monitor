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
    v-if="addType === 'common'"
    key="preAdd"
    class="input-add"
    @click.stop.prevent="handleAddClick"
  >
    <i class="bk-icon icon-plus" />
  </span>
  <span
    v-else
    class="input-title"
    @click.stop.prevent="handleAddClick"
  >
    {{ addTitle }}
    <span class="input-title-desc">{{ addDesc }}</span>
  </span>
</template>
<script>
export default {
  name: 'SetAdd',
  props: {
    // character 为文字按钮
    addType: {
      type: String,
      default: 'common',
      validator(v) {
        return ['common', 'character'].includes(v);
      },
    },
    // 文字按钮按钮时显示的名称
    addTitle: {
      type: String,
      default() {
        return this.$t('添加');
      },
    },
    addDesc: {
      type: String,
      default: '',
    },
  },
  methods: {
    handleAddClick(e) {
      this.$emit('set-add', e);
    },
  },
};
</script>
<style lang="scss" scoped>
.input-add {
  box-sizing: border-box;
  width: 32px;
  height: 32px;
  border-radius: 2px;
  background-color: #f0f1f5;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #3a84ff;
  cursor: pointer;
  margin-right: 2px;
  margin-top: 2px;

  .icon-plus {
    // font-weight: bold;
    font-size: 24px;
  }

  &:hover {
    cursor: pointer;
  }
}

.input-title {
  color: #3a84ff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;

  &:hover {
    cursor: pointer;
  }

  &-desc {
    color: #c4c6cc;
  }
}
</style>
