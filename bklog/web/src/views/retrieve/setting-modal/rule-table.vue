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
  <div class="cluster-table">
    <rule-top-tools
      ref="ruleTopToolsRef"
      v-model="rulesList"
      @show-table-loading="showTableLoading()"
    />
    <div
      class="cluster-table"
      data-test-id="LogCluster_div_rulesTable"
    >
      <div class="table-row flbc">
        <div class="row-left">
          <div class="row-left-index">{{ $t('序号') }}</div>
          <div class="row-left-regular">{{ $t('正则表达式') }}</div>
        </div>
        <div class="row-right flbc">
          <div>{{ $t('占位符') }}</div>
          <div>{{ $t('操作') }}</div>
        </div>
      </div>

      <div
        v-if="rulesList.length > 0"
        v-bkloading="{ isLoading: tableLoading }"
      >
        <vue-draggable
          v-bind="dragOptions"
          v-model="rulesList"
        >
          <transition-group>
            <li
              v-for="(item, index) in rulesList"
              class="table-row table-row-li flbc"
              :key="item.__Index__"
            >
              <div class="row-left">
                <div class="row-left-index">
                  <span class="icon bklog-icon bklog-drag-dots"></span><span>{{ index }}</span>
                </div>
                <div class="regular-container">
                  <register-column
                    :context="Object.values(item)[0]"
                    :root-margin="'-180px 0px 0px 0px'"
                  >
                    <cluster-event-popover
                      :is-cluster="false"
                      :placement="'top'"
                      @event-click="() => handleMenuClick(item)"
                    >
                      <span class="row-left-regular"> {{ Object.values(item)[0] }}</span>
                    </cluster-event-popover>
                  </register-column>
                </div>
              </div>
              <div class="row-right flbc">
                <div>
                  <span
                    class="row-right-item"
                    :ref="`placeholder-${index}`"
                    >{{ Object.keys(item)[0] }}</span
                  >
                </div>
                <div class="rule-btn">
                  <bk-button
                    style="margin-right: 10px"
                    :disabled="!globalEditable"
                    theme="primary"
                    text
                    @click="clusterAddRule(index)"
                  >
                    {{ $t('添加') }}
                  </bk-button>
                  <bk-button
                    style="margin-right: 10px"
                    :disabled="!globalEditable"
                    theme="primary"
                    text
                    @click="clusterEdit(index)"
                  >
                    {{ $t('编辑') }}
                  </bk-button>
                  <bk-popover
                    ref="deletePopoverRef"
                    ext-cls="config-item"
                    :tippy-options="tippyOptions"
                  >
                    <bk-button
                      :disabled="!globalEditable"
                      theme="primary"
                      text
                    >
                      {{ $t('删除') }}
                    </bk-button>
                    <template #content>
                      <div>
                        <div class="popover-slot">
                          <span>{{ $t('确定要删除当前规则？') }}</span>
                          <div class="popover-btn">
                            <bk-button
                              text
                              @click="clusterRemove(index)"
                            >
                              {{ $t('确定') }}
                            </bk-button>
                            <bk-button
                              theme="danger"
                              text
                              @click="handleCancelDelete(index)"
                            >
                              {{ $t('取消') }}
                            </bk-button>
                          </div>
                        </div>
                      </div>
                    </template>
                  </bk-popover>
                </div>
              </div>
            </li>
          </transition-group>
        </vue-draggable>
      </div>
      <div
        v-else
        class="no-cluster-rule"
      >
        <empty-status
          :show-text="false"
          empty-type="empty"
        >
          <div>{{ $t('暂无聚类规则') }}</div>
        </empty-status>
      </div>
    </div>
    <!-- 原始日志 -->
    <div
      :class="{ 'debug-container': true, 'is-hidden': !isClickAlertIcon }"
      v-bk-clickoutside="handleClickOutSide"
    >
      <div
        class="debug-tool"
        @click="handleClickDebugButton"
      >
        <i :class="{ 'bk-icon icon-play-shape': true, 'is-active': isClickAlertIcon }"></i>
        <span>{{ $t('调试工具') }}</span>
      </div>

      <div class="debug-input-box">
        <bk-alert
          v-if="isChangeRule"
          type="warning"
          :title="$t('当前聚类规则有更变，请调试后进行保存')"
        ></bk-alert>
        <div class="fl-jfsb mt18">
          <p style="height: 32px">{{ $t('原始日志') }}</p>
          <bk-button
            style="min-width: 48px"
            :class="logOriginal !== '' && !!rulesList.length ? 'btn-hover' : ''"
            :disabled="!globalEditable || !logOriginal || !rulesList.length"
            :loading="debugRequest"
            size="small"
            @click="debugging"
          >
            {{ $t('调试') }}
          </bk-button>
        </div>

        <div class="log-style">
          <bk-input
            :input-style="{
              'background-color': '#313238',
              height: '100px',
              'line-height': '24px',
              color: '#C4C6CC',
              borderRadius: '2px',
            }"
            v-model.trim="logOriginal"
            :disabled="!globalEditable || logOriginalRequest"
            :rows="3"
            :type="'textarea'"
            placeholder=" "
          >
          </bk-input>
        </div>
        <!-- 效果 -->
        <div class="mt18">
          <p style="height: 32px">{{ $t('效果预览') }}</p>
          <div
            class="effect-container"
            v-bkloading="{ isLoading: debugRequest, size: 'mini' }"
          >
            <text-highlight
              style="word-break: break-all"
              class="monospace-text"
              :queries="getHeightLightList(effectOriginal)"
            >
              {{ effectOriginal }}
            </text-highlight>
          </div>
        </div>
        <div
          class="fl-jfsb"
          style="margin-top: 10px"
        >
          <span></span>
          <div v-if="isChangeRule">
            <bk-button
              :theme="'primary'"
              :class="logOriginal !== '' && !!rulesList.length ? 'btn-hover' : ''"
              :disabled="!globalEditable || !logOriginal || !rulesList.length || !effectOriginal"
              :loading="submitLading"
              @click="submitRuleChange"
            >
              {{ $t('保存') }}
            </bk-button>
            <bk-button @click="() => (isClickAlertIcon = false)">
              {{ $t('取消') }}
            </bk-button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
<script>
import { copyMessage, base64Encode } from '@/common/util';
import EmptyStatus from '@/components/empty-status';
import RegisterColumn from '@/views/retrieve/result-comp/register-column';
import ClusterEventPopover from '@/views/retrieve/result-table-panel/log-clustering/components/cluster-event-popover';
import TextHighlight from 'vue-text-highlight';
import VueDraggable from 'vuedraggable';
import RuleTopTools from './component/rule-top-tools.vue';

export default {
  components: {
    VueDraggable,
    ClusterEventPopover,
    RegisterColumn,
    EmptyStatus,
    TextHighlight,
    RuleTopTools,
  },
  props: {
    globalEditable: {
      type: Boolean,
      default: true,
    },
    tableStr: {
      type: String,
      require: true,
    },
    cleanConfig: {
      type: Object,
      require: true,
    },
    submitLading: {
      type: Boolean,
      default: true,
    },
  },
  data() {
    return {
      rulesList: [],
      tableLoading: false,
      logOriginal: '', // 日志源
      effectOriginal: '',
      isShowAddRule: false, // 是否展开添加规则弹窗
      editRulesIndex: 0, // 当前编辑的index
      isDetection: false, // 是否在检测
      debugRequest: false, // 调试中
      isClickAlertIcon: false,
      isChangeRule: false,
      logOriginalRequest: false, // 原始日志是否正在请求
      isFirstInitLogOrigin: false, // 是否第一次点击调试工具按钮
      dragOptions: {
        animation: 150,
        tag: 'ul',
        handle: '.bklog-drag-dots',
        'ghost-class': 'sortable-ghost-class',
      },
      tippyOptions: {
        placement: 'bottom',
        trigger: 'click',
        theme: 'light',
        interactive: true,
      },
    };
  },
  watch: {
    tableStr: {
      handler(val) {
        this.rulesList = this.$refs.ruleTopToolsRef.base64ToRuleArr(val);
      },
    },
    debugRequest(val) {
      this.$emit('debug-request-change', val);
    },
  },
  beforeDestroy() {
    this.$emit('debug-request-change', false);
  },
  methods: {
    clusterEdit(index) {
      this.$refs.ruleTopToolsRef.clusterEdit(index);
    },
    clusterAddRule(index) {
      this.$refs.ruleTopToolsRef.clusterAddRule(index);
    },
    handleCancelDelete(index) {
      this.$refs.deletePopoverRef[index].hideHandler();
    },
    clusterRemove(index) {
      this.rulesList.splice(index, 1);
      this.showTableLoading();
    },
    ruleArrToBase64(arr = []) {
      arr.length === 0 && (arr = this.rulesList);
      try {
        const ruleNewList = arr.reduce((pre, cur) => {
          const key = Object.keys(cur)[0];
          const val = Object.values(cur)[0];
          const rulesStr = JSON.stringify(`${key}:${val}`);
          pre.push(rulesStr);
          return pre;
        }, []);
        const ruleArrStr = `[${ruleNewList.join(' ,')}]`;
        return base64Encode(ruleArrStr);
      } catch (error) {
        return '';
      }
    },
    debugging() {
      this.debugRequest = true;
      this.effectOriginal = '';
      const predefinedVariables = this.ruleArrToBase64(this.rulesList);
      const query = {
        input_data: this.logOriginal,
        predefined_varibles: predefinedVariables,
      };
      this.$http
        .request('/logClustering/debug', { data: { ...query } })
        .then(res => {
          this.effectOriginal = res.data;
        })
        .finally(() => {
          this.debugRequest = false;
        });
    },
    handleClickDebugButton() {
      this.isClickAlertIcon = !this.isClickAlertIcon;
      // 请求了一次原始日志后就不再请求
      if (!this.isFirstInitLogOrigin) {
        this.getLogOriginal();
      }
      this.isFirstInitLogOrigin = true;
    },
    /**
     * @desc: 获取原始日志内容
     */
    getLogOriginal() {
      const {
        extra: { collector_config_id: collectorConfigId },
      } = this.cleanConfig;
      if (!collectorConfigId) return;
      this.logOriginalRequest = true;
      this.$http
        .request('source/dataList', {
          params: {
            collector_config_id: collectorConfigId,
          },
        })
        .then(res => {
          if (res.data?.length) {
            const data = res.data[0];
            this.logOriginal = data.etl.data || '';
          }
        })
        .catch(() => {})
        .finally(() => {
          this.logOriginalRequest = false;
        });
    },
    handleMenuClick(item) {
      copyMessage(Object.values(item)[0]);
    },
    showTableLoading() {
      this.tableLoading = true;
      setTimeout(() => {
        this.tableLoading = false;
      }, 500);
    },
    getHeightLightList(str) {
      return str.match(/#.*?#/g) || [];
    },
    submitRuleChange() {
      this.$emit('submit-rule');
    },
    handleClickOutSide() {
      this.isClickAlertIcon = false;
    },
    getRuleType() {
      return this.$refs.ruleTopToolsRef.ruleType;
    },
    getTemplateID() {
      return this.$refs.ruleTopToolsRef.templateRule;
    },
    initSelect(v) {
      this.$refs.ruleTopToolsRef.initTemplateSelect(v);
    },
  },
};
</script>
<style lang="scss" scoped>
  @import '@/scss/mixins/flex.scss';

  .cluster-table {
    .debug-container {
      position: fixed;
      bottom: 0;
      left: 0;
      z-index: 999;
      width: 100%;
      min-width: 1460px;
      height: 460px;
      background: #fff;
      transition: bottom 0.3s;

      .debug-tool {
        display: flex;
        align-items: center;
        width: 100%;
        height: 40px;
        padding-left: 26px;
        font-size: 14px;
        color: #313238;
        cursor: pointer;
        background: #f0f1f5;
        box-shadow: 0 -1px 0 0 #dcdee5;

        .icon-play-shape {
          margin-right: 4px;
          font-size: 12px;
          transition: transform 0.3s;
          transform: scale(0.8);
        }

        .is-active {
          transform: scale(0.8) rotateZ(90deg);
        }
      }

      .debug-input-box {
        max-width: 1020px;
        padding: 15px 40px;
        margin: 0 auto;

        .debug-alert {
          margin: 8px 0;
        }
      }

      .effect-container {
        height: 100px;
        padding: 5px 10px;
        overflow-y: auto;
        font-size: 12px;
        line-height: 24px;
        color: #000;
        background: #fafbfd;
        border: 1px solid#DCDEE5;
        border-radius: 2px;
      }

      &.is-hidden {
        bottom: -418px;
      }
    }

    .table-row {
      min-height: 44px;
      font-size: 12px;
      background-color: #fafbfd;
      border-bottom: 1px solid #dcdee5;

      .icon {
        margin: 0 10px 0 4px;
      }

      .bklog-drag-dots {
        width: 16px;
        font-size: 14px;
        color: #979ba5;
        text-align: left;
        cursor: move;
        opacity: 0;
        transition: opacity 0.2s linear;
      }

      &.sortable-ghost-class {
        background: #eaf3ff;
        transition: background 0.2s linear;
      }

      &:hover {
        background: #eaf3ff;
        transition: background 0.2s linear;

        .bklog-drag-dots {
          opacity: 1;
          transition: opacity 0.2s linear;
        }
      }

      &.table-row-li {
        background-color: #fff;
        transition: background 0.3s;

        &:hover {
          background-color: #f0f1f5;
        }
      }

      .row-left {
        display: flex;
        align-items: center;

        .row-left-index {
          width: 80px;
          margin-left: 14px;
        }

        .regular-container {
          width: 600px;
          padding: 2px 10px 2px 2px;
          word-break: break-all;

          .row-left-regular {
            cursor: pointer;
          }
        }
      }

      .row-right > div {
        width: 120px;

        .row-right-item {
          display: inline-block;
          word-break: break-all;
        }

        .bk-button-text {
          font-size: 12px;
        }
      }
    }

    .no-cluster-rule {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      height: 200px;
      border-bottom: 1px solid #dcdee5;

      .icon-empty {
        font-size: 80px;
        color: #c3cdd7;
      }
    }

    .log-style {
      height: 100px;

      :deep(.bk-form-textarea:focus) {
        /* stylelint-disable-next-line declaration-no-important */
        background-color: #313238 !important;
        border-radius: 2px;
      }

      :deep(.bk-form-textarea[disabled]) {
        /* stylelint-disable-next-line declaration-no-important */
        background-color: #313238 !important;
        border-radius: 2px;
      }

      :deep(.bk-textarea-wrapper) {
        border: none;
      }
    }

    .fl-jfsb {
      @include flex-justify(space-between);
    }

    .mt18 {
      margin-top: 18px;
    }
  }

  .config-item {
    .popover-slot {
      padding: 8px 8px 4px;

      .popover-btn {
        margin-top: 6px;
        text-align: right;
      }
    }
  }

  .flbc {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
</style>
