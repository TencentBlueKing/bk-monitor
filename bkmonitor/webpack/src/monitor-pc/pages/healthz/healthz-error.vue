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
  <!-- 异常告警 -->
  <div
    class="dash-board-center"
    v-show="msg === 1"
  >
    <mo-panel shadow="never">
      <div slot="header">
        <i class="icon icon-volume" />
        <span> {{ $t('通知设置') }} </span>
      </div>
      <el-form
        ref="alarmConfigForm"
        label-width="160px"
        label-position="right"
        size="small"
        :model="this"
        :rules="rules"
        v-bkloading="{ isLoading: loadingAlarmConfig }"
      >
        <el-form-item
          required
          :label="$t('通知方式')"
          prop="alarmType"
        >
          <!-- <el-checkbox-group v-model="alarmType" v-validate="{ required: true }" data-vv-name="alarmType"> -->
          <el-checkbox-group v-model="alarmType">
            <el-checkbox
              label="mail"
            ><img
              src="../../static/assets/images/mail.png"
              alt="mail"
              style="height: 20px"
            ></el-checkbox>
            <el-checkbox
              label="wechat"
            ><img
              src="../../static/assets/images/wechat.png"
              alt="wechat"
              style="height: 20px"
            ></el-checkbox>
            <el-checkbox
              label="sms"
            ><img
              src="../../static/assets/images/sms.png"
              alt="sms"
              style="height: 20px"
            ></el-checkbox>
            <el-checkbox
              v-if="$platform.te"
              label="im"
            ><img
              src="../../static/assets/images/rtx.png"
              alt="rtx"
              style="height: 20px"
            ></el-checkbox>
            <el-checkbox
              label="phone"
            ><img
              src="../../static/assets/images/phone.png"
              alt="phone"
              style="height: 20px"
            ></el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item
          required
          :label="$t('通知人员')"
          prop="alarmRole"
          class="member-item"
        >
          <member-selector
            style="width: 300px"
            v-model="alarmRole"
          />
          <el-tooltip
            placement="right"
            effect="dark"
            style="margin-left: 10px"
            :content="$t('当蓝鲸监控的进程状态异常或告警队列拥塞时会通知相关人员')"
          >
            <span><i class="fa fa-question-circle" /></span>
          </el-tooltip>
        </el-form-item>
        <el-row style="text-align: center">
          <el-button
            type="success"
            @click="setAlarmConfig"
            :loading="loadingSaveAlarmConfig"
          >
            {{ $t('保存') }}
          </el-button>
        </el-row>
      </el-form>
    </mo-panel>
  </div>
</template>
<script>
import { Button, Checkbox, CheckboxGroup, Form, FormItem, Row, Tooltip } from 'element-ui';

import MemberSelector from '../alarm-group/alarm-group-add/member-selector.vue';

import { messageMixin } from './message-mixin';
import MoPanel from './panel';

export default {
  name: 'MoHealthzAlarmConfig',
  components: {
    MoPanel,
    ElForm: Form,
    ElFormItem: FormItem,
    ElCheckboxGroup: CheckboxGroup,
    ElCheckbox: Checkbox,
    ElTooltip: Tooltip,
    ElRow: Row,
    ElButton: Button,
    MemberSelector
  },
  mixins: [messageMixin],
  props: {
    msg: {
      type: Number
    }
  },
  data() {
    return {
      alarmType: [],
      alarmRole: [],
      alarmRoleOptions: [],
      filteredRoleOptions: [],
      loadingAlarmRoleOptions: false,
      loadingAlarmConfig: false,
      loadingSaveAlarmConfig: false,
      rules: {
        alarmType: [{ required: true, message: this.$t('注意: 必填字段不能为空'), trigger: 'change' }],
        alarmRole: [{ required: true, message: this.$t('注意: 必填字段不能为空'), trigger: 'change' }]
      }
    };
  },
  watch: {
    msg: {
      handler(val) {
        if (val === 1) {
          this.getAlarmConfig();
        }
      },
      immediate: true
    }
  },
  methods: {
    getAlarmConfig() {
      // eslint-disable-next-line @typescript-eslint/no-this-alias
      const self = this;
      self.loadingAlarmConfig = true;
      self.$api.healthz
        .getAlarmConfig()
        .then((data) => {
          if (data.alarm_type.length > 0 || data.alarm_role.length > 0) {
            self.alarmRole = data.alarm_role;
            self.alarmType = data.alarm_type;
          } else {
            self.$refs.alarmConfigForm.resetFields();
          }
          self.loadingAlarmConfig = false;
        })
        .catch(() => {
          self.message.error(this.$t('获取通知设置失败'));
          self.loadingAlarmConfig = false;
        });
    },
    setAlarmConfig() {
      // eslint-disable-next-line @typescript-eslint/no-this-alias
      const self = this;
      self.loadingSaveAlarmConfig = true;
      let params = {
        alarm_type: self.alarmType,
        alarm_role: self.alarmRole
      };

      params = { alarm_config: params };

      self.$refs.alarmConfigForm.validate((valid) => {
        if (valid) {
          self.$api.healthz.updateAlarmConfig(params, { needRes: true }).then((res) => {
            if (res.result) {
              self.message.success(this.$t('保存成功'));
            } else {
              self.message.error(this.$t('获取通知设置失败'));
            }
            self.loadingSaveAlarmConfig = false;
          });
        } else {
          self.message.error(this.$t('校验失败，请检查参数'));
          self.loadingSaveAlarmConfig = false;
        }
      });
    },
    filterMethod(query) {
      if (query !== '') {
        this.loadingAlarmRoleOptions = true;
        setTimeout(() => {
          this.filteredRoleOptions = this.alarmRoleOptions.filter((item) => {
            const str = `${item.english_name}|${item.chinese_name}`;
            return str.indexOf(query) > -1;
          });

          this.filteredRoleOptions = this.filteredRoleOptions.slice(0, 500);
          this.loadingAlarmRoleOptions = false;
        });
      }
    }
  }
};
</script>
<style lang="scss">
.icon-volume {
  background: url('../../static/assets/images/icon-volume.png');
}

.el-card__header {
  padding: 15px;

  .icon,
  > span {
    float: left;
  }

  .icon {
    width: 20px;
    height: 20px;
    margin-right: 10px;

    /* stylelint-disable-next-line declaration-no-important */
    background-size: 20px 20px !important;
  }
}

.member-item {
  .el-tooltip {
    display: none;
  }
}
</style>
