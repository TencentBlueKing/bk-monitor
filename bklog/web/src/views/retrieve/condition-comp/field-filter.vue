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
  <div
    v-bkloading="{ isLoading: false, color: '#fbfbfb', zIndex: 0 }"
    class="field-filter-container"
  >
    <div class="form-container">
      <bk-input
        v-model.trim="searchKeyword"
        clearable
        class="king-input"
        right-icon="icon-search"
        :placeholder="$t('搜索字段名')"
        data-test-id="fieldFilter_input_searchFieldName"
        @change="handleSearch"
      ></bk-input>
      <bk-popover
        ref="filterPopover"
        trigger="click"
        placement="bottom-start"
        theme="light"
        animation="slide-toggle"
        :tippy-options="{ hideOnClick: false }"
        :offset="0"
        :distance="15"
        :on-show="handlePopoverShow"
        :on-hide="handlePopoverHide"
      >
        <slot name="trigger">
          <div
            class="filter-popover-trigger"
            data-test-id="fieldFilter_div_phrasesSearch"
            @click="closePopoverIfOpened"
          >
            <span class="bk-icon icon-funnel"></span>
            <span class="text">{{ $t('字段类型') }}</span>
            <span
              v-if="filterTypeCount"
              class="count"
              >{{ filterTypeCount }}</span
            >
          </div>
        </slot>
        <field-filter-popover
          slot="content"
          :value="showFilterPopover"
          @confirm="handleFilter"
          @closePopover="closePopoverIfOpened"
        />
      </bk-popover>
    </div>
    <div
      v-if="totalFields.length"
      class="fields-container is-selected"
    >
      <div class="title">{{ $t('已添加字段') }}</div>
      <!-- <ul class="filed-list"> -->
      <template v-if="visibleFields.length">
        <vue-draggable
          v-bind="dragOptions"
          v-model="dragVisibleFields"
          class="filed-list"
          @end="handleVisibleMoveEnd"
        >
          <transition-group>
            <template>
              <field-item
                v-for="item in visibleFields"
                v-show="item.filterVisible"
                :key="item.field_name"
                type="visible"
                :retrieve-params="retrieveParams"
                :field-alias-map="fieldAliasMap"
                :show-field-alias="showFieldAlias"
                :visible-length="visibleFields.length"
                :statistical-field-data="statisticalFieldsData[item.field_name]"
                :field-item="item"
                @toggleItem="handleToggleItem"
              />
            </template>
          </transition-group>
        </vue-draggable>
      </template>
      <template v-else>
        <span class="all-field-item">{{ $t('当前显示全部字段') }}</span>
      </template>
      <!-- </ul> -->
    </div>
    <div
      v-if="indexSetFields.length"
      class="fields-container not-selected"
    >
      <div class="title">{{ $t('索引字段') }}</div>
      <ul class="filed-list">
        <template>
          <field-item
            v-for="item in indexSetFields"
            v-show="item.filterVisible"
            :key="item.field_name"
            type="hidden"
            :retrieve-params="retrieveParams"
            :field-alias-map="fieldAliasMap"
            :show-field-alias="showFieldAlias"
            :statistical-field-data="statisticalFieldsData[item.field_name]"
            :field-item="item"
            @toggleItem="handleToggleItem"
          />
        </template>
      </ul>
    </div>
    <div
      v-if="builtInFields.length"
      class="fields-container not-selected"
    >
      <div class="title">{{ $t('label-内置字段').replace('label-', '') }}</div>
      <ul class="filed-list">
        <template>
          <field-item
            v-for="item in builtInFields"
            v-show="item.filterVisible"
            :key="item.field_name"
            type="hidden"
            :retrieve-params="retrieveParams"
            :field-alias-map="fieldAliasMap"
            :show-field-alias="showFieldAlias"
            :statistical-field-data="statisticalFieldsData[item.field_name]"
            :field-item="item"
            @toggleItem="handleToggleItem"
          />
        </template>
      </ul>
    </div>
  </div>
</template>

<script>
import FieldItem from './field-item';
import FieldFilterPopover from './field-filter-popover';
import VueDraggable from 'vuedraggable';
import { TABLE_LOG_FIELDS_SORT_REGULAR } from '@/common/util';

export default {
  components: {
    FieldItem,
    FieldFilterPopover,
    VueDraggable
  },
  props: {
    totalFields: {
      type: Array,
      default() {
        return [];
      }
    },
    visibleFields: {
      type: Array,
      default() {
        return [];
      }
    },
    sortList: {
      type: Array,
      default() {
        return [];
      }
    },
    fieldAliasMap: {
      type: Object,
      default() {
        return {};
      }
    },
    showFieldAlias: {
      type: Boolean,
      default: false
    },
    statisticalFieldsData: {
      type: Object,
      default() {
        return {};
      }
    },
    parentLoading: {
      type: Boolean,
      default: false
    },
    retrieveParams: {
      type: Object,
      required: true
    }
  },
  data() {
    return {
      showFilterPopover: false, // 字段类型过滤 popover 显示状态
      searchTimer: null,
      searchKeyword: '',
      polymerizable: '0', // 聚合
      fieldType: 'any', // 字段类型
      dragOptions: {
        animation: 150,
        tag: 'ul',
        handle: '.icon-drag-dots',
        'ghost-class': 'sortable-ghost-class'
      },
      dragVisibleFields: [],
      builtInHeaderList: ['log', 'ip', 'utctime', 'path']
    };
  },
  computed: {
    hiddenFields() {
      // 可选字段
      return this.totalFields.filter(item => !this.visibleFields.some(visibleItem => item === visibleItem));
    },
    indexSetFields() {
      const underlineFieldList = []; // 下划线的字段
      const otherList = []; // 其他字段
      const { indexHiddenFields } = this.hiddenFilterFields;
      indexHiddenFields.forEach(fieldItem => {
        if (/^[_]{1,2}/g.test(fieldItem.field_name)) {
          underlineFieldList.push(fieldItem);
          return;
        }
        otherList.push(fieldItem);
      });
      return this.sortHiddenList([otherList, underlineFieldList]);
    },
    hiddenFilterFields() {
      const builtInHiddenFields = [];
      const indexHiddenFields = [];
      this.hiddenFields.forEach(item => {
        if (item.field_type === '__virtual__' || item.is_built_in) {
          builtInHiddenFields.push(item);
          return;
        }
        indexHiddenFields.push(item);
      });
      return {
        builtInHiddenFields,
        indexHiddenFields
      };
    },
    builtInFields() {
      const headerList = [];
      const { builtInHiddenFields } = this.hiddenFilterFields;
      this.builtInHeaderList.forEach(item => {
        builtInHiddenFields.forEach(builtItem => {
          if (builtItem.field_name === item) {
            headerList.push(builtItem);
          }
        });
      });
      const filterHeaderBuiltFields = builtInHiddenFields.filter(
        item => !this.builtInHeaderList.includes(item.field_name)
      );
      return [...headerList, ...this.sortHiddenList([filterHeaderBuiltFields])];
    },
    filterTypeCount() {
      // 过滤的条件数量
      let count = 0;
      if (this.polymerizable !== '0') {
        count = count + 1;
      }
      if (this.fieldType !== 'any') {
        count = count + 1;
      }
      return count;
    },
    filedSettingConfigID() {
      // 当前索引集的显示字段ID
      return this.$store.state.retrieve.filedSettingConfigID;
    }
  },
  watch: {
    '$route.params.indexId'() {
      // 切换索引集重置状态
      this.polymerizable = '0';
      this.fieldType = 'any';
    },
    'visibleFields.length'() {
      this.dragVisibleFields = this.visibleFields.map(item => item.field_name);
    }
  },
  mounted() {
    document.getElementById('app').addEventListener('click', this.closePopoverIfOpened);
  },
  beforeDestroy() {
    document.getElementById('app').removeEventListener('click', this.closePopoverIfOpened);
  },
  methods: {
    handleSearch() {
      this.searchTimer && clearTimeout(this.searchTimer);
      this.searchTimer = setTimeout(this.filterListByCondition, 300);
    },
    // 字段类型过滤：可聚合、字段类型
    handleFilter({ polymerizable, fieldType }) {
      this.polymerizable = polymerizable;
      this.fieldType = fieldType;
      this.filterListByCondition();
    },
    // 按过滤条件对字段进行过滤
    filterListByCondition() {
      const { polymerizable, fieldType, searchKeyword } = this;
      [this.visibleFields, this.hiddenFields].forEach(fieldList => {
        fieldList.forEach(fieldItem => {
          fieldItem.filterVisible =
            fieldItem.field_name.includes(searchKeyword) &&
            !(
              (polymerizable === '1' && !fieldItem.es_doc_values) ||
              (polymerizable === '2' && fieldItem.es_doc_values) ||
              (fieldType === 'number' && !['long', 'integer'].includes(fieldItem.field_type)) ||
              (fieldType !== 'any' && fieldType !== 'number' && fieldItem.field_type !== fieldType)
            );
        });
      });
    },
    handlePopoverShow() {
      this.showFilterPopover = true;
    },
    handlePopoverHide() {
      this.showFilterPopover = false;
    },
    closePopoverIfOpened() {
      if (this.showFilterPopover) {
        this.$nextTick(() => {
          this.$refs.filterPopover.instance.hide();
        });
      }
    },
    handleVisibleMoveEnd() {
      this.$emit('fieldsUpdated', this.dragVisibleFields, undefined, false);
    },
    // 字段显示或隐藏
    async handleToggleItem(type, fieldItem) {
      const displayFieldNames = this.visibleFields.map(item => item.field_name);
      if (type === 'visible') {
        // 需要隐藏字段
        const index = this.visibleFields.findIndex(item => fieldItem.field_name === item.field_name);
        displayFieldNames.splice(index, 1);
      } else {
        // 需要显示字段
        displayFieldNames.push(fieldItem.field_name);
      }
      this.$emit('fieldsUpdated', displayFieldNames, undefined, false);
      if (!displayFieldNames.length) return; // 可以设置为全部隐藏，但是不请求接口
      this.$http
        .request('retrieve/postFieldsConfig', {
          params: { index_set_id: this.$route.params.indexId },
          data: { display_fields: displayFieldNames, sort_list: this.sortList, config_id: this.filedSettingConfigID }
        })
        .catch(e => {
          console.warn(e);
        });
    },
    sortHiddenList(list) {
      const sortList = [];
      list.forEach(item => {
        const sortItem = item.sort((a, b) => {
          const sortA = a.field_name.replace(TABLE_LOG_FIELDS_SORT_REGULAR, 'z');
          const sortB = b.field_name.replace(TABLE_LOG_FIELDS_SORT_REGULAR, 'z');
          return sortA.localeCompare(sortB);
        });
        sortList.push(...sortItem);
      });
      return sortList;
    }
  }
};
</script>

<style lang="scss" scoped>
.field-filter-container {
  font-size: 12px;
  line-height: 20px;
  color: #63656e;

  .is-selected {
    border-bottom: 1px solid #e1ecff;
  }

  .form-container {
    display: flex;
    height: 32px;
    margin-top: 15px;
    align-items: center;

    .king-input {
      width: 100%;
    }

    .gap {
      width: 1px;
      height: 100%;
      margin: 0 16px;
      background-color: #f0f1f5;
      flex-shrink: 0;
    }

    :deep(.bk-tooltip) {
      flex-shrink: 0;
    }

    .filter-popover-trigger {
      display: flex;
      height: 32px;
      margin-left: 16px;
      font-size: 12px;
      line-height: 18px;
      color: #3a84ff;
      cursor: pointer;
      align-items: center;

      &:active {
        color: #2761dd;
      }

      &:hover {
        color: #699df4;
      }

      .text {
        margin: 0 4px 0 2px;
      }

      .count {
        height: 18px;
        min-width: 18px;
        text-align: center;
        background-color: #e1ecff;
        border-radius: 50%;
      }
    }
  }

  .fields-container {
    margin-top: 20px;

    .title {
      margin-bottom: 7px;
    }

    .all-field-item {
      display: inline-block;
      height: 26px;
      margin: 0 0 7px 20px;
      line-height: 26px;
      color: #63656e;
    }
  }
}
</style>
