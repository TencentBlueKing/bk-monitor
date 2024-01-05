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

import { feedbackAlert } from '../../../../monitor-api/modules/alert';
import MonitorDialog from '../../../../monitor-ui/monitor-dialog/monitor-dialog.vue';

import './feedback.scss';

const TAGS = [window.i18n.tc('无法给予帮助'), window.i18n.tc('结果不准确'), window.i18n.tc('问题定位不清晰')];
interface AlarmConfirmProps {
  show: boolean;
  ids?: Array<string>;
}

interface IEvent {
  onConfirm?: boolean;
  onChange?: boolean;
}

@Component({
  name: 'AlarmConfirm'
})
export default class AlarmConfirm extends tsc<AlarmConfirmProps, IEvent> {
  @Prop({ type: Boolean, default: false }) show: boolean;
  @Prop({ type: Array, default: () => [] }) ids: Array<string>;

  loading = false;
  description = '';
  // 0: 未选 1: 有用 2：无用
  state = 0;

  errMsg = '';

  @Watch('show')
  showChange(v) {
    if (v) {
      this.loading = false;
      this.description = '';
      this.state = 0;
      this.errMsg = '';
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

  // 确认告警
  async handleAlarmConfirm() {
    if (this.state === 0) {
      this.errMsg = window.i18n.tc('选择有用或无用');
      return;
    }
    if (this.state === 2 && !Boolean(this.description)) {
      this.errMsg = window.i18n.tc('填写反馈说明');
      return;
    }
    const params = {
      alert_id: this.ids[0],
      is_anomaly: this.state === 1,
      description: this.description
    };
    this.loading = true;
    const res = await feedbackAlert(params)
      .then(() => true)
      .catch(() => false);
    this.loading = false;
    if (res) {
      this.$bkMessage({
        theme: 'success',
        message: window.i18n.tc('反馈成功')
      });
      this.handleConfirm(true);
    } else {
      this.$bkMessage({
        theme: 'error',
        message: window.i18n.tc('反馈失败')
      });
    }
    this.handleShowChange(false);
  }

  handleToMeal(id: number) {
    window.open(location.href.replace(location.hash, `#/set-meal/${id}`));
  }

  handleState(state: number) {
    this.state = state;
    this.errMsg = '';
  }

  handleClickTag(v: string) {
    this.description = v;
    this.errMsg = '';
  }

  render() {
    return (
      <MonitorDialog
        value={this.show}
        on-change={this.handleShowChange}
        title={this.$t('反馈')}
        header-position={'left'}
        width={480}
      >
        <div
          class='event-detail-feedbak-dialog'
          v-bkloading={{ isLoading: this.loading }}
        >
          <div class='state'>
            <div
              class={['left', { active: this.state === 1 }]}
              onClick={() => this.handleState(1)}
            >
              <span class='icon-monitor icon-mc-like-filled'></span>
              <span class='text'>{window.i18n.tc('有用')}</span>
            </div>
            <div
              class={['right', { active: this.state === 2 }]}
              onClick={() => this.handleState(2)}
            >
              <span class='icon-monitor icon-mc-unlike-filled'></span>
              <span class='text'>{window.i18n.tc('无用')}</span>
            </div>
          </div>
          <div class='content'>
            <div class='title'>{window.i18n.tc('反馈')}</div>
            {this.state === 2 && (
              <div class='tags'>
                {TAGS.map(item => (
                  <div
                    class='tag'
                    onClick={() => this.handleClickTag(item)}
                  >
                    {item}
                  </div>
                ))}
              </div>
            )}
            <bk-input
              v-model={this.description}
              type={'textarea'}
              rows={3}
              class='content-text'
              onChange={() => (this.errMsg = '')}
            ></bk-input>
            {this.errMsg ? <div class='err-msg'>{this.errMsg}</div> : undefined}
          </div>
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
