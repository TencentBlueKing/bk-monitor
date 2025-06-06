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
  <div v-show="false">
    <div
      ref="content"
      class="receiver-list-wrap"
      v-bkloading="{ isLoading: loading }"
    >
      <div class="title">
        {{ $t('订阅人员列表') }}
      </div>
      <bk-table
        class="receiver-list-table"
        :data="tableData"
      >
        <template v-for="(item, index) in tableColumnsMap">
          <bk-table-column
            v-if="item.key !== 'handle'"
            :key="index"
            :label="item.label"
            :prop="item.key"
            :width="item.width"
            :formatter="item.formatter"
          />
          <bk-table-column
            :key="'handle-' + index"
            v-else-if="needHandle"
            :label="item.label"
            :prop="item.key"
          >
            <template slot-scope="scope">
              <bk-button
                v-if="!scope.row.isEnabled && scope.row.createTime"
                :text="true"
                @click="emitReceiver(scope.row)"
              >{{ $t('重新订阅') }}{{ scope.row[item.key] }}</bk-button>
            </template>
          </bk-table-column>
        </template>
      </bk-table>
    </div>
  </div>
</template>

<script lang="ts">
import { Component, Emit, Prop, PropSync, Ref, Vue, Watch } from 'vue-property-decorator';

const { i18n } = window;
/**
 * 接收人列表
 */
@Component({
  name: 'receiver-list',
})
export default class ReceiverList extends Vue {
  @PropSync('show', { default: false, type: Boolean }) localShow;
  @Prop({ default: null, type: Element }) readonly target;
  @Prop({ default: () => [], type: Array }) readonly tableData;
  @Prop({ default: 'bottom', type: String }) readonly placement;
  @Prop({ default: false, type: Boolean }) readonly needHandle;
  @Prop({ default: false, type: Boolean }) readonly loading;

  @Ref('content') private readonly contentRef: any;

  private tipsPopoverInstance: any = null;
  private offsetMap = {
    'bottom-start': -10,
    'bottom-end': 10,
  };

  private tableColumnsMap: any = [
    {
      label: i18n.t('订阅人'),
      key: 'name',
      formatter: row => row.name ? this.$createElement('bk-user-display-name', {
        attrs: {
          'user-id': row.name,
        },
      }) : '--',
    },
    {
      label: i18n.t('订阅时间'),
      key: 'createTime',
      width: 150,
      formatter: row => row.createTime || '--',
    },
    {
      label: i18n.t('订阅状态'),
      key: 'isEnabled',
      formatter: row => (row.isEnabled === null ? '--' : row.isEnabled ? i18n.t('已订阅') : i18n.t('已取消')),
    },
    {
      label: i18n.t('最后一次发送'),
      key: 'lastSendTime',
      width: 150,
      formatter: row => row.lastSendTime || '--',
    },
    {
      label: i18n.t('操作'),
      key: 'handle',
    },
  ];

  @Watch('localShow')
  handleShowChange(v: boolean) {
    if (v) {
      this.initTipsPopover();
    }
  }

  @Emit('on-receiver')
  emitReceiver(row) {
    return row;
  }

  destroyed() {
    this.hiddenPopover();
  }

  private initTipsPopover() {
    if (!this.target) return;
    if (!this.tipsPopoverInstance) {
      this.tipsPopoverInstance = this.$bkPopover(this.target, {
        content: this.contentRef,
        theme: 'receiver-list light',
        trigger: 'manual',
        hideOnClick: true,
        interactive: true,
        arrow: true,
        zIndex: 100,
        offset: this.offsetMap[this.placement],
        placement: this.placement,
        onHidden: () => {
          this.tipsPopoverInstance?.destroy();
          this.tipsPopoverInstance = null;
          this.localShow = false;
        },
      });
      this.tipsPopoverInstance?.show();
    }
  }

  private hiddenPopover() {
    this.tipsPopoverInstance?.hide();
  }
}
</script>

<style lang="scss">
.receiver-list-wrap {
  position: relative;
  width: 640px;
  padding: 16px;
  // height: 300px;
  background-color: #fff;

  .receiver-list-table {
    .bk-table-body-wrapper {
      /* stylelint-disable-next-line declaration-no-important */
      max-height: 420px !important;

      /* stylelint-disable-next-line declaration-no-important */
      overflow-y: auto !important;
    }
  }

  .title {
    margin-bottom: 8px;
  }

  .arrow {
    position: absolute;
    top: -4px;
    width: 6px;
    height: 6px;
    background-color: #fff;
    border: 1px solid #dcdee5;
    border-right: 0;
    border-bottom: 0;
    transform: rotate(45deg);
  }

  .arrow[data-placement='bottom-start'] {
    left: 14px;
  }

  .arrow[data-placement='bottom-end'] {
    right: 14px;
  }
}

.receiver-list-theme {
  padding: 0px;

  /* stylelint-disable-next-line declaration-no-important */
  overflow: visible !important;
  color: #63656e;
  box-shadow: 0;

  .tippy-backdrop {
    width: 0;
    background: none;
  }
}
</style>
