<!--
  - Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
  - Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
  - BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
  -
  - License for BK-LOG 蓝鲸日志平台:
  - -------------------------------------------------------------------
  -
  - Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
  - documentation files (the "Software"), to deal in the Software without restriction, including without limitation
  - the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
  - and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
  - The above copyright notice and this permission notice shall be included in all copies or substantial
  - portions of the Software.
  -
  - THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
  - LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
  - NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
  - WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
  - SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE
  -->

<template>
  <div class="expand-view-wrapper">
    <div class="view-tab">
      <span
        :class="{ active: activeExpandView === 'kv' }"
        @click="activeExpandView = 'kv'"
      >
        KV
      </span>
      <span
        :class="{ active: activeExpandView === 'json' }"
        @click="activeExpandView = 'json'"
      >
        JSON
      </span>
    </div>
    <div
      v-show="activeExpandView === 'kv'"
      class="view-content kv-view-content"
    >
      <kv-list
        v-bind="$attrs"
        :data="data"
        :list-data="listData"
        :field-list="totalFields"
        :total-fields="totalFields"
        :kv-show-fields-list="kvShowFieldsList"
        @menuClick="(val, isLink) => $emit('menuClick', val, isLink)"
      />
    </div>
    <div
      v-show="activeExpandView === 'json'"
      class="view-content json-view-content"
    >
      <VueJsonPretty
        :deep="5"
        :data="jsonShowData"
      />
    </div>
  </div>
</template>

<script>
import tableRowDeepViewMixin from '@/mixins/table-row-deep-view-mixin';
import KvList from '../../result-comp/kv-list.vue';
import { TABLE_LOG_FIELDS_SORT_REGULAR } from '@/common/util';

export default {
  components: {
    KvList
  },
  mixins: [tableRowDeepViewMixin],
  props: {
    data: {
      type: Object,
      default: () => {}
    },
    totalFields: {
      type: Array,
      required: true
    },
    listData: {
      type: Object,
      default: () => {}
    },
    kvShowFieldsList: {
      type: Array,
      require: true
    }
  },
  data() {
    return {
      activeExpandView: 'kv'
    };
  },
  computed: {
    kvListData() {
      return this.totalFields
        .filter(item => this.kvShowFieldsList.includes(item.field_name))
        .sort((a, b) => {
          const sortA = a.field_name.replace(TABLE_LOG_FIELDS_SORT_REGULAR, 'z');
          const sortB = b.field_name.replace(TABLE_LOG_FIELDS_SORT_REGULAR, 'z');
          return sortA.localeCompare(sortB);
        });
    },
    jsonShowData() {
      return this.kvListData.reduce((pre, cur) => {
        const showTableData = cur.field_type === '__virtual__' ? this.listData : this.data;
        pre[cur.field_name] = this.tableRowDeepView(showTableData, cur.field_name, cur.field_type) ?? '';
        return pre;
      }, {});
    }
  }
};
</script>

<style lang="scss" scoped>
.expand-view-wrapper {
  color: #313238;

  .view-tab {
    font-size: 0;
    background-color: #fafbfd;

    span {
      display: inline-block;
      width: 68px;
      height: 26px;
      font-size: 12px;
      line-height: 26px;
      text-align: center;
      cursor: pointer;
      background-color: #f5f7fa;
      border: 1px solid #eaebf0;
      border-top: 0;

      &:first-child {
        border-left: 0;
      }

      &.active {
        color: #3a84ff;
        background-color: #fafbfd;
        border: 0;
      }
    }
  }

  .view-content {
    padding: 10px 30px;
    background-color: #fafbfd;

    :deep(.vjs-tree) {
      /* stylelint-disable-next-line declaration-no-important */
      font-size: 12px !important;

      .vjs-value__string {
        white-space: pre-wrap;
        tab-size: 3;
      }
    }
  }
}
</style>
