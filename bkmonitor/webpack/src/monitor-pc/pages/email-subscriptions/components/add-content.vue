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
  <bk-sideslider
    class="add-content-wrap"
    :width="960"
    :is-show.sync="isShow"
    :quick-close="true"
  >
    <div slot="header">
      {{ $t('添加内容') }}
    </div>
    <div
      slot="content"
      class="content-main"
    >
      <bk-form
        ref="validateForm"
        :model="formData"
        :rules="rules"
        :label-width="$store.getters.lang === 'en' ? 136 : 120"
        class="form-wrap"
      >
        <bk-form-item
          :label="$t('子标题')"
          :required="true"
          :property="'contentTitle'"
          :error-display-type="'normal'"
        >
          <bk-input
            v-model="formData.contentTitle"
            class="input"
            :placeholder="$t('输入子标题')"
          />
        </bk-form-item>
        <bk-form-item :label="$t('说明')">
          <bk-input
            v-model="formData.contentDetails"
            class="input"
            :placeholder="$t('输入说明')"
            :type="'textarea'"
            :rows="3"
            :maxlength="200"
          />
        </bk-form-item>
        <template v-if="contentType === 'view'">
          <bk-form-item
            :label="$t('模块布局')"
            :required="true"
          >
            <bk-radio-group
              v-model="formData.rowPicturesNum"
              class="radio-wrap"
              @change="handlePicturesnumChange"
            >
              <bk-radio :value="2">
                {{ `2${$t('个/行')}` }}
              </bk-radio>
              <bk-radio :value="1">
                {{ `1${$t('个/行')}` }}
              </bk-radio>
            </bk-radio-group>
          </bk-form-item>
          <bk-form-item
            :label="$t('单图宽高')"
            :required="true"
          >
            <bk-input
              v-model="formData.width"
              class="img-size-input"
              :max="4000"
              :min="1"
              :placeholder="`${$t('最大')}4000`"
              type="number"
            >
              <template slot="prepend">
                <span class="group-text">{{ $t('宽') }}</span>
              </template>
            </bk-input>
            <span class="img-size-span">×</span>
            <bk-input
              v-model="formData.height"
              class="img-size-input"
              :placeholder="`${$t('最大')}2000`"
              :min="1"
              :max="2000"
              type="number"
            >
              <template slot="prepend">
                <span class="group-text">{{ $t('高') }}</span>
              </template>
            </bk-input>
          </bk-form-item>
          <bk-form-item
            :label="$t('选择图表')"
            :required="true"
            :property="'graphs'"
            :error-display-type="'normal'"
          >
            <select-chart v-model="formData.graphs" />
          </bk-form-item>
        </template>
        <template v-else-if="contentType === 'full'">
          <bk-form-item
            :label="$t('选择业务')"
            :required="true"
          >
            <!-- <bk-select
              class="biz-list-wrap"
              v-model="formData.curBizId"
              searchable
              :clearable="false"
              @change="() => getChartList()">
              <bk-option
                v-for="(option, index) in bizIdList"
                :key="index"
                :id="option.id"
                :name="option.text">
              </bk-option>
            </bk-select> -->
            <div class="biz-list-wrap">
              <space-select
                :value="[formData.curBizId]"
                :space-list="$store.getters.bizList"
                :need-authority-option="false"
                :need-alarm-option="false"
                :multiple="false"
                @change="handleBizIdChange"
              />
            </div>
          </bk-form-item>
          <bk-form-item
            :label="$t('选择仪表盘')"
            :required="true"
          >
            <bk-select
              v-model="formData.curGrafana"
              v-bkloading="{ isLoading: grafanaLoading }"
              class="biz-list-wrap"
              searchable
              :clearable="false"
            >
              <bk-option
                v-for="option in grafanaList"
                :id="option.uid"
                :key="option.uid"
                :name="option.text"
              />
            </bk-select>
          </bk-form-item>
          <bk-form-item
            :label="$t('图片宽度')"
            :required="true"
          >
            <bk-input
              v-model="formData.width"
              class="img-size-input single"
              :max="4000"
              :min="1"
              :placeholder="`${$t('高度自适应，宽度最大值为')}4000`"
              type="number"
            />
          </bk-form-item>
        </template>
        <bk-form-item class="form-action-buttons">
          <bk-button
            :disabled="!canSave"
            theme="primary"
            @click="handleConfirm"
            >{{ $t('确认') }}</bk-button
          >
          <bk-button @click="isShow = false">
            {{ $t('取消') }}
          </bk-button>
        </bk-form-item>
      </bk-form>
    </div>
  </bk-sideslider>
</template>

<script lang="ts">
import { Component, Emit, Prop, PropSync, Ref, Vue, Watch } from 'vue-property-decorator';

import { getDashboardList } from 'monitor-api/modules/grafana';

import SpaceSelect from '../../../components/space-select/space-select';
import selectChart from './select-chart.vue';

import type { IContentFormData } from '../types';
/**
 * 添加内容-侧边伸缩栏
 */
@Component({
  name: 'add-content',
  components: {
    selectChart,
    SpaceSelect,
  },
})
export default class AddContent extends Vue {
  // 侧栏展示状态
  @PropSync('show', { type: Boolean, default: false }) isShow: boolean;
  // 新增/编辑状态
  @Prop({ default: 'add', type: String }) private readonly type: 'add' | 'edit';
  // 编辑传入数据
  @Prop({ type: Object }) private readonly data: IContentFormData;
  // view: 视图截取  pull: 整屏截取
  @Prop({ type: String, default: 'view' }) private readonly contentType: 'full' | 'view';
  @Ref('validateForm') private readonly validateFormRef: any;
  // 表单展示数据

  private formData: IContentFormData = {
    contentTitle: '',
    contentDetails: '',
    rowPicturesNum: 2,
    graphs: [],
    curBizId: `${window.cc_biz_id}`,
    curGrafana: '',
    curGrafanaName: '',
    width: 620,
    height: 300,
  };

  private rules = {
    contentTitle: [{ required: true, message: window.i18n.t('必填项'), trigger: 'none' }],
    contentDetails: [{ required: true, message: window.i18n.t('必填项'), trigger: 'none' }],
    rowPicturesNum: [{ required: true, message: window.i18n.t('必填项'), trigger: 'none' }],
    graphs: [
      {
        validator(val) {
          return !!val.length;
        },
        message: window.i18n.t('必填项'),
        trigger: 'none',
      },
    ],
    curBizId: [{ required: true, message: window.i18n.t('必填项'), trigger: 'none' }],
    curGrafana: [{ required: true, message: window.i18n.t('必填项'), trigger: 'none' }],
  };
  private bizIdList = [];
  private allGrafanaListMap = [];

  private grafanaLoading = false;

  get grafanaList() {
    return this.allGrafanaListMap[this.formData.curBizId] || [];
  }

  get canSave() {
    const { contentTitle, rowPicturesNum, graphs, curBizId, curGrafana, width, height } = this.formData;
    // if (imgSize.some(item => Number.isNaN(+item) || item <= 0)) return false;
    if (Number.isNaN(+width) || width <= 0) return false;
    return this.contentType === 'view'
      ? !!(contentTitle && rowPicturesNum && graphs.length && !Number.isNaN(+height) && height > 0)
      : !!(contentTitle && curBizId && curGrafana !== '');
  }

  created() {
    this.bizIdList = this.$store.getters.bizList.map(item => ({
      id: String(item.id),
      text: item.text,
    }));
  }

  @Watch('formData.curGrafana')
  handleCurGrafana(v: string) {
    if (v) {
      this.formData.curGrafanaName = this.grafanaList.find(item => item.uid === v)?.text;
    }
  }

  /**
   * 数据更新操作
   * @params data 更新的数据
   */
  @Watch('data', { immediate: true, deep: true })
  dataChange(data: IContentFormData) {
    data && (this.formData = data);
  }

  /**
   * 初始化表单
   * @params show 展开状态
   */
  @Watch('isShow', { immediate: true })
  initFormData(show: boolean) {
    if (this.contentType === 'full' && show) {
      this.getChartList(true);
    }
    if (show && this.type === 'add') {
      this.formData = {
        contentTitle: '',
        contentDetails: '',
        rowPicturesNum: 2,
        graphs: [],
        width: 620,
        height: 300,
      };
      if (this.contentType === 'full') {
        this.formData = {
          ...this.formData,
          width: 1600,
          height: null,
          curBizId: `${window.cc_biz_id}`,
          curGrafana: '',
          curGrafanaName: '',
        };
      }
    }
  }

  // 新建时的默认值
  handlePicturesnumChange(v) {
    if (this.type === 'add') {
      this.formData.width = v === 1 ? 800 : 620;
      this.formData.height = v === 1 ? 270 : 300;
    }
  }

  /**
   * 确认操作
   */
  private handleConfirm() {
    this.validateFormRef.validate().then(() => {
      this.isShow = false;
      this.updateData();
    });
  }

  /**
   * 对外派发更新数据事件
   */
  @Emit('change')
  private updateData() {
    return this.formData;
  }

  private getChartList(isCreate = false) {
    // const noPermission = !this.bizIdList.some(item => `${item.id}` === `${this.curBizId}`)
    if (+this.formData.curBizId === -1) return;
    this.grafanaLoading = true;
    const bizId = this.formData.curBizId || window.cc_biz_id;
    getDashboardList({ bk_biz_id: bizId })
      .then(list => {
        const graphBiziId: any = {};
        graphBiziId[bizId] = list;
        this.allGrafanaListMap = graphBiziId;
        if (!isCreate) {
          this.formData.curGrafana = graphBiziId[this.formData.curBizId][0]?.uid || '';
        }
      })
      .catch(() => [])
      .finally(() => {
        this.grafanaLoading = false;
      });
  }

  private handleBizIdChange(value) {
    if (value.length) {
      this.formData.curBizId = value[0];
      this.getChartList();
    }
  }
}
</script>

<style lang="scss" scoped>
/* stylelint-disable no-descending-specificity */
.add-content-wrap {
  .content-main {
    position: relative;
    height: calc(100vh - 60px);
    max-height: calc(100vh - 60px);

    .form-wrap {
      box-sizing: border-box;
      // max-height: calc(100vh - 111px);
      padding: 24px 0;
      overflow-y: auto;
      background-color: #fff;

      :deep(.bk-label-text) {
        font-size: 12px;
      }

      :deep(.bk-form-item) {
        &:not(:first-child) {
          margin-top: 18px;
        }

        &.form-action-buttons {
          margin-top: 30px;
        }
      }

      .radio-wrap {
        & > :not(:last-child) {
          margin-right: 56px;
        }

        .bk-form-radio {
          line-height: 32px;
        }
      }

      .bk-form-item.is-error {
        :deep(.bk-select) {
          border-color: #c4c6cc;
        }
      }

      .input,
      .biz-list-wrap {
        width: 810px;
      }
    }

    .footer-wrap {
      position: absolute;
      bottom: 0;
      left: 0;
      display: flex;
      align-items: center;
      width: 100%;
      height: 51px;
      padding: 0 24px;
      background: #fafbfd;
      border: 1px solid #dcdee5;

      & > :not(:last-child) {
        margin-right: 10px;
      }
    }
  }

  .img-size-input {
    display: inline-flex;
    width: 140px;
    height: 32px;
    vertical-align: middle;

    &.single {
      width: 240px;
    }

    .group-text {
      width: 28px;
      padding: 0;
      font-size: 12px;
      line-height: 30px;
      color: #4d4f56;
      text-align: center;
    }

    ::v-deep .input-number-option {
      background-color: #f5f7fa;

      .number-option-item {
        color: #979ba5;
      }
    }
  }

  .img-size-span {
    margin: 0 2px;
    font-size: 12px;
    vertical-align: middle;
    color: #313238;
  }
}
</style>
