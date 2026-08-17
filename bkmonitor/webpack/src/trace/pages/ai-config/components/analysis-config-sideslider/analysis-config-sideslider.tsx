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
import { defineComponent, watch } from 'vue';

import { Button, Input, Sideslider, Switcher } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import { useMatchRuleFields } from '../../composables/use-match-rule-fields';
import { useRuleBasicInfo } from '../../composables/use-rule-basic-info';
import MatchRule from '../match-rule/match-rule';

import './analysis-config-sideslider.scss';

/**
 * @description 新增绑定侧弹窗
 * 用于源码 AI 分析中新增告警策略与流程实例的绑定关系。
 */
export default defineComponent({
  name: 'AnalysisConfigSideslider',
  props: {
    /** 是否展示抽屉 */
    show: {
      type: Boolean,
      default: false,
    },
    /** 当前绑定流程名称 */
    processName: {
      type: String,
      default: '',
    },
  },
  emits: {
    /** 抽屉显隐更新（v-model:show） */
    'update:show': (_v: boolean) => true,
    /** 确认提交 */
    confirm: () => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const {
      conditions,
      priority,
      isEnabled,
      errors,
      handleConditionsChange,
      handlePriorityChange,
      handleEnabledChange,
      validate,
    } = useRuleBasicInfo();
    const { fields: matchRuleFields, fetchFields: fetchMatchRuleFields } = useMatchRuleFields();

    watch(
      () => props.show,
      () => {
        if (props.show) {
          fetchMatchRuleFields();
        }
      }
    );

    /**
     * @description 关闭抽屉
     */
    const handleClose = () => {
      emit('update:show', false);
    };

    /**
     * @description 确认提交：先校验基础信息，通过后抛出 confirm 事件
     */
    const handleConfirm = () => {
      if (!validate()) return;
      emit('confirm');
    };

    /**
     * @description 渲染抽屉头部
     */
    const renderHeader = () => {
      return <span class='analysis-config-sideslider-header-title'>{t('新增绑定')}</span>;
    };

    /**
     * @description 渲染基础信息区域
     */
    const renderBasicInfo = () => {
      return (
        <div class='main-section'>
          <div class='main-section-header'>
            <div class='main-section-title'>{t('基础信息')}</div>
          </div>
          <div class='main-section-content'>
            <div class='form-item'>
              <div class='form-item-label'>
                <span>{t('告警策略匹配规则')}</span>
                <span class='required-star'>*</span>
              </div>
              <div class='form-item-content'>
                <MatchRule
                  fields={matchRuleFields.value}
                  value={conditions.value}
                  onUpdate:value={handleConditionsChange}
                />
                {errors.value?.conditions && <div class='form-item-error'>{errors.value.conditions}</div>}
              </div>
            </div>
            <div class='form-items mt-24'>
              <div class='form-item'>
                <div class='form-item-label'>
                  <span>{t('优先级')}</span>
                  <span class='required-star'>*</span>
                  <span class='form-item-label-tip'>
                    <span class='icon-monitor icon-hint' />
                    {t('数值越高，优先级越高，最大值为10000')}
                  </span>
                </div>
                <div class='form-item-content'>
                  <Input
                    style='width: 340px'
                    modelValue={priority.value}
                    type='number'
                    onUpdate:modelValue={handlePriorityChange}
                  />
                  {errors.value?.priority && <div class='form-item-error'>{errors.value.priority}</div>}
                </div>
              </div>
              <div class='form-item'>
                <div class='form-item-label'>
                  <span>{t('状态')}</span>
                  <span class='required-star'>*</span>
                </div>
                <div class='form-item-content'>
                  <Switcher
                    class='mt-6'
                    modelValue={isEnabled.value}
                    onChange={handleEnabledChange}
                  />
                </div>
              </div>
            </div>
          </div>
        </div>
      );
    };

    /**
     * @description 渲染流程实例参数区域
     */
    const renderProcessParams = () => {
      return (
        <div class='main-section'>
          <div class='main-section-header'>
            <span class='main-section-title'>{t('流程实例参数')}</span>
            <div class='section-header-division' />
            <span class='main-section-subtitle'>
              {t('当前绑定流程')}：{props.processName ?? '--'}
            </span>
          </div>
          <div class='main-section-content'>{/* 智能体、知识库、Skill 等详细内容待实现 */}</div>
        </div>
      );
    };

    /**
     * @description 渲染底部操作栏
     */
    const renderFooter = () => {
      return (
        <div class='analysis-config-sideslider-footer'>
          <Button
            theme='primary'
            onClick={handleConfirm}
          >
            {t('确定')}
          </Button>
          <Button onClick={handleClose}>{t('取消')}</Button>
        </div>
      );
    };

    return {
      conditions,
      priority,
      isEnabled,
      errors,
      handleConditionsChange,
      handlePriorityChange,
      handleEnabledChange,
      renderHeader,
      renderBasicInfo,
      renderProcessParams,
      renderFooter,
      handleClose,
    };
  },
  render() {
    return (
      <Sideslider
        width={960}
        extCls='analysis-config-sideslider'
        isShow={this.show}
        quickClose
        onUpdate:isShow={v => this.$emit('update:show', v)}
      >
        {{
          header: this.renderHeader,
          default: () => (
            <div class='analysis-config-sideslider-main'>
              {this.renderBasicInfo()}
              {this.renderProcessParams()}
            </div>
          ),
          footer: this.renderFooter,
        }}
      </Sideslider>
    );
  },
});
