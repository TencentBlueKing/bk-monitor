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
  <div class="original-log-panel">
    <div class="original-log-panel-tools">
      <div class="left-operate">
        <div class="bk-button-group">
          <span v-for="type in ['original', 'table']" class="option"
            :class="contentType === type ? 'option-selected' : ''" :key="type" @click="handleClickTableBtn(type)">
            {{ type === 'table' ? $t('表格') : $t('原始') }}
          </span>
        </div>
        <ResultStorage></ResultStorage>
      </div>
      <div class="tools-more">
        <div class="operation-icons">
          <div class="group-text light-search">
            <label class="light-search-label">{{ $t('高亮') }}</label>
            <bklogTagChoice :foucsFixed="true" :onTagRender="handleTagRender" class="bklog-v3-tag-highlight"
              focusBorderColor="#c4c6cc" minHeight="32px" :maxWidth="highlightStyle.width"
              :minWidth="highlightStyle.width" :value="highlightValue" :placeholder="$t('输入后按 Enter...')"
              template="tag-input" @change="handleHighlightEnter">
            </bklogTagChoice>
            <MatchMode class="bklog-v3-match-mode" :border="true" :match-mode="matchMode" @change="handleMatchModeChange"></MatchMode>
          </div>

          <export-log v-if="!isMonitorTrace" :async-export-usable="asyncExportUsable"
            :async-export-usable-reason="asyncExportUsableReason" :index-set-list="indexSetList"
            :queue-status="queueStatus" :retrieve-params="retrieveParams" :total-count="totalCount">
          </export-log>
          <BkLogPopover ref="refFieldsSettingPopper" content-class="bklog-v3-select-dropdown" :options="tippyOptions"
            :beforeHide="handleBeforeHide">
            <div class="operation-icon">
              <span style="font-size: 16px" class="icon bklog-icon bklog-shezhi"></span>
            </div>
            <template #content>
              <div class="fields-setting-container">
                <fields-setting :field-alias-map="fieldAliasMap" :is-show="true" :retrieve-params="retrieveParams"
                  config-type="list" @cancel="cancelModifyFields" />
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
import { mapGetters, mapState } from 'vuex';
import { debounce } from 'lodash-es';
// MONITOR_APP !== 'trace'
import ExportLog from '../../result-comp/export-log.vue';
// #else
// #code const ExportLog = () => null;
// #endif
import FieldsSetting from '../../result-comp/update/fields-setting';
import TableLog from './log-result.vue';
import RetrieveHelper, { RetrieveEvent } from '../../../retrieve-helper';
import bklogTagChoice from '../../search-bar/bklog-tag-choice';
import ResultStorage from '../../components/result-storage/index';
import BkLogPopover from '../../../../components/bklog-popover/index';
import { BK_LOG_STORAGE } from '@/store/store.type';
import useRetrieveEvent from '@/hooks/use-retrieve-event';
import MatchMode from '@/global/match-mode';

let logResultResizeObserver;
let logResultResizeObserverFn;

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
  data() {
    return {
      highlightValue: [],
      contentType: 'table',
      showFieldsSetting: false,
      showAsyncExport: false, // 异步下载弹窗
      exportLoading: false,
      isInitActiveTab: false,
      isMonitorTrace: window.__IS_MONITOR_TRACE__,
      highlightWidth: 200,
      matchMode: {
        caseSensitive: false,
        regexMode: false,
        wordMatch: false,
      },
      tippyOptions: {
        maxWidth: 1200,
        arrow: false,
        hideOnClick: false,
      },
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
      return this.$store.state.retrieve.filedSettingConfigID;
    },
    ...mapGetters({
      unionIndexList: 'unionIndexList',
      isUnionSearch: 'isUnionSearch',
    }),
    ...mapState({
      indexSetList: state => state.retrieve?.indexSetList ?? [],
      indexSetQueryResult: 'indexSetQueryResult',
      indexFieldInfo: 'indexFieldInfo',
    }),

    routeIndexSet() {
      return this.$route.params.indexId;
    },

    tableList() {
      return this.indexSetQueryResult.list ?? [];
    },

    fieldAliasMap() {
      return (this.indexFieldInfo.fields ?? []).reduce(
        (out, field) => ({ ...out, [field.field_name]: field.field_alias || field.field_name }),
        {},
      );
    },
    showFieldsConfigPopoverNum() {
      return this.$store.state.showFieldsConfigPopoverNum;
    },
    jsonFormat() {
      return this.$store.state.storage[BK_LOG_STORAGE.TABLE_JSON_FORMAT];
    },
    highlightStyle() {
      return {
        width: `${this.highlightWidth}px`,
      };
    },
  },
  watch: {
    showFieldsConfigPopoverNum() {
      this.handleAddNewConfig();
    },
    jsonFormat() {
      this.$nextTick(this.calcHighlightWidth);
    },
  },
  mounted() {
    this.contentType = localStorage.getItem('SEARCH_STORAGE_ACTIVE_TAB') || 'table';
    RetrieveHelper.setMarkInstance();

    const { addEvent } = useRetrieveEvent();
    addEvent(RetrieveEvent.HILIGHT_TRIGGER, ({ event, value }) => {
      if (event === 'mark' && !this.highlightValue.includes(value)) {
        this.highlightValue.push(...value.split(/\s+/));
        RetrieveHelper.highLightKeywords(this.highlightValue.filter(w => w.length > 0));
      }
    });

    if (document.body.offsetHeight < 900) {
      this.$refs.refFieldsSettingPopper?.setProps({
        placement: 'auto',
        arrow: true,
      });
    }

    logResultResizeObserverFn = debounce(this.calcHighlightWidth, 100);
    logResultResizeObserver = new ResizeObserver(logResultResizeObserverFn);
    logResultResizeObserver.observe(this.$el);
  },
  unmounted() {
    logResultResizeObserver?.unobserve(this.$el);
    logResultResizeObserver?.disconnect();
    logResultResizeObserver = null;
    logResultResizeObserverFn = null;
  },
  methods: {
    calcHighlightWidth() {
      const { offsetWidth } = this.$el;
      const leftWidth = this.$el.querySelector('.left-operate')?.offsetWidth ?? 0;
      const rightWidth = 200;
      const calcWidth = offsetWidth - leftWidth - rightWidth;
      if (calcWidth > 400) {
        this.highlightWidth = 400;
        return;
      }

      this.highlightWidth = offsetWidth - leftWidth - rightWidth;
    },
    handleMatchModeChange(args) {
      Object.assign(this.matchMode, args);
      RetrieveHelper.markInstance?.setCaseSensitive(args.caseSensitive);
      RetrieveHelper.markInstance?.setRegExpMode(args.regexMode);
      RetrieveHelper.markInstance?.setAccuracy(args.wordMatch ? 'exactly' : 'partially');
      RetrieveHelper.highLightKeywords(this.highlightValue);
    },
    handleBeforeHide(e) {
      if (e.target?.closest?.('.bklog-v3-popover-tag')) {
        return false;
      }

      return true;
    },
    handleTagRender(item, index) {
      const colors = RetrieveHelper.RGBA_LIST;
      return {
        style: {
          backgroundColor: colors[index % colors.length],
        },
      };
    },
    handleHighlightEnter(valList) {
      this.highlightValue = valList
        .map(v => v.split(/\s+/))
        .flat()
        .filter(w => w.length > 0);
      RetrieveHelper.highLightKeywords(this.highlightValue);
    },

    cancelModifyFields() {
      this.closeDropdown();
    },
    closeDropdown() {
      this.$refs.refFieldsSettingPopper?.hide();
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
@import '@/scss/mixins/flex.scss';

.original-log-panel {
  .original-log-panel-tools {
    display: flex;
    justify-content: space-between;
    padding: 0 6px 0 6px;
  }

  .tools-more {
    @include flex-center;

    .switch-label {
      margin-right: 2px;
      font-size: 12px;
      color: #63656e;
    }
  }

  .operation-icons {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-left: 16px;

    .operation-icon {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 32px;
      height: 32px;
      margin-left: 10px;
      cursor: pointer;
      background-color: #f0f1f5;
      border-radius: 2px;
      outline: none;
      transition: boder-color 0.2s;

      &:hover {
        border-color: #4d4f56;
        transition: boder-color 0.2s;
      }

      &:active {
        border-color: #3a84ff;
        transition: boder-color 0.2s;
      }

      .bklog-icon {
        width: 16px;
        font-size: 16px;
        color: #4d4f56;
      }
    }

    .light-search {
      display: flex;
      align-items: center;
      font-size: 12px;
      color: #4d4f56;
      background: #ffffff;

      label {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 40px;
        height: 32px;
        padding: 0px 0px;
        color: #4d4f56;
        text-align: center;
        background: #fafbfd;
        border-top: 1px solid #c4c6cc;
        border-right: none;
        border-bottom: 1px solid #c4c6cc;
        border-left: 1px solid #c4c6cc;
        border-top-left-radius: 2px;
        border-bottom-left-radius: 2px;
      }
    }

    .disabled-icon {
      cursor: not-allowed;
      background-color: #fff;
      border-color: #dcdee5;

      &:hover,
      .bklog-icon {
        color: #c4c6cc;
        border-color: #dcdee5;
      }
    }
  }

  .left-operate {
    flex-wrap: nowrap;
    align-items: center;

    @include flex-justify(space-between);

    >div {
      flex-shrink: 0;
    }

    .bk-button-group {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 104px;
      height: 32px;
      padding: 4px 4px;
      font-size: 12px;
      background-color: #f0f1f5;
      border-radius: 2px;
    }

    .option {
      display: flex;

      /* 使用 flex 布局 */
      flex: 1;
      align-items: center;

      /* 垂直居中 */
      justify-content: center;

      /* 水平居中 */
      width: 100%;
      height: 100%;
      color: #4d4f56;
      cursor: pointer;
      transition: background-color 0.3s;
    }

    .option.option-selected {
      color: #3a84ff;

      /* 蓝色 */
      background-color: #ffffff;
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
  &.bk-form-control {
    width: 96px;

    .bk-input-number {
      input {
        &.bk-form-input {
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
  height: 32px;
  padding-left: 6px;
}
</style>
