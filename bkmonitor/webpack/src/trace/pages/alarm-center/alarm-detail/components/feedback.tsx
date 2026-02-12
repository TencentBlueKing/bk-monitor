/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
import { type PropType, defineComponent, shallowRef, watch } from 'vue';

import { Button, Dialog, Input, Loading, Message } from 'bkui-vue';
import { feedbackAlert } from 'monitor-api/modules/alert_v2';
import { useI18n } from 'vue-i18n';

import './feedback.scss';

const TAGS = [window.i18n.t('无法给予帮助'), window.i18n.t('结果不准确'), window.i18n.t('问题定位不清晰')];

export default defineComponent({
  name: 'AlarmConfirm',
  props: {
    show: {
      type: Boolean,
      default: false,
    },
    ids: {
      type: Array as PropType<string[]>,
      default: () => [],
    },
  },
  emits: ['update:isShow', 'confirm'],
  setup(props, { emit }) {
    const { t } = useI18n();

    const loading = shallowRef(false);
    const description = shallowRef('');
    // 0: 未选 1: 有用 2：无用
    const state = shallowRef(0);
    const errMsg = shallowRef('');

    watch(
      () => props.show,
      v => {
        if (v) {
          loading.value = false;
          description.value = '';
          state.value = 0;
          errMsg.value = '';
        }
      }
    );

    // 确认告警
    const handleAlarmConfirm = async () => {
      if (state.value === 0) {
        errMsg.value = t('选择有用或无用');
        return;
      }
      if (state.value === 2 && !description.value) {
        errMsg.value = t('填写反馈说明');
        return;
      }
      const params = {
        alert_id: props.ids[0],
        is_anomaly: state.value === 1,
        description: description.value,
      };
      loading.value = true;
      const res = await feedbackAlert(params)
        .then(() => true)
        .catch(() => false);
      loading.value = false;
      if (res) {
        Message({
          theme: 'success',
          message: t('反馈成功'),
        });
        handleConfirm(true);
      } else {
        Message({
          theme: 'error',
          message: t('反馈失败'),
        });
      }
      handleShowChange(false);
    };

    const handleConfirm = (v = true) => {
      emit('confirm', v);
    };

    const handleState = (val: number) => {
      state.value = val;
      errMsg.value = '';
    };

    const handleClickTag = (v: string) => {
      description.value = v;
      errMsg.value = '';
    };

    const handleShowChange = (v: boolean) => {
      emit('update:isShow', v);
    };

    return {
      t,
      handleShowChange,
      loading,
      state,
      description,
      errMsg,
      handleState,
      handleAlarmConfirm,
      handleClickTag,
    };
  },
  render() {
    return (
      <Dialog
        width={480}
        v-slots={{
          default: () => (
            <Loading loading={this.loading}>
              <div class='event-detail-feedbak-dialog'>
                <div class='state'>
                  <div
                    class={['left', { active: this.state === 1 }]}
                    onClick={() => this.handleState(1)}
                  >
                    <span class='icon-monitor icon-mc-like-filled' />
                    <span class='text'>{this.t('有用')}</span>
                  </div>
                  <div
                    class={['right', { active: this.state === 2 }]}
                    onClick={() => this.handleState(2)}
                  >
                    <span class='icon-monitor icon-mc-unlike-filled' />
                    <span class='text'>{this.t('无用')}</span>
                  </div>
                </div>
                <div class='content'>
                  <div class='title'>{this.t('反馈说明')}</div>
                  {this.state === 2 && (
                    <div class='tags'>
                      {TAGS.map(item => (
                        <div
                          key={item}
                          class='tag'
                          onClick={() => this.handleClickTag(item)}
                        >
                          {item}
                        </div>
                      ))}
                    </div>
                  )}
                  <Input
                    class='content-text'
                    v-model={this.description}
                    rows={3}
                    type={'textarea'}
                    onChange={() => {
                      this.errMsg = '';
                    }}
                  />
                  {this.errMsg ? <div class='err-msg'>{this.errMsg}</div> : undefined}
                </div>
              </div>
            </Loading>
          ),
          footer: () => (
            <div class='btns'>
              <Button
                style='margin-right: 10px'
                disabled={this.loading}
                theme='primary'
                onClick={this.handleAlarmConfirm}
              >
                {this.$t('确认')}
              </Button>
              <Button onClick={() => this.handleShowChange(false)}>{this.$t('取消')}</Button>
            </div>
          ),
        }}
        header-position={'left'}
        isShow={this.show}
        title={this.t('反馈')}
        onUpdate:isShow={this.handleShowChange}
      />
    );
  },
});
