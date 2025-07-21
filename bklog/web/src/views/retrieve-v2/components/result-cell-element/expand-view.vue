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
  <div class="expand-view-wrapper">
    <div class="view-tab">
      <div class="tab-left">
        <span
          :class="{ activeKv: activeExpandView === 'kv' }"
          @click="activeExpandView = 'kv'"
        >
          KV
        </span>
        <span
          :class="{ activeJson: activeExpandView === 'json' }"
          @click="activeExpandView = 'json'"
        >
          JSON
        </span>
      </div>
      <div class="tab-right">
        <span
          class="bklog-icon bklog-data-copy"
          v-bk-tooltips="{ content: $t('复制') }"
          @click="handleCopy"
        ></span>
      </div>
    </div>
    <div
      class="view-content kv-view-content"
      v-show="activeExpandView === 'kv'"
    >
      <kv-list
        :data="data"
        :field-list="totalFields"
        :kv-show-fields-list="kvShowFieldsList"
        :list-data="listData"
        :total-fields="totalFields"
        :visible-fields="visibleFields"
        @value-click="
          (type, content, isLink, field, depth) => $emit('value-click', type, content, isLink, field, depth)
        "
      />
    </div>
    <div
      style="padding: 2px 12px 10px 39px"
      class="view-content json-view-content"
      v-show="activeExpandView === 'json'"
    >
      <JsonFormatWrapper
        :data="jsonShowData"
        :deep="5"
      />
    </div>
  </div>
</template>

<script>
import { TABLE_LOG_FIELDS_SORT_REGULAR, copyMessage } from '@/common/util';
import { getFieldNameByField } from '@/hooks/use-field-name';
import tableRowDeepViewMixin from '@/mixins/table-row-deep-view-mixin';

import KvList from '../../result-comp/kv-list.vue';

export default {
  components: {
    KvList,
  },
  mixins: [tableRowDeepViewMixin],
  inheritAttrs: false,
  props: {
    data: {
      type: Object,
      default: () => {},
    },
    listData: {
      type: Object,
      default: () => {},
    },
    kvShowFieldsList: {
      type: Array,
      require: true,
    },
    rowIndex: {
      type: Number,
    },
  },
  data() {
    return {
      activeExpandView: 'kv',
    };
  },
  computed: {
    visibleFields() {
      return this.$store.state.visibleFields ?? [];
    },
    totalFields() {
      return this.$store.state.indexFieldInfo.fields ?? [];
    },
    kvListData() {
      return this.totalFields
        .filter(item => this.kvShowFieldsList.includes(item.field_name))
        .sort((a, b) => {
          const sortA = getFieldNameByField(a, this.$store).replace(TABLE_LOG_FIELDS_SORT_REGULAR, 'z');
          const sortB = getFieldNameByField(b, this.$store).replace(TABLE_LOG_FIELDS_SORT_REGULAR, 'z');
          return sortA.localeCompare(sortB);
        });
    },
    jsonList() {
      if (this.rowIndex === undefined) {
        return this.listData ?? this.data;
      }

      return this.$store.state.indexSetQueryResult?.origin_log_list?.[this.rowIndex] ?? this.listData ?? this.data;
    },
    jsonShowData() {
      return this.kvListData.reduce((pre, cur) => {
        const fieldName = getFieldNameByField(cur, this.$store);
        pre[fieldName] = this.tableRowDeepView(this.jsonList, cur.field_name, cur.field_type) ?? '';
        return pre;
      }, {});
    },
  },
  methods: {
    handleCopy() {
      copyMessage(JSON.stringify(this.jsonShowData));
    },
  },
};
</script>

<style lang="scss" scoped>
  .expand-view-wrapper {
    width: 100%;
    color: #313238;
    background-color: #f5f7fa;

    .view-tab {
      display: flex;
      justify-content: space-between;
      padding-right: 15px;
      font-size: 0;
      background-color: #f5f7fa;

      .tab-left {
        span {
          display: inline-block;
          width: 46px;
          height: 23px;
          font-size: 12px;
          line-height: 23px;
          color: #313238;
          text-align: center;
          cursor: pointer;

          border-top: 0;

          &:first-child {
            border-left: 0;
          }

          &.activeKv,
          &.activeJson {
            position: relative;
            font-size: 12px;
            font-weight: 700;
          }

          &.activeKv::after {
            position: absolute;
            top: -2px; /* 确保线条在元素的上方 */
            left: 14px;
            width: 17px;
            height: 2px;
            content: ''; /* 必须有content属性，即使为空 */
            background-color: #313238; /* 红色横线 */
          }

          &.activeJson::after {
            position: absolute;
            top: -2px; /* 确保线条在元素的上方 */
            left: 10px;
            width: 30px;
            height: 2px;
            content: ''; /* 必须有content属性，即使为空 */
            background-color: #313238; /* 红色横线 */
          }
        }
      }

      .tab-right {
        position: sticky;
        right: 20px;
        display: flex;
        align-items: center;

        .bklog-icon {
          font-size: 16px;
          color: #63656e;
          cursor: pointer;

          &:hover {
            color: #3a84ff;
          }
        }
      }
    }

    .view-content {
      padding: 2px 15px 14px 15px;
      background-color: #f5f7fa;

      :deep(.vjs-tree) {
        /* stylelint-disable-next-line declaration-no-important */
        font-size: var(--table-fount-size) !important;

        .vjs-tree-node {
          line-height: 22px;
          .vjs-value {
            &.vjs-value-string {
              white-space: pre-wrap;
            }
          }
        }
      }

      :deep(.kv-content) {
        .bklog-text-segment {
          &.bklog-root-field {
            max-height: fit-content;
          }
        }
      }
    }
  }
</style>
<style lang="scss">
  .json-view-content {
    .vjs-tree-brackets,
    .vjs-key {
      /* stylelint-disable-next-line declaration-no-important */
      color: #9d694c !important;
    }

    .vjs-value-string {
      color: #357a94;
    }

    .vjs-value-number {
      color: #2caf5e;
    }

    .vjs-indent-unit.has-line {
      border-left: 1px solid #bfcbd9;
    }
  }
</style>
