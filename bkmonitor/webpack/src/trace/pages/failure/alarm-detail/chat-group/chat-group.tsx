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
import { computed, defineComponent, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import { Button, Checkbox, Dialog, Message } from 'bkui-vue';
import { createChatGroup } from 'monitor-api/modules/action';
import { incidentRecordOperation } from 'monitor-api/modules/incident';

import UserSelector from '../../../../components/user-selector/user-selector';

import './chat-group.scss';

export default defineComponent({
  props: {
    show: { type: Boolean, default: false },
    alarmEventName: { type: String, default: '' },
    assignee: { type: Array, default: () => [] },
    alertIds: { type: Array, default: () => [] },
    bizId: { type: Array, default: () => [] },
    type: { type: String, default: 'alarm' },
    data: {
      type: Object,
      default: () => ({}),
    },
  },
  emits: ['showChange', 'refresh'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const isLoading = ref(false);
    const localValue = ref([]);
    const contentType = ref([]);

    const handleShowChange = (v?: boolean) => {
      emit('showChange', v);
    };

    const isAlarm = computed(() => {
      return props.type === 'alarm';
    });

    const bkUrl = computed(() => `${window.site_url}rest/v2/commons/user/list_users/`);

    const title = computed(() => {
      const alarmTitle =
        props.alertIds.length > 1
          ? t('已经选择了{0}个告警事件,将通过企业微信将相关人员邀请到一个群里面进行讨论', [props.alertIds.length])
          : t('已经选择了{0}告警事件,将通过企业微信将相关人员邀请到一个群里面进行讨论', [props.alarmEventName]);
      const incidentTitle = t('将通过企业微信把当前故障相关人员邀请到一个群里面进行讨论', [props.alarmEventName]);
      return isAlarm.value ? alarmTitle : incidentTitle;
    });

    watch(
      () => props.show,
      (v: boolean) => {
        if (v) {
          if (props.alertIds.length > 1) {
            contentType.value = ['detail_url'];
          } else {
            contentType.value = ['alarm_content'];
          }
          localValue.value.splice(0, localValue.value.length, ...props.assignee);
        }
      }
    );

    const handleConfirm = () => {
      const { id, incident_id, bk_biz_id } = props.data;
      const params = {
        bk_biz_id,
        alert_ids: props.alertIds,
        content_type: contentType.value,
        chat_members: localValue.value,
      };
      isLoading.value = true;
      createChatGroup(params)
        .then(data => {
          if (data) {
            Message({
              message: t('拉群成功'),
              theme: 'success',
            });
            handleShowChange(false);
          }
          incidentRecordOperation({
            id,
            incident_id,
            operation_type: 'group_gather',
            extra_info: {
              group_name: localValue.value,
            },
          }).then(res => {
            res && setTimeout(() => emit('refresh'), 2000);
          });
        })
        .finally(() => (isLoading.value = false));
    };
    return {
      title,
      localValue,
      bkUrl,
      contentType,
      isLoading,
      handleShowChange,
      handleConfirm,
      isAlarm,
      t,
    };
  },
  render() {
    return (
      <Dialog
        width={640}
        class='chat-group-dialog-wrap'
        v-slots={{
          default: [
            <div
              key={'header'}
              class='header'
            >
              {/* eslint-disable-next-line @typescript-eslint/no-require-imports */}
              <img src={require('../../../../../fta-solutions/static/img/we-com.svg')} />
              <span>{this.title}</span>
            </div>,
            <div
              key={'content'}
              class='content'
            >
              <p class='title'>{this.t('群聊邀请')}</p>
              <div class='checkbox-group'>
                <Checkbox
                  checked={true}
                  modelValue={true}
                  disabled
                >
                  {this.isAlarm ? this.t('告警关注人') : this.t('故障关注人')}
                </Checkbox>
                {/* <Checkbox value={this.isHandler}>{this.t('告警处理人')}</Checkbox> */}
              </div>
              <UserSelector
                class='bk-user-selector'
                v-model={this.localValue}
              />
              <div class='checkbox-group'>
                <Checkbox.Group v-model={this.contentType}>
                  {!this.isAlarm
                    ? [
                        <Checkbox
                          key={'1'}
                          label={'2'}
                        >
                          {this.t('故障链接')}
                        </Checkbox>,
                        <Checkbox
                          key={'2'}
                          label={'alarm_content'}
                        >
                          {this.t('故障内告警')}
                        </Checkbox>,
                      ]
                    : [
                        <Checkbox
                          key={'1'}
                          label={'detail_url'}
                        >
                          {this.t('告警事件链接')}
                        </Checkbox>,
                        <Checkbox
                          key={'2'}
                          label={'alarm_content'}
                        >
                          {this.t('告警事件内容')}
                        </Checkbox>,
                      ]}
                </Checkbox.Group>
              </div>
            </div>,
          ],
          footer: [
            <Button
              key={'confirm'}
              style='margin-right: 10px'
              disabled={!this.localValue.length || !this.contentType.length}
              loading={this.isLoading}
              theme='primary'
              onClick={() => this.handleConfirm()}
            >
              {this.t('确定')}
            </Button>,
            <Button
              key={'cancel'}
              onClick={() => this.handleShowChange(false)}
            >
              {this.t('取消')}
            </Button>,
          ],
        }}
        header-position='left'
        is-show={this.show}
        mask-close={true}
        render-directive='if'
        title={this.t('一键拉群')}
        on-value-change={this.handleShowChange}
        onClosed={this.handleShowChange}
      />
    );
  },
});
