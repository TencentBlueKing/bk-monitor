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
  <div class="alarm-shield-container">
    <common-nav-bar
      :route-list="routeList"
      need-back
      :position-text="positionText"
      need-copy-link
      nav-mode="copy"
    />
    <div
      class="alarm-shield-content"
      v-bkloading="{ isLoading: loading }"
    >
      <div class="operation">
        <bk-button
          style="width: 88px; margin-right: 8px;"
          theme="primary"
          outline
          v-authority="{ active: !authority.MANAGE_AUTH }"
          @click="handleEditShield"
        >
          {{ $t('编辑') }}
        </bk-button>
        <history-dialog :list="historyList" />
      </div>
      <div
        v-if="detailData.category === 'scope'"
        class="title"
      >{{ $t('基于范围进行屏蔽') }}</div>
      <div
        v-else-if="detailData.category === 'strategy'"
        class="title"
      >{{ $t('基于策略进行屏蔽') }}</div>
      <div
        v-else-if="detailData.category === 'event'"
        class="title"
      >{{ $t('基于告警事件进行屏蔽') }}</div>
      <div class="scope-item">
        <div class="item-label">
          {{ $t('所属') }}
        </div>
        <div class="item-content">
          {{ bizName }}
        </div>
      </div>
      <div class="scope-item">
        <div class="item-label">
          {{ $t('屏蔽状态') }}
        </div>
        <div class="item-content">
          <span :style="{ color: statusColorMap[detailData.status] }">{{ statusMap[detailData.status] }}</span>
        </div>
      </div>
      <!-- 屏蔽对象的详情展示 -->
      <component
        v-if="!loading"
        :is="componentId"
        :dimension="detailData.dimensionConfig"
        :detail-data="detailData"
      />
      <!-- 时间范围 -->
      <div class="scope-item">
        <div class="item-label">
          {{ $t('屏蔽周期') }}
        </div>
        <div class="item-content">
          {{ cycleMap[cycleConfig.type] }}
        </div>
      </div>
      <div class="scope-item">
        <div class="item-label">
          {{ $t('时间范围') }}
        </div>
        <div
          v-if="cycleConfig.type === 1"
          class="item-data"
        >{{ detailData.beginTime }} ~ {{ detailData.endTime }}</div>
        <div
          v-else-if="cycleConfig.type === 2"
          class="item-data"
        >
          {{ $t('每天的') }}&nbsp;<span
            class="item-highlight"
          >{{ cycleConfig.startTime }} ~ {{ cycleConfig.endTime }}</span>&nbsp;{{ $t('进行告警屏蔽') }}
        </div>
        <div
          v-else-if="cycleConfig.type === 3"
          class="item-data"
        >
          {{ $t('每周') }}&nbsp;<span class="item-highlight">{{ cycleConfig.weekList }}</span>&nbsp;{{ $t('的') }}&nbsp;<span
            class="item-highlight"
          >{{ cycleConfig.startTime }} ~ {{ cycleConfig.endTime }}</span>&nbsp;{{ $t('进行告警屏蔽') }}
        </div>
        <div
          v-else-if="cycleConfig.type === 4"
          class="item-data"
        >
          {{ $t('每月') }}&nbsp;<span class="item-highlight">{{ cycleConfig.dayList }}</span>&nbsp;{{ $t('日的') }}&nbsp;<span
            class="item-highlight"
          >{{ cycleConfig.startTime }} ~ {{ cycleConfig.endTime }}</span>&nbsp;{{ $t('进行告警屏蔽') }}
        </div>
      </div>
      <div
        v-if="cycleConfig.type !== 1"
        class="scope-item"
      >
        <div class="item-label">
          {{ $t('日期范围') }}
        </div>
        <div class="item-content">
          {{ detailData.beginTime }} ~ {{ detailData.endTime }}
        </div>
      </div>
      <!-- 屏蔽原因 -->
      <div class="scope-item">
        <div class="item-label">
          {{ $t('屏蔽原因') }}
        </div>
        <div class="item-content">
          <pre style="margin: 0; white-space: pre-wrap">
{{ detailData.description || '--' }}
</pre>
        </div>
      </div>
      <!-- 通知方式 -->
      <div v-if="detailData.shieldNotice">
        <div
          class="scope-item"
          style="margin-bottom: 10px"
        >
          <div class="item-label item-img">
            {{ $t('通知对象') }}
          </div>
          <div class="item-content">
            <div
              class="personnel-choice"
              v-for="(item, index) in noticeConfig.receiver"
              :key="index"
            >
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
              <span>{{ item.displayName }}</span>
            </div>
          </div>
        </div>
        <div class="scope-item">
          <div class="item-label">
            {{ $t('通知方式') }}
          </div>
          <div class="item-content">
            {{ noticeConfig.way }}；
          </div>
        </div>
        <div class="scope-item">
          <div class="item-label">
            {{ $t('通知时间') }}
          </div>
          <i18n
            path="屏蔽开始/结束前{0}分钟发送通知"
            tag="div"
            class="item-data"
          >
            <span class="item-highlight">&nbsp;{{ noticeConfig.time }}&nbsp;</span>
          </i18n>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { mapMutations } from 'vuex';

import { shieldSnapshot } from '../../../../monitor-api/modules/alert_events';
import { getNoticeWay } from '../../../../monitor-api/modules/notice_group';
import { frontendShieldDetail } from '../../../../monitor-api/modules/shield';
import { transformDataKey } from '../../../../monitor-common/utils/utils';
import HistoryDialog from '../../../components/history-dialog/history-dialog';
import authorityMixinCreate from '../../../mixins/authorityMixin';
import { SET_NAV_ROUTE_LIST } from '../../../store/modules/app';
import * as alarmShieldAuth from '../../authority-map';
import CommonNavBar from '../../monitor-k8s/components/common-nav-bar';

import AlarmShieldDetailDimension from './alarm-shield-detail-dimension.tsx';
import AlarmShieldDetailEvent from './alarm-shield-detail-event.vue';
import AlarmShieldDetailScope from './alarm-shield-detail-scope.vue';
import AlarmShieldDetailStrategy from './alarm-shield-detail-strategy.vue';

export default {
  name: 'AlarmShieldDetail',
  components: {
    AlarmShieldDetailScope,
    AlarmShieldDetailEvent,
    AlarmShieldDetailStrategy,
    AlarmShieldDetailDimension,
    CommonNavBar,
    HistoryDialog
  },
  mixins: [authorityMixinCreate(alarmShieldAuth)],
  props: {
    id: [Number, String],
    fromRouteName: {
      type: String,
      default: ''
    }
  },
  data() {
    return {
      loading: false,
      bizName: '',
      detailData: {}, // 屏蔽详情数据
      title: '',
      routeList: Object.freeze([{ id: 'alarm-shield-detail', name: this.$t('告警屏蔽详情') }]),
      typeMap: [
        {
          type: 'scope',
          title: this.$t('基于范围进行屏蔽'),
          componentId: 'AlarmShieldDetailScope'
        },
        {
          type: 'strategy',
          title: this.$t('基于策略进行屏蔽'),
          componentId: 'AlarmShieldDetailStrategy'
        },
        {
          type: 'event',
          title: this.$t('基于告警事件进行屏蔽'),
          componentId: 'AlarmShieldDetailEvent'
        },
        {
          type: 'alert',
          title: this.$t('基于告警事件进行屏蔽'),
          componentId: 'AlarmShieldDetailEvent'
        },
        {
          type: 'dimension',
          title: this.$t('基于维度进行屏蔽'),
          componentId: 'AlarmShieldDetailDimension'
        }
      ],
      componentId: 'AlarmShieldDetailScope',
      statusMap: ['', this.$t('屏蔽中'), this.$t('已过期'), this.$t('被解除')],
      statusColorMap: {
        [this.$t('屏蔽中')]: '#63656E',
        [this.$t('被解除')]: '#FF9C01',
        [this.$t('已过期')]: '#C4C6CC'
      },
      // 时间，日期数据
      cycleConfig: {},
      cycleMap: ['', this.$t('单次'), this.$t('每天'), this.$t('每周'), this.$t('每月')],
      weekListMap: [
        '',
        this.$t('星期一'),
        this.$t('星期二'),
        this.$t('星期三'),
        this.$t('星期四'),
        this.$t('星期五'),
        this.$t('星期六'),
        this.$t('星期日')
      ],
      strategyStatusMap: {
        UPDATED: this.$t('（已修改）'),
        DELETED: this.$t('（已修改）'),
        UNCHANGED: ''
      },
      // 通知方式数据
      noticeConfig: {}
    };
  },
  computed: {
    // 是否事件中心跳转过来
    fromEvent() {
      return this.fromRouteName === 'event-center-detail';
    },
    positionText() {
      return `${this.$t('屏蔽ID')}：${this.detailData.id || ''}`;
    },
    historyList() {
      return [
        { label: this.$t('创建人'), value: this.detailData.createUser || '--' },
        { label: this.$t('创建时间'), value: this.detailData.createTime || '--' },
        { label: this.$t('最近更新人'), value: this.detailData.updateUser || '--' },
        { label: this.$t('修改时间'), value: this.detailData.updateTime || '--' }
      ];
    }
  },
  watch: {
    id(newId, oldId) {
      if (`${newId}` !== `${oldId}`) {
        this.getDetailData(newId);
      }
    }
  },
  mounted() {
    const { params } = this.$route;
    this.updateNavData(this.$t('查看'));
    this.$nextTick(() => {
      this.getDetailData(params.id, params.eventId);
    });
  },
  methods: {
    ...mapMutations('app', ['SET_NAV_TITLE']),
    async getNoticeWay() {
      let noticeWay = [];
      await getNoticeWay({ bk_biz_id: this.bizId }).then((data) => {
        noticeWay = data;
      });
      return noticeWay;
    },
    /** 更新面包屑 */
    updateNavData(name = '') {
      if (!name) return;
      const routeList = [];
      routeList.push({
        name,
        id: ''
      });
      this.$store.commit(`app/${SET_NAV_ROUTE_LIST}`, routeList);
    },
    // 获取屏蔽详情数据
    async getDetailData(id, eventId) {
      this.loading = true;
      let data = {};
      if (this.fromEvent) {
        data = await shieldSnapshot({
          shield_snapshot_id: id,
          id: eventId
        })
          .then(data => transformDataKey(data))
          .catch(() => ({}));
        const statusText = this.strategyStatusMap[data.shield_status];
        this.updateNavData(`${this.$t('查看')} ${statusText ? `#${data.id}${statusText}` : `#${data.id}`}`);
      } else {
        data = await frontendShieldDetail({ id })
          .then(data => transformDataKey(data))
          .catch(() => {
            this.$bkMessage({ theme: 'error', message: this.$t('屏蔽详情获取失败') });
            this.loading = false;
          });
        this.updateNavData(`${this.$t('查看')} #${id}`);
      }
      this.detailData = data;
      this.handleDetailData(data);
    },
    // 处理屏蔽详情数据
    async handleDetailData(data) {
      // 筛选出所属空间
      const bizItem = this.$store.getters.bizList.filter(item => data.bkBizId === item.id);
      this.bizName = bizItem[0].text;
      // type处理
      const { title, componentId } = this.typeMap.find(item => item.type === data.category);
      this.title = title;
      this.componentId = componentId;
      // 时间，日期处理
      const weekList = data.cycleConfig.weekList.map(item => this.weekListMap[item]);
      this.cycleConfig = {
        type: data.cycleConfig.type,
        startTime: data.cycleConfig.beginTime,
        endTime: data.cycleConfig.endTime,
        dayList: data.cycleConfig.dayList.join('、'),
        weekList: weekList.join('、')
      };
      // 通知方式处理 shieldNotice: 是否开启通知方式
      if (data.shieldNotice) {
        const { noticeConfig } = data;
        const noticeWay = await this.getNoticeWay();
        const way = noticeConfig.noticeWay.map((item) => {
          const res = noticeWay.find(el => el.type === item);
          return res.label;
        });
        this.noticeConfig = {
          receiver: noticeConfig.noticeReceiver,
          way: way.join('；'),
          time: noticeConfig.noticeTime
        };
      }
      this.loading = false;
    },
    handleEditShield() {
      this.$router.push({
        name: 'alarm-shield-edit',
        params: {
          id: this.detailData.id,
          type: this.detailData.category
        }
      });
    }
  }
};
</script>

<style lang="scss" scoped>
.common-nav-bar {
  padding-left: 19px;
}

.alarm-shield-content {
  min-height: calc(100vh - 102px);
  padding: 18px 94px 18px 30px;
  margin: 20px;
  font-size: 14px;
  color: #63656e;
  background: #fff;
  border: 1px solid #dcdee5;
  border-radius: 2px;

  .operation {
    position: absolute;
    top: 16px;
    right: 24px;
    font-size: 0;
  }

  .title {
    margin-bottom: 23px;
    font-size: 14px;
    font-weight: bold;
    color: #313238;
  }

  .scope-item {
    display: flex;
    align-items: flex-start;
    margin-bottom: 20px;

    .item-label {
      min-width: 90px;
      margin-right: 24px;
      color: #979ba5;
      text-align: right;
    }

    .item-img {
      margin-top: 4px;
    }

    .item-data {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      min-height: 19px;

      .item-highlight {
        font-weight: bold;
        color: #3a84ff;
      }
    }

    .item-content {
      display: flex;
      flex-wrap: wrap;
      align-items: flex-end;
      min-height: 19px;
      word-break: break-all;

      .personnel-choice {
        display: flex;
        align-items: center;
        margin: 0 21px 10px 0;

        img {
          width: 24px;
          height: 24px;
          margin-right: 5px;
          border-radius: 16px;
        }

        .no-img {
          margin-right: 5px;
          font-size: 24px;
          color: #c4c6cc;
          background: #fafbfd;
          border-radius: 16px;
        }
      }
    }
  }
}
</style>
