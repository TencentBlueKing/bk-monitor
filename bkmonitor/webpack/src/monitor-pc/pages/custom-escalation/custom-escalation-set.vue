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
    v-bkloading="{ isLoading: loading }"
    class="escalation"
  >
    <article class="escalation-form">
      <section class="escalation-form-title">
        {{ $t('基本信息') }}
      </section>
      <!--表单-->
      <section class="escalation-form-content">
        <bk-form
          :model="formData"
          :label-width="$store.getters.lang === 'en' ? 150 : 130"
        >
          <!--ID-->
          <bk-form-item
            ext-cls="content-basic"
            :label="$t('数据ID')"
            required
          >
            <bk-input
              v-model="formData[currentItemIdName]"
              :placeholder="$t('系统自动生成')"
              disabled
            />
          </bk-form-item>
          <!-- Token -->
          <bk-form-item
            ext-cls="content-basic"
            :label="'Token'"
            required
          >
            <bk-input
              v-model="formData.token"
              :placeholder="$t('系统自动生成')"
              disabled
            />
          </bk-form-item>
          <!-- 英文名 -->
          <bk-form-item
            :ext-cls="rule.dataLabel ? 'content-check' : 'content-basic'"
            :label="$t('数据标签')"
            property="dataLabel"
            required
          >
            <verify-input
              :show-validate.sync="rule.dataLabel"
              :validator="{ content: rule.dataLabelTips }"
            >
              <bk-input
                v-model="formData.dataLabel"
                :placeholder="type === 'customEvent' ? $t('输入自定义事件英文名称') : $t('输入数据ID的英文名称')"
                @focus="handleEnNameFocus"
                @blur="handleEnNameBlur"
              />
            </verify-input>
          </bk-form-item>
          <!--名称-->
          <bk-form-item
            :ext-cls="rule.name ? 'content-check' : 'content-basic'"
            :label="$t('名称')"
            property="name"
            required
          >
            <verify-input
              :show-validate.sync="rule.name"
              :validator="{ content: rule.nameTips }"
            >
              <bk-input
                v-model="formData.name"
                :placeholder="type === 'customEvent' ? $t('输入自定义事件名称') : $t('输入数据ID的名称')"
                @focus="handleNameFocus"
                @blur="handleNameBlur"
              />
            </verify-input>
          </bk-form-item>
          <!--监控对象-->
          <bk-form-item
            :ext-cls="rule.scenario ? 'content-check' : 'content-basic'"
            :label="$t('监控对象')"
            property="scenario"
            required
          >
            <verify-input
              :show-validate.sync="rule.scenario"
              :validator="{ content: $t('必填项') }"
            >
              <bk-select
                v-model="formData.scenario"
                :placeholder="$t('选择')"
                :clearable="false"
                class="form-content-select"
                @selected="rule.scenario = false"
              >
                <bk-option-group
                  v-for="(group, index) in scenarioList"
                  :key="index"
                  :name="group.name"
                >
                  <bk-option
                    v-for="(option, groupIndex) in group.children"
                    :id="option.id"
                    :key="groupIndex"
                    :name="option.name"
                  />
                </bk-option-group>
              </bk-select>
            </verify-input>
          </bk-form-item>
          <!-- 上报协议 -->
          <bk-form-item
            v-if="type !== 'customEvent'"
            :ext-cls="rule.protocol ? 'content-check' : 'content-basic'"
            :label="$t('上报协议')"
            property="protocol"
            required
          >
            <verify-input
              :show-validate.sync="rule.protocol"
              :validator="{ content: $t('必填项') }"
            >
              <div class="bk-button-group">
                <bk-button
                  v-for="(protocol, index) in protocolList"
                  :key="index"
                  :class="{ 'is-selected': protocol.id === formData.protocol }"
                  @click="handleProtocolChange(protocol.id)"
                >
                  {{ protocol.name }}
                </bk-button>
              </div>
            </verify-input>
            <span
              v-if="protocolDes"
              class="description"
            >
              {{ protocolDes }}
            </span>
          </bk-form-item>
          <!--ID-->
          <bk-form-item
            ext-cls="content-basic"
            :label="type === 'customEvent' ? $t('是否为平台事件') : $t('作用范围')"
          >
            <bk-checkbox
              v-if="type === 'customEvent'"
              v-model="formData.isPlatform"
            />
            <div v-else>
              <bk-radio-group
                v-model="formData.isPlatform"
                class="bk-radio-group"
              >
                <bk-radio
                  v-for="(scope, index) in scopeList"
                  :key="index"
                  :value="scope.id"
                  >{{ $t(scope.name) }}</bk-radio
                >
              </bk-radio-group>
            </div>
            <div
              v-if="type !== 'customEvent' && !!formData.isPlatform"
              class="platform-tips"
            >
              <span class="icon-monitor icon-tixing" />
              <span>{{
                $t('开启全业务作用范围，全部业务都可见属于自身业务的数据，有平台特定的数据格式要求，请联系平台管理员。')
              }}</span>
            </div>
          </bk-form-item>
          <bk-form-item
            v-if="type !== 'customEvent'"
            :ext-cls="'content-basic'"
            :label="$t('描述')"
          >
            <bk-input
              v-model="formData.desc"
              :placeholder="$t('未输入')"
              :type="'textarea'"
              :maxlength="100"
              :rows="3"
              class="form-content-textarea"
            />
          </bk-form-item>
        </bk-form>
      </section>
    </article>
    <!-- 事件列表 -->
    <div class="escalation-form escalation-list">
      <span
        v-if="type === 'customEvent'"
        class="escalation-form-title"
        >{{ $t('事件列表') }}</span
      >
      <span
        v-else
        class="escalation-form-title"
        >{{ $t('时序列表') }}</span
      >
      <span class="escalation-list-explain">{{ $t('（新建完成后自动获取）') }}</span>
    </div>
    <!-- 底部按钮 -->
    <div class="escalation-footer">
      <bk-button
        class="mc-btn-add"
        theme="primary"
        :icon="btnLoadingIcon"
        :disabled="disableSubmit || !isAllowSubmit"
        @click="handleSubmit"
      >
        {{ submitBtnText }}
      </bk-button>
      <bk-button
        class="ml10 mc-btn-add"
        @click="handleCancel"
      >
        {{ $t('取消') }}
      </bk-button>
    </div>
  </div>
</template>

<script lang="ts">
import { Component, Vue, Watch } from 'vue-property-decorator';

import { getLabel } from 'monitor-api/modules/commons';
import {
  createCustomEventGroup,
  createCustomTimeSeries,
  validateCustomEventGroupLabel,
  validateCustomTsGroupLabel,
} from 'monitor-api/modules/custom_report';

import VerifyInput from '../../components/verify-input/verify-input.vue';
import { SET_NAV_ROUTE_LIST } from '../../store/modules/app';

import type { IFormData, IParams, IRule } from '../../types/custom-escalation/custom-escalation-set';
import type MonitorVue from '../../types/index';

@Component({
  components: {
    VerifyInput,
  },
})
export default class CustomEscalationSet extends Vue<MonitorVue> {
  //   //  区别自定义事件和自定义指标
  //   @Prop({
  //     default: 'customEvent',
  //     validator: v => ['customEvent', 'customTimeSeries'].includes(v)
  //   }) readonly type: string

  private loading = false;
  private scenarioList: any[] = []; // 监控对象
  private currentItemIdName = 'bkEventGroupId'; // 当前 ID 字段
  private disableSubmit = false; // 是否禁用提交按钮（防止重复点击）
  private btnLoadingIcon = ''; // 提交时显示按钮loading效果
  private protocolList: Array<{ id: string; name: string }> = [
    { id: 'json', name: 'JSON' },
    { id: 'prometheus', name: 'Prometheus' },
  ]; // 上报协议字典
  private scopeList: Array<{ id: boolean; name: string }> = [
    { id: false, name: '本业务' },
    { id: true, name: '全业务' },
  ]; // 作用范围字典
  // 表单model
  private formData: IFormData = {
    bkEventGroupId: '',
    bkDataId: '',
    name: '',
    scenario: '',
    token: '',
    dataLabel: '',
    isPlatform: false,
    protocol: '',
    desc: '',
  };

  // 校验
  private rule: IRule = {
    name: false,
    scenario: false,
    nameTips: '',
    dataLabel: false,
    dataLabelTips: '',
    protocol: false,
  };

  /** 是否点击提交 */
  private isSubmit = false;

  /** 是否允许提交 */
  get isAllowSubmit() {
    const { name, scenario, dataLabel } = this.rule;
    return !name && !scenario && !dataLabel;
  }

  @Watch('type', { immediate: true })
  onTypeChange(v: string) {
    v === 'customEvent' ? (this.currentItemIdName = 'bkEventGroupId') : (this.currentItemIdName = 'bkDataId');
  }

  //  按钮文案
  get submitBtnText() {
    if (this.btnLoadingIcon === 'loading') {
      return this.$t('创建中...');
    }
    return this.$t('提交');
  }

  /** 上报协议提示 */
  get protocolDes() {
    const des = {
      json: this.$t('蓝鲸监控自有的JSON数据格式，创建完后有具体的格式说明'),
      prometheus: this.$t('支持Prometheus的标准输出格式'),
    };
    return des[this.formData.protocol];
  }

  get type() {
    return this.$route.name === 'custom-set-event' ? 'customEvent' : 'customTimeSeries';
  }

  created() {
    this.handleInit();
    this.rule.nameTips = this.$tc('必填项');
    this.rule.dataLabelTips = this.$tc('必填项');
  }

  /** 更新面包屑 */
  updateNavData(name = '') {
    if (!name) return;
    const routeList = [];
    routeList.push({
      name,
      id: '',
    });
    this.$store.commit(`app/${SET_NAV_ROUTE_LIST}`, routeList);
  }

  /** 选择上传协议类型 */
  handleProtocolChange(id = '') {
    this.rule.protocol = false;
    this.formData.protocol = id;
  }

  //  表单初始化
  async handleInit() {
    this.loading = true;
    this.type === 'customEvent'
      ? this.updateNavData(this.$t('新建自定义事件'))
      : this.updateNavData(this.$t('新建自定义指标'));
    if (!this.scenarioList.length) {
      // this.scenarioList = await this.$store.dispatch('custom-escalation/getScenarioList')
      this.scenarioList = await getLabel({ include_admin_only: false }).catch(() => []);
    }
    this.loading = false;
  }

  //  名字失焦校验
  async handleCheckName() {
    if (this.formData.name) {
      const res =
        this.type === 'customEvent'
          ? await this.$store
              .dispatch('custom-escalation/validateCustomEventName', {
                params: { name: this.formData.name },
                options: { needRes: true, needMessage: false },
              })
              .catch(err => err)
          : await this.$store
              .dispatch('custom-escalation/validateCustomTimetName', {
                params: { name: this.formData.name },
                options: { needRes: true, needMessage: false },
              })
              .catch(err => err);
      if (!res.result) {
        this.rule.nameTips = res.message;
        this.rule.name = true;
      }
      return !!res.result;
    }
    return false;
  }

  /**
   * 名称聚焦
   */
  handleNameFocus() {
    this.rule.name = false;
    this.isSubmit = false;
  }
  /**
   * 英文名聚焦
   */
  handleEnNameFocus() {
    this.rule.dataLabel = false;
    this.isSubmit = false;
  }
  /**
   * 名称失焦校验
   */
  handleNameBlur() {
    setTimeout(() => {
      if (this.isSubmit) {
        this.isSubmit = false;
      } else {
        this.handleCheckName();
      }
    }, 100);
  }
  /**
   * 英文名失焦校验
   */
  handleEnNameBlur() {
    setTimeout(() => {
      if (this.isSubmit) {
        this.isSubmit = false;
      } else {
        this.handleCheckDataLabel();
      }
    }, 100);
  }

  /** 英文名失焦校验 */
  async handleCheckDataLabel() {
    if (!this.formData.dataLabel) return false;
    if (/[\u4e00-\u9fa5]/.test(this.formData.dataLabel)) {
      this.rule.dataLabelTips = this.$tc('输入非中文符号');
      this.rule.dataLabel = true;
      return false;
    }
    const res =
      this.type === 'customEvent'
        ? await validateCustomEventGroupLabel(
            { data_label: this.formData.dataLabel },
            { needRes: true, needMessage: false, needTraceId: false }
          ).catch(err => err)
        : await validateCustomTsGroupLabel(
            { data_label: this.formData.dataLabel },
            { needRes: true, needMessage: false, needTraceId: false }
          ).catch(err => err);
    if (res.code !== 200) {
      this.rule.dataLabelTips = res.message;
      this.rule.dataLabel = true;
      return false;
    }
    return true;
  }

  /**
   * 提交前表单校验
   */
  async handleValidate() {
    let isPass = true;
    if (!this.formData.name) {
      isPass = false;
      this.rule.name = true;
    }
    if (!this.formData.scenario) {
      isPass = false;
      this.rule.scenario = true;
    }
    if (!this.formData.dataLabel) {
      isPass = false;
      this.rule.dataLabel = true;
      this.rule.dataLabelTips = this.$tc('必填项');
    }
    if (this.type !== 'customEvent' && !this.formData.protocol) {
      isPass = false;
      this.rule.protocol = true;
    }
    return isPass;
  }

  //  提交（事件、时序）
  async handleSubmit() {
    this.isSubmit = true;
    const isPass = await this.handleValidate();
    if (!isPass) return;
    this.disableSubmit = true;
    this.btnLoadingIcon = 'loading';
    const params = {
      name: this.formData.name,
      scenario: this.formData.scenario,
      data_label: this.formData.dataLabel,
      is_platform: this.formData.isPlatform,
    };
    let result: IParams = {};
    if (this.type === 'customEvent') {
      // 自定义事件
      result = await createCustomEventGroup(params, { needMessage: false }).catch(err => ({
        bk_event_group_id: '',
        message: err.message,
        code: err.code,
      }));
      this.handleToDetail(result.bk_event_group_id);
    } else {
      // 自定义指标新增字段

      const addParams = {
        protocol: this.formData.protocol,
        desc: this.formData.desc,
      };
      // 自定义指标
      result = await createCustomTimeSeries({ ...params, ...addParams }, { needMessage: false }).catch(err => ({
        time_series_group_id: '',
        message: err.error_details || err.message,
        code: err.code,
      }));
      this.handleToDetail(result.time_series_group_id);
    }
    if (result.code === 3335007) {
      // 英文名报错
      this.rule.dataLabel = true;
      this.rule.dataLabelTips = result.message;
    } else if (result.code === 3335006) {
      // 名称报错
      this.rule.name = true;
      this.rule.nameTips = result.message;
    } else if (result.code) {
      this.$bkMessage({ message: result.message, theme: 'error' });
    }
    this.disableSubmit = false;
    this.btnLoadingIcon = '';
  }

  //  跳转详情
  handleToDetail(id: string) {
    if (id) {
      this.$bkMessage({
        theme: 'success',
        message: this.$t('创建成功'),
      });

      const name = this.type === 'customEvent' ? 'custom-detail-event' : 'custom-detail-timeseries';
      this.$router.replace({
        name,
        params: {
          id,
          isCreat: 'creat',
        },
      });
    }
  }

  //  取消按钮
  handleCancel() {
    // this.$router.push({ name: 'custom-escalation' });
    this.$router.back();
  }
}
</script>

<style lang="scss" scoped>
@import '../../theme/index';

.escalation {
  height: calc(100vh - 102px);
  padding: 20px;

  :deep(.bk-button-icon-loading::before) {
    content: '';
  }

  :deep(.step-verify-input) {
    .bottom-text {
      padding-top: 10px;
    }
  }

  &-form {
    padding: 23px 20px 4px 37px;
    font-size: 12px;
    background: $whiteColor;
    border-radius: 2px;
    box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.1);

    @include border-1px($color: $defaultBorderColor);

    .bk-button-group {
      .bk-button {
        width: 134px;
      }
    }

    .description {
      padding-top: 9px;
      font-size: 12px;
      line-height: 1;
      color: #979ba5;
    }

    .bk-radio-group {
      padding-top: 6px;

      .bk-form-radio {
        margin-right: 24px;
      }
    }

    &-title {
      font-weight: bold;
    }

    &-content {
      margin-top: 25px;

      .content-basic {
        width: 576px;
        margin-bottom: 20px;

        .platform-tips {
          display: flex;
          width: max-content;
          padding: 6px 9px;
          margin-top: 6px;
          line-height: 20px;
          background: #fff4e2;
          border: 1px solid #ffdfac;
          border-radius: 2px;

          .icon-tixing {
            margin-right: 9px;
            font-size: 16px;
            color: #ff9c01;
          }
        }
      }

      .content-check {
        width: 576px;
        margin-bottom: 32px;
      }

      .form-content-select {
        width: 240px;
      }
    }
  }

  &-list {
    display: flex;
    align-items: center;
    height: 64px;
    padding-bottom: 24px;
    margin-top: 16px;

    &-explain {
      color: $unsetIconColor;
    }
  }

  &-footer {
    margin-top: 20px;
  }
}
</style>
