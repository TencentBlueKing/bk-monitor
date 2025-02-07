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
  <div class="log-filter-container">
    <div class="switcher-container">
      <bk-switcher
        v-model="switcherValue"
        size="large"
        theme="primary"
        @change="switcherChange"
      ></bk-switcher>
      <div class="switcher-tips">
        <i class="bk-icon icon-info-circle" />
        <span>
          {{ this.$t("该设置可以将采集设备的元数据信息补充至日志中") }}
        </span>
      </div>
    </div>
    <div v-if="switcherValue" class="filter-table-container">
      <bk-select
        ref="select"
        searchable
        multiple
        selected-style="checkbox"
        v-model="selectValue"
        :remote-method="remote"
        :display-tag="true"
        :show-empty="false"
        :auto-height="true"
        @tab-remove="handleValuesChange"
        @clear="handleClear"
      >
        <bk-option
          v-for="option in groupList"
          :key="option.field"
          :id="option.field"
          :name="`${option.field}(${option.name})`"
        >
        </bk-option>
      </bk-select>
    </div>
  </div>
</template>
<script>
export default {
  props: {
    metadata: {
      type: Array,
    },
  },
  data() {
    return {
      switcherValue: false,
      selectValue: [],
      treeOption: {
        idKey: "field",
      },
      groupList: [],
    };
  },
  computed: {},
  mounted() {
    this.getDeviceMetaData();
    if (this.metadata.filter((item) => item.key).length) {
      this.switcherValue = true;
    }
  },
  watch: {
    selectValue(val) {
      this.emitExtraLabels();
    },
  },
  methods: {
    switcherChange(val) {
      if (!val) {
        this.$emit("extra-labels-change", []);
      }
    },
    remote(keyword) {
      this.$refs.treeRef && this.$refs.treeRef.filter(keyword);
    },

    handleValuesChange(options) {
      this.$refs.treeRef &&
        this.$refs.treeRef.setChecked(options.id, { emitEvent: true, checked: false });
    },
    handleClear() {
      this.$refs.treeRef && this.$refs.treeRef.removeChecked({ emitEvent: false });
    },
    emitExtraLabels() {
      const result = this.groupList.reduce((accumulator, item) => {
        if (this.selectValue.includes(item.field)) {
          accumulator.push({ key: item.field, value: item.key });
        }
        return accumulator;
      }, []);
      this.$emit("extra-labels-change", result);
    },
    // 获取元数据
    async getDeviceMetaData() {
      try {
        const res = await this.$http.request(
          "linkConfiguration/getSearchObjectAttribute"
        );
        const { scope, host } = res.data;
        this.groupList.push(
          ...scope.map((item) => {
            item.key = "scope";
            return item;
          })
        );
        this.groupList.push(
          ...host.map((item) => {
            item.key = "host";
            return item;
          })
        );
        this.selectValue = this.metadata.map((item) => item.key);
      } catch (e) {
        console.warn(e);
      }
    },
  },
};
</script>
<style lang="scss" scoped>
.filter-table-container {
  margin-top: 10px;
  width: 518px;
}
.bklog-option-group {
  :deep(.bk-option-group-name) {
    font-family: MicrosoftYaHei;
    font-size: 12px;
    color: #979ba5;
    border: none;
    margin-bottom: -5px !important;
  }
  :deep(.bk-checkbox-text) {
    font-family: MicrosoftYaHei;
    font-size: 12px;
    color: #4d4f56;
  }
  :deep(.bk-option-group-prefix) {
    display: none !important;
  }
}
.tree-select {
  :deep(.is-root) {
    font-family: MicrosoftYaHei;
    font-size: 12px;
    color: #979ba5;
    .node-checkbox {
      display: none;
    }
  }
  :deep(.node-content) {
    font-family: MicrosoftYaHei;
    font-size: 12px;
    color: #4d4f56;
  }
}
</style>
