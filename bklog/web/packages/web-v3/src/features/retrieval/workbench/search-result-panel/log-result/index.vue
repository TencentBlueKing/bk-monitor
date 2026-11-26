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
  <div class="original-log-panel" :style="{ '--bklog-result-tools-height': `${resultToolsHeight}px` }">
    <div ref="resultTools" :class="['original-log-panel-tools', { 'trace-log-panel': isMonitorTrace }]">
      <div class="left-operate">
        <div class="bk-button-group">
          <button
            type="button"
            v-for="type in ['original', 'table']"
            :key="type"
            class="option"
            :aria-pressed="contentType === type"
            @click="handleClickTableBtn(type)"
          >
            {{ type === 'table' ? $t('表格') : $t('原始') }}
          </button>
        </div>
        <ResultStorage />
      </div>
      <div class="tools-more">
        <div class="operation-icons">
          <div class="group-text light-search">
            <label class="light-search-label">{{ $t('高亮') }}</label>
            <bklogTagChoice
              :foucs-fixed="true"
              :on-tag-render="handleTagRender"
              class="bklog-v3-tag-highlight"
              focus-border-color="var(--td-border-level-2-color)"
              min-height="32px"
              max-width="400px"
              min-width="0px"
              :value="highlightValue"
              :placeholder="$t('输入后按 Enter...')"
              template="tag-input"
              @change="handleHighlightEnter"
            />
            <MatchMode
              v-if="!isMonitorApm && !isMonitorTrace"
              class="bklog-v3-match-mode"
              :border="true"
              :match-mode="matchMode"
              @change="handleMatchModeChange"
            />
          </div>

          <export-log
            v-if="!isMonitorTrace"
            :async-export-usable="asyncExportUsable"
            :async-export-usable-reason="asyncExportUsableReason"
            :index-set-list="indexSetList"
            :queue-status="queueStatus"
            :retrieve-params="retrieveParams"
            :total-count="totalCount"
          />
          <BkLogPopover
            ref="refFieldsSettingPopper"
            content-class="bklog-v3-select-dropdown"
            :options="tippyOptions"
            :before-hide="handleBeforeHide"
          >
            <button type="button" class="operation-icon" :aria-label="$t('字段设置')" :aria-expanded="showFieldsSetting">
              <span class="icon bklog-icon bklog-shezhi" aria-hidden="true" />
            </button>
            <template #content>
              <div class="fields-setting-container">
                <fields-setting
                  :field-alias-map="fieldAliasMap"
                  :is-show="showFieldsSetting"
                  :retrieve-params="retrieveParams"
                  config-type="list"
                  @cancel="cancelModifyFields"
                />
              </div>
            </template>
          </BkLogPopover>
        </div>
      </div>
    </div>

    <TableLog
      :content-type="contentType"
      :retrieve-params="retrieveParams"
    />
  </div>
</template>

<script>
import { mapState as mapPiniaState } from 'pinia';
import { ref } from 'vue';
import useResizeObserve from '@/shared/composables/use-resize-observe';


import { useApplicationStore } from '@/app/state/domains/application-store';
import { useRetrieveStore } from '@/app/state/domains/retrieve-store';


  // MONITOR_APP !== 'trace'
  import ExportLog from '../../result-comp/export-log.vue';
  // #else
  // #code const ExportLog = () => null;
  // #endif
  import MatchMode from '@/shared/global/match-mode/index';
  import BkLogPopover from '../../../../../shared/ui/bklog-popover/index';
  import RetrieveHelper, { RetrieveEvent } from '../../../retrieve-helper';
  import ResultStorage from '../../components/result-storage/index';
  import FieldsSetting from '../../result-comp/update/fields-setting';
  import bklogTagChoice from '../../search-bar/components/bklog-tag-choice';
  import TableLog from './log-result.vue';

  export default {
    components: {
      TableLog,
      FieldsSetting,
      ExportLog,
      bklogTagChoice,
      ResultStorage,
      BkLogPopover,
      MatchMode,
    },
    inheritAttrs: false,
    props: {
      retrieveParams: {
        type: Object,
        required: true,
      },
      totalCount: {
        type: Number,
        default: 0,
      },
      queueStatus: {
        type: Boolean,
        default: true,
      },
    },
    setup() {
      const resultTools = ref(null);
      const resultToolsHeight = ref(0);

      useResizeObserve(resultTools, ({ target }) => {
        resultToolsHeight.value = target.getBoundingClientRect().height;
      }, false);

      return { resultTools, resultToolsHeight };
    },
    data() {
      return {
        highlightValue: [],
        contentType: 'table',
        showFieldsSetting: false,
        showAsyncExport: false, // 异步下载弹窗
        exportLoading: false,
        isInitActiveTab: false,
        isMonitorTrace: window.__IS_MONITOR_TRACE__,
        isMonitorApm: window.__IS_MONITOR_APM__,
        matchMode: {
          caseSensitive: false,
          regexMode: false,
          wordMatch: false,
        },
        tippyOptions: {
          maxWidth: 1200,
          arrow: false,
          hideOnClick: false,
          appendTo: document.body,
          popperOptions: {
            strategy: 'fixed',
          },
          onShow: () => {
            this.showFieldsSetting = true;
          },
        },
        highlightTriggerHandler: null,
      };
    },
    computed: {
      showOriginalLog() {
        return this.contentType === 'original';
      },
      asyncExportUsable() {
        return this.$attrs['async-export-usable'];
      },
      asyncExportUsableReason() {
        return this.$attrs['async-export-usable-reason'];
      },
      filedSettingConfigID() {
        // 当前索引集的显示字段ID
        return useRetrieveStore().$state.filedSettingConfigID;
      },
      ...mapPiniaState(useApplicationStore, {
        unionIndexList: 'unionIndexList',
        isUnionSearch: 'isUnionSearch',
      }),
      ...mapPiniaState(useApplicationStore, {
        indexSetList: () => useRetrieveStore().indexSetList,
        indexSetQueryResult: 'indexSetQueryResult',
        indexFieldInfo: 'indexFieldInfo',
      }),

      routeIndexSet() {
        return this.$route.params.indexId;
      },

      fieldAliasMap() {
        return useApplicationStore().fieldAliasMap;
      },
      showFieldsConfigPopoverNum() {
        return useApplicationStore().showFieldsConfigPopoverNum;
      },
    },
    watch: {
      showFieldsConfigPopoverNum() {
        this.handleAddNewConfig();
      },
    },
    mounted() {
      this.contentType = localStorage.getItem('SEARCH_STORAGE_ACTIVE_TAB') || 'table';
      RetrieveHelper.setMarkInstance();

      this.highlightTriggerHandler = ({ event, value, values }) => {
        if (event !== 'mark') {
          return;
        }

        const nextValues = (Array.isArray(values) ? values : value !== null && value !== undefined ? [value] : [])
          .map(item => String(item ?? '').trim())
          .filter(item => item.length > 0 && !this.highlightValue.includes(item));

        if (!nextValues.length) {
          return;
        }

        this.highlightValue.push(...nextValues);
        RetrieveHelper.highLightKeywords(this.highlightValue.filter(w => w.length > 0));
      };
      RetrieveHelper.on(RetrieveEvent.HILIGHT_TRIGGER, this.highlightTriggerHandler);

      if (document.body.offsetHeight < 900) {
        this.$refs.refFieldsSettingPopper?.setProps({
          placement: 'auto',
          arrow: true,
        });
      }

    },
    unmounted() {
      if (this.highlightTriggerHandler) {
        RetrieveHelper.off(RetrieveEvent.HILIGHT_TRIGGER, this.highlightTriggerHandler);
        this.highlightTriggerHandler = null;
      }
      this.$refs.refFieldsSettingPopper?.hide?.();
      RetrieveHelper.destroyMarkInstance();
    },
    methods: {
      handleMatchModeChange(args) {
        Object.assign(this.matchMode, args);
        RetrieveHelper.setHighlightCaseSensitive(args.caseSensitive);
        RetrieveHelper.setHighlightRegExpMode(args.regexMode);
        RetrieveHelper.setHighlightAccuracy(args.wordMatch ? 'exactly' : 'partially');
        RetrieveHelper.highLightKeywords(this.highlightValue);
      },
      handleBeforeHide(e) {
        if (e.target?.closest?.('.bklog-v3-popover-tag')) {
          return false;
        }

        this.showFieldsSetting = false;
        return true;
      },
      handleTagRender(item, index) {
        const colors = RetrieveHelper.RGBA_LIST;
        const colorPair = colors[index % colors.length];
        return {
          style: {
            backgroundColor: colorPair[0],
            color: colorPair[1],
          },
        };
      },
      handleHighlightEnter(valList) {
        this.highlightValue = [];
        for (let i = 0; i < valList.length; i++) {
          const val = valList[i];
          this.highlightValue.push(val);
          // const values = val.split(/\s+/);
          // for (let j = 0; j < values.length; j++) {
          //   const value = values[j].replace(/^\s+|\s+$/g, '');
          //   if (value.length > 0) {
          //     this.highlightValue.push(value);
          //   }
          // }
        }

        RetrieveHelper.highLightKeywords(this.highlightValue);
      },

      cancelModifyFields() {
        this.closeDropdown();
      },
      closeDropdown() {
        if (!this.showFieldsSetting) {
          return;
        }
        this.$refs.refFieldsSettingPopper?.hide();
        this.showFieldsSetting = false;
      },

      handleAddNewConfig() {
        this.$refs.refFieldsSettingPopper.show();
      },
      handleClickTableBtn(active = 'table') {
        this.contentType = active;
        localStorage.setItem('SEARCH_STORAGE_ACTIVE_TAB', active);
        setTimeout(() => {
          RetrieveHelper.highLightKeywords(this.highlightValue);
        });
      },
    },
  };
</script>

<style lang="scss" scoped>
@use '@/shared/styles/mixins/flex.scss' as *;
@use '@/shared/styles/theme/components/contracts' as bklogControls;
  .original-log-panel {
    .original-log-panel-tools {
      position: sticky;
      top: var(--bklog-result-tools-sticky-top, var(--offset-search-bar, var(--top-searchbar-height, 0)));
      z-index: var(--bklog-z-sticky, 6);
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      row-gap: var(--bklog-space-4);
      padding: var(--bklog-space-12) var(--bklog-space-8) var(--bklog-space-12) 0;
      background: var(--td-bg-color-container);
      // border-bottom: 1px solid #dfe0e5;

      &.trace-log-panel {
        padding-top: 6px;
        padding-bottom: 6px;
      }
    }

    .tools-more {
      flex: 1 1 260px;
      min-width: 0;

      @include flex-center;

      .switch-label {
        margin-right: 2px;
        font-size: 12px;
        color: #63656e;
      }
    }

    .operation-icons {
      display: flex;
      flex: 1;
      align-items: center;
      justify-content: flex-end;
      min-width: 0;
      margin-left: 16px;

      > :not(.light-search) {
        flex-shrink: 0;
      }

      .operation-icon {
        display: flex;
        align-items: center;
        justify-content: center;
        width: var(--bklog-control-size-medium);
        height: var(--bklog-control-size-medium);
        margin-inline-start: calc(var(--bklog-space-8) + var(--bklog-space-2));
        padding: 0;
        border: 0;
        cursor: pointer;
        background-color: var(--td-bg-color-component);
        border-radius: var(--bklog-standard-control-radius);
        transition: background-color 0.2s;

        &:not(.disabled-icon):hover {
          background-color: var(--td-bg-color-component-hover);
        }

        &:not(.disabled-icon):active {
          background-color: var(--td-bg-color-component-active);
        }

        &:focus-visible {
          outline: var(--bklog-border-width) solid var(--td-brand-color);
          outline-offset: var(--bklog-space-2);
        }

        .bklog-icon {
          width: 16px;
          font-size: 16px;
          color: var(--td-text-color-secondary);
        }
      }

      .light-search {
        display: flex;
        flex: 0 1 auto;
        align-items: center;
        min-width: 0;
        font-size: 12px;
        color: var(--td-text-color-secondary);
        background: var(--td-bg-color-container);

        :deep(.bklog-v3-tag-highlight) {
          flex: 0 1 auto;
          width: 400px;
          min-width: 0;
          border-radius: 0;
        }

        :deep(.bklog-v3-tag-highlight .bklog-tag-choice-input) {
          width: 100%;
          min-width: 0;
          max-width: 100%;
        }

        .bklog-v3-match-mode {
          flex-shrink: 0;
        }

        label {
          display: flex;
          flex-shrink: 0;
          align-items: center;
          justify-content: center;
          width: 40px;
          height: 32px;
          padding: 0px 0px;
          color: var(--td-text-color-secondary);
          text-align: center;
          background: var(--td-bg-color-secondarycontainer);
          border-top: 1px solid var(--td-border-level-2-color);
          border-right: none;
          border-bottom: 1px solid var(--td-border-level-2-color);
          border-left: 1px solid var(--td-border-level-2-color);
          border-radius: var(--bklog-standard-control-radius) 0 0 var(--bklog-standard-control-radius);
        }
      }

      .disabled-icon {
        cursor: not-allowed;
        background-color: var(--td-bg-color-container);
        border-color: var(--td-component-stroke);

        &:hover,
        .bklog-icon {
          color: var(--td-text-color-disabled);
          border-color: var(--td-component-stroke);
        }
      }
    }

    .left-operate {
      flex: 0 0 auto;
      flex-wrap: nowrap;
      align-items: center;

      @include flex-justify(space-between);

      > div {
        flex-shrink: 0;
      }

      .bk-button-group {
        @include bklogControls.log-segmented-container;
        width: 104px;
      }

      .option {
        @include bklogControls.log-segmented-option;
        transition: background-color 0.3s;
      }

      .option[aria-pressed="true"] {
        @include bklogControls.log-segmented-selected;
      }

      .bklog-option-item {
        font-size: 12px;
        line-height: 20px;
        color: #63656e;
      }
    }

    .field-select {
      position: relative;
      width: 120px;
      margin-left: 16px;

      .icon-field-config {
        position: absolute;
        top: 4px;
        left: 4px;
        width: 18px;
      }

      :deep(.bk-select .bk-select-name) {
        padding: 0px 36px 0 30px;
      }
    }
  }

  .extension-add-new-config {
    cursor: pointer;

    @include flex-center();

    :last-child {
      margin-left: 4px;
      color: #63656e;
    }

    .icon-close-circle {
      margin-left: 4px;
      font-size: 14px;
      color: #979ba5;
      transform: rotateZ(45deg);
    }
  }
</style>
<style lang="scss">
  .json-depth-num.json-depth-num-input {
    &.t-input__wrap {
      width: 96px;

      .bk-input-number {
        input {
          &.t-input__inner {
            height: 26px;
          }
        }
      }
    }
  }

  body.no-user-select {
    user-select: none;
  }

  .bklog-v3-match-mode {
    box-sizing: border-box;
    height: var(--bklog-control-size-medium);
    padding-inline-start: calc(var(--bklog-space-4) + var(--bklog-space-2));
  }

  .bklog-v3-select-dropdown {
    z-index: var(--bklog-z-overlay);
  }
</style>
