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
    :value="show"
    :title="$t('通知状态明细')"
    header-position="left"
    :show-footer="false"
    :show-confirm-btn="false"
    width="620"
    @change="handleShowChange"
  >
    <div
      v-bkloading="{ isLoading: loading }"
      class="notice-detail"
    >
      <div class="notice-detail-select">
        <span class="select-lable"> {{ $t('通知次数:') }} </span>
        <bk-select
          v-model="value"
          class="select-input"
          :clearable="false"
          @change="handleSelectChange"
        >
          <bk-option
            v-for="(option, index) in list"
            :id="option.actionId"
            :key="index"
            :name="handleNoticeSelectName(option)"
          />
        </bk-select>
      </div>
      <div
        v-bkloading="{ isLoading: table.loading }"
        class="notice-detail-table"
      >
        <bk-table
          v-if="table.column.length"
          :data="table.data"
          max-height="500"
        >
          <bk-table-column
            v-for="column in table.column"
            :key="column.id"
            :min-width="column.id === 'notice' ? '120px' : '50'"
            :label="column.name"
          >
            <template slot-scope="scope">
              <div
                v-if="column.id === 'notice'"
                :title="scope.row.noticeInfo"
              >
                {{ scope.row.receiver }}
                <span
                  v-show="scope.row.noticeGroup"
                  class="col-notice"
                  >（{{ scope.row.noticeGroup }}）</span
                >
              </div>
              <template v-else>
                <div v-if="scope.row[column.id]">
                  <bk-popover
                    v-if="scope.row[column.id].status === 0 && scope.row[column.id].message"
                    placement="top"
                    width="200"
                  >
                    <div :class="'notice-' + scope.row[column.id].status" />
                    <div
                      slot="content"
                      style="word-break: break-all"
                    >
                      {{ scope.row[column.id].message }}
                    </div>
                  </bk-popover>
                  <div
                    v-else
                    :class="'notice-' + scope.row[column.id].status"
                  />
                </div>
                <div v-else>
                  <div>--</div>
                </div>
              </template>
            </template>
          </bk-table-column>
          <template #empty>
            <i
              class="bk-table-empty-icon bk-icon"
              :class="tableAbnormalIcon"
            />
            <div>{{ tableAbnormalText }}</div>
          </template>
        </bk-table>
      </div>
    </div>
  </monitor-dialog>
</template>
<script>
import MonitorDialog from 'monitor-ui/monitor-dialog/monitor-dialog';
import { createNamespacedHelpers } from 'vuex';

const { mapActions } = createNamespacedHelpers('event-center');
export default {
  name: 'AlarmNoticeDetail',
  components: {
    MonitorDialog,
  },
  model: {
    prop: 'show',
    event: 'change',
  },
  props: {
    show: {
      type: Boolean,
      required: true,
    },
    bizId: {
      type: [String, Number],
      required: true,
    },
    id: {
      type: [String, Number],
      required: true,
    },
    defaultSelectActionId: {
      type: [String, Number],
      default: -1,
    },
  },
  data() {
    return {
      list: [],
      value: -1,
      table: {
        data: [],
        column: [],
        loading: false,
      },
      selectedItem: null,
      loading: false,
      popoverInstance: null,
      isShielded: false,
      isEmptyReceiver: false,
    };
  },
  computed: {
    tableAbnormalText() {
      const textMap = {
        SHIELDED: this.$t('已屏蔽'),
        EMPTY_RECEIVER: this.$t('通知人为空'),
      };
      return this.table.data.length === 0 && !this.isShielded && !this.isEmptyReceiver
        ? this.$t('无数据')
        : textMap[this.selectedItem.status];
    },
    tableAbnormalIcon() {
      return this.table.data.length === 0 && !this.isShielded ? 'icon-empty' : 'icon-monitor icon-mc-notice-shield';
    },
  },
  watch: {
    show: {
      handler(v) {
        // 设置初始值
        this.value = this.defaultSelectActionId;
        v ? this.handleNoticeShow() : (this.list = []);
      },
      immediate: true,
    },
  },
  beforeDestroy() {
    this.handleMouseLeave();
  },
  methods: {
    ...mapActions(['getNoticeDetail', 'getNoticeTableDetail']),
    async handleNoticeShow() {
      this.loading = true;
      const list = await this.getNoticeDetail({
        bk_biz_id: this.bizId,
        id: this.id,
      }).catch(() => {
        this.loading = false;
      });
      this.list = list.reverse();
      if (list.length > 0) {
        if (this.value === -1) {
          this.value = list[0].actionId;
        }
        await this.handleGetTableData(false);
      }
      this.loading = false;
    },
    async handleGetTableData(needLoading = true) {
      this.table.loading = needLoading;
      const tableData = await this.getNoticeTableDetail({
        action_id: this.value,
      }).catch(() => {
        this.table.loading = false;
      });
      if (!tableData.alertDetail) {
        this.table.data = [];
        this.table.loading = false;
        return;
      }
      this.table.data = tableData.alertDetail.map(item => ({
        ...item,
        noticeInfo: item.noticeGroup ? `${item.receiver}（${item.noticeGroup}）` : item.receiver,
      }));
      this.table.column = tableData.alertWay;
      this.table.column.unshift({
        id: 'notice',
        name: this.$t('通知对象'),
      });
      this.table.loading = false;
    },
    handleShowChange(v) {
      this.$emit('change', v);
    },
    handleSelectChange(v) {
      this.selectedItem = this.list.find(item => item.actionId === v) || {};
      const isShielded = this.selectedItem.status === 'SHIELDED';
      const isEmptyReceiver = this.selectedItem.status === 'EMPTY_RECEIVER';
      if (isShielded || isEmptyReceiver) {
        this.table.data = [];
      } else {
        !this.loading && this.handleGetTableData();
      }
      this.isShielded = isShielded;
      this.isEmptyReceiver = isEmptyReceiver;
    },
    handleMouseEnter(data, e) {
      if (data.status === 0 && data.message) {
        this.popoverInstance = this.$bkPopover(e.target, {
          content: data.message,
          arrow: true,
          maxWidth: 320,
        });
        this.popoverInstance.show(100);
      }
    },
    handleMouseLeave() {
      if (this.popoverInstance) {
        this.popoverInstance.hide(0);
        this.popoverInstance.destroy();
        this.popoverInstance = null;
      }
    },
    handleNoticeSelectName(option) {
      return `${this.$t('第')}${option.index}${this.$t('次')}（${option.actionTime}）`;
    },
  },
};
</script>
<style lang="scss" scoped>
.notice-detail {
  font-size: 12px;
  color: #63656e;

  &-select {
    display: flex;
    align-items: center;
    margin-bottom: 16px;
    font-size: 14px;

    .select-lable {
      margin-right: 12px;
      color: #979ba5;
    }

    .select-input {
      width: 265px;
    }
  }

  &-table {
    min-height: 300px;

    .col-notice {
      color: #c4c6cc;
    }

    .notice-0 {
      width: 12px;
      height: 12px;
      background-image: url('../../../static/images/svg/notice-failed.svg');
      background-size: cover;
    }

    .notice-1 {
      width: 12px;
      height: 12px;
      background: url('../../../static/images/svg/notice-success.svg');
      background-size: cover;
    }
  }
}
</style>
