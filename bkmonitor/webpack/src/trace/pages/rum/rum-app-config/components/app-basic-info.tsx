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
import { type PropType, computed, defineComponent, reactive, shallowRef, useTemplateRef } from 'vue';

import { Button, Form, Input, Message, Popover } from 'bkui-vue';
import { EditLine } from 'bkui-vue/lib/icon';
import { copyText } from 'monitor-common/utils';
import { useI18n } from 'vue-i18n';

import { operateApplication, queryAppToken, updateAppBasicInfo } from '../services/app-config';

import type { ApplicationOperationType, IRumAppConfig } from '../../typings/rum-app-config';

import './app-basic-info.scss';

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
      type: Object as PropType<IRumAppConfig>,
      default: () => ({}),
    },
  },
  emits: {
    applicationOperation: (_type: ApplicationOperationType) => true,
    applicationInfoChange: (_params: { app_alias: string; description: string }) => true,
    showSdkGuide: () => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();

    /** 编辑弹窗引用 */
    const editDescPopoverRef = useTemplateRef<InstanceType<typeof Popover>>('editDescPopover');
    /** 编辑表单引用 */
    const editDescFormRef = useTemplateRef<InstanceType<typeof Form>>('editDescForm');
    /** 应用 TOKEN */
    const token = shallowRef('');
    /** 是否显示 TOKEN */
    const isShowToken = shallowRef(false);
    /** TOKEN 加载中 */
    const tokenLoading = shallowRef(false);

    /** 表单校验规则 */
    const rules = {
      alias: [{ required: true, message: t('应用别名必填'), trigger: 'change' }],
    };

    /** 编辑表单数据模型 */
    const model = reactive({
      alias: '',
      desc: '',
    });

    /** 保存loading */
    const saveLoading = shallowRef(false);

    /** 编辑弹窗打开 */
    const handleEditPopoverShow = () => {
      model.alias = props.data.app_alias;
      model.desc = props.data.description;
    };

    /**
     * 处理保存操作
     * 触发 save 事件并关闭弹窗
     */
    const handleSave = async () => {
      const isValid = await editDescFormRef.value.validate().catch(() => false);
      if (!isValid) return;
      saveLoading.value = true;
      updateAppBasicInfo({
        bk_biz_id: props.data?.bk_biz_id,
        app_name: props.data?.app_name,
        app_alias: model.alias,
        description: model.desc,
      })
        .then(() => {
          emit('applicationInfoChange', { app_alias: model.alias, description: model.desc });
          editDescPopoverRef.value?.hide();
          Message({
            message: t('保存成功'),
            theme: 'success',
          });
        })
        .finally(() => {
          saveLoading.value = false;
        });
    };

    /**
     * 处理取消操作
     */
    const handleCancel = () => {
      editDescPopoverRef.value?.hide();
    };

    /**
     * 处理复制 TOKEN
     */
    const handleCopyToken = () => {
      let isError = false;
      copyText(token.value, msg => {
        Message({
          message: msg,
          theme: 'error',
        });
        isError = true;
        return;
      });
      if (isError) return;
      Message({
        message: t('复制成功'),
        theme: 'success',
      });
    };

    /**
     * 处理查看 TOKEN
     */
    const handleViewToken = async () => {
      if (!isShowToken.value && !token.value) {
        tokenLoading.value = true;
        token.value = await queryAppToken({ app_name: props.data?.app_name, bk_biz_id: props.data?.bk_biz_id });
        tokenLoading.value = false;
        if (!token.value) return;
      }
      isShowToken.value = !isShowToken.value;
    };

    /** 更多菜单 Popover 引用 */
    const menuPopoverRef = useTemplateRef<InstanceType<typeof Popover>>('menuPopover');
    /** 更多菜单是否显示 */
    const appOperationMenuShow = shallowRef(false);
    /** 操作确认弹窗加载状态 */
    const popoverLoading = shallowRef(false);
    /** 当前操作类型 */
    const operationType = shallowRef<ApplicationOperationType>('stop');
    /** 操作确认弹窗是否显示 */
    const appConfirmPopoverShow = shallowRef(false);
    /** 各操作类型对应的文案映射 */
    const operationMap = {
      delete: {
        title: t('确认删除该应用？'),
        confirmText: t('删除'),
        tips: t('删除后无法恢复，请谨慎操作！'),
      },
      start: {
        title: t('确认启用该应用？'),
        confirmText: t('启用'),
        tips: t('启用后数据将重新上报至该应用，若无数据，请检查上报配置'),
      },
      stop: {
        title: t('确认停用该应用？'),
        confirmText: t('停用'),
        tips: t('停用后将不会有数据上报，请谨慎操作'),
      },
    };
    /** 根据当前操作类型获取对应的文案配置 */
    const appOperationMapText = computed(() => {
      return operationMap[operationType.value];
    });

    /** 全局点击事件，关闭所有操作弹窗 */
    const documentClickFn = () => {
      appOperationMenuShow.value = false;
      appConfirmPopoverShow.value = false;
    };
    /** 点击"更多"按钮，显示操作菜单 */
    const handleAppOperationMenuShow = (e: Event) => {
      e.stopPropagation();
      appOperationMenuShow.value = true;
      document.addEventListener('click', documentClickFn);
    };
    /** 操作菜单隐藏后，移除全局点击监听 */
    const handleAppOperationMenuHidden = () => {
      appOperationMenuShow.value = false;
      document.removeEventListener('click', documentClickFn);
    };

    /** 选中操作项，设置操作类型并显示确认弹窗 */
    const handleOperationApp = (_e: Event, type: ApplicationOperationType) => {
      operationType.value = type;
      appConfirmPopoverShow.value = true;
    };

    /** 取消操作，隐藏确认弹窗 */
    const handleOperationCancel = () => {
      appConfirmPopoverShow.value = false;
    };

    /** 执行应用操作（启用/停用/删除），成功后通知父组件 */
    const handleApplicationOperation = async () => {
      popoverLoading.value = true;
      operateApplication(operationType.value, {
        bk_biz_id: props.data?.bk_biz_id,
        app_name: props.data?.app_name,
      })
        .then(() => {
          Message({
            message: t('操作成功'),
            theme: 'success',
          });
          appConfirmPopoverShow.value = false;
          menuPopoverRef.value?.hide();
          emit('applicationOperation', operationType.value);
        })
        .finally(() => {
          popoverLoading.value = false;
        });
    };

    return {
      token,
      isShowToken,
      tokenLoading,
      model,
      rules,
      t,
      saveLoading,
      appOperationMenuShow,
      appOperationMapText,
      appConfirmPopoverShow,
      popoverLoading,
      handleAppOperationMenuShow,
      handleAppOperationMenuHidden,
      handleEditPopoverShow,
      handleSave,
      handleCancel,
      handleCopyToken,
      handleViewToken,
      handleOperationApp,
      handleOperationCancel,
      handleApplicationOperation,
    };
  },

  render() {
    return (
      <div class='app-basic-info'>
        <div class='app-basic-info__left'>
          <div class='app-icon-wrapper'>
            <i class='icon-monitor icon-wangye app-icon' />
          </div>
          <div class='app-content'>
            <div class='content-row'>
              <span
                class='app-name'
                v-overflow-tips
              >
                {this.data.app_name}
              </span>
              <span class={['app-status', { 'is-enabled': this.data.is_enabled }]}>
                {this.data.is_enabled ? this.$t('启用中') : this.$t('已停用')}
              </span>
              <div class='app-token'>
                <span class='token-label'>TOKEN：</span>
                {this.tokenLoading ? (
                  <div
                    style='height: 12px; width: 65px'
                    class='skeleton-element'
                  />
                ) : (
                  <span class='token-value'>{this.isShowToken ? this.token : '●●●●●●●●●●'}</span>
                )}
                <span
                  class='token-action'
                  onClick={this.handleViewToken}
                >
                  <i class={['icon-monitor', this.isShowToken ? 'icon-mc-invisible' : 'icon-mc-visual']} />
                  <span>{this.isShowToken ? this.$t('隐藏') : this.$t('查看')}</span>
                </span>
                {this.isShowToken && (
                  <span
                    class='token-action'
                    onClick={this.handleCopyToken}
                  >
                    <i class='icon-monitor icon-mc-copy' />
                    <span>{this.$t('复制')}</span>
                  </span>
                )}
              </div>
            </div>
            <div class='content-row'>
              <span
                class='app-alias'
                v-overflow-tips
              >
                {this.data.app_alias}
              </span>
              <div class='separator' />
              <div class='app-desc'>
                <span
                  class='desc-text'
                  v-overflow-tips
                >
                  {this.data.description}
                </span>
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
                  onAfterShow={this.handleEditPopoverShow}
                >
                  <EditLine
                    class='edit-icon'
                    v-tippy={{
                      content: this.t('编辑'),
                    }}
                  />
                </Popover>
              </div>
            </div>
          </div>
        </div>
        <div class='app-basic-info__right'>
          <span
            class='operation-btn'
            onClick={() => this.$emit('showSdkGuide')}
          >
            <i class='icon-monitor icon-bangzhuwendang link-icon' />
            <span>{this.$t('SDK 接入指引')}</span>
          </span>
          <Popover
            v-slots={{
              content: () => (
                <div class='rum-app-operation-content'>
                  <div class='title'>{this.appOperationMapText.title}</div>
                  <div class='app-name'>
                    <span class='label'>{this.$t('应用名称')}：</span>
                    <span class='value'>{this.data.app_name}</span>
                  </div>
                  <div class='tips'>{this.appOperationMapText.tips}</div>
                  <div class='btns'>
                    <Button
                      loading={this.popoverLoading}
                      size='small'
                      theme='primary'
                      onClick={this.handleApplicationOperation}
                    >
                      {this.appOperationMapText.confirmText}
                    </Button>
                    <Button
                      size='small'
                      onClick={this.handleOperationCancel}
                    >
                      {this.$t('取消')}
                    </Button>
                  </div>
                </div>
              ),
            }}
            arrow={true}
            isShow={this.appConfirmPopoverShow}
            placement='left'
            theme='light rum-app-operation-popover'
            trigger='manual'
          >
            <Popover
              ref='menuPopover'
              extCls='rum-app-more-menu-popover'
              v-slots={{
                content: () => (
                  <div class='more-menu'>
                    <div
                      class='more-menu-item'
                      onClick={e => {
                        this.handleOperationApp(e, this.data?.is_enabled ? 'stop' : 'start');
                      }}
                    >
                      {this.data?.is_enabled ? this.$t('停用') : this.$t('启用')}
                    </div>
                    <div
                      class='more-menu-item'
                      onClick={e => {
                        this.handleOperationApp(e, 'delete');
                      }}
                    >
                      {this.$t('删除')}
                    </div>
                  </div>
                ),
              }}
              isShow={this.appOperationMenuShow}
              placement='bottom'
              theme='light'
              trigger='manual'
              onAfterHidden={this.handleAppOperationMenuHidden}
            >
              <span
                class='operation-btn'
                onClick={this.handleAppOperationMenuShow}
              >
                <i class='icon-monitor icon-mc-more' />
                <span>{this.$t('更多')}</span>
              </span>
            </Popover>
          </Popover>
        </div>
      </div>
    );
  },
});
