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
  <!-- eslint-disable vue/no-mutating-props -->
  <bk-dialog
    v-model="options.isShow"
    class="indicator-preview"
    :title="$t('预览')"
    width="960"
    header-position="left"
    :show-footer="false"
  >
    <div class="preview-container">
      <div class="preview-content">
        <div
          v-if="!options.isOfficial"
          class="hint-text"
        >
          <span> {{ $t('编辑/增加/删除/启动/停用指标？') }} </span>
          <span
            class="hint-here"
            @click="handelEditPlugin(options.pluginId)"
          >
            {{ $t('点击这里') }}
          </span>
        </div>
        <div class="preview-data">
          <right-panel
            v-for="(table, index) in options.data"
            :key="index"
            class="data-container"
            :collapse="table.expand"
            need-border
            :class="{ 'no-bottom': table.expand }"
            @change="handleToggleTable(index, table.expand)"
          >
            <div
              slot="title"
              class="data-header"
            >
              <span class="data-name">{{ table.table_name }}（{{ table.table_desc }}）</span>
            </div>
            <bk-table
              class="data-table"
              :data="table.fields"
            >
              <bk-table-column
                :label="$t('指标/维度')"
                width="150"
              >
                <template slot-scope="props">
                  <div class="row-header">
                    {{ props.row.monitor_type === 'metric' ? `${$t('指标')}(Metric)` : `${$t('维度')}(Dimension)` }}
                  </div>
                </template>
              </bk-table-column>
              <bk-table-column :label="$t('英文名')">
                <template slot-scope="props">
                  <div
                    :title="props.row.name"
                    class="name"
                  >
                    {{ props.row.name }}
                  </div>
                </template>
              </bk-table-column>
              <bk-table-column :label="$t('别名')">
                <template slot-scope="props">
                  <div
                    :title="props.row.description"
                    class="alias"
                  >
                    {{ props.row.description }}
                  </div>
                </template>
              </bk-table-column>
              <bk-table-column
                :label="$t('类型')"
                width="80"
              >
                <template slot-scope="props">
                  <div class="type">
                    {{ props.row.type }}
                  </div>
                </template>
              </bk-table-column>
              <bk-table-column
                :label="$t('单位')"
                width="80"
              >
                <template slot-scope="props">
                  <div class="unit">
                    {{ props.row.unit ? props.row.unit : '--' }}
                  </div>
                </template>
              </bk-table-column>
              <bk-table-column
                :label="$t('启/停')"
                width="100"
              >
                <template slot-scope="props">
                  <div
                    v-if="props.row.monitor_type === 'metric'"
                    :class="props.row.is_active ? 'start' : 'stop'"
                  >
                    {{ props.row.is_active ? $t('已启用') : $t('已停用') }}
                  </div>
                  <div v-else>--</div>
                </template>
              </bk-table-column>
            </bk-table>
          </right-panel>
        </div>
      </div>
    </div>
  </bk-dialog>
</template>

<script>
import RightPanel from '../../../../components/ip-select/right-panel';

export default {
  name: 'IndicatorPreview',
  components: {
    RightPanel,
  },
  props: {
    options: {
      type: Object,
      default: () => ({
        isShow: false,
        isOfficial: false,
        pluginId: '',
        data: [],
      }),
    },
  },
  watch: {
    'options.isShow'(v) {
      if (v && this.options.data.length) {
        this.handleToggleTable(0);
      }
    },
  },
  methods: {
    handleClose() {
      /* eslint-disable vue/no-mutating-props */
      this.options.isShow = false;
    },
    handleToggleTable(index, expand) {
      const { data } = this.options;
      data.forEach((item, i) => {
        this.$set(data[i], 'expand', index === i ? !expand : false);
      });
    },
    handelEditPlugin(id) {
      window.open(location.href.replace(location.hash, `#/plugin/setmetric/${id}`), '_blank');
    },
  },
};
</script>

<style lang="scss" scoped>
.indicator-preview {
  :deep(.bk-dialog-header) {
    padding: 3px 24px 15px;
  }

  .preview-container {
    height: 460px;

    .preview-content {
      .hint-text {
        height: 20px;
        margin-bottom: 12px;
        font-size: 12px;
        line-height: 20px;
        color: #63656e;

        .hint-here {
          color: #3a84ff;
          cursor: pointer;
          // margin-left: -6px;
        }
      }

      .preview-data {
        height: 445px;
        overflow-y: scroll;

        .data-container {
          margin-bottom: 10px;

          :deep(.right-panel-title) {
            background: #f0f1f5;
          }

          &.no-bottom {
            border-bottom: 0px;
          }

          :deep(.bk-table-outer-border) {
            border-top: 0;
            border-radius: 0 0 2px 2px;
          }

          .data-header {
            height: 40px;
            cursor: pointer;

            .data-name {
              height: 40px;
              margin-left: 3px;
              line-height: 40px;
            }
          }

          .start {
            color: #2dcb56;
          }

          .stop {
            color: #c4c6cc;
          }

          &:last-child {
            margin-bottom: 0;
          }
        }
      }
    }
  }
}
</style>
