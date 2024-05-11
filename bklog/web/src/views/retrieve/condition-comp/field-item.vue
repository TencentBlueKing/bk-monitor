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
  <li class="filed-item">
    <div
      class="filed-title"
      :class="{ expanded: isExpand }"
      @click="handleClickItem(fieldItem)"
    >
      <span :class="['icon log-icon icon-drag-dots', { 'hidden-icon': type === 'hidden' }]"></span>
      <!-- 三角符号 -->
      <span
        class="bk-icon"
        :class="{ 'icon-right-shape': showFieldsChart }"
      ></span>
      <!-- 字段类型对应的图标 -->
      <span
        v-bk-tooltips="{
          content: fieldTypeMap[fieldItem.field_type] && fieldTypeMap[fieldItem.field_type].name,
          disabled: !fieldTypeMap[fieldItem.field_type]
        }"
        class="field-type-icon"
        :class="getFieldIcon(fieldItem.field_type) || 'log-icon icon-unkown'"
      ></span>
      <!-- 字段名 -->
      <span class="overflow-tips field-name">
        <span
          v-bk-overflow-tips
          class=""
        >
          {{ showFieldAlias ? fieldAliasMap[fieldItem.field_name] : fieldItem.field_name }}
        </span>
        <span
          v-show="isShowFieldsCount"
          class="field-count"
          >({{ gatherFieldsCount }})</span
        >
        <template v-if="isUnionConflictFields(fieldItem.field_type)">
          <bk-popover
            theme="light"
            ext-cls="conflict-popover"
          >
            <i class="conflict-icon bk-icon icon-exclamation-triangle-shape"></i>
            <div slot="content">
              <p>{{ $t('该字段在以下索引集存在冲突') }}</p>
              <template>
                <bk-tag
                  v-for="(item, index) in unionConflictFieldsName"
                  :key="index"
                  >{{ item }}</bk-tag
                >
              </template>
            </div>
          </bk-popover>
        </template>
      </span>
      <!-- 聚合字段数量 -->
      <!-- 设置字段显示或隐藏 -->
      <div
        class="operation-text"
        @click.stop="handleShowOrHiddenItem"
      >
        {{ type === 'visible' ? $t('隐藏') : $t('显示') }}
      </div>
    </div>
    <!-- 显示聚合字段图表信息 -->
    <agg-chart
      v-if="showFieldsChart"
      v-show="isExpand"
      :retrieve-params="retrieveParams"
      :parent-expand="isExpand"
      :statistical-field-data="statisticalFieldData"
      :field-name="fieldItem.field_name"
      :field-type="fieldItem.field_type"
    />
  </li>
</template>

<script>
import { mapState, mapGetters } from 'vuex';
import AggChart from './agg-chart';

export default {
  components: {
    AggChart
  },
  props: {
    type: {
      type: String,
      default: 'visible',
      validator: v => ['visible', 'hidden'].includes(v)
    },
    fieldItem: {
      type: Object,
      default() {
        return {};
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
    statisticalFieldData: {
      type: Object,
      default() {
        return {};
      }
    },
    retrieveParams: {
      type: Object,
      required: true
    },
    visibleFields: {
      type: Array,
      default: () => []
    }
  },
  data() {
    return {
      isExpand: false
    };
  },
  computed: {
    ...mapState('globals', ['fieldTypeMap']),
    ...mapGetters({
      unionIndexList: 'unionIndexList',
      isUnionSearch: 'isUnionSearch',
      unionIndexItemList: 'unionIndexItemList'
    }),
    gatherFieldsCount() {
      // 聚合字段有多少个
      return Object.keys(this.statisticalFieldData).length;
    },
    // 显示融合字段统计比例图表
    showFieldsChart() {
      return Object.keys(this.statisticalFieldData).length && this.fieldItem.field_type !== 'text';
    },
    isShowFieldsCount() {
      return !['object', 'nested', 'text'].includes(this.fieldItem.field_type);
    },
    /** 冲突字段索引集名称*/
    unionConflictFieldsName() {
      return this.unionIndexItemList
        .filter(item => this.unionIndexList.includes(item.index_set_id))
        .map(item => item.indexName);
    }
  },
  methods: {
    getFieldIcon(fieldType) {
      return this.fieldTypeMap[fieldType] ? this.fieldTypeMap[fieldType].icon : 'log-icon icon-unkown';
    },
    // 点击字段行，展开显示聚合信息
    handleClickItem() {
      if (this.showFieldsChart) {
        this.isExpand = !this.isExpand;
      }
    },
    // 显示或隐藏字段
    handleShowOrHiddenItem() {
      // if (this.isDisabledHiddenField) return;
      this.$emit('toggleItem', this.type, this.fieldItem);
    },
    /** 联合查询并且有冲突字段 */
    isUnionConflictFields(fieldType) {
      return this.isUnionSearch && fieldType === 'conflict';
    }
  }
};
</script>

<style lang="scss" scoped>
@import '@/scss/mixins/overflow-tips.scss';

.filed-item {
  margin-bottom: 6px;

  .hidden-icon {
    &.icon-drag-dots {
      visibility: hidden;
    }
  }

  .icon-drag-dots {
    width: 16px;
    padding-left: 4px;
    font-size: 14px;
    color: #979ba5;
    text-align: left;
    cursor: move;
    opacity: 0;
    transition: opacity 0.2s linear;
  }

  &:hover {
    background-color: #f4f5f8;
    // transition: background .2s linear;

    .icon-drag-dots {
      opacity: 1;
      transition: opacity 0.2s linear;
    }
  }

  .filed-title {
    position: relative;
    display: flex;
    height: 26px;
    padding-right: 50px;
    cursor: pointer;
    border-radius: 2px;
    flex: 1;
    flex-shrink: 0;
    align-items: center;

    .bk-icon {
      width: 12px;
      margin: 0 5px;
      font-size: 12px;
      transition: transform 0.3s;
    }

    .field-type-icon {
      width: 12px;
      margin: 0 5px 0 0;
      font-size: 12px;
      color: #979ba5;
    }

    .field-name {
      display: flex;

      span:first-child {
        overflow: hidden;
        text-overflow: ellipsis;
      }
    }

    .conflict-icon {
      font-size: 14px;
      color: #ff9c01;
    }

    .icon-ext {
      width: 18px;
      transform: scale(0.8);
    }

    .field-count {
      padding: 0 4px;
      margin-left: 4px;
      text-align: center;
    }

    .operation-text {
      position: absolute;
      right: 0;
      display: none;
      width: 40px;
      color: #3a84ff;
      text-align: center;

      &:active {
        color: #2761dd;
      }

      &:hover {
        color: #699df4;
      }
    }

    // .disable-hidden {
    //   color: #979ba5;

    //   &:hover {
    //     color: #979ba5;
    //   }
    // }

    &:hover {
      background-color: #f4f5f8;

      .operation-text {
        display: block;
      }
    }

    &.expanded {
      background-color: #f0f1f5;

      .icon-right-shape {
        transform: rotate(90deg);
        transition: transform 0.3s;
      }
    }
  }
}

.conflict-popover {
  p {
    margin: 0 0 4px 6px;
    font-size: 12px;
    color: #63656e;
  }
}
</style>
