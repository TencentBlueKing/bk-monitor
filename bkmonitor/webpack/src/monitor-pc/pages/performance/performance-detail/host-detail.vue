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
  <div
    v-bkloading="{ isLoading }"
    class="host-detail"
  >
    <div class="host-detail-title">
      <i
        class="icon-monitor icon-double-up"
        @click="handleTogglePanel"
      />
      <span>{{ data.type === 'host' ? $t('主机详情') : $t('节点详情') }}</span>
    </div>
    <div class="host-detail-content">
      <ul>
        <template v-if="data.type === 'host'">
          <!-- 主机基本信息 -->
          <li
            v-for="item in hostInfo"
            :key="item.id"
            class="host-info"
          >
            <span class="host-info-title">{{ `${item.title}:` }}</span>
            <div class="host-info-content">
              <!-- 状态 -->
              <span
                v-if="item.id === 'status'"
                :class="item.value === 0 ? 'status-normal' : 'status-unkown'"
              >
                {{ statusMap[item.value] }}
              </span>
              <div v-else-if="item.id === 'module'">
                <ul :class="{ 'module-expand': !showAllModule }">
                  <li
                    v-for="(data, index) in item.value"
                    :key="index"
                    class="module-item"
                  >
                    {{ data.topo_link_display.join('-') }}
                  </li>
                </ul>
                <li
                  v-if="item.value.length > 2"
                  class="module-item"
                >
                  <bk-button
                    class="btn"
                    text
                    @click="handleToggleModule"
                  >
                    {{ showAllModule ? $t('收起') : $t('展开') }}
                  </bk-button>
                </li>
              </div>
              <div
                v-else-if="item.id === 'bk_state'"
                class="content-bk-state"
              >
                {{ item.value || '--' }}
                <i
                  v-if="handleIpStatusData(curHostStatus.ignore_monitoring, curHostStatus.is_shielding).id"
                  :class="`icon-monitor ${
                    handleIpStatusData(curHostStatus.ignore_monitoring, curHostStatus.is_shielding).icon
                  }`"
                  @mouseenter="handleIpStatusTips"
                />
              </div>
              <span v-else>{{ item.value || '--' }}</span>
              <i
                v-if="item.link && item.value"
                v-bk-tooltips="$t('查看详情')"
                class="ml5 icon-monitor icon-mc-link"
                @click="handleToCmdbHost"
              />
              <i
                v-if="item.copy && item.value"
                v-bk-tooltips="$t('复制')"
                class="ml5 icon-monitor icon-mc-copy"
                @click="handleCopyValue(item.value)"
              />
            </div>
          </li>
        </template>
        <template v-else>
          <!-- 节点基本信息 -->
          <li
            v-for="item in nodeInfo.filter(
              item => !['bk_bak_operato', 'operator'].includes(item.id) || data.bkObjId === 'module'
            )"
            :key="item.id"
            class="node-info"
          >
            <span class="node-info-title">{{ `${item.title}:` }}</span>
            <div class="node-info-content">
              <span v-if="Array.isArray(item.value)">{{ item.value.join(',') || '--' }}</span>
              <span v-else>{{ item.value || '--' }}</span>
              <i
                v-if="item.link && item.value"
                v-bk-tooltips="$t('查看详情')"
                class="ml5 icon-monitor icon-mc-link"
                @click="handleToCmdbHost"
              />
              <i
                v-if="item.copy && item.value"
                v-bk-tooltips="$t('复制')"
                class="ml5 icon-monitor icon-mc-copy"
                @click="handleCopyValue(item.value)"
              />
            </div>
          </li>
        </template>
        <!-- 主机告警信息 -->
        <li class="host-alarm">
          <div class="alarm-info-panel">
            <div
              :class="['count', { active: alarmInfo.alarm_count > 0 }]"
              @click="handleToEventCenter"
            >
              {{ alarmInfo.alarm_count }}
            </div>
            <div class="desc">
              {{ $t('未恢复告警') }}
            </div>
          </div>
          <div class="alarm-info-panel">
            <div
              :class="[
                'count',
                { active: alarmInfo.alarm_strategy.enabled > 0 || alarmInfo.alarm_strategy.disabled > 0 },
              ]"
              @click="handleToStrategyConfig"
            >
              <span>
                {{ alarmInfo.alarm_strategy.enabled }}
              </span>
              <span class="disabled-count"> /{{ alarmInfo.alarm_strategy.disabled }} </span>
            </div>
            <div class="desc">
              {{ $t('启/停策略') }}
            </div>
          </div>
        </li>
      </ul>
    </div>
    <div v-show="false">
      <ip-status-tips
        ref="ipStatusTips"
        :ignore-monitoring="curHostStatus.ignore_monitoring"
        :is-shielding="curHostStatus.is_shielding"
        :host-id="curHostStatus.bk_host_id"
      />
    </div>
  </div>
</template>
<script lang="ts">
import { Component, Emit, Model, Prop, Ref, Vue, Watch } from 'vue-property-decorator';

import { copyText } from 'monitor-common/utils/utils.js';

import PerformanceModule, { type ICurNode } from '../../../store/modules/performance';
import IpStatusTips, { handleIpStatusData } from '../components/ip-status-tips';

import type MonitorVue from '../../../types/index';
import type { IHostInfo } from '../performance-type';

@Component({ name: 'host-detail', components: { IpStatusTips } })
export default class HostDetail extends Vue<MonitorVue> {
  @Prop({ default: () => ({}), type: Object }) data: ICurNode;
  // 是否显示面板
  @Model('visible-change', { default: true }) readonly visible: boolean;

  @Ref('ipStatusTips') ipStatusTipsRef;

  private isLoading = false;
  // 主机信息
  private hostInfo: IHostInfo[] = [];
  // 节点信息
  private nodeInfo: IHostInfo[] = [];
  // 告警信息
  private alarmInfo = {
    alarm_count: 0,
    alarm_strategy: {
      disabled: 0,
      enabled: 0,
    },
  };
  // 是否展示所有模块
  private showAllModule = false;
  // 主机ID
  private hostId = '';
  // 状态Map
  private statusMap = {
    '-1': window.i18n.t('未知'),
    0: window.i18n.t('正常'),
    1: window.i18n.t('离线'),
    2: window.i18n.t('无Agent'),
    3: window.i18n.t('无数据上报'),
  };

  private handleIpStatusData: Function = handleIpStatusData;
  private tipsPopoverInstance = null;

  @Watch('data', { immediate: true, deep: true })
  handleParamsChange(data: ICurNode, old: ICurNode) {
    if (!old || data.id !== old.id) {
      this.getDetailData();
    }
  }

  created() {
    this.hostInfo = [
      {
        id: 'bk_host_name',
        title: this.$t('主机名'),
        value: '',
        copy: true,
      },
      {
        id: 'bk_host_innerip',
        title: this.$t('内网IP'),
        value: '',
        copy: true,
        link: true,
      },
      {
        id: 'bk_host_outerip',
        title: this.$t('外网IP'),
        value: '',
        copy: true,
      },
      {
        id: 'bk_biz_name',
        title: this.$t('所属业务'),
        value: '',
      },
      {
        id: 'bk_state',
        title: this.$t('主机运营'),
        value: '',
      },
      {
        id: 'status',
        title: this.$t('采集状态'),
        value: '',
      },
      {
        id: 'bk_os_name',
        title: this.$t('OS名称'),
        value: '',
      },
      {
        id: 'bk_cloud_name',
        title: this.$t('管控区域'),
        value: '',
      },
      {
        id: 'module',
        title: this.$t('所属模块'),
        value: '',
      },
    ];
    this.nodeInfo = [
      {
        id: 'bk_inst_id',
        title: this.$t('ID'),
        value: '',
      },
      {
        id: 'bk_obj_name',
        title: this.$t('节点类型'),
        value: '',
      },
      {
        id: 'bk_inst_name',
        title: this.$t('节点名称'),
        value: '',
      },
      {
        id: 'child_count',
        title: this.$t('子级数量'),
        value: '',
      },
      {
        id: 'host_count',
        title: this.$t('主机数量'),
        value: '',
      },
      {
        id: 'operator',
        title: this.$t('主要维护人'),
        value: [],
      },
      {
        id: 'bk_bak_operato',
        title: this.$t('备份维护人'),
        value: [],
      },
    ];
  }

  get curHostStatus() {
    return PerformanceModule.curHostStatus;
  }

  @Emit('visible-change')
  handleTogglePanel() {
    return !this.visible;
  }
  /**
   * @description: 展开提示
   * @param {*} e 鼠标事件
   * @return {*}
   */
  handleIpStatusTips(e) {
    const tipsTpl = this.ipStatusTipsRef.$el;
    this.initTipsPopover(e.target, tipsTpl, { width: 215 });
  }
  /**
   * @description: 初始化tooltips
   * @param {*} target 目标
   * @param {*} content tips内容
   * @param {*} options 配置
   * @return {*}
   */
  initTipsPopover(target, content, options?) {
    if (!this.tipsPopoverInstance) {
      this.tipsPopoverInstance = this.$bkPopover(
        target,
        Object.assign(
          {
            content,
            interactive: true,
            arrow: true,
            placement: 'top',
            onHidden: () => {
              this.tipsPopoverInstance?.destroy();
              this.tipsPopoverInstance = null;
            },
          },
          options
        )
      );
      this.tipsPopoverInstance?.show();
    }
  }
  // 跳转事件中心
  handleToEventCenter() {
    if (this.alarmInfo.alarm_count > 0) {
      this.$router.push({
        name: 'event-center',
        query: {
          from: 'now-7d',
          to: 'now',
          queryString: ['zh', 'zhCN', 'zh-cn'].includes(window.i18n.locale)
            ? `目标IP : ${this.data.ip}`
            : `ip : ${this.data.ip}`,
          activeFilterId: 'NOT_SHIELDED_ABNORMAL',
        },
      });
    }
  }
  // 跳转策略
  handleToStrategyConfig() {
    const { alarm_strategy } = this.alarmInfo;
    if (alarm_strategy.enabled > 0 || alarm_strategy.disabled > 0) {
      this.$router.push({
        name: 'strategy-config',
        params: {
          ip: this.data.ip,
          bkCloudId: this.data.cloudId,
        },
      });
    }
  }

  async getDetailData() {
    this.isLoading = true;
    let detailData: any = {};
    let configData = [];
    if (this.data.type === 'host' && this.data.ip) {
      this.showAllModule = false;
      detailData = await PerformanceModule.getHostDetail({
        ip: this.data.ip,
        bk_cloud_id: this.data.cloudId,
      });
      configData = this.hostInfo;
      this.hostId = detailData.bk_host_id;
    } else if (this.data.type === 'node' && this.data.bkInstId) {
      detailData = await PerformanceModule.getNodeDetail({
        bk_obj_id: this.data.bkObjId,
        bk_inst_id: this.data.bkInstId,
      });
      configData = this.nodeInfo;
    }

    // 基本信息
    Object.keys(detailData).forEach(key => {
      const item = configData.find(item => item.id === key);
      item && (item.value = detailData[key]);
    });
    // 告警信息
    this.alarmInfo.alarm_count = detailData.alarm_count || 0;
    this.alarmInfo.alarm_strategy = detailData.alarm_strategy || {};
    this.$store.commit(
      'app/SET_NAV_TITLE',
      this.data.type === 'host' ? detailData.bk_host_innerip : detailData.bk_inst_name
    );
    this.isLoading = false;
  }

  handleToggleModule() {
    this.showAllModule = !this.showAllModule;
  }

  handleToCmdbHost() {
    window.open(`${this.$store.getters.cmdbUrl}/#/resource/host/${this.hostId}`, '_blank');
  }

  handleCopyValue(value) {
    copyText(value);
    this.$bkMessage({
      theme: 'success',
      message: this.$t('复制成功'),
    });
  }
}
</script>
<style lang="scss" scoped>
/* stylelint-disable no-descending-specificity */
.host-detail {
  display: flex;
  flex-direction: column;
  border-left: 1px solid #f0f1f5;

  &-title {
    display: flex;
    flex: 0 0 42px;
    align-items: center;
    border-bottom: 1px solid #f0f1f5;

    i {
      margin-left: 2px;
      font-size: 24px;
      color: #979ba5;
      cursor: pointer;
      transform: rotate(90deg);
    }

    span {
      margin-left: 4px;
    }
  }

  &-content {
    padding: 15px 24px 0 16px;
    overflow: auto;

    .host-info {
      display: flex;
      margin-bottom: 10px;
      line-height: 20px;

      &-title {
        flex: 0 0 60px;
        color: #979ba5;
        text-align: left;
      }

      &-content {
        flex: 1;

        .status-unkown {
          color: #ea3636;
        }

        .module-expand {
          height: 40px;
          overflow: hidden;
        }

        .status-normal {
          color: #2dcb56;
        }

        .module-item {
          margin: 0;
          line-height: 20px;
        }

        .btn {
          font-size: 12px;
        }

        i {
          cursor: pointer;
        }

        .icon-mc-copy {
          font-size: 14px;
          color: #3a84ff;
        }

        .icon-mc-link {
          color: #3a84ff;
        }

        .content-bk-state {
          .icon-monitor {
            margin-left: 13px;
            font-size: 18px;
            color: #63656e;

            &:hover {
              color: #3a84ff;
            }

            &.icon-mc-notice-shield {
              font-size: 16px;
            }
          }
        }
      }
    }

    .node-info {
      display: flex;
      margin-bottom: 10px;
      line-height: 20px;

      &-title {
        flex: 0 0 80px;
        color: #979ba5;
        text-align: left;
      }

      &-content {
        flex: 1;

        .module-item {
          margin: 0;
          line-height: 20px;
        }

        .status-unkown {
          color: #ea3636;
        }

        .module-expand {
          height: 40px;
          overflow: hidden;
        }

        .btn {
          font-size: 12px;
        }

        .status-normal {
          color: #2dcb56;
        }

        i {
          cursor: pointer;
        }

        .icon-mc-copy {
          font-size: 14px;
          color: #3a84ff;
        }

        .icon-mc-link {
          color: #3a84ff;
        }
      }
    }

    .host-alarm {
      display: flex;

      .alarm-info-panel {
        display: flex;
        flex: 1;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        height: 64px;
        background: #f5f6fa;
        border-radius: 2px;

        &:hover {
          background: #3a84ff;

          & span:nth-of-type(1),
          & .count.active {
            color: #ffff;
          }

          & span:nth-of-type(2),
          & .desc {
            color: #a3c5fd;
          }
        }

        &:last-child {
          margin-left: 2px;
        }

        .count {
          font-size: 16px;
          line-height: 26px;
          color: #979ba5;

          &.active {
            color: #000;
            cursor: pointer;
          }

          .disabled-count {
            color: #979ba5;
          }
        }

        .desc {
          line-height: 20px;
          color: #979ba5;
        }
      }
    }
  }
}
</style>
