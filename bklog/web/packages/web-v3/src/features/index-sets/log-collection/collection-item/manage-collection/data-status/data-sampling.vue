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
  <section :aria-label="$t('数据采样')">
    <div :aria-busy="loading">
      <bk-table
        :loading="loading && !data.length"
        :data="data"
        :empty-text="$t('暂无内容')"
        :size="size"
      >
        <bk-table-column
          style="margin-top: 13px"
          width="120"
          :label="$t('序号')"
          align="center"
          type="index"
        >
        </bk-table-column>
        <bk-table-column
          native-cell-slot
          :label="$t('原始日志')"
        >
          <template #default="props">
            <button
              type="button"
              :aria-expanded="expandIndex === props.$index"
              :class="{ 'text-style': true, 'expand-style': expandIndex === props.$index }"
              @click="showClick(props.$index)"
              v-log-overflow-tips="{
                content: $t('点击展示全部'),
                disabled: expandIndex === props.$index,
                checkChildOverflow: true,
                delay: 1000,
              }"
            >
              <span
                v-for="(val, index) in props.row.etl.batch"
                :key="index"
                >{{ val }}</span
              >
            </button>
          </template>
        </bk-table-column>
        <bk-table-column
          native-cell-slot
          width="200"
          :label="$t('采集时间')"
        >
          <template #default="props">
            <div>{{ props.row.etl.datetime }}</div>
          </template>
        </bk-table-column>
        <bk-table-column
          native-cell-slot
          width="210"
          :label="$t('操作')"
        >
          <template #default="props">
            <div class="sample-row-actions">
              <TButton size="small" theme="primary" variant="text" @click="copyText(props.row.etl.batch, 'log')">
                {{ $t('复制') }}
              </TButton>
              <TButton size="small" theme="primary" variant="text" @click="openReportedLog(props.row)">
                {{ $t('查看上报日志') }}
              </TButton>
            </div>
          </template>
        </bk-table-column>
        <template #empty>
          <div class="bklog-table-empty-region">
            <empty-status
              v-if="!loading"
              :empty-type="failed ? '500' : 'empty'"
              :show-operation="failed"
              @operation="$emit('retry')"
            />
          </div>
        </template>
      </bk-table>
    </div>
    <bk-sideslider
      :is-show.sync="defaultSettings.isShow"
      :modal="false"
      :quick-close="true"
      width="min(596px, 100vw)"
      transfer
    >
      <template #header>
        <div class="sample-log-header">
          <span>{{ customSettings.title }}</span>
          <TButton class="sample-log-copy" :disabled="!hasReportedLog" theme="primary" variant="text" @click="copyText(JSON.stringify(jsonText))">
            {{ $t('复制') }}
          </TButton>
        </div>
      </template>
      <template #content>
        <div class="json-text-style">
          <JsonFormatWrapper
            v-if="hasReportedLog"
            :data="jsonText"
            :deep="5"
            class="log-report-json-wrapper"
          />
          <div v-else class="bklog-table-empty-region"><EmptyStatus /></div>
        </div>
      </template>
    </bk-sideslider>
  </section>
</template>

<script>
  import { Button as TButton } from 'tdesign-vue-next';
  import { copyMessage } from '@/shared/lib/util';
  import EmptyStatus from '@/shared/ui/empty-status/index';
  export default {
    components: {
      EmptyStatus,
      TButton,
    },
    emits: ['retry'],
    props: {
      failed: Boolean,
      loading: {
        type: Boolean,
        required: true,
      },
      data: {
        type: Array,
        required: true,
      },
    },
    data() {
      return {
        customSettings: {
          isShow: false,
          title: this.$t('上报日志详情'),
        },
        jsonText: '',
        defaultSettings: {
          isShow: false,
        },
        size: 'small',
        expandIndex: -1,
      };
    },
    computed: {
      hasReportedLog() {
        return !!this.jsonText && Object.keys(this.jsonText).length > 0;
      },
    },
    watch: {
      data() {
        this.expandIndex = -1;
      },
    },
    methods: {
      showClick(rowIndex) {
        if (this.expandIndex === rowIndex) {
          this.expandIndex = -1;
          return;
        }
        this.expandIndex = rowIndex;
      },
      openReportedLog(data) {
        this.defaultSettings.isShow = true;
        this.jsonText = data.origin;
      },
      copyText(data, val) {
        const text = val === 'log' ? data.map(line => `${line}\n`).join('') : data;
        copyMessage(text, this.$t('复制成功'));
      },
    },
  };
</script>

<style scoped lang="scss">
  .sample-row-actions {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--bklog-space-4);
  }

  .text-style {
    display: flex;
    flex-flow: column;
    align-items: stretch;
    width: 100%;
    max-height: 54px;
    padding: 0;
    overflow: hidden;
    font: inherit;
    line-height: 18px;
    color: inherit;
    text-align: start;
    cursor: pointer;
    background: transparent;
    border: 0;

    &:focus-visible {
      outline: var(--bklog-border-width) solid var(--td-brand-color);
      outline-offset: calc(-1 * var(--bklog-border-width));
    }

    span {
      flex-shrink: 0;
      overflow: hidden;
      font-size: 12px;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
  }

  .expand-style {
    max-height: fit-content;

    span {
      overflow-wrap: anywhere;
      white-space: pre-wrap;
    }
  }

  .sample-log-header {
    width: 100%;
    display: flex;
    gap: var(--bklog-space-8);
    align-items: center;
    justify-content: space-between;
    min-width: 0;
    color: var(--td-text-color-primary);

    > span {
      min-width: 0;
      overflow-wrap: anywhere;
    }

    > .sample-log-copy {
      flex-shrink: 0;
    }
  }

  .json-text-style {
    color: var(--td-text-color-secondary);
    background-color: var(--td-bg-color-container);
  }

  .log-report-json-wrapper {
    :deep(.json-pagination-wrapper) {
      max-height: none;
    }
  }
</style>
