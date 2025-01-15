<!-- eslint-disable vue/no-deprecated-dollar-listeners-api -->
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
  <div>
    <bk-table
      ref="resultTable"
      :class="['king-table original-table', { 'is-wrap': isWrap }]"
      :data="tableList"
      :outer-border="false"
      :show-header="false"
      @header-dragend="handleHeaderDragend"
      @row-click="tableRowClick"
    >
      <!-- 展开详情 -->
      <bk-table-column
        width="30"
        align="center"
        type="expand"
      >
        <template #default="{ $index }">
          <expand-view
            v-bind="$attrs"
            :data="originTableList[$index]"
            :list-data="tableList[$index]"
            :retrieve-params="retrieveParams"
            :total-fields="totalFields"
            :visible-fields="visibleFields"
            @menu-click="handleMenuClick"
          >
          </expand-view>
        </template>
      </bk-table-column>
      <!-- 显示字段 -->
      <template>
        <bk-table-column
          :width="originFieldWidth"
          class-name="original-time"
        >
          <template #default="{ row }">
            <span
              class="time-field"
              :title="isWrap ? '' : getOriginTimeShow(row[timeField])"
            >
              {{ getOriginTimeShow(row[timeField]) }}
            </span>
          </template>
        </bk-table-column>
        <bk-table-column :class-name="`original-str${isWrap ? ' is-wrap' : ''}`">
          <!-- eslint-disable-next-line -->
          <template slot-scope="{ row, column, $index }">
            <div :class="['str-content', 'origin-str', { 'is-limit': getLimitState($index) }]">
              <!-- eslint-disable-next-line vue/no-v-html -->
              <!-- <span>{{ JSON.stringify(row) }}</span> -->
              <original-light-height
                :is-wrap="isWrap"
                :operator-config="operatorConfig"
                :origin-json="row"
                :visible-fields="getShowTableVisibleFields"
                @menu-click="({ option, isLink }) => handleMenuClick(option, isLink)"
              />
              <template v-if="!isLimitExpandView">
                <p
                  v-if="!cacheExpandStr.includes($index)"
                  class="show-whole-btn"
                  @click.stop="handleShowWhole($index)"
                >
                  {{ $t('展开全部') }}
                </p>
                <p
                  v-else
                  class="hide-whole-btn"
                  @click.stop="handleHideWhole($index)"
                >
                  {{ $t('收起') }}
                </p>
              </template>
            </div>
          </template>
        </bk-table-column>
      </template>
      <!-- 操作按钮 -->
      <bk-table-column
        v-if="showHandleOption"
        :label="$t('操作')"
        :resizable="false"
        :width="getOperatorToolsWidth"
        align="right"
        fixed="right"
      >
        <!-- eslint-disable-next-line -->
        <template slot-scope="{ row, column, $index }">
          <operator-tools
            :handle-click="event => handleClickTools(event, row, operatorConfig)"
            :index="$index"
            :operator-config="operatorConfig"
            :row-data="row"
            log-type="origin"
          />
        </template>
      </bk-table-column>
      <!-- 初次加载骨架屏loading -->
      <template
        v-if="tableLoading"
        #empty
      >
        <bk-table-column>
          <retrieve-loader
            :is-original-field="true"
            :visible-fields="getShowTableVisibleFields"
            is-loading
          >
          </retrieve-loader>
        </bk-table-column>
      </template>
      <template
        v-else
        #empty
      >
        <empty-view
          v-bind="$attrs"
          v-on="$listeners"
        />
      </template>
      <!-- 下拉刷新骨架屏loading -->
      <template
        v-if="tableList.length && getShowTableVisibleFields.length && isPageOver"
        #append
      >
        <retrieve-loader
          :is-original-field="true"
          :is-page-over="isPageOver"
          :visible-fields="getShowTableVisibleFields"
        >
        </retrieve-loader>
      </template>
    </bk-table>
  </div>
</template>

<script>
  import resultTableMixin from '@/mixins/result-table-mixin';

  export default {
    name: 'OriginalList',
    mixins: [resultTableMixin],
    inheritAttrs: false,
    computed: {
      scrollContent() {
        return document.querySelector('.result-scroll-container');
      },
    },
    activated() {
      // keep-alive之后再进入到原始日志时需要重新布局表格
      this.$refs.resultTable.doLayout();
    },
  };
</script>
<style lang="scss">
td {
  &.original-str {
    .cell {
      display: flex;
      text-overflow: unset;

        .str-content {
          &.origin-str {
            width: 100%;

            .origin-content {
              word-break: break-all;
              white-space: pre-line;
            }
          }
        }
      }
    }

    &.is-wrap {
      .cell {
        .str-content {
          &.origin-str {
            .origin-content {
              display: flex;
              flex-direction: column;
              flex-wrap: wrap;
            }
          }
        }
      }
    }
}
</style>
