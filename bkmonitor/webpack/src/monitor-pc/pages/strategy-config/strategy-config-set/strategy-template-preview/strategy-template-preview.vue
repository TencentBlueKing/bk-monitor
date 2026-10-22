<!--
* Tencent is pleased to support the open source community by making
* 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
*
* Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
    width="860"
    :need-footer="true"
    :title="$t('告警模板预览')"
    :value.sync="show"
    @change="handleValueChange"
    @on-confirm="handleConfirm"
  >
    <template>
      <div v-bkloading="{ isLoading: loading }">
        <p class="preview-example-tip">
          {{ $t('预览使用固定示例数据，不是当前策略的查询值。') }}
        </p>
        <p
          v-if="previewError"
          class="preview-error"
          role="alert"
        >
          {{ previewError }}
        </p>
        <ul class="preview-tab">
          <li
            v-for="(item, index) in renderData"
            :key="index"
            class="preview-tab-item"
            :class="{ 'tab-active': tabActive === index }"
            @click="handleTabItemClick(item, index)"
          >
            {{ item.label }}
          </li>
        </ul>
        <preview-template :render-list="renderTemplate" />
      </div>
    </template>
  </monitor-dialog>
</template>
<script>
import { renderNoticeTemplate } from 'monitor-api/modules/action';
import { sanitizeMailHtml } from 'monitor-common/utils/xss';
import MonitorDialog from 'monitor-ui/monitor-dialog/monitor-dialog';
import { createNamespacedHelpers } from 'vuex';

import PreviewTemplate from './preview-template';

const { mapActions } = createNamespacedHelpers('strategy-config');
export default {
  name: 'StrategyTemplatePreview',
  components: {
    PreviewTemplate,
    MonitorDialog,
  },
  props: {
    // 是否显示
    dialogShow: Boolean,
    // 通知模板
    template: {
      type: String,
      required: true,
    },
    // 监控对象id
    scenario: {
      type: [String, Number],
      required: false,
    },
    previewItem: {
      type: Object,
      required: false,
    },
    strategyId: {
      type: [String, Number],
      default: 0,
    },
    bkBizId: {
      type: [String, Number],
      required: false,
    },
  },
  data() {
    return {
      show: false,
      renderData: [],
      tabActive: 0,
      loading: false,
      oldTemplate: '',
      oldScenario: null,
      oldPreviewContext: '',
      previewError: '',
      requestId: 0,
    };
  },
  computed: {
    renderTemplate() {
      const data = this.renderData[this.tabActive];
      const stripStyleTag = (message = '') => {
        let next = message;
        let prev;
        do {
          prev = next;
          next = next.replace(/<style[^>]*>[^<]*<\/style>/gim, '');
        } while (next !== prev);
        return next;
      };
      return (
        data?.messages.map(item => ({
          ...item,
          tabActive: this.tabActive,
          message: data.type === 'mail' ? sanitizeMailHtml(item.message) : stripStyleTag(item.message),
          type: data.type || '',
        })) || []
      );
    },
  },
  watch: {
    dialogShow: {
      handler(v) {
        this.show = v;
        if (!v) {
          this.requestId += 1;
          this.loading = false;
          return;
        }
        return this.loadPreview();
      },
      immediate: true,
    },
    template() {
      if (this.show) this.loadPreview();
    },
    scenario() {
      if (this.show) this.loadPreview();
    },
    previewItem: {
      handler() {
        if (this.show) this.loadPreview();
      },
      deep: true,
    },
    strategyId() {
      if (this.show) this.loadPreview();
    },
    bkBizId() {
      if (this.show) this.loadPreview();
    },
  },
  beforeDestroy() {
    this.handleConfirm();
  },
  methods: {
    ...mapActions(['getRenderNoticeTemplate']),
    async loadPreview() {
      const requestId = ++this.requestId;
      const template = this.template;
      const scenario = this.scenario;
      const params = scenario
        ? { scenario, template }
        : {
            template,
            ...(this.previewItem
              ? { preview_item: this.previewItem, strategy_id: Number(this.strategyId) || 0, bk_biz_id: this.bkBizId }
              : {}),
          };
      const previewContext = JSON.stringify(params);
      if (template && this.oldPreviewContext === previewContext) return;
      this.oldTemplate = '';
      this.oldPreviewContext = '';
      this.renderData = [];
      this.previewError = '';
      if (!template) {
        this.loading = false;
        return;
      }
      this.loading = true;
      try {
        const data = scenario
          ? await this.getRenderNoticeTemplate(params)
          : await renderNoticeTemplate(params);
        if (requestId !== this.requestId) return;
        this.renderData = data || [];
        this.tabActive = 0;
        this.oldTemplate = template;
        this.oldScenario = scenario;
        this.oldPreviewContext = previewContext;
      } catch (error) {
        if (requestId !== this.requestId) return;
        this.renderData = [];
        this.previewError = error?.error_details || error?.message || this.$t('模板预览失败，请稍后重试');
      } finally {
        if (requestId === this.requestId) this.loading = false;
      }
    },
    //  dialog显示变更触发
    handleValueChange(v) {
      if (!v) {
        this.requestId += 1;
        this.loading = false;
      }
      this.$emit('update:dialogShow', v);
    },
    // tabitem 点击触发事件
    handleTabItemClick(item, index) {
      this.tabActive = index;
    },
    handleConfirm() {
      this.show = false;
      this.handleValueChange(false);
    },
  },
};
</script>
<style lang="scss" scoped>
.preview-example-tip,
.preview-error {
  margin: 0 0 12px;
  line-height: 20px;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}

.preview-tab {
  display: flex;
  align-items: center;
  height: 36px;
  margin-top: 10px;
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
</style>
