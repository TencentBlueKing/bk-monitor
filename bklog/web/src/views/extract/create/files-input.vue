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
  <bk-popover
    ref="selectDropdown"
    class="bk-select-dropdown"
    :distance="16"
    :offset="-1"
    animation="slide-toggle"
    placement="bottom-start"
    theme="light bk-select-dropdown"
    trigger="click"
  >
    <slot name="trigger">
      <bk-input
        style="width: 669px"
        v-model="showValue"
        :class="isError && 'is-error'"
        data-test-id="addNewExtraction_input_specifyFolder"
        @change="handleChange"
      >
      </bk-input>
    </slot>
    <template #content>
      <div
        style="width: 671px; height: 224px"
        class="bk-select-dropdown-content"
      >
        <div
          style="height: 32px"
          class="bk-select-search-wrapper"
        >
          <i class="left-icon bk-icon icon-search"></i>
          <input
            class="bk-select-search-input"
            v-model="searchValue"
            :placeholder="$t('输入关键字搜索')"
            type="text"
          />
        </div>
        <div
          style="max-height: 190px"
          class="bk-options-wrapper"
        >
          <ul
            style="max-height: 190px"
            class="bk-options bk-options-single"
          >
            <li
              v-for="option in filesSearchedPath"
              class="bk-option"
              :key="option"
              @click="handleSelectOption(option)"
            >
              <div class="bk-option-content">{{ option }}</div>
            </li>
          </ul>
        </div>
        <div
          v-if="!filesSearchedPath.length"
          class="bk-select-empty"
        >
          {{ $t('暂无选项') }}
        </div>
      </div>
    </template>
  </bk-popover>
</template>

<script>
  export default {
    model: {
      event: 'change',
    },
    props: {
      value: {
        type: String,
        required: true,
      },
      availablePaths: {
        type: Array,
        required: true,
      },
    },
    data() {
      return {
        isError: false,
        showValue: '',
        searchValue: '',
      };
    },
    computed: {
      filesSearchedPath() {
        return this.availablePaths.filter(item => item.toLowerCase().includes(this.searchValue.toLowerCase()));
      },
    },
    watch: {
      availablePaths() {
        this.showValue && this.handleChange(this.showValue);
      },
      value(val) {
        this.showValue = val;
      },
    },
    methods: {
      handleChange(val) {
        if (this.validate(val)) {
          this.$emit('change', val);
        } else {
          this.$emit('change', '');
        }
      },
      handleSelectOption(val) {
        this.validate(val);
        this.showValue = val;
        this.$emit('change', val);
        this.$emit('update:select', val);
        this.$refs.selectDropdown.hideHandler();
      },
      validate(val) {
        let isAvailable = false;
        for (const path of this.availablePaths) {
          if (val.startsWith(path)) {
            isAvailable = true;
            break;
          }
        }
        const isValidated = isAvailable && !/\.\//.test(val);
        this.isError = !isValidated;
        return isValidated;
      },
    },
  };
</script>
