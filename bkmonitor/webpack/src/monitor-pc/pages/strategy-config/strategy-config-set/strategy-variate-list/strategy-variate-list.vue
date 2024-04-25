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
  <monitor-dialog
    :value.sync="show"
    :title="$t('变量列表')"
    width="960"
    :need-footer="false"
    @on-confirm="handleConfirm"
    @change="handleValueChange"
  >
    <div class="variate-wrapper">
      <ul class="preview-tab">
        <li
          v-for="(tab, index) in variateList"
          :key="index"
          :class="{ 'tab-active': tabActive === index }"
          class="preview-tab-item"
          @click="tabActive = index"
        >
          {{ tab.name }}
        </li>
      </ul>
      <div class="variate-list">
        <bk-table
          class="variate-list-table"
          :data="tableData"
        >
          <bk-table-column
            min-width="200"
            :label="$t('变量名')"
          >
            <template #default="{ row }">
              {{ `{{${row.id}\}\}` }}
            </template>
          </bk-table-column>
          <bk-table-column
            :label="$t('含义')"
            prop="name"
          />
          <bk-table-column
            :label="$t('示例')"
            prop="description"
          />
        </bk-table>
        <div class="variate-list-desc">
          <h5 class="desc-title">
            {{ $t('说明') }}
          </h5>
          <div class="item-title">{{ $t('变量格式') }}:</div>
          <div class="item-desc">
            {{ descData['format'] || '--' }}
          </div>
          <div class="item-title">{{ $t('对象包含') }}:</div>
          <div class="item-desc">
            <template v-if="descData['object']">
              <div
                v-for="item in descData['object']"
                :key="item.id"
              >
                {{ item.id }} {{ item.name }}
              </div>
            </template>
            <template v-else> -- </template>
          </div>
          <div class="item-title">{{ $t('字段名') }}:</div>
          <div class="item-desc">
            {{ descData['field'] || '--' }}
          </div>
        </div>
        <div class="variate-list-mask" />
      </div>
    </div>
  </monitor-dialog>
</template>
<script>
import MonitorDialog from 'monitor-ui/monitor-dialog/monitor-dialog';

export default {
  name: 'StrategyVariateList',
  components: {
    MonitorDialog,
  },
  // 是否显示
  props: {
    dialogShow: Boolean,
    variateList: {
      type: Array,
      required: true,
      default: () => [],
    },
  },
  data() {
    return {
      show: false,
      tabActive: 0,
    };
  },
  computed: {
    tableData() {
      const tab = this.variateList[this.tabActive];
      return tab ? tab.items : [];
    },
    descData() {
      const tab = this.variateList[this.tabActive];
      return tab ? tab.description : {};
    },
  },
  watch: {
    dialogShow: {
      handler(v) {
        this.show = v;
      },
      immediate: true,
    },
  },
  beforeDestroy() {
    this.handleConfirm();
  },
  methods: {
    // dialog显示变更触发
    handleValueChange(v) {
      this.$emit('update:dialogShow', v);
    },
    handleConfirm() {
      this.show = false;
      this.$emit('update:dialogShow', false);
    },
  },
};
</script>
<style lang="scss" scoped>
.variate-wrapper {
  position: relative;
  height: 528px;
  // margin-bottom: -26px;
  margin-top: 10px;

  .preview-tab {
    display: flex;
    align-items: center;
    height: 36px;
    font-size: 14px;
    color: #63656e;
    border-bottom: 1px solid #dcdee5;

    &-item {
      display: flex;
      align-items: center;
      height: 100%;
      margin-right: 22px;
      margin-bottom: -1px;
      cursor: pointer;
      border-bottom: 2px solid transparent;

      &.tab-active {
        color: #3a84ff;
        border-bottom-color: #3a84ff;
      }

      &:hover {
        color: #3a84ff;
      }
    }
  }

  .variate-list {
    display: flex;
    margin-top: 10px;

    &-table {
      flex: 1;

      :deep(.bk-table-body-wrapper) {
        max-height: 435px;
        overflow-x: hidden;
        overflow-y: auto;
      }
    }

    &-desc {
      flex: 0 0 153px;
      padding: 15px 10px 15px 18px;
      font-size: 12px;
      color: #63656e;
      border: 1px solid #dcdee5;
      border-left: 0;
      border-radius: 0px 2px 0px 0px;

      .desc-title {
        margin: 0;
        font-weight: bold;
      }

      .item-title {
        margin-top: 16px;
        line-height: 16px;
      }

      .item-desc {
        margin-top: 6px;
        line-height: 16px;
        color: #979ba5;
        word-break: break-word;
      }
    }

    &-mask {
      position: absolute;
      right: 0;
      bottom: 0;
      left: 0;
      z-index: 9;
      height: 5px;
      background-color: #fff;
    }
  }
}
</style>
