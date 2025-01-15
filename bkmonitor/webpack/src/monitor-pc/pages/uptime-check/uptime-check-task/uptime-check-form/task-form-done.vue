<!-- eslint-disable vue/no-v-html -->
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
  <article class="task-from-done">
    <section class="done-top">
      <div class="done-top-icon">
        <i
          class="icon-monitor"
          :class="currentStatusText.icon"
        />
      </div>
      <div class="done-top-title">
        {{ currentStatusText.title }}
      </div>
      <!-- eslint-disable-next-line vue/no-v-html -->
      <div
        v-if="status === 'error' && errorMsg"
        class="done-top-content"
        v-html="errorMsg"
      />
      <div class="done-top-operate">
        <bk-button
          class="mr10"
          @click="cancelUptimeCheckTask"
          >{{ currentStatusText.cancelText }}</bk-button
        >
        <bk-button
          v-if="status === 'error'"
          class="mr10"
          theme="primary"
          @click="handleEnforceSave"
          >{{ $t('强制保存') }}</bk-button
        >
        <bk-button
          v-if="showToEdit"
          theme="primary"
          @click="goToEdit"
          >{{ currentStatusText.confirmText }}</bk-button
        >
        <bk-button
          v-else
          theme="primary"
          @click="confirmUptimeCheckTask"
          >{{ currentStatusText.confirmText }}</bk-button
        >
      </div>
    </section>
    <section
      v-if="status === 'success' && tableData.length > 0"
      class="done-bottom"
    >
      <bk-table :data="tableData">
        <bk-table-column
          width="198"
          :label="$t('指标')"
          prop="label"
        />
        <bk-table-column
          width="311"
          :label="$t('详情')"
          prop="detail"
        />
        <bk-table-column
          :label="$t('操作')"
          :width="isEn ? 200 : 102"
        >
          <template #default="{ row }">
            <bk-button
              class="table-operate-button"
              :disabled="row.status === 0"
              theme="primary"
              text
              @click="goStrategy(row)"
            >
              {{ $t('前往配置策略') }}
            </bk-button>
          </template>
        </bk-table-column>
      </bk-table>
    </section>
  </article>
</template>
<script>
import { isEn } from '../../../../i18n/lang';

export default {
  name: 'UptimeCheckTaskDone',
  props: {
    // 拨测新增报错时显示
    errorMsg: String,
    editId: [String, Number],
    status: {
      type: String,
      default: 'success',
      validator(value) {
        return ['success', 'error'].includes(value);
      },
    },
    tableData: {
      type: Array,
      default: () => [],
    },
    type: {
      type: String,
      default: 'add',
      validator(value) {
        return ['add', 'edit'].includes(value);
      },
    },
  },
  data() {
    return {
      success: {
        add: {
          icon: 'icon-duihao icon-success',
          title: this.$t('创建拨测任务成功'),
          cancelText: this.$t('返回列表'),
          confirmText: this.$t('继续添加拨测任务'),
        },
        edit: {
          icon: 'icon-duihao icon-success',
          title: this.$t('编辑拨测任务成功'),
          cancelText: this.$t('返回列表'),
          confirmText: this.$t('继续添加拨测任务'),
        },
      },
      error: {
        add: {
          icon: 'icon-remind icon-error',
          title: this.$t('拨测任务创建失败'),
          cancelText: this.$t('放弃'),
          confirmText: this.$t('修改后重试'),
        },
        edit: {
          icon: 'icon-remind icon-error',
          title: this.$t('拨测任务编辑失败'),
          cancelText: this.$t('放弃'),
          confirmText: this.$t('修改后重试'),
        },
      },
      isEn,
    };
  },
  computed: {
    currentStatusText() {
      return this[this.status][this.type];
    },
    showToEdit() {
      return this.status === 'error' && this.editId && this.type === 'add';
    },
  },
  methods: {
    cancelUptimeCheckTask() {
      this.$emit('back-add');
      this.$router.push({
        name: 'uptime-check',
      });
    },
    confirmUptimeCheckTask() {
      this.status === 'success' ? this.$emit('clear-task-data', true) : this.$emit('clear-task-data', false);
    },
    goStrategy(row) {
      this.$router.push({
        name: 'strategy-config-add',
        params: {
          data: {
            where: [
              {
                key: 'task_id',
                method: 'eq',
                value: row.relatedId.toString(),
              },
            ],
            group_by: [],
            interval: 60,
            method: 'AVG',
            data_source_label: 'bk_monitor',
            data_type_label: 'time_series',
            metric_field: row.metric,
            metric_field_name: row.label,
            result_table_id: row.resultTableId,
            result_table_label: row.resultTableLabel,
            related_id: row.relatedId,
            related_name: row.relatedName,
          },
        },
      });
    },
    goToEdit() {
      this.$router.push({
        name: 'uptime-check-task-edit',
        params: {
          id: this.editId,
        },
      });
    },
    /* 强制保存 */
    handleEnforceSave() {
      this.$emit('enforce-save');
    },
  },
};
</script>
<style lang="scss" scoped>
@mixin horizontal-center {
  display: flex;
  flex-direction: column;
  align-items: center;
}

@mixin done-top-item($marginTop, $fontSize, $color) {
  margin-top: $marginTop;
  font-size: $fontSize;
  color: $color;
}

.task-from-done {
  @include horizontal-center;

  .done-top {
    @include horizontal-center;

    &-icon {
      margin-top: 54px;

      .icon-success {
        font-size: 50px;
        color: #2dcb56;
      }

      .icon-error {
        font-size: 50px;
        color: #ea3636;
      }
    }

    &-title {
      @include done-top-item(16px, 16px, #313238);
    }

    &-content {
      max-width: 500px;
      word-break: break-word;
      white-space: normal;

      @include done-top-item(12px, 12px, #63656e);
    }

    &-operate {
      margin-top: 19px;
    }
  }

  .done-bottom {
    margin-top: 40px;

    .table-operate-button {
      padding: 0;
    }
  }
}
</style>
