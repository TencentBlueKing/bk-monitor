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
  <div class="bklog-result-box">
    <LogRows
      :content-type="contentType"
      :handle-click-tools="handleClickTools"
    ></LogRows>

    <!-- 实时滚动日志/上下文弹窗 -->
    <bk-dialog
      v-model="logDialog.visible"
      :draggable="false"
      :esc-close="false"
      :ext-cls="logDialog.fullscreen ? 'log-dialog log-full-dialog' : 'log-dialog'"
      :fullscreen="logDialog.fullscreen"
      :header-position="logDialog.headerPosition"
      :mask-close="false"
      :show-footer="false"
      :width="logDialog.width"
      @after-leave="hideDialog"
    >
      <real-time-log
        v-if="logDialog.type === 'realTimeLog'"
        :log-params="logDialog.data"
        :target-fields="targetFields"
        :title="logDialog.title"
        :indexSetId="logDialog.indexSetId"
        @close-dialog="hideDialog"
        @toggle-screen-full="toggleScreenFull"
      />
      <context-log
        v-if="logDialog.type === 'contextLog'"
        :log-params="logDialog.data"
        :retrieve-params="retrieveParams"
        :target-fields="targetFields"
        :title="logDialog.title"
        :indexSetId="logDialog.indexSetId"
        @close-dialog="hideDialog"
        @toggle-screen-full="toggleScreenFull"
      />
    </bk-dialog>

    <AiAssitant
      ref="refAiAssitant"
      @close="handleAiClose"
    ></AiAssitant>
  </div>
</template>

<script>
  import { parseTableRowData } from '@/common/util';
  import RetrieveLoader from '@/skeleton/retrieve-loader';

  import ContextLog from '../../result-comp/context-log';
  import RealTimeLog from '../../result-comp/real-time-log';
  import LogRows from './log-rows.tsx';
  // #if MONITOR_APP !== 'apm' && MONITOR_APP !== 'trace'
  import AiAssitant from '@/global/ai-assitant.tsx';
  // #else
  // #code const AiAssitant = () => null;
  // #endif
  export default {
    components: {
      RetrieveLoader,
      ContextLog,
      RealTimeLog,
      AiAssitant,
      LogRows,
    },
    props: {
      contentType: {
        type: String,
        default: 'table',
      },
      retrieveParams: {
        type: Object,
        default: () => ({}),
      },
    },
    data() {
      return {
        targetFields: [],
        logDialog: {
          title: '',
          type: '',
          width: '100%',
          visible: false,
          headerPosition: 'left',
          fullscreen: true,
          data: {},
          indexSetId: '',
        },
      };
    },

    methods: {
      handleAiClose() {
        this.$el.querySelector('.ai-active')?.classList.remove('ai-active');
      },
      // 打开实时日志或上下文弹窗
      openLogDialog(row, type , indexSetId) {
        this.logDialog.data = row;
        this.logDialog.type = type;
        this.logDialog.title = type === 'realTimeLog' ? this.$t('实时滚动日志') : this.$t('上下文');
        this.logDialog.visible = true;
        this.logDialog.fullscreen = true;
        this.logDialog.indexSetId = indexSetId;
      },
      openWebConsole(row) {
        // (('cluster', 'container_id'),
        // ('__ext.io_tencent_bcs_cluster', '__ext.container_id'),
        // ('__ext.bk_bcs_cluster_id', '__ext.container_id')) 不能同时为空
        const { cluster, container_id: containerID, __ext } = row;
        let queryData = {};
        if (cluster && containerID) {
          queryData = {
            cluster_id: encodeURIComponent(cluster),
            container_id: containerID,
          };
        } else {
          if (!__ext) return;
          if (!__ext.container_id) return;
          queryData = { container_id: __ext.container_id };
          if (__ext.io_tencent_bcs_cluster) {
            Object.assign(queryData, {
              cluster_id: encodeURIComponent(__ext.io_tencent_bcs_cluster),
            });
          } else if (__ext.bk_bcs_cluster_id) {
            Object.assign(queryData, {
              cluster_id: encodeURIComponent(__ext.bk_bcs_cluster_id),
            });
          }
        }
        if (!queryData.cluster_id || !queryData.container_id) return;
        this.$http
          .request('retrieve/getWebConsoleUrl', {
            params: {
              index_set_id: this.$route.params.indexId,
            },
            query: queryData,
          })
          .then(res => {
            window.open(res.data);
          })
          .catch(e => {
            console.warn(e);
          });
      },
      handleClickTools(event, row, config, index) {
        if (event === 'ai') {
          this.$refs.refAiAssitant.open(true, {
            space_uid: this.$store.getters.spaceUid,
            index_set_id: this.$store.getters.indexId,
            log_data: row,
            index,
          });
          return;
        }
        if (['realTimeLog', 'contextLog'].includes(event)) {
          const contextFields = config.contextAndRealtime.extra?.context_fields;
          const timeField = this.$store.state.indexFieldInfo.time_field;
          const dialogNewParams = {};
          const { targetFields = [], sortFields = [] } = config.indexSetValue;

          // const fieldParamsKey = [...new Set([...targetFields, ...sortFields])];
          this.targetFields = targetFields ?? [];

          Object.assign(dialogNewParams, { dtEventTimeStamp: row.dtEventTimeStamp });
          // 非日志采集的情况下判断是否设置过字段设置 设置了的话传已设置过的参数
          // if (config.indexSetValue.scenarioID !== 'log' && fieldParamsKey.length) {
          //   fieldParamsKey.forEach(field => {
          //     dialogNewParams[field] = parseTableRowData(row, field, '', this.$store.state.isFormatDate, '');
          //   });
          // } else 
          if (Array.isArray(contextFields) && contextFields.length) {
            // 传参配置指定字段
            contextFields.push(timeField);
            contextFields.forEach(field => {
              if (field === 'bk_host_id') {
                if (row[field]) dialogNewParams[field] = row[field];
              } else {
                dialogNewParams[field] = parseTableRowData(row, field, '', this.$store.state.isFormatDate, '');
              }
            });
          } else {
            Object.assign(dialogNewParams, row);
          }
          this.openLogDialog(dialogNewParams, event, row.__index_set_id__);
        } else if (event === 'webConsole') this.openWebConsole(row);
        else if (event === 'logSource') this.$store.dispatch('changeShowUnionSource');
      },
      // 关闭实时日志或上下文弹窗后的回调
      hideDialog() {
        this.logDialog.type = '';
        this.logDialog.title = '';
        this.logDialog.visible = false;
        this.targetFields = [];
      },
      // 实时日志或上下文弹窗开启或关闭全屏
      toggleScreenFull(isScreenFull) {
        this.logDialog.width = isScreenFull ? '100%' : 1078;
        this.logDialog.fullscreen = isScreenFull;
      },
    },
  };
</script>
<style lang="scss">
  .bklog-result-box {
    position: relative;

    .bklog-skeleton-loading {
      position: absolute;
      top: 0;
      z-index: 10;
    }
  }
</style>
