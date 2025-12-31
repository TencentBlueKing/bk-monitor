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
import { Component, Emit, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import IndicatorSelector from './components/indicator-seletor';

import type { IGroupingRule } from '../../../../../service';

import './index.scss';

/** 组件事件接口 */
interface IEmits {
  /** 取消操作事件 */
  onCancel: (v: boolean) => void;
  /** 提交分组事件 */
  onGroupSubmit: (config: Partial<IGroupingRule>) => void;
}

/** 组件属性接口 */
interface IProps {
  /** 分组信息 */
  groupInfo: IGroupingRule;
  /** 是否为编辑模式 */
  isEdit: boolean;
  /** 是否显示对话框 */
  isShow: boolean;
  /** 分组名称列表，用于校验重名 */
  nameList: string[];
}

@Component
export default class AddGroupDialog extends tsc<IProps, IEmits> {
  /** 是否显示对话框 */
  @Prop({ default: false, type: Boolean }) isShow: IProps['isShow'];
  /** 是否为编辑模式 */
  @Prop({ default: false, type: Boolean }) isEdit: IProps['isEdit'];
  /** 分组信息 */
  @Prop({ default: () => ({}) }) groupInfo: IProps['groupInfo'];
  /** 分组名称列表，用于校验重名 */
  @Prop({ default: () => [] }) nameList: IProps['nameList'];
  /** 表单组件引用 */
  @Ref('groupRef') readonly groupRef!: HTMLFormElement;
  /** 指标选择器组件引用 */
  @Ref('indicatorSelectorRef') readonly indicatorSelectorRef!: InstanceType<typeof IndicatorSelector>;

  /** 本地分组信息，用于表单编辑 */
  localGroupInfo: Partial<IGroupingRule> = {
    create_from: 'user',
    scope_id: 0,
    auto_rules: [],
    metric_list: [],
  };

  formData = {
    name: '',
  };

  /** 分组表单验证规则 */
  get rules() {
    return {
      name: [
        {
          // 必填验证
          required: true,
          message: this.$t('必填项'),
          trigger: 'blur',
        },
        {
          // 名称长度验证：长度不能超过20个字符
          validator: (value: string) => value.length <= 20,
          message: this.$t('长度不能超过20个字符'),
          trigger: 'blur',
        },
        {
          // "default" 和 "默认分组"  这两个是内置的名称
          validator: (value: string) => !['default', '默认分组'].includes(value),
          message: this.$t('和内置分组名冲突'),
          trigger: 'blur',
        },
        {
          // 名称唯一性验证：编辑模式下排除当前分组名称，新建模式下检查所有名称
          validator: (value: string) => {
            if (this.groupInfo) {
              const groupNames = this.nameList.filter(name => name !== this.groupInfo.name);
              return !groupNames.includes(value);
            }
            return !this.nameList.includes(value);
          },
          message: this.$t('注意: 名字冲突'),
          trigger: 'blur',
        },
        {
          // 字符格式验证：只允许中文、英文、数字、下划线和连字符
          validator: (value: string) => /^[\u4E00-\u9FA5A-Za-z0-9_-]+$/g.test(value),
          message: this.$t('输入中文、英文、数字、下划线类型的字符'),
          trigger: 'blur',
        },
      ],
    };
  }

  /** 监听分组信息变化，同步到本地数据 */
  @Watch('groupInfo', { immediate: true, deep: true })
  handleGroupInfoChange(newVal: IGroupingRule) {
    this.localGroupInfo = { ...newVal };
    this.formData.name = this.localGroupInfo.name;
  }

  /** 提交分组表单 */
  handleSubmit() {
    this.groupRef?.validate().then(valid => {
      if (valid) {
        // 构建提交配置：包含手动选择的指标和自动规则
        const config: Partial<IGroupingRule> = {
          scope_id: this.localGroupInfo.scope_id,
          name: this.formData.name,
          // 手动选择的指标列表
          metric_list: this.indicatorSelectorRef.manualList
            .filter(item => !item.isDeleted)
            .map(item => ({
              field_id: Number(item.id),
              metric_name: item.name,
            })),
          // 自动规则列表
          auto_rules: this.indicatorSelectorRef.autoList.reduce<string[]>((dataList, item) => {
            if (item.name && !item.isDeleted) {
              dataList.push(item.name);
            }
            return dataList;
          }, []),
        };
        // 新建模式下不需要 scope_id
        if (!this.isEdit) {
          delete config.scope_id;
        }
        this.$emit('groupSubmit', config);
      }
    });
  }

  /** 取消操作，清空表单并关闭对话框 */
  @Emit('cancel')
  handleCancel() {
    this.clear();
    return false;
  }

  /** 清空表单数据和错误信息，重置为初始状态 */
  clear() {
    this.groupRef?.clearError?.();
    this.localGroupInfo = {
      scope_id: 0,
      auto_rules: [],
      metric_list: [],
      create_from: 'user',
    };
    this.formData = {
      name: '',
    };
  }

  /**
   * @description: 关闭设置前进行保存校验
   * @return 返回true为关闭，false则取消关闭设置
   */
  async handleBeforeCloseSettings(): Promise<boolean> {
    /** 编辑后存在差异 */
    const isNameChange = this.groupInfo.name !== this.formData.name;
    const isMetricListChange = this.groupInfo.metric_list.length !== this.indicatorSelectorRef.manualList.length;
    const isAutoRulesChange = this.groupInfo.auto_rules.length !== this.indicatorSelectorRef.autoList.length;
    if (isNameChange || isMetricListChange || isAutoRulesChange) {
      const res = await new Promise((resolve, reject) => {
        this.$bkInfo({
          zIndex: 99999,
          title: this.$t('是否放弃本次操作？'),
          confirmFn: () => resolve(true),
          cancelFn: () => reject(false),
        });
      });
      return !!res;
    }
    return true;
  }

  render() {
    return (
      <bk-sideslider
        width={1080}
        beforeClose={this.handleBeforeCloseSettings}
        {...{ on: { 'update:isShow': this.handleCancel } }}
        extCls={'custom-metric-group-main'}
        after-leave={this.clear}
        isShow={this.isShow}
        quick-close={true}
        title={this.isEdit ? this.$t('编辑分组') : this.$t('新建分组')}
        onHidden={this.handleCancel}
      >
        <div
          class='group-content'
          slot='content'
        >
          <bk-alert
            class='tips-main'
            title={this.$t('分组 用于指标归类，建议拥有相同维度的指标归到一个组里。')}
          />
          <bk-form
            ref='groupRef'
            formType='vertical'
            {...{
              props: {
                model: this.formData,
                rules: this.rules,
              },
            }}
          >
            <bk-form-item
              ext-cls='name'
              error-display-type='normal'
              label={this.$t('名称')}
              property='name'
              required
            >
              <bk-input
                v-model={this.formData.name}
                disabled={this.localGroupInfo.create_from === 'data'}
                placeholder={this.$t('请输入')}
              />
            </bk-form-item>
            <bk-form-item label={this.$t('选择指标')}>
              <IndicatorSelector
                isEdit={this.isEdit}
                ref='indicatorSelectorRef'
                groupInfo={this.localGroupInfo}
              />
            </bk-form-item>
          </bk-form>
        </div>
        <div slot='footer'>
          <bk-button
            style='margin-right: 8px;'
            class='operate-btn'
            theme='primary'
            onClick={this.handleSubmit}
          >
            {this.isEdit ? this.$t('保存') : this.$t('提交')}
          </bk-button>
          <bk-button
            class='operate-btn'
            onClick={this.handleCancel}
          >
            {this.$t('取消')}
          </bk-button>
        </div>
      </bk-sideslider>
    );
  }
}
