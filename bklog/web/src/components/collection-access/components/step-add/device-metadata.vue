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
      <bk-switcher v-model="switcherValue" size="large" theme="primary"></bk-switcher>
      <div class="switcher-tips">
        <i class="bk-icon icon-info-circle" />
        <span>
          {{
            this.$t("过滤器支持采集时过滤不符合的日志内容，请保证采集器已升级到最新版本")
          }}
        </span>
      </div>
    </div>
    <div v-if="switcherValue" class="filter-table-container">
      <!-- <bk-select :disabled="false" v-model="selectValue" searchable multiple display-tag>
        <bk-option-group
          v-for="(group, index) in groupList"
          :name="group.name"
          :key="index"
          :show-collapse="true"
          class="bklog-option-group"
          :show-count="false"
        >
          <bk-option
            v-for="option in group.children"
            :key="option.id"
            :id="option.id"
            :name="option.name"
          >
            <bk-checkbox
              :true-value="true"
              :false-value="false"
              v-model="option.isSelected"
              @click="selectOption"
            >
              {{ option.name }}
            </bk-checkbox>
          </bk-option>
        </bk-option-group>
      </bk-select> -->
      <bk-select
        ref="select"
        searchable
        multiple
        v-model="selectValue"
        :remote-method="remote"
        :display-tag="true"
        :show-empty="false"
        :auto-height="true"
        @tab-remove="handleValuesChange"
        @clear="handleClear"
      >
        <bk-big-tree
          :data="groupList"
          show-checkbox
          class="tree-select"
          ref="tree"
          :default-checked-nodes="selectValue"
          @check-change="handleCheckChange"
          @select-change="handleSelectChange"
          :default-expand-all="true"
          :check-on-click="true"
          :check-strictly="false"
        >
        </bk-big-tree>
      </bk-select>
    </div>
  </div>
</template>
<script>
export default {
  props: {},
  data() {
    return {
      switcherValue: true,
      selectValue: [],
      demo2: false,
      groupList: [
        {
          id: 1,
          name: "我是分组1",
          disable: true,
          children: [
            { id: "1-1", name: "hostname(主机名)", isSelected: false },
            { id: "1-2", name: "hostid(主机ID)", isSelected: false },
          ],
        },
        {
          id: 2,
          name: "我是分组2",
          disable: false,
          children: [
            { id: "2-1", name: "englishname(中文名)", isSelected: false },
            { id: "2-2", name: "englishname(中文名)", isSelected: false },
            { id: "2-3", name: "englishname(中文名)", isSelected: false },
            { id: "2-4", name: "englishname(中文名)", isSelected: false },
          ],
        },
      ],
    };
  },
  computed: {},
  mounted() {
    // this.getDeviceMetaData();
  },
  watch: {
    selectValue(val) {
      this.groupList.forEach((item) => {
        item.children.forEach((option) => {
          option.isSelected = val.includes(option.id);
        });
      });
    },
  },
  methods: {
    remote(keyword) {
      this.$refs.tree && this.$refs.tree.filter(keyword);
    },
    handleCheckChange(id, checked) {
      // 过滤最外层选中
      const list = id.filter((item) => item !== 1 && item !== 2);
      this.$refs.tree.setChecked(list);
      if (checked.level === 0) {
        // const list = id.filter((item) => item !== 1 && item !== 2);
        // this.$refs.tree.setChecked(list);
        return;
      }
      this.selectValue = [...id];
    },
    handleValuesChange(options) {
      this.$refs.tree &&
        this.$refs.tree.setChecked(options.id, { emitEvent: true, checked: false });
    },
    handleClear() {
      this.$refs.tree && this.$refs.tree.removeChecked({ emitEvent: false });
    },
    selectOption(option) {
      // this.$nextTick(() => {
      //   option.isgetDeviceMetaDataSelected = this.value.includes(option.id);
      // });
    },
    handleSelectChange(option) {
      console.log(option);
    },
    async getDeviceMetaData() {
      try {
        const res = await this.$http.request(
          "linkConfiguration/getSearchObjectAttribute"
        );
        console.log(res);
      } catch (e) {
        console.warn(e);
      } finally {
        this.tableLoading = false;
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
