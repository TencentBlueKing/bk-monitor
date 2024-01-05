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
<!--
 * @Date: 2021-06-15 10:53:50
 * @LastEditTime: 2021-06-23 16:09:06
 * @Description:
-->
<template>
  <bk-sideslider
    :width="780"
    :quick-close="true"
    :is-show.sync="detail.show"
    :title="detail.title"
    @hidden="handleDetailClose"
  >
    <div
      class="alarm-detail-header"
      slot="header"
    >
      <span
        v-if="loading"
        class="header-name"
      >{{ $t('加载中...') }}</span>
      <span
        v-else
        class="header-name"
      >{{ `${$t('告警组详情')} - #${detail.id} ${detail.title}` }}</span>
      <span
        class="header-edit"
        v-authority="{ active: !authority.MANAGE_AUTH }"
        @click="authority.MANAGE_AUTH ? handleEditAlarmGroup() : handleShowAuthorityDetail(alarmGroupAuth.MANAGE_AUTH)"
      >{{ $t('编辑告警组') }}</span>
      <span
        class="header-record"
        @click="handleShowChangeRecord"
      >{{ $t('查看变更记录') }}</span>
    </div>
    <div
      slot="content"
      class="alarm-details"
      v-bkloading="{ isLoading: loading }"
    >
      <div class="alarm-details-col">
        <div class="alarm-details-label">
          {{ $t('所属') }}
        </div>
        <div class="alarm-details-item">
          {{ bizName }}
        </div>
      </div>
      <div class="alarm-details-col">
        <div class="alarm-details-label">
          {{ $t('告警组名称') }}
        </div>
        <div class="alarm-details-item alarm-details-content">
          {{ detailData.name }}
        </div>
      </div>
      <div
        class="alarm-details-col text-top"
        style="margin-bottom: 14px"
      >
        <div class="alarm-details-label alarm-details-person-label">
          {{ $t('通知对象') }}
        </div>
        <div class="alarm-details-item alarm-details-person">
          <template v-if="detailData.noticeReceiver && detailData.noticeReceiver.length">
            <div
              class="person-box"
              v-for="(item, index) in detailData.noticeReceiver"
              :key="index"
            >
              <div class="person-image">
                <img
                  v-if="item.logo"
                  :src="item.logo"
                  alt=''
                >
                <i
                  v-else-if="!item.logo && item.type === 'group'"
                  class="icon-monitor icon-mc-user-group no-img"
                />
                <i
                  v-else-if="!item.logo && item.type === 'user'"
                  class="icon-monitor icon-mc-user-one no-img"
                />
              </div>
              <span class="person-name">{{ item.displayName }}</span>
            </div>
          </template>
          <span
            class="notice-empty"
            v-else
          >--</span>
        </div>
      </div>
      <div class="alarm-details-col text-top">
        <div class="alarm-details-label alarm-details-noticeway-label">
          {{ $t('通知方式') }}
        </div>
        <div class="alarm-details-notice-way alarm-details-item">
          <table
            class="notice-table"
            cellspacing="0"
            v-if="noticeWay"
          >
            <thead>
              <th>{{ $t('告警级别') }}</th>
              <th
                v-for="(item, index) in noticeWay"
                :key="index"
              >
                <div>
                  <!-- <i class="icon-monitor icon" :class="item.icon"></i> -->
                  <img
                    class="item-img"
                    :src="item.icon"
                    alt=''
                  >
                  {{ item.label }}
                </div>
              </th>
            </thead>
            <tbody>
              <tr
                v-for="(item, index) in noticeData"
                :key="index"
              >
                <td>{{ item.title }}</td>
                <td
                  v-for="notice in item.list"
                  :key="notice.type"
                  :class="{ 'work-group': notice.type === 'wxwork-bot' }"
                >
                  <i
                    v-if="notice.checked && notice.type !== 'wxwork-bot'"
                    class="bk-icon icon-check-1 checklist"
                  />
                  <div
                    :title="notice.workGroupId"
                    class="wechat-group-id"
                    v-if="notice.type === 'wxwork-bot' && notice.checked && notice.workGroupId"
                  >
                    {{ notice.workGroupId }}
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      <div class="alarm-details-col">
        <div class="alarm-details-label">
          {{ $t('回调地址') }}
        </div>
        <div class="alarm-details-item">
          {{ detailData.webhookUrl || '--' }}
        </div>
      </div>
      <div class="alarm-details-col text-top">
        <div class="alarm-details-label alarm-details-des-label">
          {{ $t('说明') }}
        </div>
        <div class="alarm-details-item">
          <pre style="margin: 0; white-space: pre-wrap">
{{ detailData.message || '--' }}
</pre>
        </div>
      </div>
      <change-record
        :record-data="detailData"
        :show="recordShow"
        @updateShow="(v) => (recordShow = v)"
      />
    </div>
  </bk-sideslider>
</template>

<script>
import { mapActions } from 'vuex';

import ChangeRecord from '../../../components/change-record/change-record';

export default {
  name: 'AlarmGroupDetail',
  components: {
    ChangeRecord
  },
  inject: ['authority', 'handleShowAuthorityDetail', 'alarmGroupAuth'],
  props: {
    id: {
      type: [String, Number], // 告警组详情ID
      default: 0
    },
    detail: {
      type: Object,
      default() {
        return {
          show: false,
          title: ''
        };
      }
    }
  },
  data() {
    return {
      recordShow: false,
      detailData: {},
      bizName: '',
      noticeWay: [], // 通知方式
      noticeData: [], //  通知表格勾选数据
      webhookUrl: '',
      iconMap: {
        weixin: 'icon-mc-weixin',
        mail: 'icon-mc-youjian',
        sms: 'icon-mc-duanxin',
        voice: 'icon-mc-dianhua',
        'wxwork-bot': 'icon-qiye-weixin'
      },
      levelMap: {
        1: this.$t('致命'),
        2: this.$t('预警'),
        3: this.$t('提醒')
      },
      loading: false
    };
  },
  watch: {
    id(newV) {
      if (newV !== 0) {
        this.handleDetailData(newV);
      }
    },
    immediate: true
  },
  created() {
    this.id && this.handleDetailData(this.id);
  },
  methods: {
    ...mapActions('alarm-group', ['noticeGroupDetail', 'getNoticeWay']),
    handleEditAlarmGroup() {
      this.$emit('edit-group', this.id);
    },
    handleShowChangeRecord() {
      this.recordShow = true;
    },
    handleDetailClose() {
      this.$emit('detail-close', false);
    },
    async handleDetailData(id) {
      this.loading = true;
      // 通知方式接口
      this.noticeWay = await this.getNoticeWay();
      // 替换数据中对应的icon的展示样式
      this.noticeWay.forEach((way) => {
        way.icon = `data:image/png;base64,${way.icon}`;
      });
      // 告警详情数据
      this.detailData = await this.noticeGroupDetail({ id });
      const tableData = [];
      Object.keys(this.detailData.noticeWay).forEach((key, index) => {
        const noticeWay = this.detailData.noticeWay[key];
        // 渲染初始表格
        const list = this.noticeWay.map((set) => {
          if (set.type === 'wxwork-bot') {
            return { type: set.type, checked: false, workGroupId: '' };
          }
          return { type: set.type, checked: false };
        });
        // 对应勾选
        noticeWay.forEach((notice) => {
          const listItem = list.find(set => set.type === notice);
          listItem && (listItem.checked = true);
        });
        // 企业微信群勾选项
        if (this.detailData?.wxworkGroup[key]) {
          const listItem = list.find(set => set.type === 'wxwork-bot');
          if (listItem) {
            listItem.checked = true;
            listItem.workGroupId = this.detailData.wxworkGroup[key];
          }
        }
        tableData.push({
          list,
          level: key,
          title: this.levelMap[index + 1]
        });
      });
      this.noticeData = tableData.reverse();
      // 筛选出所属空间
      if (this.detailData.bkBizId === 0) {
        this.bizName = this.$t('全业务');
      } else {
        const bizItem = this.$store.getters.bizList.filter(item => this.detailData.bkBizId === item.id);
        this.bizName = bizItem[0].text;
      }
      this.loading = false;
    }
  }
};
</script>

<style lang="scss" scoped>
.alarm-details {
  display: flex;
  flex-direction: column;
  padding: 38px 40px 38px 30px;
  color: #63656e;

  .alarm-dividing-line {
    width: 100%;
    height: 1px;
    margin-bottom: 20px;
    background: #dcdee5;
  }

  &-content {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  &-col {
    display: flex;
    align-items: center;
    margin-bottom: 20px;
    line-height: 16px;
  }

  &-item {
    flex: 1;
    word-break: break-all;
  }

  &-label {
    width: 70px;
    margin-right: 21px;
    color: #979ba5;
    text-align: right;
  }

  &-person {
    display: flex;
    flex-flow: row wrap;

    .person-box {
      display: flex;
      align-items: center;
      height: 26px;
      margin-bottom: 10px;
    }

    .person-image {
      display: flex;
      align-items: center;

      img {
        width: 24px;
        height: 24px;
        border-radius: 50%;
      }

      .no-img {
        font-size: 22px;
        color: #c4c6cc;
        background: #fafbfd;
        border-radius: 16px;
      }
    }

    .person-name {
      margin-right: 20px;
      margin-left: 6px;
    }
  }

  &-person-label {
    position: relative;
    top: 5px;
  }

  &-noticeway-label {
    position: relative;
    top: 4px;
  }

  &-des-label {
    position: relative;
    top: 1px;
  }

  .notice-empty {
    position: relative;
    top: 5px;
  }

  .text-top {
    align-items: start;
  }

  .notice-table {
    width: 100%;
    color: #63656e;
    border: 1px solid #dcdee5;
    border-bottom: 0;

    .icon {
      margin-right: 6px;
      font-size: 16px;
    }

    .item-img {
      width: 16px;
      height: 16px;
      margin-right: 6px;
      filter: grayscale(100%);
    }

    th {
      height: 40px;
      padding: 0;
      margin: 0;
      font-weight: 400;
      background: #fafbfd;
      border-right: 1px solid #dcdee5;
      border-bottom: 1px solid #dcdee5;

      &:first-child {
        width: 97px;
      }

      &:last-child {
        border-right: 0;
      }

      div {
        display: flex;
        align-items: center;
        justify-content: center;
        height: 40px;
      }
    }

    td {
      height: 40px;
      padding: 0;
      margin: 0;
      text-align: center;
      background-color: #fff;
      border-right: 1px solid #dcdee5;
      border-bottom: 1px solid #dcdee5;

      &:last-child {
        border-right: 0;
      }

      &.work-group {
        width: 20%;
      }

      .checklist {
        font-size: 24px;
        font-weight: 600;
        color: #2dcb56;
      }

      .wechat-group-id {
        max-width: 200px;
        padding: 0 10px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
    }
  }
}

.alarm-detail-header {
  display: flex;
  align-items: center;

  .header-name {
    max-width: 513px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .header-edit {
    margin-left: auto;
    font-size: 12px;
    font-weight: normal;
    color: #3a84ff;
    cursor: pointer;
  }

  .header-record {
    margin: 0 40px 0 16px;

    /* stylelint-disable-next-line scss/at-extend-no-missing-placeholder */
    @extend .header-edit;
  }
}
</style>
