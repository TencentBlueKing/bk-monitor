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
import { Component, Ref, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import VerifyInput from '@/components/verify-input/verify-input.vue';
import { execCopy } from '../../utils';
import { validateCustomTsGroupName, validateCustomTsGroupLabel, type ICustomTimeSeriesDetail } from '../../../service';

import './index.scss';

/**
 * 组件Props接口
 */
interface IProps {
  /** 详情数据 */
  detailData: ICustomTimeSeriesDetail;
  /** 是否为平台级别（用于判断作用范围） */
  copyIsPlatform: boolean;
}

/**
 * 组件事件接口
 */
interface IEmits {
  /** 编辑字段事件
   * @param props 要编辑的字段属性对象
   * @param showMsg 是否显示成功消息
   */
  onEditFiled: (props: Record<string, any>, showMsg: boolean) => void;
}

/**
 * 自定义指标详情页组件
 */
@Component
export default class BasicInfo extends tsc<IProps, IEmits> {
  /** 详情数据 */
  @Prop({ default: () => ({}) }) detailData: IProps['detailData'];
  /** 是否为平台级别 */
  @Prop({ default: false }) copyIsPlatform: IProps['copyIsPlatform'];
  /** 名称输入框引用 */
  @Ref('nameInput') readonly nameInput!: HTMLInputElement;
  /** 数据标签输入框引用 */
  @Ref('dataLabelInput') readonly dataLabelInput!: HTMLInputElement;
  /** 描述输入框引用 */
  @Ref('describeInput') readonly describeInput!: HTMLInputElement;

  /** 修改的名字（临时存储） */
  copyName = '';
  /** 修改的英文名（临时存储） */
  copyDataLabel = '';
  /** 修改的描述（临时存储） */
  copyDescribe = '';
  /** 是否显示名字编辑框 */
  isShowEditName = false;
  /** 是否展示英文名编辑框 */
  isShowEditDataLabel = false;
  /** 是否展示描述编辑框 */
  isShowEditDesc = false;

  /**
   * 数据标签验证规则
   * @property {string} dataLabelTips - 验证错误提示信息
   * @property {boolean} dataLabel - 是否显示验证错误
   */
  rule = {
    dataLabelTips: '',
    dataLabel: false,
  };

  /**
   * 获取当前页面类型：自定义事件或自定义时序
   */
  get type(): string {
    return this.$route.name === 'custom-detail-event' ? 'customEvent' : 'customTimeSeries';
  }

  /**
   * 检查数据是否为只读
   * @returns {boolean} 是否为只读状态
   */
  get isReadonly(): boolean {
    return !!this.detailData.is_readonly;
  }

  /**
   * 监听详情数据变化，同步更新临时编辑值
   * @param {ICustomTimeSeriesDetail} newVal - 新的详情数据
   */
  @Watch('detailData', { immediate: true })
  handleDetailDataChange(newVal: ICustomTimeSeriesDetail) {
    this.copyName = newVal.name;
    this.copyDataLabel = newVal.data_label;
    this.copyDescribe = newVal.desc;
  }

  /**
   * 显示名称编辑框并聚焦输入框
   */
  handleShowEdit(): void {
    this.isShowEditName = true;
    this.$nextTick(() => {
      this.nameInput.focus();
    });
  }

  /**
   * 显示英文名编辑框并聚焦输入框
   * 同时重置验证规则状态
   */
  handleShowEditDataLabel(): void {
    this.isShowEditDataLabel = true;
    this.rule.dataLabelTips = '';
    this.rule.dataLabel = false;
    this.$nextTick(() => {
      this.dataLabelInput.focus();
    });
  }

  /**
   * 显示描述编辑框并聚焦输入框
   */
  handleShowEditDes(): void {
    this.isShowEditDesc = true;
    this.$nextTick(() => {
      this.describeInput.focus();
    });
  }

  /**
   * 编辑字段通用方法
   * @param props 字段属性
   * @param showMsg 是否显示成功消息
   */
  async handleEditFiled(props: Record<string, any>, showMsg = true): Promise<void> {
    this.$emit('editFiled', props, showMsg);
  }

  /**
   * 编辑英文名（数据标签）
   * 包含验证逻辑：非空检查、中文检查、唯一性验证
   */
  async handleEditDataLabel(): Promise<void> {
    // 如果英文名为空或未变更，则不做处理
    if (!this.copyDataLabel || this.copyDataLabel === this.detailData.data_label) {
      this.copyDataLabel = this.detailData.data_label;
      this.isShowEditDataLabel = false;
      return;
    }

    // 检查是否含有中文（数据标签不允许包含中文）
    if (/[\u4e00-\u9fa5]/.test(this.copyDataLabel)) {
      this.rule.dataLabelTips = this.$tc('输入非中文符号');
      this.rule.dataLabel = true;
      return;
    }

    // 验证英文名唯一性（通过API验证）
    const { message: errorMsg } = await validateCustomTsGroupLabel(
      {
        data_label: this.copyDataLabel,
        time_series_group_id: this.detailData.time_series_group_id,
      },
      {
        needMessage: false,
      }
    ).catch(err => err);

    // 如果验证失败，显示错误信息
    if (errorMsg) {
      this.rule.dataLabelTips = this.$t(errorMsg) as string;
      this.rule.dataLabel = true;
      return;
    }

    // 验证通过，保存英文名
    await this.handleEditFiled({
      data_label: this.copyDataLabel,
    });

    // 更新详情数据并关闭编辑框
    this.detailData.data_label = this.copyDataLabel;
    this.isShowEditDataLabel = false;
  }

  /**
   * 编辑名字
   * 包含验证逻辑：非空检查、唯一性验证
   */
  async handleEditName(): Promise<void> {
    // 如果名字为空或未变更，则不做处理
    if (!(this.copyName && this.copyName !== this.detailData.name)) {
      this.copyName = this.detailData.name;
      this.isShowEditName = false;
      return;
    }

    // 验证名字唯一性（通过API验证）
    let isOkName = true;
    const res = await validateCustomTsGroupName({
      name: this.copyName,
      time_series_group_id: this.detailData.time_series_group_id,
    })
      .then(res => res.result ?? true)
      .catch(() => false);

    // 如果验证失败，标记为无效
    if (!res) {
      isOkName = false;
    }

    // 如果名字验证失败，恢复原值并重新聚焦输入框
    if (!isOkName) {
      this.copyName = this.detailData.name;
      this.$nextTick(() => {
        this.nameInput.focus();
      });
      return;
    }

    // 验证通过，保存名字
    await this.handleEditFiled({
      name: this.copyName,
    });

    // 更新详情数据并关闭编辑框
    this.detailData.name = this.copyName;
    this.isShowEditName = false;
  }

  /**
   * 编辑描述
   * 描述字段不需要特殊验证，直接保存
   */
  async handleEditDescribe(): Promise<void> {
    // 如果描述未变更（去除空格后比较），则不做处理
    if (this.copyDescribe.trim() === this.detailData.desc) {
      this.copyDescribe = this.detailData.desc || '';
      this.isShowEditDesc = false;
      return;
    }

    // 关闭编辑框并保存描述
    this.isShowEditDesc = false;
    this.handleEditFiled({
      desc: this.copyDescribe,
    });

    // 更新详情数据
    this.detailData.desc = this.copyDescribe;
  }

  // 复制Token
  handleCopyToken(): void {
    execCopy(this.detailData.access_token);
    this.$bkMessage({ theme: 'success', message: this.$t('复制成功') });
  }

  /**
   * 渲染组件
   * @returns 组件JSX
   */
  render(): JSX.Element {
    return (
      <div class='detail-information'>
        <div class='detail-information-title'>{this.$t('基本信息')}</div>
        <div class='detail-information-content'>
          <div class='detail-information-row'>
            <span class='row-label'>{this.$t('数据ID')}: </span>
            <span
              class='row-content'
              v-bk-overflow-tips
            >
              {this.detailData.bk_data_id}
            </span>
          </div>
          <div class='detail-information-row'>
            <span class='row-label'>Token: </span>
            <span
              class='row-content'
              v-bk-overflow-tips
            >
              {this.detailData.access_token}
            </span>
            <i
              class='icon-monitor icon-mc-copy copy-icon'
              onClick={this.handleCopyToken}
            />
          </div>
          <div class='detail-information-row'>
            <span class='row-label'>{this.$t('监控对象')}: </span>
            <span
              class='row-content'
              v-bk-overflow-tips
            >
              {this.detailData.scenario}
            </span>
          </div>
          <div class='detail-information-row'>
            <span class='row-label'>{this.$t('上报协议')}: </span>
            {this.detailData.protocol ? (
              <span
                class='row-content'
                v-bk-overflow-tips
              >
                {this.detailData.protocol === 'json' ? 'JSON' : 'Prometheus'}
              </span>
            ) : (
              <span> -- </span>
            )}
          </div>
          <div class={'detail-information-row'}>
            <span class='row-label'>
              {this.type === 'customEvent' ? this.$t('是否为平台事件') : this.$t('作用范围')}:{' '}
            </span>
            <span
              class='row-content'
              v-bk-overflow-tips
            >
              {this.copyIsPlatform === false ? this.$t('本空间') : this.$t('全局')}
            </span>
          </div>{' '}
          <div class='detail-information-row'>
            <span class='row-label'>{this.$t('数据标签')}: </span>
            {!this.isShowEditDataLabel ? (
              <div style='display: flex; min-width: 0'>
                <span
                  class='row-content'
                  v-bk-overflow-tips
                >
                  {this.detailData.data_label || '--'}
                </span>
                {!this.isShowEditDataLabel && !this.isReadonly && (
                  <i
                    class='icon-monitor icon-bianji edit-name'
                    onClick={this.handleShowEditDataLabel}
                  />
                )}
              </div>
            ) : (
              <VerifyInput
                show-validate={this.rule.dataLabel}
                validator={{ content: this.rule.dataLabelTips }}
              >
                <bk-input
                  ref='dataLabelInput'
                  v-model={this.copyDataLabel}
                  onBlur={this.handleEditDataLabel}
                  onInput={() => {
                    this.rule.dataLabel = false;
                    this.rule.dataLabelTips = '';
                  }}
                />
              </VerifyInput>
            )}
          </div>
          <div class='detail-information-row'>
            <span class='row-label'>{this.$t('名称')}: </span>
            {!this.isShowEditName ? (
              <div style='display: flex; min-width: 0'>
                <span
                  class='row-content'
                  v-bk-overflow-tips
                >
                  {this.detailData.name}
                </span>
                {this.detailData.name && !this.isReadonly && (
                  <i
                    class='icon-monitor icon-bianji edit-name'
                    onClick={this.handleShowEdit}
                  />
                )}
              </div>
            ) : (
              <bk-input
                ref='nameInput'
                v-model={this.copyName}
                onBlur={this.handleEditName}
              />
            )}
          </div>
          <div class='detail-information-row last-row'>
            <span class='row-label'>{this.$t('描述')}: </span>
            {!this.isShowEditDesc ? (
              <div style='display: flex; min-width: 0'>
                <span
                  class='row-content'
                  v-bk-overflow-tips
                >
                  {this.detailData.desc || '--'}
                </span>
                {!this.isReadonly && (
                  <i
                    class='icon-monitor icon-bianji edit-name'
                    onClick={this.handleShowEditDes}
                  />
                )}
              </div>
            ) : (
              <bk-input
                ref='describeInput'
                class='form-content-textarea'
                v-model={this.copyDescribe}
                rows={3}
                type='textarea'
                onBlur={this.handleEditDescribe}
              />
            )}
          </div>
        </div>
      </div>
    );
  }
}
