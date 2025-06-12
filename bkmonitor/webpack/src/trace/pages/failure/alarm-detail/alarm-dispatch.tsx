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
import { computed, defineComponent, reactive, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import { Button, Checkbox, Dialog, Input, Loading, Message } from 'bkui-vue';
import { BkCheckboxGroup } from 'bkui-vue/lib/checkbox';
import { assignAlert } from 'monitor-api/modules/action';
import { incidentRecordOperation } from 'monitor-api/modules/incident';
import { getNoticeWay } from 'monitor-api/modules/notice_group';

import UserSelector from '../../../components/user-selector/user-selector';

import './alarm-dispatch.scss';

const reasonList = [window.i18n.t('当前工作安排较多'), window.i18n.t('不在职责范围内'), window.i18n.t('无法处理')];

export default defineComponent({
  props: {
    show: {
      type: Boolean,
      default: false,
    },
    alertIds: {
      type: Array,
      default: () => [],
    },
    bizIds: {
      type: Array,
      default: () => [],
    },
    data: {
      type: Object,
      default: () => ({}),
    },
  },
  emits: ['show', 'success', 'refresh'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const users = ref<string[]>([]);
    const noticeWay = ref([]);
    const noticeWayList = ref<{ label: string; type: string }[]>([]);
    const reason = ref('');
    const loading = ref(false);
    const errorMsg = reactive({
      reason: '',
      users: '',
      notice: '',
    });
    const bkUrl = computed(() => `${window.site_url}rest/v2/commons/user/list_users/`);

    watch(
      () => props.show,
      async v => {
        if (v) {
          users.value = [];
          loading.value = true;
          handleFocus();
          await getNoticeWayList();
          loading.value = false;
        }
      }
    );

    /* 通知方式列表 */
    const getNoticeWayList = async () => {
      if (!noticeWayList.value.length) {
        noticeWayList.value = await getNoticeWay()
          .then(data => data.filter(item => item.type !== 'wxwork-bot'))
          .catch(() => []);
        const noticeWays = noticeWayList.value.map(item => item.type);
        noticeWay.value = noticeWay.value.filter(type => noticeWays.includes(type));
      }
    };

    const handleTagClick = (tag: string) => {
      if (reason.value) {
        reason.value += `，${tag}`;
      } else {
        reason.value += tag;
      }
    };
    const handleShowChange = v => {
      emit('show', v);
    };
    const handleCancel = () => {
      emit('show', false);
    };

    const handleSubmit = async () => {
      const validate = validator();
      if (validate) {
        // submit
        loading.value = true;
        const data = await assignAlert({
          bk_biz_id: props.bizIds?.[0], // || this.$store.getters.bizId,
          alert_ids: props.alertIds,
          appointees: users.value,
          reason: reason.value,
          notice_ways: noticeWay.value,
        }).catch(() => null);
        if (data) {
          Message({
            theme: 'success',
            message: t('分派成功'),
          });
          handleCancel();
          handleSuccess();
          const { id, alert_name, incident_id } = props.data;
          incidentRecordOperation({
            id,
            incident_id,
            bk_biz_id: props.bizIds?.[0],
            operation_type: 'alert_dispatch',
            extra_info: {
              alert_name,
              alert_id: props.alertIds[0],
              handlers: users.value,
            },
          }).then(res => {
            res && setTimeout(() => emit('refresh'), 2000);
          });
        }
        loading.value = false;
      }
    };

    const handleSuccess = () => {
      emit('success', {
        ids: props.alertIds,
        users: users.value,
      });
    };

    const validator = () => {
      if (!users.value.length) {
        errorMsg.users = t('输入分派人员') as string;
        return false;
      }
      if (!reason.value) {
        errorMsg.reason = t('输入分派原因') as string;
        return false;
      }
      if (!noticeWay.value.length) {
        errorMsg.notice = t('选择通知方式') as string;
        return false;
      }
      return true;
    };

    const handleFocus = () => {
      errorMsg.reason = '';
      errorMsg.users = '';
      errorMsg.notice = '';
    };
    return {
      loading,
      noticeWay,
      noticeWayList,
      reason,
      users,
      errorMsg,
      bkUrl,
      handleFocus,
      handleTagClick,
      handleShowChange,
      handleSubmit,
      handleCancel,
      t,
    };
  },
  render() {
    return (
      <Dialog
        width={480}
        class='alarm-dispatch-component-dialog'
        v-slots={{
          default: () => (
            <Loading loading={this.loading}>
              <div class='alarm-dispatch'>
                <div class='tips'>
                  <span class='icon-monitor icon-hint' />
                  {this.t('您一共选择了{0}条告警', [this.alertIds.length])}
                </div>
                <div class='form-item'>
                  <div class='label require'>{this.t('分派人员')}</div>
                  <div
                    class='content'
                    onClick={this.handleFocus}
                  >
                    <UserSelector
                      class='content-user-selector'
                      v-model={this.users}
                      empty-text={this.t('搜索结果为空')}
                    />
                  </div>
                  {!!this.errorMsg.users && <div class='err-msg'>{this.errorMsg.users}</div>}
                </div>
                <div class='form-item'>
                  <div class='label'>
                    <div class='title require'>{this.t('分派原因')}</div>
                    <div class='tags'>
                      {reasonList.map(tag => (
                        <span
                          key={tag}
                          class='tag'
                          onClick={() => this.handleTagClick(tag)}
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  </div>
                  <div
                    class='content mr0'
                    onClick={this.handleFocus}
                  >
                    <Input
                      v-model={this.reason}
                      maxlength={100}
                      placeholder={this.t('请输入')}
                      rows={3}
                      type={'textarea'}
                    />
                  </div>
                  {!!this.errorMsg.reason && <div class='err-msg'>{this.errorMsg.reason}</div>}
                </div>
                <div class='form-item'>
                  <div class='label require'>{this.t('通知方式')}</div>
                  <div
                    class='content'
                    onClick={this.handleFocus}
                  >
                    <BkCheckboxGroup v-model={this.noticeWay}>
                      {this.noticeWayList.map(item => (
                        <Checkbox
                          key={item.type}
                          label={item.type}
                        >
                          {item.label}
                        </Checkbox>
                      ))}
                    </BkCheckboxGroup>
                  </div>
                  {!!this.errorMsg.notice && <div class='err-msg'>{this.errorMsg.notice}</div>}
                </div>
              </div>
            </Loading>
          ),
          footer: () => [
            <Button
              key='submit'
              style={{ 'margin-right': '8px' }}
              disabled={this.loading}
              theme='primary'
              onClick={this.handleSubmit}
            >
              {this.t('确定')}
            </Button>,
            <Button
              key={'cancel'}
              onClick={this.handleCancel}
            >
              {this.t('取消')}
            </Button>,
          ],
        }}
        header-position='left'
        is-show={this.show}
        mask-close={true}
        render-directive='if'
        title={this.t('告警分派')}
        onClosed={this.handleShowChange}
        onValue-change={this.handleShowChange}
      />
    );
  },
});
