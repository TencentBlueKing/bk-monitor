/*
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
 */
import { Component, Emit, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { getActionConfigByAlerts } from '../../../../monitor-api/modules/action';
import { ackAlert } from '../../../../monitor-api/modules/alert';
import MonitorDialog from '../../../../monitor-ui/monitor-dialog/monitor-dialog.vue';

import './alarm-confirm.scss';

// import { FtaAlertAck } from './mock'

interface AlarmConfirmProps {
  show: boolean;
  ids?: Array<string>;
  bizIds?: number[];
}

interface IEvent {
  onConfirm?: boolean;
}

@Component({
  name: 'AlarmConfirm'
})
export default class AlarmConfirm extends tsc<AlarmConfirmProps, IEvent> {
  @Prop({ type: Boolean, default: false }) show: boolean;
  @Prop({ type: Array, default: () => [] }) ids: Array<string>;
  /* 事件中心暂不允许跨业务操作， 此数组只有一个业务 */
  @Prop({ type: Array, default: () => [] }) bizIds: number[];

  public content = '';
  public loading = false;

  public infoContent = []; // 关联套餐信息

  @Watch('show')
  showChange(v) {
    if (v) {
      this.getInfoData();
    }
  }

  @Emit('change')
  handleShowChange(v) {
    return v;
  }

  @Emit('confirm')
  handleConfirm(v = true) {
    return v;
  }

  // 获取关联的套餐信息
  getInfoData() {
    this.loading = true;
    getActionConfigByAlerts({
      alert_ids: this.ids,
      bk_biz_id: this.bizIds?.[0] || this.$store.getters.bizId
    })
      .then(data => {
        this.infoContent = data
          .reduce((total, item) => {
            if (item.action_configs?.length) {
              return [...total, ...item.action_configs];
            }
            return total;
          }, [])
          .filter((item, index, arr) => arr.map(a => a.id).indexOf(item.id, 0) === index); // 去重
      })
      .finally(() => (this.loading = false));
  }

  // 确认告警
  async handleAlarmConfirm() {
    this.loading = true;
    const params = {
      ids: this.ids,
      bk_biz_id: this.bizIds?.[0] || this.$store.getters.bizId,
      message: this.content
    };
    const res = await ackAlert(params).finally(() => (this.loading = false));
    if (res) {
      let msg = {
        theme: 'success',
        message: this.$t('告警确认成功')
      };
      if (res.alerts_ack_success.length) {
        msg = {
          theme: 'success',
          message: this.$t('告警确认成功')
        };
        this.handleConfirm(true);
        this.handleShowChange(false);
      } else {
        msg = {
          theme: 'error',
          message: this.$t('所有告警已恢复/关闭，无需确认')
        };
      }
      this.$bkMessage(msg);
    }
  }

  handleToMeal(id: number) {
    window.open(location.href.replace(location.hash, `#/set-meal/${id}`));
  }

  render() {
    return (
      <MonitorDialog
        value={this.show}
        on-change={this.handleShowChange}
        title={this.$t('告警确认')}
        header-position={'left'}
        width={480}
      >
        <div
          class='alarm-confirm-dialog'
          v-bkloading={{ isLoading: this.loading }}
        >
          <bk-alert
            class='info-tips'
            type='info'
          >
            <div slot='title'>
              <div>{`${this.$t('当该告警确认需要处理，并且希望该告警不再通知时，可以直接进行告警确认')}。`}</div>
              <div>
                {`${this.$t('注意')}：${this.$t(
                  '告警确认不会影响其他告警，只是避免当前告警的周期间隔发送和处理套餐的执行'
                )}。`}
              </div>
            </div>
          </bk-alert>
          {this.infoContent.length
            ? [
                <div class='info-content-title'>{this.$t('关联的处理套餐')}</div>,
                <div class='info-content'>
                  {this.infoContent.map(item => (
                    <div class='lint-item'>
                      <span
                        class='item-name'
                        onClick={() => this.handleToMeal(item.id)}
                      >
                        {item.name}
                        {this.$t('套餐')}
                      </span>
                      <span class='item-id'>{`(#${item.id})`}</span>
                    </div>
                  ))}
                </div>
              ]
            : undefined}
          <bk-input
            v-model={this.content}
            type='textarea'
            class='alarm-config-content'
            placeholder={this.$t('填写告警确认备注信息')}
            rows={5}
          ></bk-input>
        </div>
        <template slot='footer'>
          <bk-button
            on-click={this.handleAlarmConfirm}
            theme='primary'
            style='margin-right: 10px'
            disabled={this.loading}
          >
            {this.$t('确认')}
          </bk-button>
          <bk-button on-click={() => this.handleShowChange(false)}>{this.$t('取消')}</bk-button>
        </template>
      </MonitorDialog>
    );
  }
}
