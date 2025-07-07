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
    width="860"
    :need-footer="true"
    :title="$t('告警模板预览')"
    :value.sync="show"
    @change="handleValueChange"
    @on-confirm="handleConfirm"
  >
    <template>
      <div v-bkloading="{ isLoading: loading }">
        <ul class="preview-tab">
          <li
            v-for="(item, index) in renderData"
            class="preview-tab-item"
            :class="{ 'tab-active': tabActive === index }"
            :key="index"
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
  },
  data() {
    return {
      show: false,
      renderData: [],
      tabActive: 0,
      loading: false,
      oldTemplate: '',
    };
  },
  computed: {
    renderTemplate() {
      const data = this.renderData[this.tabActive];
      return (
        data?.messages.map(item => ({
          ...item,
          tabActive: this.tabActive,
          message: (() => {
            let sanitizedMessage = item.message.replace(/\n/gim, '</br>');
            let previousMessage;
            do {
              previousMessage = sanitizedMessage;
              sanitizedMessage = sanitizedMessage.replace(/<style[^>]*>[^<]*<\/style>/gim, '');
            } while (sanitizedMessage !== previousMessage);
            return sanitizedMessage;
          })(),
          type: data.type || '',
        })) || []
      );
    },
  },
  watch: {
    dialogShow: {
      async handler(v) {
        this.show = v;
        if (v && this.template.length && this.oldTemplate !== this.template) {
          this.loading = true;
          this.oldTemplate = this.template;
          let data = null;
          // 策略告警模版
          if (this.scenario) {
            data = await this.getRenderNoticeTemplate({
              scenario: this.scenario,
              template: this.template,
            }).finally(() => (this.loading = false));
          } else {
            // 自愈套餐告警模版
            data = await renderNoticeTemplate({ template: this.template }).finally(() => (this.loading = false));
          }
          if (data) {
            this.renderData = data;
          }
        }
      },
      immediate: true,
    },
  },
  beforeDestroy() {
    this.handleConfirm();
  },
  methods: {
    ...mapActions(['getRenderNoticeTemplate']),
    //  dialog显示变更触发
    handleValueChange(v) {
      this.$emit('update:dialogShow', v);
    },
    // tabitem 点击触发事件
    handleTabItemClick(item, index) {
      this.tabActive = index;
    },
    handleConfirm() {
      this.show = false;
      this.$emit('update:dialogShow', false);
    },
  },
};
</script>
<style lang="scss" scoped>
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
