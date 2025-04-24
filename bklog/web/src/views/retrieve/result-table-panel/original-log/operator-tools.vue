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
  <div :class="{ 'handle-content': true, 'fix-content': showAllHandle, 'origin-content': logType === 'origin' }">
    <template v-if="!isUnionSearch">
      <span
        class="handle-card"
        v-bk-tooltips="{ allowHtml: true, content: '#realTimeLog-html', delay: 500 }"
      >
        <span
          :class="`icon bklog-icon bklog-handle bklog-time ${!isActiveLog && 'is-disable'}`"
          @click.stop="handleCheckClick('realTimeLog', isActiveLog)"
        >
        </span>
      </span>
      <span
        class="handle-card"
        v-bk-tooltips="{ allowHtml: true, content: '#contextLog-html', delay: 500 }"
      >
        <span
          :class="`icon bklog-icon bklog-handle bklog-document ${!isActiveLog && 'is-disable'}`"
          @click.stop="handleCheckClick('contextLog', isActiveLog)"
        >
        </span>
      </span>
      <span
        v-if="isActiveWebConsole"
        class="handle-card"
        v-bk-tooltips="{ allowHtml: true, content: '#webConsole-html', delay: 500 }"
      >
        <span
          :class="`icon bklog-icon bklog-consola ${!isCanClickWebConsole && 'is-disable'}`"
          @click.stop="handleCheckClick('webConsole', isCanClickWebConsole)"
        ></span>
      </span>
      <div v-show="false">
        <div id="realTimeLog-html">
          <span>
            <span
              v-if="!isActiveLog"
              class="bk-icon icon-exclamation-circle-shape"
            ></span>
            <span>{{ toolMessage.realTimeLog }}</span>
            <!-- <i18n path="请前往 {0}">
                  <span class="clean-str">{{$t('清洗')}}</span>
                </i18n>
              <span class="clean-str" @click="handleGotoLink('logExtract')">{{$t('说明文档')}}</span> -->
          </span>
        </div>
      </div>
      <div v-show="false">
        <div id="webConsole-html">
          <span>
            <span
              v-if="!isCanClickWebConsole"
              class="bk-icon icon-exclamation-circle-shape"
            ></span>
            <span>{{ toolMessage.webConsole }}</span>
            <!-- <i18n path="请前往 {0}">
              <span class="clean-str">{{$t('清洗')}}</span>
            </i18n>
            <span class="clean-str" @click="handleGotoLink('logExtract')">{{$t('说明文档')}}</span> -->
          </span>
        </div>
      </div>
      <div v-show="false">
        <div id="contextLog-html">
          <span>
            <span
              v-if="!isActiveLog"
              class="bk-icon icon-exclamation-circle-shape"
            ></span>
            <span>{{ toolMessage.contextLog }}</span>
            <!-- <i18n path="请前往 {0}">
                <span class="clean-str">{{$t('清洗')}}</span>
              </i18n>
              <span class="clean-str" @click="handleGotoLink('logExtract')">{{$t('说明文档')}}</span> -->
          </span>
        </div>
      </div>
    </template>
    <template v-else>
      <span
        class="handle-card union-icon"
        v-bk-tooltips="
          $t('{0}日志来源', {
            0: !isShowSourceField ? $t('显示') : $t('隐藏'),
          })
        "
        @click.stop="handleClick('logSource')"
      >
        <i :class="['bk-icon bklog-handle', `${!isShowSourceField ? 'icon-eye' : 'icon-eye-slash'}`]"></i>
      </span>
    </template>
  </div>
</template>

<script>
  import { mapGetters } from 'vuex';
  export default {
    props: {
      index: {
        type: Number,
        default: 0,
      },
      rowData: {
        type: Object,
        required: true,
      },
      operatorConfig: {
        type: Object,
        required: true,
      },
      logType: {
        type: String,
        default: 'table',
      },
      handleClick: Function,
    },
    data() {
      return {
        showAllHandle: false, // hove操作区域显示全部icon
      };
    },
    computed: {
      ...mapGetters({
        unionIndexList: 'unionIndexList',
        isUnionSearch: 'isUnionSearch',
      }),
      isActiveLog() {
        return this.operatorConfig?.contextAndRealtime?.is_active ?? false;
      },
      isActiveWebConsole() {
        return this.operatorConfig?.bcsWebConsole?.is_active ?? false;
      },
      /** 判断webConsole是否能点击 */
      isCanClickWebConsole() {
        if (!this.isActiveWebConsole) return false;
        const { cluster, container_id: containerID, __ext } = this.rowData;
        let queryData = {};
        if (cluster && containerID) {
          queryData = {
            cluster,
            container_id: containerID,
          };
        } else {
          if (!__ext) return false;
          if (!__ext.container_id) return false;
          queryData = { container_id: __ext.container_id };
          if (__ext.io_tencent_bcs_cluster) {
            Object.assign(queryData, {
              cluster: __ext.io_tencent_bcs_cluster,
            });
          } else if (__ext.bk_bcs_cluster_id) {
            Object.assign(queryData, {
              cluster: __ext.bk_bcs_cluster_id,
            });
          }
        }
        if (!queryData.cluster || !queryData.container_id) return false;
        return true;
      },
      toolMessage() {
        return (
          this.operatorConfig?.toolMessage ?? {
            realTimeLog: '',
            webConsole: '',
            contextLog: '',
          }
        );
      },
      isShowSourceField() {
        return this.operatorConfig?.isShowSourceField;
      },
    },
    methods: {
      handleCheckClick(clickType, isActive = false) {
        if (!isActive) return;
        return this.handleClick(clickType);
      },
    },
  };
</script>

<style lang="scss" scoped>
  .handle-content {
    position: absolute;
    top: 0;
    right: 0;
    display: flex;
    align-items: flex-start;
    justify-content: flex-end;
    width: 84px;
    padding: 14px 10px;
    overflow: hidden;
  }

  .fix-content {
    width: auto;
    background-color: #f5f7fa;
  }

  .icon-exclamation-circle-shape {
    color: #d7473f;
  }

  .icon-more {
    transform: translateY(2px) translateX(4px);
  }

  .is-disable {
    /* stylelint-disable-next-line declaration-no-important */
    color: #eceef2 !important;

    /* stylelint-disable-next-line declaration-no-important */
    cursor: no-drop !important;
  }

  .clean-str {
    color: #3a84ff;
    cursor: pointer;
  }

  .union-icon {
    margin-right: 8px;
  }

  .bklog-handle {
    font-size: 14px;
    color: #979ba5;
    cursor: pointer;

    &:hover {
      color: #3a84ff;
    }
  }
</style>
