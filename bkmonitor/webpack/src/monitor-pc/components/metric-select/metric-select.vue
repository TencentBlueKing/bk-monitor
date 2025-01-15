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
  <div class="metric-select-wrapper">
    <div class="select-wrapper">
      <bk-select
        v-model="metric.value"
        :clearable="false"
        :popover-min-width="250"
        :class="{ 'right-border-highlight': showLeftBorder }"
        @change="handleChange"
      >
        <bk-option
          v-for="(option, index) in data"
          :id="option.name"
          :key="index"
          style="font-size: 12px"
          :name="option.name"
        >
          <span class="name">{{ option.name }}</span>
          <span
            style="margin-right: 5px; color: #c4c6cc"
            class="alias"
            >{{ option.description }}</span
          >
        </bk-option>
      </bk-select>
    </div>
    <div class="search-wrapper">
      <bk-input
        v-model="metric.keyword"
        :placeholder="$t('指标')"
        @focus="showLeftBorder = true"
        @blur="showLeftBorder = false"
        @change="handleSearch"
      />
    </div>
  </div>
</template>
<script>
import { debounce } from 'throttle-debounce';

export default {
  name: 'MetricSelect',
  props: {
    data: {
      type: Array,
      default: () => [],
    },
  },
  data() {
    return {
      metric: {
        value: 'all metric',
        keyword: '',
        selectedData: [],
      },
      showLeftBorder: false,
      handleSearch() {},
    };
  },
  watch: {
    data: {
      handler(v) {
        if (v.length) {
          this.metric.selectedData = v[0].children;
        }
      },
      deep: true,
    },
  },
  created() {
    this.handleSearch = debounce(300, this.handleFilter);
  },
  methods: {
    handleChange(v) {
      let children = [];
      if (v === 'all metric') {
        children = this.data.length ? this.data[0].children : [];
      } else {
        const data = this.data.find(item => item.name === v);
        children = data ? data.children : [];
      }
      const result = children.filter(
        item => item.description.includes(this.metric.keyword) || item.name.includes(this.metric.keyword)
      );
      this.$emit('change', result, v);
    },
    handleFilter(v) {
      const result = this.metric.selectedData.filter(item => item.description.includes(v) || item.name.includes(v));
      this.$emit('change', result, v);
    },
  },
};
</script>
<style lang="scss" scoped>
.metric-select-wrapper {
  display: flex;

  .select-wrapper {
    font-size: 12px;

    :deep(.alias) {
      margin-right: 10px;
      color: #c4c6cc;
    }

    :deep(.bk-select) {
      max-width: 250px;
      border-radius: 2px 0 0 2px;
    }

    .right-border-highlight {
      border-right-color: #3c96ff;
    }
  }

  .search-wrapper {
    width: 170px;

    :deep(.bk-form-input) {
      border-left: 0;
      border-radius: 0 2px 2px 0;
    }
  }
}
</style>
