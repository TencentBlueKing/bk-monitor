/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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
import { defineComponent, reactive, shallowRef, useTemplateRef } from 'vue';

import { Button, Form, Input, Popover } from 'bkui-vue';
import { EditLine } from 'bkui-vue/lib/icon';
import { useI18n } from 'vue-i18n';

import './app-basic-info.scss';

/**
 * 应用基本信息数据接口
 */
export interface IAppBasicInfo {
  /** 应用别名 */
  alias: string;
  /** 应用描述 */
  desc: string;
  /** 应用域名 */
  domain: string;
  /** 应用状态 */
  status: string;
  /** 应用TOKEN */
  token: string;
}

/**
 * 应用基本信息展示组件
 * @description 展示 RUM 应用的基本信息，包括域名、状态、TOKEN、别名和描述
 * 支持编辑别名和描述，支持复制和重置 TOKEN
 */
export default defineComponent({
  name: 'AppBasicInfo',
  props: {
    /** 应用基本信息数据 */
    data: {
      type: Object as () => IAppBasicInfo,
      required: true,
    },
  },
  setup(props) {
    const { t } = useI18n();

    /** 编辑弹窗引用 */
    const editDescPopoverRef = useTemplateRef<InstanceType<typeof Popover>>('editDescPopover');
    /** 编辑表单引用 */
    const editDescFormRef = useTemplateRef<InstanceType<typeof Form>>('editDescForm');

    /** 表单校验规则 */
    const rules = {
      alias: [{ required: true, message: t('应用别名必填'), trigger: 'change' }],
    };

    /** 编辑表单数据模型 */
    const model = reactive({
      alias: props.data.alias,
      desc: props.data.desc,
    });

    /** 保存loading */
    const saveLoading = shallowRef(false);

    /**
     * 处理保存操作
     * 触发 save 事件并关闭弹窗
     */
    const handleSave = () => {
      const isValid = editDescFormRef.value.validate();
      if (!isValid) return;
      saveLoading.value = true;
      saveLoading.value = false;
    };

    /**
     * 处理取消操作
     * 重置表单数据并关闭弹窗
     */
    const handleCancel = () => {
      model.alias = props.data.alias;
      model.desc = props.data.desc;
      editDescPopoverRef.value?.hide();
    };

    /**
     * 处理复制 TOKEN
     */
    const handleCopyToken = () => {};

    /**
     * 处理重置 TOKEN
     */
    const handleResetToken = () => {};

    const handleOperationApp = (type: 'delete' | 'start' | 'stop') => {
      console.log(type);
    };

    return {
      t,
      model,
      rules,
      saveLoading,
      handleSave,
      handleCancel,
      handleCopyToken,
      handleResetToken,
      handleOperationApp,
    };
  },

  render() {
    const { data } = this;

    return (
      <div class='app-basic-info'>
        <div class='app-basic-info__left'>
          <div class='app-icon-wrapper'>
            <i class='icon-monitor icon-wangye app-icon' />
          </div>
          <div class='app-content'>
            <div class='content-row'>
              <span class='app-domain'>{data.domain}</span>
              <span class='app-status'>{data.status}</span>
              <div class='app-token'>
                <span class='token-label'>TOKEN：</span>
                <span class='token-value'>{data.token}</span>
                <span
                  class='token-action'
                  onClick={this.handleCopyToken}
                >
                  <i class='icon-monitor icon-mc-copy' />
                  <span>{this.$t('复制')}</span>
                </span>
                <span
                  class='token-action'
                  onClick={this.handleResetToken}
                >
                  <i class='icon-monitor icon-zhongzhi1' />
                  <span>{this.$t('重置')}</span>
                </span>
              </div>
            </div>
            <div class='content-row'>
              <span class='app-alias'>{data.alias}</span>
              <div class='separator' />
              <div class='app-desc'>
                <span class='desc-text'>{data.desc}</span>
                {/* 编辑弹窗 */}
                <Popover
                  ref='editDescPopover'
                  width={480}
                  extCls='edit-app-info-popover'
                  v-slots={{
                    content: () => (
                      <div class='edit-app-info-popover-content'>
                        <Form
                          ref='editDescForm'
                          class='edit-info-form'
                          form-type='vertical'
                          model={this.model}
                          rules={this.rules}
                        >
                          <Form.FormItem
                            label={this.$t('应用别名')}
                            property='alias'
                            required
                          >
                            <Input v-model={this.model.alias} />
                          </Form.FormItem>
                          <Form.FormItem
                            label={this.$t('应用描述')}
                            property='desc'
                          >
                            <Input
                              v-model={this.model.desc}
                              max={100}
                              resize={false}
                              type='textarea'
                            />
                          </Form.FormItem>
                        </Form>
                        <div class='action-btns'>
                          <Button
                            loading={this.saveLoading}
                            size='small'
                            theme='primary'
                            onClick={this.handleSave}
                          >
                            {this.$t('保存')}
                          </Button>
                          <Button
                            size='small'
                            onClick={this.handleCancel}
                          >
                            {this.$t('取消')}
                          </Button>
                        </div>
                      </div>
                    ),
                  }}
                  placement='bottom'
                  theme='light'
                  trigger='click'
                >
                  <EditLine class='edit-icon' />
                </Popover>
              </div>
            </div>
          </div>
        </div>
        <div class='app-basic-info__right'>
          <span class='operation-btn'>
            <i class='icon-monitor icon-bangzhuwendang link-icon' />
            <span>{this.$t('SDK 接入指引')}</span>
          </span>
          <Popover
            extCls='rum-app-more-menu-popover'
            v-slots={{
              content: () => (
                <div class='more-menu'>
                  <div
                    class='more-menu-item'
                    onClick={() => {
                      this.handleOperationApp('stop');
                    }}
                  >
                    {this.$t('停用')}
                  </div>
                  <div
                    class='more-menu-item'
                    onClick={() => {
                      this.handleOperationApp('delete');
                    }}
                  >
                    {this.$t('删除')}
                  </div>
                </div>
              ),
            }}
            placement='bottom'
            theme='light'
            trigger='click'
          >
            <span class='operation-btn'>
              <i class='icon-monitor icon-mc-more' />
              <span>{this.$t('更多')}</span>
            </span>
          </Popover>
        </div>
      </div>
    );
  },
});
