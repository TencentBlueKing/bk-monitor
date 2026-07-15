/**
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
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions
 * of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */
import { type PropType, defineComponent, useTemplateRef } from 'vue';

import { Form, Select } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import { TapdTypeMap } from '../../../constant';
import { TapdLinkModeEnum } from '../../constant';

import type { CreateTapdDefaultSetting, TapdLinkModeType, TapdWorkspaceItem } from '../../typing';

import './tapd-basic-form.scss';
export default defineComponent({
  name: 'TapdBasicForm',
  props: {
    modelValue: {
      type: Object,
      default: () => ({
        workspace_id: null,
        tapd_type: 'story',
      }),
    },
    workspaceList: {
      type: Array<TapdWorkspaceItem>,
      default: () => [],
    },
    tabActive: {
      type: String as PropType<TapdLinkModeType>,
      default: TapdLinkModeEnum.CREATE,
    },
    defaultValue: {
      type: Object as PropType<CreateTapdDefaultSetting>,
      default: null,
    },
  },
  emits: ['update:modelValue', 'tabChange', 'setDefaultValue', 'addWorkspace'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const formRef = useTemplateRef<InstanceType<typeof Form>>('form');
    const workspaceSelectRef = useTemplateRef<InstanceType<typeof Select>>('workspaceSelect');
    const rules = {
      workspace_id: [{ required: true, message: t('项目必填'), trigger: 'select' }],
      tapd_type: [{ required: true, message: t('单据类型必填'), trigger: 'select' }],
    };

    const tabList = [
      { label: t('新建单据'), value: TapdLinkModeEnum.CREATE, icon: 'icon-jia' },
      { label: t('关联已有'), value: TapdLinkModeEnum.LINK, icon: 'icon-mc-guanlian' },
    ];

    const handleWorkspaceChange = value => {
      emit('update:modelValue', {
        ...props.modelValue,
        workspace_id: value,
      });
    };

    const handleTapdTypeChange = value => {
      emit('update:modelValue', {
        ...props.modelValue,
        tapd_type: value,
      });
    };

    const handleTabChange = (value: string) => {
      emit('tabChange', value);
    };

    const handleSetDefaultValue = type => {
      emit('setDefaultValue', type);
    };

    const handleAddWorkspace = () => {
      workspaceSelectRef.value?.hidePopover();
      emit('addWorkspace');
    };

    const validate = async () => {
      return formRef.value?.validate();
    };

    return {
      rules,
      tabList,
      validate,
      handleWorkspaceChange,
      handleTapdTypeChange,
      handleTabChange,
      handleSetDefaultValue,
      handleAddWorkspace,
    };
  },
  render() {
    const workspaceIsDefault =
      this.defaultValue?.workspace_id && this.defaultValue?.workspace_id === this.modelValue.workspace_id;
    const tapdTypeIsDefault =
      this.defaultValue?.tapd_type && this.defaultValue?.tapd_type === this.modelValue.tapd_type;

    return (
      <div class='tapd-basic-form'>
        <Form
          ref='form'
          class='tapd-form'
          form-type='vertical'
          model={this.modelValue}
          rules={this.rules}
        >
          <Form.FormItem
            v-slots={{
              label: () => (
                <div class='form-label-row'>
                  <span class='form-label-text'>{this.$t('项目')}</span>
                  <span
                    class={['default-tag', { active: workspaceIsDefault }]}
                    onClick={() => {
                      this.handleSetDefaultValue('workspace_id');
                    }}
                  >
                    <i class={['icon-monitor', workspaceIsDefault ? 'icon-mc-collect' : 'icon-mc-uncollect']} />
                    {workspaceIsDefault ? this.$t('已设默认') : this.$t('设为默认')}
                  </span>
                </div>
              ),
            }}
            property='workspace_id'
          >
            <Select
              ref='workspaceSelect'
              clearable={false}
              modelValue={this.modelValue.workspace_id}
              filterable
              onChange={this.handleWorkspaceChange}
            >
              {{
                default: () =>
                  this.workspaceList.map(item => (
                    <Select.Option
                      id={item.workspace_id}
                      key={item.workspace_id}
                      name={item.workspace_name}
                    />
                  )),
                extension: () => (
                  <div
                    style='display: flex;align-items: center;justify-content: center;width: 100%;gap: 9px;cursor: pointer;'
                    class='add-workspace'
                    onClick={this.handleAddWorkspace}
                  >
                    <i
                      style='font-size: 16px; color: #979BA5'
                      class='icon-monitor icon-jia'
                    />
                    <span style='color: #4D4F56'>{this.$t('关联更多项目')}</span>
                  </div>
                ),
              }}
            </Select>
          </Form.FormItem>
          <Form.FormItem
            v-slots={{
              label: () => (
                <div class='form-label-row'>
                  <span class='form-label-text'>{this.$t('单据类型')}</span>
                  <span
                    class={['default-tag', { active: tapdTypeIsDefault }]}
                    onClick={() => {
                      this.handleSetDefaultValue('tapd_type');
                    }}
                  >
                    <i class={['icon-monitor', tapdTypeIsDefault ? 'icon-mc-collect' : 'icon-mc-uncollect']} />
                    {tapdTypeIsDefault ? this.$t('已设默认') : this.$t('设为默认')}
                  </span>
                </div>
              ),
            }}
            property='tapd_type'
          >
            <Select
              clearable={false}
              modelValue={this.modelValue.tapd_type}
              onChange={this.handleTapdTypeChange}
            >
              {TapdTypeMap.map(item => (
                <Select.Option
                  id={item.value}
                  key={item.value}
                  name={item.label}
                />
              ))}
            </Select>
          </Form.FormItem>
        </Form>
        <div class='create-tapd-tab'>
          {this.tabList.map((item, index) => [
            <div
              key={item.value}
              class={['tab-item', { active: this.tabActive === item.value }]}
              onClick={() => this.handleTabChange(item.value)}
            >
              <i class={['icon-monitor', item.icon]} />
              {item.label}
            </div>,
            index === 0 && <div class='divider' />,
          ])}
        </div>
      </div>
    );
  },
});
