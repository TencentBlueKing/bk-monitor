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
    class="alarm-shield-notice"
    :class="{ 'is-show': isShow }"
  >
    <div class="notice-btn">
      <bk-switcher
        v-model="isShow"
        size="small"
        theme="primary"
        style="margin-right: 10px"
        @change="handleChangeShow"
      />
      {{ $t('通知设置') }}
    </div>
    <div
      v-if="isShow"
      class="notice-config"
    >
      <div
        class="notice-item notice-input"
        :class="{ 'verify-show': rule.isMemberValue }"
      >
        <div
          class="notice-item-label notice-input-label"
        >{{ $t('通知对象') }}</div>
        <verify-input
          :show-validate.sync="rule.isMemberValue"
          :validator="{ content: $t('至少添加一个通知对象') }"
        >
          <div class="notice-item-content">
            <div
              class="over-input"
              v-if="isShowOverInput"
            >
              <img
                src="../../../static/images/svg/spinner.svg"
                class="status-loading"
                alt=''
              >
            </div>
            <member-selector
              class="bk-member-selector"
              v-model="member.value"
              :group-list="groupList"
            />
          </div>
        </verify-input>
      </div>
      <div
        class="notice-item"
        :class="{ 'verify-show': rule.isNotificationMethod }"
      >
        <div class="notice-item-label">
          {{ $t('通知方式') }}
        </div>
        <verify-input
          :show-validate.sync="rule.isNotificationMethod"
          :validator="{ content: $t('至少选择一种通知方式') }"
        >
          <div class="notice-item-content">
            <bk-checkbox-group v-model="notificationMethod">
              <bk-checkbox
                v-for="(item, index) in setWay"
                :key="index"
                class="checkbox-group"
                :value="item.type"
              >{{
                item.label
              }}</bk-checkbox>
            </bk-checkbox-group>
          </div>
        </verify-input>
      </div>
      <div
        class="notice-item"
        style="margin-bottom: 30px"
      >
        <div class="notice-item-label">
          {{ $t('通知时间') }}
        </div>
        <verify-input
          :show-validate.sync="rule.isNoticeNumber"
          :validator="{ content: $t('仅支持整数') }"
        >
          <div class="notice-item-content">
            <i18n
              class="noitce-number"
              path="屏蔽开始/结束前{0}分钟发送通知"
            >
              <div class="input-demo mlr-10">
                <bk-input
                  type="number"
                  :max="1440"
                  :min="1"
                  v-model="noticeNumber"
                  @change="handleTriggerNumber"
                  placeholder="0"
                />
              </div>
            </i18n>
          </div>
        </verify-input>
      </div>
    </div>
  </div>
</template>

<script>
import { getNoticeWay, getReceiver } from '../../../../monitor-api/modules/notice_group';
import VerifyInput from '../../../components/verify-input/verify-input';
import MemberSelector from '../../alarm-group/alarm-group-add/member-selector.vue';

export default {
  name: 'AlarmShieldNotice',
  components: {
    VerifyInput,
    MemberSelector
  },
  data() {
    return {
      bizId: '',
      isShow: false,
      noticeNumber: 5,
      notificationMethod: [],
      isShowOverInput: true,
      member: {
        data: [],
        value: [],
        noticeWayError: false
      },
      setWay: [],
      rule: {
        isNotificationMethod: false,
        isMemberValue: false,
        isNoticeNumber: false
      }
    };
  },
  computed: {
    /** 人员组数据 */
    groupList() {
      const list = this.member.data.find(item => item.id === 'group')?.children || [];
      return list.map(item => ({
        ...item,
        username: item.id
      }));
    }
  },
  created() {
    this.bizId = this.$store.getters.bizId;
    this.getNoticeData();
  },
  methods: {
    handleChangeShow(v) {
      this.$emit('change-show', v);
    },
    handleSelectNoticeWay() {
      this.member.noticeWayError = !this.member.value.length;
    },
    handleTriggerNumber(v) {
      if (`${v}`.includes('.')) {
        this.noticeNumber = Number(v.replace(/\./gi, ''));
      }
    },
    handleNoticeReceiver() {
      const { data } = this.member;
      const groupList = data.find(item => item.id === 'group')?.children || [];
      const result = this.member.value.map((id) => {
        const isGroup = groupList.find(group => group.id === id);
        return {
          logo: '',
          display_name: '',
          type: isGroup ? 'group' : 'user',
          id
        };
      });
      return result;
    },
    async getNoticeData() {
      getReceiver()
        .then((data) => {
          this.member.data = data;
        })
        .finally(() => {
          this.isShowOverInput = false;
        });
      this.setWay = (await getNoticeWay({ bk_biz_id: this.bizId }) || []).filter(item => item.channel === 'user');
    },
    getNoticeConfig() {
      const { rule } = this;
      const noticeNumberRule = /^\d+$/;
      if (this.isShow) {
        if (!this.notificationMethod.length || !this.member.value.length || !noticeNumberRule.test(this.noticeNumber)) {
          rule.isNotificationMethod = !this.notificationMethod.length;
          rule.isMemberValue = !this.member.value.length;
          rule.isNoticeNumber = !noticeNumberRule.test(this.noticeNumber);
          return false;
        }
        return {
          notice_receiver: this.handleNoticeReceiver(),
          notice_way: this.notificationMethod,
          notice_time: this.noticeNumber
        };
      }
      return true;
    },
    setNoticeData(data) {
      this.isShow = true;
      this.member.value = data.member.value;
      this.notificationMethod = data.notificationMethod;
      this.noticeNumber = data.noticeNumber;
    }
  }
};
</script>

<style lang="scss" scoped>
.alarm-shield-notice {
  font-size: 14px;
  color: #63656e;

  .is-show {
    margin-bottom: 30px;
  }

  .notice-btn {
    display: flex;
    align-items: center;
    margin: 0 0 18px 134px;
  }

  .notice-config {
    .verify-show {
      /* stylelint-disable-next-line declaration-no-important */
      margin-bottom: 32px !important;
    }

    .notice-item {
      display: flex;
      align-items: center;
      margin-bottom: 20px;

      &-label {
        position: relative;
        flex: 0 0;
        min-width: 110px;
        margin-right: 24px;
        text-align: right;

        &::before {
          position: absolute;
          top: 2px;
          right: -9px;
          color: #ea3636;
          content: '*';
        }
      }

      &-content {
        position: relative;
        flex-grow: 1;

        .checkbox-group {
          margin-right: 32px;
        }

        .mr-10 {
          margin-right: 10px;
        }

        .mlr-10 {
          margin: 0 10px;
        }

        .over-input {
          position: absolute;
          top: 0;
          z-index: 2;
          display: flex;
          align-items: center;
          justify-content: flex-end;
          width: 100%;
          height: 32px;
          padding-right: 10px;

          &:hover {
            cursor: no-drop;
          }

          .status-loading {
            width: 16px;
            height: 16px;
          }
        }
      }

      .noitce-number {
        display: flex;
        align-items: center;

        .bk-form-control {
          width: 68px;
        }
      }
    }

    .notice-input {
      align-items: flex-start;

      &-label {
        margin-top: 6px;
      }
    }
  }

  .bk-member-selector {
    width: 834px;
    // min-height: 32px;
    .bk-selector-member {
      display: flex;
      align-items: center;
      padding: 0 10px;
    }

    .avatar {
      width: 22px;
      height: 22px;
      border: 1px solid #c4c6cc;
      border-radius: 50%;
    }

    :deep(.tag-list) {
      > li {
        height: 22px;
      }

      .no-img {
        margin-right: 5px;
        font-size: 22px;
        color: #979ba5;
        background: #fafbfd;
        border-radius: 16px;
      }

      .key-node {
        /* stylelint-disable-next-line declaration-no-important */
        background: none !important;

        .tag {
          display: flex;
          align-items: center;
          height: 22px;
          background: none;

          .avatar {
            float: left;
            width: 22px;
            height: 22px;
            margin-right: 8px;
            vertical-align: middle;
            border: 1px solid #c4c6cc;
            border-radius: 50%;
          }
        }
      }
    }

    .notice-input {
      align-items: flex-start;

      &-label {
        margin-top: 6px;
      }
    }
  }
}
</style>
