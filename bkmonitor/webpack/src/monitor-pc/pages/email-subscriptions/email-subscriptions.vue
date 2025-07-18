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
  <div class="email-subscriptions-wrap">
    <!-- 已订阅列表 -->
    <list-collapse
      class="collapse-wrap"
      :title="$t('已订阅')"
      :active-name="subAcitveList"
      @item-click="arr => handleItemClick(arr, 'subAcitveList')"
    >
      <span
        class="header-btn"
        slot="header-btn"
        @click.stop="handleRouterTo('email-subscriptions-add')"
      >
        <span class="icon-monitor icon-mc-plus-fill" />
        <span>{{ $t('新建订阅') }}</span>
      </span>
      <div
        slot="content"
        class="list-content"
      >
        <table-skeleton
          style="padding: 16px"
          :type="3"
          v-if="subscribedLoading"
        />
        <bk-table
          v-else
          v-bkloading="{ isLoading: subscribedLoading, zIndex: 1 }"
          style="margin-top: 15px"
          :data="subscribedTableData"
          :outer-border="true"
          :header-border="false"
          :pagination="subscribedPagination"
          @page-change="page => changelistPage(page, 'subscribed')"
          @page-limit-change="limit => handlePageLimitChange(limit, 'subscribed')"
        >
          <template v-for="(item, index) in subListColumnsMap">
            <!-- 启停状态 -->
            <bk-table-column
              v-if="item.key === 'isEnabled'"
              :key="index + '-isEnabled'"
              :label="item.label"
              :prop="item.key"
              :width="isEn ? 130 : 100"
            >
              <template slot-scope="scope">
                <bk-switcher
                  v-model="scope.row.isEnabled"
                  :disabled="isPermissionDenied(scope.row)"
                  theme="primary"
                  size="small"
                  @change="handleSwitchChange(scope.row)"
                />
              </template>
            </bk-table-column>
            <!-- 订阅状态 -->
            <bk-table-column
              v-else-if="item.key === 'receivers'"
              :key="index + '-receivers'"
              :label="item.label"
              :prop="item.key"
              :width="isEn ? 150 : 100"
            >
              <template slot-scope="scope">
                <div class="receivers-status">
                  <template v-if="isAllowSubscriptions(scope.row)">
                    <span class="text">{{ $t('已取消') }}</span>
                  </template>
                  <template v-else>
                    <span class="text">{{ $t('已订阅') }}</span>
                    <i
                      class="icon-monitor icon-audit"
                      @click="handleReceiversList($event, scope.row)"
                    />
                  </template>
                </div>
              </template>
            </bk-table-column>
            <bk-table-column
              v-else-if="item.key === 'mailTitle'"
              :key="index + '-mailTitle'"
              :label="item.label"
              :prop="item.key"
              :min-width="300"
              show-overflow-tooltip
            />
            <bk-table-column
              v-else
              :show-overflow-tooltip="item.overflow"
              :width="item.width"
              :key="index"
              :label="item.label"
              :prop="item.key"
              :formatter="item.formatter"
            />
          </template>
          <bk-table-column
            :width="isEn ? 280 : 200"
            :label="$t('操作')"
            fixed="right"
          >
            <template slot-scope="scope">
              <div class="btn-wrap">
                <bk-button
                  :text="true"
                  :disabled="isPermissionDenied(scope.row)"
                  @click="handleToEdit(scope.row)"
                  >{{ $t('编辑') }}</bk-button
                >
                <bk-button
                  v-show="isAllowSubscriptions(scope.row)"
                  :text="true"
                  @click="handleSubscriptions(scope.row, true)"
                  >{{ $t('订阅') }}</bk-button
                >
                <bk-button
                  v-show="!isAllowSubscriptions(scope.row)"
                  :text="true"
                  @click="handleSubscriptions(scope.row, false)"
                  >{{ $t('取消订阅') }}</bk-button
                >
                <bk-button
                  :text="true"
                  :disabled="isPermissionDenied(scope.row)"
                  @click="handleDele(scope.row, scope.$index)"
                  >{{ $t('删除') }}</bk-button
                >
                <bk-button
                  :text="true"
                  :disabled="isPermissionDenied(scope.row)"
                  @click="handleToClone(scope.row)"
                  >{{ $t('克隆') }}</bk-button
                >
              </div>
            </template>
          </bk-table-column>
        </bk-table>
      </div>
    </list-collapse>
    <!-- 已发送列表 -->
    <!-- <list-collapse
      class="collapse-wrap"
      style="margin-top: 17px"
      :title="$t('已发送')"
      :active-name="sendActiveList"
      @item-click="(arr) => handleItemClick(arr, 'sendActiveList')"
    >
      <div slot="content" class="list-content">
        <bk-table
          v-bkloading="{ isLoading: sendLoading }"
          style="margin-top: 15px"
          :data="sendTableData"
          :outer-border="true"
          :header-border="false"
          :pagination="sendPagination"
          @page-change="(page) => changelistPage(page, 'send')"
          @page-limit-change="(limit) => handlePageLimitChange(limit, 'send')"
        >
          <template v-for="(item, index) in sendListColumnsMap">
            <bk-table-column v-if="item.key === 'isSuccess'" :key="index" :label="$t('发送状态')" prop="isSuccess">
              <template slot-scope="scope">
                <span :class="scope.row.isSuccess ? 'is-success' : 'is-fail'">{{
                  scope.row.isSuccess ? $t('成功') : $t('失败')
                }}</span>
              </template>
            </bk-table-column>
            <bk-table-column
              v-else
              :key="index"
              :label="item.label"
              :prop="item.key"
              :formatter="item.formatter"
            ></bk-table-column>
          </template>
        </bk-table>
      </div>
    </list-collapse> -->
    <!-- 接收人列表浮层 -->
    <receiver-list
      :show.sync="receiverList.show"
      :target="receiverTarget"
      :table-data="receiverList.tableData"
      placement="bottom-end"
    />
  </div>
</template>

<script lang="ts">
import {
  groupList,
  reportClone,
  // statusList,
  reportCreateOrUpdate,
  reportDelete,
  reportList,
} from 'monitor-api/modules/report';
import { deepClone, getCookie, transformDataKey } from 'monitor-common/utils/utils';
import { Component, Vue } from 'vue-property-decorator';

import { isEn } from '../../i18n/lang';

import ListCollapse from './components/list-collapse.vue';
// import { getReceiver } from 'monitor-api/modules/notice_group'
import ReceiverList from './components/receiver-list.vue';
import type { ITableColumnItem } from './types';

import TableSkeleton from '../../components/skeleton/table-skeleton';

const { i18n } = window;
const frequencyMap: string[] = [
  i18n.tc('仅一次'),
  i18n.tc('每天'),
  i18n.tc('每周'),
  i18n.tc('每月'),
  i18n.tc('按小时'),
];
const hourTextMap = {
  0.5: i18n.tc('每个小时整点,半点发送'),
  1: i18n.tc('每个小时整点发送'),
  2: i18n.tc('从0点开始,每隔2小时整点发送'),
  6: i18n.tc('从0点开始,每隔6小时整点发送'),
  12: i18n.tc('每天9:00,21:00发送'),
};
// let groupList: any = []
/**
 * 邮件订阅列表页
 */
@Component({
  name: 'email-subscriptions',
  components: {
    ListCollapse,
    ReceiverList,
    TableSkeleton,
  },
})
export default class EmailSubscriptions extends Vue {
  private subscribedLoading = false;
  // private sendLoading = false;
  // 已订阅列表数据
  private subscribedTableData: any = [];
  private subscribedAllData: any = [];
  private subscribedPagination = {
    current: 1,
    count: 0,
    limit: 10,
  };

  private isEn = false;

  // 已发送列表
  // private sendTableData: any = [];
  private sendAllData: any = [];
  private sendPagination = {
    current: 1,
    count: 0,
    limit: 10,
  };

  // 已经订阅表格列数据
  private subListColumnsMap: ITableColumnItem[] = [
    { label: 'ID', key: 'id', formatter: row => `#${row.id}`, width: 100 },
    { label: i18n.t('邮件标题'), key: 'mailTitle', overflow: true },
    { label: i18n.t('发送频率'), key: 'frequency', width: 120, formatter: row => frequencyMap[row.frequency.type] },
    {
      label: i18n.t('发送时间'),
      key: 'lastSendTime',
      width: 300,
      overflow: true,
      formatter: row => {
        const weekMap = [
          i18n.t('周一'),
          i18n.t('周二'),
          i18n.t('周三'),
          i18n.t('周四'),
          i18n.t('周五'),
          i18n.t('周六'),
          i18n.t('周日'),
        ];
        let str = '';
        switch (row.frequency.type) {
          case 3: {
            const weekStrArr = row.frequency.weekList.map(item => weekMap[item - 1]);
            const weekStr = weekStrArr.join(', ');
            str = `${weekStr} ${row.frequency.runTime}`;
            break;
          }
          case 4: {
            const dayArr = row.frequency.dayList.map(item => `${item}号`);
            const dayStr = dayArr.join(', ');
            str = `${dayStr} ${row.frequency.runTime}`;
            break;
          }
          case 5: {
            str = hourTextMap[row.frequency.hour];
            break;
          }
          default:
            str = row.frequency.runTime;
            break;
        }
        return str;
      },
    },
    {
      label: i18n.t('管理员'),
      key: 'createUser',
      width: 340,
      overflow: true,
      formatter: row => this.managerFormatter(row),
    },
    {
      label: i18n.t('订阅状态'),
      key: 'receivers',
    },
    { label: i18n.t('启/停'), key: 'isEnabled' },
  ];

  // private sendListColumnsMap: ITableColumnItem[] = [
  //   { label: i18n.t('发送时间'), key: 'createTime' },
  //   { label: i18n.t('发送标题'), key: 'mailTitle' },
  //   { label: i18n.t('发送者'), key: 'username' },
  //   {
  //     label: i18n.t('接收者'),
  //     key: 'receivers',
  //     formatter: row => (row?.details?.receivers?.length ? row.receivers.join(', ') : '--')
  //   },
  //   { label: i18n.t('发送状态'), key: 'isSuccess' }
  // ];

  // 折叠组件数据
  private subAcitveList: string[] = ['1'];
  // private sendActiveList: string[] = ['1'];

  // 接收人数据
  private receiverList: any = {
    show: false,
    tableData: [],
  };
  private receiverTarget = null;
  private groupList = [];

  async created() {
    await this.getReceiver();
    this.isEn = isEn;
    this.getSubscribedList();
    // this.getSendList();
  }

  private managerFormatter(row) {
    return row.managers
      .filter(item => !item.group)
      .map((v, index, arr) => {
        const userId = v.type === 'group' ? this.groupList.find(me => me.id === v.id)?.display_name : v.id;
        return [
          this.$createElement('bk-user-display-name', {
            attrs: {
              'user-id': userId,
            },
          }),
          index === arr.length - 1 ? '' : ',',
        ];
      });
  }

  /**
   * 翻页
   */
  private changelistPage(page: number, type: 'subscribed' | 'send') {
    const temp = type === 'subscribed' ? this.subscribedPagination : this.sendPagination;
    temp.current = page;
    const { current, limit } = temp;
    const start = (current - 1) * limit;
    const end = current * limit;
    if (type === 'subscribed') {
      this.subscribedTableData = this.subscribedAllData.slice(start, end);
    } else {
      // this.sendTableData = this.sendAllData.slice(start, end);
    }
  }

  /**
   * 切换每页数量
   */
  private handlePageLimitChange(limit: number, type: 'subscribed' | 'send') {
    const temp = type === 'subscribed' ? this.subscribedPagination : this.sendPagination;
    temp.limit = limit;
    this.changelistPage(1, type);
  }

  /**
   * 已订阅列表
   */
  private getSubscribedList(needLoading = true) {
    needLoading && (this.subscribedLoading = true);
    return reportList()
      .then(res => {
        this.subscribedAllData = transformDataKey(res);
        this.subscribedPagination.count = res.length;
        this.changelistPage(1, 'subscribed');
      })
      .finally(() => needLoading && (this.subscribedLoading = false));
  }

  /**
   * 已发送列表
   */
  // private getSendList() {
  //   this.sendLoading = true;
  //   statusList()
  //     .then((res) => {
  //       this.sendAllData = transformDataKey(res);
  //       this.sendPagination.count = res.length;
  //       this.changelistPage(1, 'send');
  //     })
  //     .finally(() => (this.sendLoading = false));
  // }

  /**
   * 人员信息
   */
  private getReceiver() {
    this.subscribedLoading = true;
    return groupList({ bk_biz_id: this.$store.getters.bizId || +window.cc_biz_id })
      .then(res => {
        this.groupList = res;
      })
      .finally(() => (this.subscribedLoading = false));
  }

  private handleItemClick(arr: string[], type: 'subAcitveList' | 'sendActiveList') {
    this[type] = arr;
  }

  private handleRouterTo(name: string) {
    this.$router.push({
      name,
    });
  }

  /**
   * 权限
   * 超级管理员或者邮件创建人有权限
   */
  private isPermissionDenied(row: any) {
    const { userName } = this.$store.state.app;
    const { isSuperUser } = this.$store.state.app;
    const isManager = row.managers.some(item => item.type === 'user' && item.id === userName);
    return !(isSuperUser || isManager);
  }

  /**
   * 订阅按钮状态
   */
  private isAllowSubscriptions(row) {
    const curReceivers = this.getCurReceivers(row);
    return curReceivers ? !curReceivers.isEnabled : true;
  }

  private getCurReceivers(row) {
    const { userName } = this.$store.state.app;
    return row.receivers.find(item => item.type === 'user' && item.id === userName);
  }

  /**
   * 订阅操作
   */
  private handleSubscriptions(row, bool) {
    const { userName } = this.$store.state.app;
    const curReceivers = this.getCurReceivers(row);
    let params = {
      reportItemId: row.id,
      receivers: curReceivers
        ? row.receivers.map(item => {
            const temp = deepClone(item);
            if (temp.id === curReceivers.id) temp.isEnabled = !temp.isEnabled;
            return temp;
          })
        : [...row.receivers, { id: userName, name: userName, isEnabled: bool, type: 'user' }],
    };
    params = transformDataKey(params, true);
    this.$bkInfo({
      title: this.$t(bool ? '重新订阅' : '取消订阅该邮件，且不再显示？'),
      width: getCookie('blueking_language') === 'en' && !bool ? 500 : 400,
      confirmLoading: true,
      // eslint-disable-next-line @typescript-eslint/no-misused-promises
      confirmFn: async () => {
        try {
          await reportCreateOrUpdate(params).then(() => {
            curReceivers
              ? (curReceivers.isEnabled = bool)
              : row.receivers.push({ id: userName, name: userName, isEnabled: bool, type: 'user' });
            if (this.isAllowSubscriptions(row) && !bool && this.isPermissionDenied(row)) {
              const index = this.subscribedAllData.findIndex(item => item.id === row.id);
              this.subscribedAllData.splice(index, 1);
              this.changelistPage(this.subscribedPagination.current, 'subscribed');
            }
          });
          this.$bkMessage({ message: this.$t(bool ? '订阅成功' : '取消订阅成功'), theme: 'success' });
          return true;
        } catch (e) {
          console.warn(e);
          return false;
        }
      },
    });
  }

  /**
   * 启停操作
   */
  private handleSwitchChange(row: any) {
    const params = {
      report_item_id: row.id,
      is_enabled: row.isEnabled,
    };
    reportCreateOrUpdate(params).catch(() => {
      row.isEnabled = !row.isEnabled;
    });
  }

  /**
   * 编辑
   */
  private handleToEdit(row) {
    this.$router.push({
      name: 'email-subscriptions-edit',
      params: {
        id: row.id,
      },
    });
  }

  /**
   * 删除
   */
  private handleDele(row, index) {
    this.$bkInfo({
      title: this.$t('删除订阅'),
      confirmLoading: true,
      // eslint-disable-next-line @typescript-eslint/no-misused-promises
      confirmFn: async () => {
        try {
          await reportDelete({ report_item_id: row.id }).then(() => {
            this.subscribedTableData.splice(index, 1);
            const i = this.subscribedAllData.findIndex(item => item.id === row.id);
            this.subscribedAllData.splice(i, 1);
            this.subscribedPagination.count = this.subscribedAllData.length;
            if (!this.subscribedTableData.length && this.subscribedPagination.current > 1) {
              this.changelistPage(this.subscribedPagination.current - 1, 'subscribed');
            }
          });
          this.$bkMessage({ message: this.$t('删除成功'), theme: 'success' });
          return true;
        } catch (e) {
          console.warn(e);
          return false;
        }
      },
    });
  }
  /**
   * 克隆订阅
   */
  private handleToClone(row) {
    this.subscribedLoading = true;
    reportClone({ report_item_id: row.id })
      .then(() => {
        this.$bkMessage({ theme: 'success', message: this.$t('克隆成功') });
        this.getSubscribedList(false).finally(() => (this.subscribedLoading = false));
      })
      .catch(() => (this.subscribedLoading = false));
  }

  private handleReceiversList(event, row) {
    let tableData = [];
    row.receivers.forEach(item => {
      if (item.type !== 'group') {
        tableData.push(item);
      }
    });
    tableData = tableData.map(item => {
      item.name = item.name || item.id;
      return item;
    });
    this.receiverTarget = event.target;
    this.receiverList.tableData = tableData;
    this.receiverList.show = true;
  }
}
</script>

<style lang="scss">
.email-subscriptions-wrap {
  margin: 24px;

  .collapse-wrap {
    .list-header {
      color: #63656e;
    }

    .title {
      font-size: 12px;
      font-weight: 700;

      &:hover {
        color: #3a84ff;
      }
    }

    .btn-wrap {
      & > :not(:first-child) {
        margin-left: 6px;
      }
    }
  }

  .header-btn {
    display: flex;
    align-items: center;
    margin-left: 39px;
    font-size: 12px;
    color: #3a84ff;
    cursor: pointer;

    .icon-mc-plus-fill {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 16px;
      height: 16px;
      margin-right: 6px;
      margin-bottom: 2px;
      font-size: 16px;
    }
  }

  .list-content {
    background-color: #fff;

    .receivers-status {
      display: flex;
      align-items: center;
      font-size: 0;

      .icon-audit {
        margin-left: 3px;
        font-size: 14px;
        color: #3a84ff;
        cursor: pointer;
      }

      .text {
        font-size: 12px;
      }
    }
  }

  .is-success {
    color: #2dcb56;
  }

  .is-fail {
    color: #ea3636;
  }
}
</style>
