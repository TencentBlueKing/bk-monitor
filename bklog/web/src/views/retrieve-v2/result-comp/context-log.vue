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
  <section
    :class="{
      'log-full-dialog-wrapper': isScreenFull,
      'bk-form': true,
      'context-log-wrapper': true,
      'log-full-width': !isScreenFull,
    }"
  >
    <!-- IP 日志路径 -->
    <div class="dialog-label">
      <span class="dialog-title">{{ title }}</span>
      <template v-if="!targetFields.length">
        <span style="margin-right: 10px">IP: {{ params.ip || params.serverIp }}</span>
        <span
          class="title-overflow"
          v-bk-overflow-tips
        >
          {{ $t('日志路径') + ': ' + (params.path || params.logfile) }}
        </span>
      </template>
      <template v-else>
        <span
          class="title-overflow"
          v-bk-tooltips.bottom="getTargetFieldsStr"
        >
          <span
            v-for="(item, index) of targetFields"
            style="margin-right: 10px"
            :key="index"
          >
            <span>{{ item }}: </span>
            <span>{{ params[item] || '/' }}</span>
          </span>
        </span>
      </template>
    </div>

    <div class="dialog-bars">
      <data-filter
        :is-screen-full="isScreenFull"
        @handle-filter="handleFilter"
        @fix-current-row="handleFixCurrentRow"
      />
      <!-- 暂停、复制、全屏 -->
      <div class="controls">
        <div
          ref="fieldsConfigRef"
          class="control-icon"
          v-bk-tooltips="fieldsConfigTooltip"
        >
          <span
            style="font-size: 16px"
            class="icon bklog-icon bklog-set-icon"
          ></span>
        </div>
        <fields-config
          :display="displayFieldNames"
          :id="fieldsConfigId"
          :is-loading="isConfigLoading"
          :total="totalFieldNames"
          @cancel="cancelConfig"
          @confirm="confirmConfig"
        ></fields-config>
        <div
          class="control-icon"
          @click="toggleScreenFull"
        >
          <span class="icon bklog-icon bklog-full-screen-log"></span>
        </div>
      </div>
    </div>
    <div
      ref="contextLog"
      class="dialog-log-markdown"
      tabindex="0"
      v-bkloading="{ isLoading: logLoading, opacity: 0.6 }"
    >
      <log-view
        :filter-key="activeFilterKey"
        :filter-type="filterType"
        :ignore-case="ignoreCase"
        :interval="interval"
        :log-list="logList"
        :reverse-log-list="reverseLogList"
        :show-type="showType"
        :light-list="highlightList"
      />
    </div>
    <log-view-control
      ref="viewControlRef"
      :show-type="showType"
      :light-list="highlightList"
    />

    <p class="handle-tips">{{ $t('快捷键  Esc:退出; PageUp: 向上翻页; PageDn: 向下翻页') }}</p>
    <!--        <div class="scroll-bar">-->
    <!--            <span class="icon bklog-icon bklog-up" @click.stop="scrollPage('up')"></span>-->
    <!--            <span class="icon bklog-icon bklog-down" @click.stop="scrollPage('down')"></span>-->
    <!--        </div>-->
  </section>
</template>

<script>
  import FieldsConfig from '@/components/common/fields-config';
  import logView from '@/components/log-view';
  import logViewControl from '@/components/log-view/log-view-control';
  import { getFlatObjValues } from '@/common/util';
  import useFieldNameHook from '@/hooks/use-field-name';
  import DataFilter from '../condition-comp/data-filter.vue';

  export default {
    name: 'ContextLog',
    components: {
      logView,
      logViewControl,
      FieldsConfig,
      DataFilter,
    },
    props: {
      retrieveParams: {
        type: Object,
        required: true,
      },
      logParams: {
        type: Object,
        default() {
          return {};
        },
      },
      title: {
        type: String,
        require: true,
      },
      targetFields: {
        type: Array,
        default: () => [],
      },
      indexSetId: {
        type: Number,
        default: 0,
      },
    },
    data() {
      const id = 'fields-config-tippy';
      return {
        logLoading: false,
        totalFields: [], // 所有字段信息
        totalFieldNames: [], // 所有的字段名
        displayFields: [], // 按顺序展示的字段信息
        displayFieldNames: [], // 展示的字段名
        isConfigLoading: false,
        fieldsConfigId: id,
        fieldsConfigTooltip: {
          allowHtml: true,
          width: 380,
          trigger: 'click',
          placement: 'bottom-end',
          theme: 'light',
          extCls: 'fields-config-tippy',
          content: `#${id}`,
          onShow: this.requestFields,
        },
        rawList: [],
        logList: [],
        reverseRawList: [],
        reverseLogList: [],
        isScreenFull: true,
        params: {},
        zero: true,
        prevBegin: 0,
        nextBegin: 0,
        firstLogEl: null,
        filterType: 'include',
        activeFilterKey: '',
        timer: null,
        throttleTimer: null,
        ignoreCase: false,
        flipScreen: '',
        flipScreenList: [],
        interval: {
          prev: 0,
          next: 0,
        },
        showType: 'log',
        highlightList: [],
        currentConfigID: 0,
        isRowChange: false,
      };
    },
    computed: {
      filedSettingConfigID() {
        // 当前索引集的显示字段ID
        return this.$store.state.retrieve.filedSettingConfigID;
      },
      getTargetFieldsStr() {
        return this.targetFields.reduce((acc, cur) => {
          acc += `${cur}: ${this.params[cur] || '/ '} `;
          return acc;
        }, '');
      },
    },
    created() {
      this.deepClone(this.logParams);
    },
    async mounted() {
      document.addEventListener('keyup', this.handleKeyup);

      await this.requestFields();
      await this.requestContentLog();

      this.$nextTick(() => {
        document.querySelector('.dialog-log-markdown').focus();
      });
    },
    destroyed() {
      document.removeEventListener('keyup', this.handleKeyup);
    },
    methods: {
      handleFixCurrentRow() {
        const target = this.$refs.contextLog;
        const listElement = target.querySelector('#log-content');
        const activeRow = listElement.querySelector('.line.log-init');
        const scrollTop = activeRow.offsetTop;
        target.scrollTo({ left: 0, top: scrollTop, behavior: 'smooth' });
      },
      handleKeyup(event) {
        if (event.keyCode === 27) {
          this.$emit('close-dialog');
        }
      },
      deepClone(obj, prefix = '') {
        for (const key in obj) {
          const prefixKey = prefix ? `${prefix}.${key}` : key;
          if (typeof obj[key] === 'object') {
            this.deepClone(obj[key], prefixKey);
          } else {
            this.params[prefixKey] = String(obj[key])
              .replace(/<mark>/g, '')
              .replace(/<\/mark>/g, '');
          }
        }
      },
      toggleScreenFull() {
        this.isScreenFull = !this.isScreenFull;
        this.$emit('toggle-screen-full', this.isScreenFull);
      },
      async requestFields() {
        try {
          this.isConfigLoading = true;
          const res = await this.$http.request('retrieve/getLogTableHead', {
            params: {
              index_set_id: this.indexSetId,
            },
            query: {
              scope: 'search_context',
              start_time: this.retrieveParams.start_time,
              end_time: this.retrieveParams.end_time,
              is_realtime: 'True',
            },
          });
          this.currentConfigID = res.data.config_id;
          this.totalFields = res.data.fields;
          const { getFieldNames, getFieldName } = useFieldNameHook({ store: this.$store });
          this.displayFieldNames = res.data.display_fields.map(item => getFieldName(item));
          this.totalFieldNames = getFieldNames(res.data.fields);
          this.displayFields = res.data.display_fields.map(fieldName => {
            return res.data.fields.find(fieldInfo => fieldInfo.field_name === fieldName);
          });
          return true;
        } catch (err) {
          console.warn(err);
        } finally {
          this.isConfigLoading = false;
        }
      },
      async requestContentLog(direction) {
        const data = Object.assign(
          {
            size: 50,
            zero: this.zero,
            dtEventTimeStamp: this.logParams.dtEventTimeStamp,
          },
          this.params,
        );
        if (direction === 'down') {
          data.begin = this.nextBegin;
        } else if (direction === 'top') {
          data.begin = this.prevBegin;
        } else {
          data.begin = 0;
        }

        try {
          this.logLoading = true;
          const res = await this.$http.request('retrieve/getContentLog', {
            params: {
              index_set_id: this.indexSetId,
            },
            data,
          });

          const { list } = res.data;
          if (list && list.length) {
            const formatList = this.formatList(list, this.displayFieldNames.length ? this.displayFieldNames : ['log']);
            if (direction) {
              if (direction === 'down') {
                this.logList.push(...formatList);
                this.rawList.push(...list);
                this.nextBegin += formatList.length;
              } else {
                this.reverseLogList.unshift(...formatList);
                this.reverseRawList.unshift(...list);
                this.prevBegin -= formatList.length;
              }
            } else {
              const zeroIndex = res.data.zero_index;
              if ((!zeroIndex && zeroIndex !== 0) || zeroIndex === -1) {
                this.logList.splice(this.logList.length, 0, { error: this.$t('无法定位上下文') });
              } else {
                this.logList.push(...formatList.slice(zeroIndex, list.length));
                this.rawList.push(...list.slice(zeroIndex, list.length));

                this.reverseLogList.unshift(...formatList.slice(0, zeroIndex));
                this.reverseRawList.unshift(...list.slice(0, zeroIndex));

                const value = zeroIndex - res.data.count_start;
                this.nextBegin = value + this.logList.length;
                this.prevBegin = value - this.reverseLogList.length;
              }
            }
          }
        } catch (e) {
          console.warn(e);
        } finally {
          this.logLoading = false;
          if (this.highlightList.length) this.$refs.viewControlRef.initLightItemList();
          if (this.zero) {
            this.$nextTick(() => {
              this.initLogScrollPosition();
            });
          }
        }
      },
      /**
       * 将列表根据字段组合成字符串数组
       * @param {Array} list 当前页码
       * @param {Array} displayFieldNames 当前页码
       * @return {Array<string>}
       **/
      formatList(list, displayFieldNames) {
        const filterDisplayList = [];
        list.forEach(listItem => {
          const displayObj = {};
          const { newObject } = getFlatObjValues(listItem);
          const { changeFieldName } = useFieldNameHook({ store: this.$store });
          displayFieldNames.forEach(field => {
            Object.assign(displayObj, { [field]: newObject[changeFieldName(field)] });
          });
          filterDisplayList.push(displayObj);
        });
        return filterDisplayList;
      },
      // 确定设置显示字段
      async confirmConfig(list) {
        this.isConfigLoading = true;
        const { changeFieldName } = useFieldNameHook({ store: this.$store });
        const copyList = list.map(item => changeFieldName(item));
        const data = { display_fields: copyList };
        try {
          const configRes = await this.$http.request('retrieve/getFieldsConfigByContextLog', {
            params: {
              index_set_id: this.indexSetId,
              config_id: this.currentConfigID,
            },
          });
          Object.assign(data, {
            sort_list: configRes.data.sort_list,
            name: configRes.data.name,
            config_id: this.currentConfigID,
            index_set_id: this.indexSetId,
          });
          await this.$http.request('retrieve/updateFieldsConfig', {
            data,
          });
          const res = await this.requestFields();
          if (res) {
            this.logList = this.formatList(this.rawList, this.displayFieldNames);
            this.reverseLogList = this.formatList(this.reverseRawList, this.displayFieldNames);
            this.$refs.fieldsConfigRef._tippy.hide();
            this.messageSuccess(this.$t('设置成功'));
          }
        } catch (err) {
          console.warn(err);
          this.isConfigLoading = false;
        }
      },
      // 取消设置显示字段
      cancelConfig() {
        this.$refs.fieldsConfigRef._tippy.hide();
      },
      initLogScrollPosition() {
        // 确定第0条的位置
        this.firstLogEl = document.querySelector('.dialog-log-markdown .log-init');
        // 没有数据
        if (!this.firstLogEl) return;
        const logContentHeight = this.firstLogEl.scrollHeight;
        const logOffsetTop = this.firstLogEl.offsetTop;

        const wrapperOffsetHeight = this.$refs.contextLog.offsetHeight;

        if (wrapperOffsetHeight <= logContentHeight) {
          this.$refs.contextLog.scrollTop = logOffsetTop;
        } else {
          this.$refs.contextLog.scrollTop = logOffsetTop - Math.ceil((wrapperOffsetHeight - logContentHeight) / 2);
        }
        this.zero = false;
        // 避免重复请求
        setTimeout(() => {
          this.$refs.contextLog.addEventListener('scroll', this.handleScroll, { passive: true });
        }, 64);
      },
      handleScroll() {
        clearTimeout(this.timer);
        this.timer = setTimeout(() => {
          if (this.logLoading) return;
          const { scrollTop } = this.$refs.contextLog;
          const { scrollHeight } = this.$refs.contextLog;
          const { offsetHeight } = this.$refs.contextLog;
          if (scrollTop === 0) {
            // 滚动到顶部
            this.requestContentLog('top').then(() => {
              this.$nextTick(() => {
                // 记录刷新前滚动位置
                const newScrollHeight = this.$refs.contextLog.scrollHeight;
                this.$refs.contextLog.scrollTo({ top: newScrollHeight - scrollHeight });
              });
            });
          } else if (scrollHeight - scrollTop - offsetHeight < 1) {
            // 滚动到底部
            this.requestContentLog('down');
          }
        }, 200);
      },
      handleFilter(field, value) {
        if (field === 'filterKey') {
          this.filterLog(value);
        } else {
          this[field] = value;
        }
      },
      filterLog(value) {
        this.activeFilterKey = value;
        clearTimeout(this.throttleTimer);
        this.throttleTimer = setTimeout(() => {
          if (!value) {
            this.$nextTick(() => {
              this.initLogScrollPosition();
            });
          }
        }, 300);
      },
    },
  };
</script>

<style lang="scss" scoped>
  @import '../../../scss/mixins/clearfix';
  @import '../../../scss/mixins/scroller';

  .context-log-wrapper {
    position: relative;

    @include clearfix;

    .dialog-label {
      display: flex;
      align-items: center;
      margin-bottom: 20px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .dialog-title {
      margin-right: 20px;
      font-size: 20px;
      line-height: 20px;
      color: #313238;
    }

    .dialog-bars {
      display: flex;
      justify-content: space-between;

      .controls {
        display: flex;
        align-items: flex-start;

        .control-icon {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 32px;
          height: 32px;
          font-size: 32px;
          cursor: pointer;
          border: 1px solid #c4c6cc;
          transition: color 0.2s;

          &:not(:last-child) {
            margin-right: 10px;
          }

          &:hover {
            color: #3a84ff;
            transition: color 0.2s;
          }
        }
      }
    }

    .dialog-log-markdown {
      height: 404px;
      overflow-y: auto;
      background: #f5f7fa;
      border: 1px solid #dcdee5;
      border-bottom: none;

      @include scroller($backgroundColor: #aaa, $width: 4px);

      &::-webkit-scrollbar {
        background-color: #dedede;
      }
    }

    .scroll-bar {
      position: absolute;
      top: 68px;
      right: 24px;
      display: flex;
      flex-flow: column;
      justify-content: space-between;
      // height: 56px;

      .icon {
        font-size: 24px;
        color: #d9d9d9;
        cursor: pointer;
      }
    }

    .handle-tips {
      margin-top: 10px;
      color: #63656e;
    }
  }

  .log-full-dialog-wrapper {
    height: 100%;
    overflow: hidden;

    .dialog-log-markdown {
      height: calc(100% - 200px);
    }

    .handle-tips {
      margin-top: 18px;
    }

    .dialog-label {
      padding-top: 15px;
    }
  }

  .log-full-width {
    width: 1030px;
  }
</style>
