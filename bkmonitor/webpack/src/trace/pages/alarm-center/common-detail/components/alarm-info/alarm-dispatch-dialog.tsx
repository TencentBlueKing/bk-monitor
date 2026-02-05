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
import { type PropType, defineComponent, reactive, shallowRef, watch } from 'vue';

import { Button, Checkbox, Dialog, Input, Loading, Message } from 'bkui-vue';
import { assignAlert } from 'monitor-api/modules/action';
import { getNoticeWay } from 'monitor-api/modules/notice_group';
import { useI18n } from 'vue-i18n';

import UserSelector from '@/components/user-selector/user-selector';

import './alarm-dispatch-dialog.scss';

export default defineComponent({
  name: 'AlarmDispatch',
  props: {
    show: {
      type: Boolean,
      default: false,
    },
    alarmIds: {
      type: Array as PropType<string[]>,
      default: () => [],
    },
    alarmBizId: {
      type: Number,
      default: null,
    },
  },
  emits: {
    'update:show': (val: boolean) => typeof val === 'boolean',
    success: (value: string[]) => Array.isArray(value),
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const loading = shallowRef(false);
    const users = shallowRef<string[]>([]);
    const noticeWay = shallowRef([]);
    const noticeWayList = shallowRef<{ label: string; type: string }[]>([]);
    const reasonList = [t('当前工作安排较多'), t('不在职责范围内'), t('无法处理')];
    const reason = shallowRef('');
    const errorMsg = reactive({
      reason: '',
      users: '',
      notice: '',
    });

    /* 通知方式列表 */
    const getNoticeWayList = async () => {
      if (!noticeWayList.value.length) {
        noticeWayList.value = await getNoticeWay()
          .then(data => data.filter(item => item.type !== 'wxwork-bot'))
          .catch(() => []);
        const ways = noticeWayList.value.map(item => item.type);
        noticeWay.value = noticeWay.value.filter(type => ways.includes(type));
      }
    };

    watch(
      () => props.show,
      async show => {
        if (show) {
          users.value = [];
          loading.value = true;
          initErrorMsg();
          await getNoticeWayList();
          loading.value = false;
        }
      }
    );

    const handleTagClick = (tag: string) => {
      if (reason.value) {
        reason.value += `，${tag}`;
      } else {
        reason.value += tag;
      }
    };

    const initErrorMsg = () => {
      errorMsg.notice = '';
      errorMsg.reason = '';
      errorMsg.users = '';
    };

    const handleShowChange = (val: boolean) => {
      emit('update:show', val);
    };

    const handleSubmit = async () => {
      const validate = validator();
      if (validate) {
        // submit
        loading.value = true;
        const data = await assignAlert({
          bk_biz_id: props.alarmBizId,
          alert_ids: props.alarmIds,
          appointees: users.value,
          reason: reason.value,
          notice_ways: noticeWay.value,
        }).catch(() => null);
        if (data) {
          Message({
            theme: 'success',
            message: t('分派成功'),
          });
          handleSuccess();
          handleShowChange(false);
        }
        loading.value = false;
      }
    };

    const handleSuccess = () => {
      emit('success', users.value);
    };

    const handleSelectUser = (val: string[]) => {
      users.value = val;
    };

    const validator = () => {
      if (!users.value.length) {
        errorMsg.users = t('输入分派人员');
        return false;
      }
      if (!reason.value) {
        errorMsg.reason = t('输入分派原因');
        return false;
      }
      if (!noticeWay.value.length) {
        errorMsg.notice = t('选择通知方式');
        return false;
      }
      return true;
    };

    return {
      loading,
      users,
      reason,
      noticeWay,
      noticeWayList,
      errorMsg,
      reasonList,
      handleShowChange,
      initErrorMsg,
      handleSelectUser,
      handleTagClick,
      handleSubmit,
    };
  },
  render() {
    return (
      <Dialog
        width={480}
        class={'alarm-dispatch-component-dialog'}
        v-slots={{
          default: () => (
            <Loading loading={this.loading}>
              <div class='alarm-dispatch'>
                <div class='tips'>
                  <span class='icon-monitor icon-hint' />
                  {this.$t('您一共选择了{0}条告警', [this.alarmIds.length])}
                </div>
                <div class='form-item'>
                  <div class='label require'>{this.$t('分派人员')}</div>
                  <div
                    class='content'
                    onClick={this.initErrorMsg}
                  >
                    <UserSelector
                      class='content-user-selector'
                      emptyText={this.$t('搜索结果为空')}
                      modelValue={this.users}
                      placeholder={this.$t('输入用户')}
                      onUpdate:modelValue={this.handleSelectUser}
                    />
                  </div>
                  {!!this.errorMsg.users && <div class='err-msg'>{this.errorMsg.users}</div>}
                </div>
                <div class='form-item'>
                  <div class='label'>
                    <div class='title require'>{this.$t('分派原因')}</div>
                    <div class='tags'>
                      {this.reasonList.map(tag => (
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
                    onClick={this.initErrorMsg}
                  >
                    <Input
                      v-model={this.reason}
                      maxlength={100}
                      rows={3}
                      type={'textarea'}
                    />
                  </div>
                  {!!this.errorMsg.reason && <div class='err-msg'>{this.errorMsg.reason}</div>}
                </div>
                <div class='form-item'>
                  <div class='label require'>{this.$t('通知方式')}</div>
                  <div
                    class='content'
                    onClick={this.initErrorMsg}
                  >
                    <Checkbox.Group v-model={this.noticeWay}>
                      {this.noticeWayList.map(item => (
                        <Checkbox
                          key={item.type}
                          label={item.type}
                        >
                          {item.label}
                        </Checkbox>
                      ))}
                    </Checkbox.Group>
                  </div>
                  {!!this.errorMsg.notice && <div class='err-msg'>{this.errorMsg.notice}</div>}
                </div>
              </div>
            </Loading>
          ),
          footer: () => (
            <div class='footer'>
              <Button
                style={{ 'margin-right': '8px' }}
                theme='primary'
                onClick={this.handleSubmit}
              >
                {this.$t('确定')}
              </Button>
              <Button
                onClick={() => {
                  this.handleShowChange(false);
                }}
              >
                {this.$t('取消')}
              </Button>
            </div>
          ),
        }}
        header-position='left'
        isShow={this.show}
        mask-close={true}
        render-directive='if'
        title={this.$t('告警分派')}
        onUpdate:isShow={this.handleShowChange}
      />
    );
  },
});
