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
    v-if="selectAlarm"
    class="business-alarm"
  >
    <panel-card
      class="left"
      :title="$t('业务监控状态总览')"
    >
      <business-alarm-aquare
        class="content"
        :is-all-normal.sync="isAllNormal"
        :selected-index.sync="selectedIndex"
        :squares="businessAlarm"
        :status="selectAlarm.status"
      />
    </panel-card>
    <div class="right">
      <!-- <all-overview v-if="isAllNormal" :selected-index.sync="selectedIndex" :business-alarm="businessAlarm" :alarm="selectAlarm"></all-overview> -->
      <business-alarm-panel
        v-show="!isAllNormal"
        :icon="selectAlarm.status"
        :title="selectTitle"
      >
        <keep-alive>
          <uptimecheck
            v-if="selectAlarm.name === alarmMap.uptimecheck"
            :alarm="selectAlarm"
          />
          <service
            v-if="selectAlarm.name === alarmMap.service"
            :alarm="selectAlarm"
          />
          <process
            v-if="selectAlarm.name === alarmMap.process"
            :alarm="selectAlarm"
          />
          <os
            v-if="selectAlarm.name === alarmMap.os"
            :alarm="selectAlarm"
          />
        </keep-alive>
      </business-alarm-panel>
    </div>
  </section>
</template>

<script>
// import AllOverview from './all-overview'
import { alarmDetailChartData } from 'monitor-api/modules/event_center';

import BusinessAlarmPanel from '../components/business-alarm-panel/business-alarm-panel';
import BusinessAlarmAquare from '../components/business-alarm-square/business-alarm-square';
import PanelCard from '../components/panel-card/panel-card';
import Os from './os';
import Process from './process';
import Service from './service';
import Uptimecheck from './uptimecheck';

export default {
  name: 'BusinessAlarmOverview',
  components: {
    BusinessAlarmAquare,
    PanelCard,
    BusinessAlarmPanel,
    Uptimecheck,
    Service,
    Os,
    Process,
    // AllOverview
  },
  props: {
    businessAlarm: {
      type: Array,
      required: true,
      default: () => [],
    },
  },
  data() {
    return {
      selectedIndex: 0,
      isAllNormal: false,
      alarmMap: {
        uptimecheck: 'uptimecheck',
        service: 'service',
        process: 'process',
        os: 'os',
      },
      titleMap: {
        uptimecheck: {
          serious: this.$t('拨测监控异常报告'),
          slight: this.$t('拨测监控异常报告'),
          normal: this.$t('拨测监控很健康'),
          unset: this.$t('综合拨测 - 未配置'),
        },
        service: {
          serious: this.$t('服务监控异常报告'),
          slight: this.$t('服务监控异常报告'),
          normal: this.$t('服务监控很健康'),
          unset: this.$t('服务监控 - 未配置'),
        },

        process: {
          serious: this.$t('进程监控异常报告'),
          slight: this.$t('进程监控异常报告'),
          normal: this.$t('进程监控很健康'),
          unset: this.$t('进程监控 - 未配置'),
        },
        os: {
          serious: this.$t('主机监控异常报告'),
          slight: this.$t('主机监控异常报告'),
          normal: this.$t('主机监控很健康'),
          unset: this.$t('主机监控 - 未配置'),
        },
      },
    };
  },
  computed: {
    selectAlarm() {
      return this.businessAlarm[this.selectedIndex];
    },
    selectTitle() {
      return this.titleMap[this.selectAlarm.name][this.selectAlarm.status];
    },
    selectLogs() {
      return this.selectAlarm.operate_records ? this.selectAlarm.operate_records[0].operate_desc : '';
    },
  },
  watch: {
    businessAlarm: {
      handler() {
        this.handleSetIndex();
      },
      deep: true,
    },
  },
  created() {
    if (this.businessAlarm.length) {
      this.handleSetIndex();
    }
  },
  methods: {
    getCustomAlarmChartData() {
      alarmDetailChartData({
        alarm_id: 5838598, // 告警实例ID
        monitor_id: 364, // 监控项ID
        chart_type: 'main', // 固定值
      });
    },
    findIndexByStatus(status) {
      return this.businessAlarm.findIndex(item => item.status === status);
    },
    handleSetIndex() {
      // if (this.businessAlarm.every(item => item.status === 'normal')) {
      //     this.isAllNormal = true
      // }
      let selectIndex = this.findIndexByStatus('serious');
      if (selectIndex === -1) {
        selectIndex = this.findIndexByStatus('slight');
        if (selectIndex === -1) {
          selectIndex = this.findIndexByStatus('unset');
        }
      }
      this.selectedIndex = selectIndex === -1 ? 0 : selectIndex;
    },
  },
};
</script>

<style scoped lang="scss">
.business-alarm {
  display: flex;

  .left {
    width: 357px;
    height: 403px;
    background: #fff;

    .content {
      position: relative;
      top: 108px;
      left: 80px;
    }
  }

  .right {
    flex: 1;
    background: #fafbfd;
    border-radius: 0px 2px 2px 0px;
  }
}
</style>
