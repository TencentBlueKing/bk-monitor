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
  <div class="alarm-info">
    <van-collapse
      class="alarm-info-header"
      :value="header.active"
      @change="handleCollapseChange"
    >
      <van-collapse-item
        v-for="item in header.list"
        :key="item.id"
        class="header-item"
        :border="item.id !== 'message'"
        :is-link="item.id === 'message'"
        :name="item.id"
        :title="item.title"
      >
        <template
          v-if="item.id !== 'message'"
          #value
        >
          {{ item.value }}
        </template>
        <template v-else-if="item.value">
          <div class="header-item-pre">{{ item.value }}</div>
        </template>
      </van-collapse-item>
    </van-collapse>
    <div class="list-title">
      {{ `${$t('事件列表')}(${(eventList && eventList.length) || 0})` }}
    </div>
    <van-list class="card-list">
      <div
        v-for="(item, index) in eventList"
        :key="index"
        class="card-list-item"
        @click="handleGotoDetail(item)"
      >
        <div class="card-title">
          <span class="van-ellipsis">{{ item.title }}</span>
          <!-- 已恢复、已关闭 -->
          <span
            v-if="['closed', 'recovered'].includes(item.status.toLocaleLowerCase())"
            :class="`status-${item.status.toLocaleLowerCase()}`"
          >
            {{ `（${statusMap[item.status]}）` }}
          </span>
          <!-- 已确认 -->
          <span
            v-else-if="item.isAck"
            class="status-recovered"
          >
            {{ `（${$t('已确认')}）` }}
          </span>
          <!-- 未恢复已屏蔽 -->
          <span
            v-else-if="item.isShielded && item.shieldType === 'saas_config'"
            class="status-abnormal"
          >
            {{ `（${$t('已屏蔽')}）` }}
          </span>
          <!-- 未恢复已抑制 -->
          <span
            v-else-if="item.isShielded && item.shieldType !== 'saas_config'"
            class="status-abnormal"
          >
            {{ `（${$t('已抑制')}）` }}
          </span>
          <!-- 未恢复 -->
          <span
            v-else
            class="status-abnormal"
          >
            {{ `（${$t('未恢复')}）` }}
          </span>
        </div>
        <div class="card-date">
          {{ item.firstAnomalyTime }}
        </div>
        <div class="card-content">
          <div class="card-content-left">
            <div class="card-line">
              {{ `${$t('策略')}：${item.strategyName}` }}
            </div>
            <div class="card-line">
              {{ `${$t('时长')}：${item.duration}` }}
            </div>
          </div>
          <div
            v-if="item.dataTypeLabel === 'time_series'"
            class="card-content-right"
            @click.stop
          >
            <monitor-mobile-echarts
              height="70"
              class="card-chart"
              :get-series-data="() => handleGetChartData(item)"
              :options="chartOption"
              @click="handleGotoTendency(item)"
            />
          </div>
        </div>
        <van-button
          class="card-button"
          :disabled="item.isShielded"
          type="info"
          plain
          @click.stop="!item.isShielded && handleGotoShield(item.id)"
        >
          {{ $t('快捷屏蔽') }}
        </van-button>
      </div>
    </van-list>
    <footer-button
      :disabled="alarmConfirmDisabled"
      @click="handleAlarmCheck"
    >
      {{ alarmConfirmDisabled ? $t('告警已确认') : $t('告警确认') }}
    </footer-button>
    <div class="mask-bottom" />
  </div>
</template>
<script lang="ts">
import { Component, Prop, Vue, Watch } from 'vue-property-decorator';

import dayjs from 'dayjs';
import { getUrlParam } from 'monitor-common/utils/utils';
import { Button, Cell, Collapse, CollapseItem, Dialog, List, PullRefresh } from 'vant';

import { ackEvent } from '../../../monitor-api/modules/mobile_event';
import MonitorMobileEcharts from '../../../monitor-ui/monitor-echarts/monitor-mobile-echarts.vue';
import FooterButton from '../../components/footer-button/footer-button.vue';
import AlarmModule from '../../store/modules/alarm-info';

import type { IEventItem, IHeader, IStatusMap } from '../../types/alarm-info';

@Component({
  name: 'AlarmInfo',
  components: {
    [Collapse.name]: Collapse,
    [CollapseItem.name]: CollapseItem,
    [PullRefresh.name]: PullRefresh,
    [List.name]: List,
    [Cell.name]: Cell,
    [Button.name]: Button,
    FooterButton,
    MonitorMobileEcharts,
  },
})
export default class AlarmDetail extends Vue {
  public header: IHeader = { list: [], active: [] };
  public loading = false;
  public eventList: IEventItem[] = [];
  public statusMap: IStatusMap = null;
  public alarmStatus = 1;
  @Prop() readonly routeKey: string;

  get alarmConfirmDisabled() {
    return this.eventList.every(item => item.isAck);
  }
  get chartOption() {
    return {
      color: ['#a0b0cb'],
      legend: {
        show: false,
      },
      grid: {
        show: true,
        left: 0,
        top: 2,
        right: 0,
        bottom: 2,
        backgroundColor: '#fafbfd',
        borderColor: '#fafbfd',
      },
      tooltip: {
        show: false,
      },
      toolbox: {
        show: false,
      },
      xAxis: {
        show: false,
      },
      yAxis: {
        show: false,
      },
    };
  }
  @Watch('routeKey')
  onRouteKeyChange() {
    this.handleGetAlarmInfo();
  }

  created() {
    this.statusMap = {
      ABNORMAL: this.$t('未恢复'),
      SHIELD_ABNORMAL: this.$t('已屏蔽未恢复'),
      CLOSED: this.$t('已失效'),
      RECOVERED: this.$t('已恢复'),
    };
  }

  activated() {
    this.handleGetAlarmInfo();
  }

  async handleGetAlarmInfo() {
    const data = await AlarmModule.getAlarmInfo();
    this.$store.commit('app/SET_APP_DATA', {
      bkBizName: data.bkBizName,
    });
    this.header.list = [
      {
        id: 'bkBizName',
        value: data.bkBizName || '--',
        title: this.$t('业务名'),
      },
      {
        id: 'alarmDate',
        value: data.collectTime ? data.collectTime.slice(0, 19) : '',
        title: this.$t('告警时间'),
      },
      {
        id: 'message',
        value: data.message,
        title: this.$t('信息摘要'),
      },
    ];
    this.eventList = data?.events || [];
    this.handleBatchAction();
  }

  // 自动弹窗确认框或跳转到屏蔽页(取第一个事件跳转到屏蔽页)
  handleBatchAction() {
    if (this.eventList.length) {
      const type = getUrlParam('batchAction');
      if (type === 'ack') {
        this.handleAlarmCheck();
      } else if (type === 'shield') {
        this.handleGotoShield(this.eventList[0].id);
      }
    }
  }

  closeBatchAction() {
    if (/batchAction=(ack|shield)/g.test(location.href)) {
      window.history.replaceState({}, '', location.href.replace(/&?batchAction=(ack|shield)/g, ''));
    }
  }

  async handleGetChartData(item: IEventItem) {
    const data = await AlarmModule.getChartData({
      event_id: item.id,
      start_time: dayjs().add(-1, 'h').unix(),
      end_time: dayjs().unix(),
    });
    let series = data.filter(item => item?.metric?.metric_field === 'value');
    series = series.length ? series : data;
    return {
      series: (series || []).map(({ markPoints, thresholds, markTimeRange, ...item }) => ({
        ...item,
        areaStyle: {
          color: '#e8ebf3',
        },
      })),
    };
  }

  // 点击展开更多信息摘要
  handleCollapseChange(v: string[]) {
    this.header.active = v.includes('message') ? ['message'] : [];
  }

  // 点击告警确认触发
  handleAlarmCheck() {
    const params = { alert_collect_id: this.$store.state.app.collectId };
    Dialog.confirm({
      title: this.$tc('告警确认'),
      message: String(
        this.$t('告警确认后，异常事件持续未恢复的情况将不会再发起通知；注意！请及时处理故障，以免影响业务正常运行。')
      ),
      beforeClose: (action, done) => {
        if (action === 'confirm') {
          ackEvent(params)
            .then(() => {
              done();
              this.handleGetAlarmInfo();
            })
            .catch(() => done());
          this.closeBatchAction();
        } else {
          done();
          this.closeBatchAction();
        }
      },
    });
  }

  // 跳转至告警详情
  handleGotoDetail({ title, id }) {
    this.$router.push({
      name: 'alarm-detail',
      params: {
        title,
        id,
      },
    });
  }

  // 跳转至告警屏蔽
  handleGotoShield(eventId) {
    this.$store.commit('app/SET_EVENT_ID', eventId);
    this.$router.push({
      name: 'quick-alarm-shield',
      params: {
        eventId,
      },
    });
  }

  // 跳转至趋势图
  handleGotoTendency({ id }) {
    this.$router.push({
      name: 'tendency-chart',
      params: {
        id,
      },
    });
  }
}
</script>
<style lang="scss">
@import '../../static/scss/variate';

$colorList: $deadlyColor $shieldColor $shieldColor $recoverColor;
$statusList: 'abnormal' 'shield_abnormal' 'closed' 'recovered';

.alarm-info {
  position: relative;
  font-size: 14px;

  &-header {
    box-shadow: 0 1px 0 0 rgb(99 101 110 / 5%);

    &.van-hairline {
      &--top-bottom::after {
        border-width: 0;
      }
    }

    .header-item {
      &-pre {
        padding: 0;
        margin: 0;
        font-size: 12px;
        line-height: 20px;
        color: #63656e;
        word-break: break-all;
        white-space: pre-line;
      }

      &.van-hairline {
        &--top::after {
          right: -45%;
          left: -45%;
        }
      }

      .van-collapse-item__content {
        padding: 10px 16px;
      }

      .content-list {
        display: flex;
        flex-direction: column;
        color: #63656e;

        &-item {
          display: flex;
          margin-bottom: 4px;
          font-size: 14px;
          line-height: 20px;

          .item-label {
            min-width: 42px;
          }

          .item-content {
            display: flex;
            flex: 1;
            flex-wrap: wrap;
            word-break: break-all;
          }
        }
      }
    }
  }

  .list-title {
    display: flex;
    align-items: center;
    height: 46px;
    margin: 0 20px;
    color: #979ba5;
  }

  .card-list {
    display: flex;
    flex-direction: column;
    padding-bottom: 60px;

    &-item {
      position: relative;
      padding: 15px 20px;
      margin: 0 16px 8px;
      background-color: #fff;
      border-radius: 4px;
      box-shadow: 0 1px 0 0 rgb(99 101 110 / 5%);

      .card-title {
        display: flex;
        align-items: center;
        margin-bottom: 2px;
        font-size: 16px;
        font-weight: bold;
        color: black;

        @for $i from 1 through 4 {
          /* stylelint-disable-next-line function-no-unknown */
          .status-#{nth($statusList, $i)} {
            font-size: 12px;
            font-weight: normal;

            /* stylelint-disable-next-line function-no-unknown */
            color: nth($colorList, $i);
          }
        }

        .van-ellipsis {
          display: inline-block;
          max-width: 52%;
        }
      }

      .card-date {
        margin-bottom: 10px;
        color: #979ba5;
      }

      .card-content {
        display: flex;
        justify-content: space-between;

        &-left {
          .card-line {
            margin-bottom: 2px;
            color: $defaultFontColor;
          }
        }

        &-right {
          position: absolute;
          top: 50px;
          right: 20px;
          flex: 0;
          flex-basis: 88px;
        }
      }

      .card-button {
        position: absolute;
        top: 20px;
        right: 20px;
        height: 28px;
        line-height: 27px;
      }
    }
  }

  .mask-bottom {
    position: fixed;
    bottom: 0;
    width: 100%;
    height: 15px;
    background: linear-gradient(rgb(255 255 255 / 0%) 0, #fff 100%);
  }
}
</style>
