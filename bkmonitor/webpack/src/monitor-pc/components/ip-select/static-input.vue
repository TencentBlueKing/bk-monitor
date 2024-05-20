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
  <div class="static-input">
    <bk-input
      v-model="text"
      class="static-input-text"
      :placeholder="$t('多个IP以回车为分隔符')"
      :type="'textarea'"
      :rows="10"
      @keydown.native="handleInputKeydown"
      @change="handleSearch"
    />
    <slot />
    <div
      class="static-input-btn"
      @click="handleChecked"
    >
      {{ $t('添加至列表') }}
    </div>
  </div>
</template>
<script>
import { debounce } from 'throttle-debounce';

export default {
  name: 'StaticInput',
  props: {
    defaultText: String,
    type: String,
  },
  data() {
    return {
      ipMatch: /^(\d{1,2}|1\d\d|2[0-4]\d|25[0-5])(\.(\d{1,2}|1\d\d|2[0-4]\d|25[0-5])){3}$/,
      text: '',
      handleSearch() {},
    };
  },
  watch: {
    defaultText: {
      handler(v) {
        this.text = `${v}`.trim().replace(/(\r|\n){2,}/gm, '\n');
      },
      immediate: true,
    },
  },
  created() {
    this.handleSearch = debounce(300, this.handleKeywordChange);
  },
  methods: {
    handleInputKeydown(e) {
      if (e.key === 'enter') {
        return true;
      }
      if (e.ctrlKey || e.shilftKey || e.metaKey) {
        return true;
      }
      if (!e.key.match(/[0-9.s|,;]/) && !e.key.match(/(backspace|enter|ctrl|shift|tab)/im)) {
        e.preventDefault();
      }
    },
    handleChecked() {
      if (this.text?.length) {
        const ipList = this.text.split(/[\r\n]+/gm);
        const errList = new Set();
        const goodList = new Set();
        ipList.forEach(i => {
          const ip = i.trim();
          if (ip.match(this.ipMatch)) {
            goodList.add(ip);
          } else {
            ip.length > 0 && errList.add(ip);
          }
        });
        if (errList.size > 0) {
          this.text = Array.from(errList).join('\n');
        }
        if (goodList.size > 0 || errList.size > 0) {
          // this.$emit('checked', 'static-ip', Array.from(goodList).join('\n'), this.text)
          this.$emit('checked', this.type, { goodList: Array.from(goodList), errList: Array.from(errList) }, this.text);
        }
      }
    },
    handleKeywordChange(v) {
      this.$emit('change-input', v);
    },
  },
};
</script>
<style lang="scss" scoped>
.static-input {
  &-text {
    margin: 10px 0;
  }
  &-btn {
    min-width: 200px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    border: 1px solid #3a84ff;
    border-radius: 2px;
    color: #3a84ff;
    cursor: pointer;
    &:hover {
      background: #3a84ff;
      color: #fff;
    }
  }
}
</style>
