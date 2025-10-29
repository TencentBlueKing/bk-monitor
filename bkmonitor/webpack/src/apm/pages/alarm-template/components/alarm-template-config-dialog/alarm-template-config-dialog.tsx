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

import { listUserGroup } from 'monitor-api/modules/model';
import AlarmGroup from 'monitor-pc/pages/strategy-config/strategy-config-set-new/components/alarm-group';

import AlgorithmRules from '../template-form/algorithm-rules/algorithm-rules';
import { AlgorithmEnum } from '../template-form/typing';

import type { IAlarmGroupList } from '../../quick-add-strategy/typing';
import type { AlarmTemplateListItem } from '../../typing';
import type { AlarmDeleteConfirmEvent } from '../alarm-delete-confirm/alarm-delete-confirm';

import './alarm-template-config-dialog.scss';

// 所有修改项类型选项
const TYPE_MAP = {
  algorithms: {
    title: window.i18n.tc('修改检测规则'),
    label: window.i18n.tc('检测规则'),
    width: 600,
  },
  user_group_list: {
    title: window.i18n.tc('修改告警组'),
    label: window.i18n.tc('告警组'),
    width: 480,
  },
};

export interface AlarmTemplateConfigDialogProps {
  /** 激活 dialog 弹窗的类型 */
  activeType: 'algorithms' | 'user_group_list';
  /** 默认值 */
  defaultValue: AlarmTemplateListItem['algorithms'] | AlarmTemplateListItem['user_group_list'];
  /** 当前操作的模板 id */
  templateId: AlarmTemplateListItem['id'];
}

interface AlarmTemplateConfigDialogEvents {
  /** 关闭弹窗事件回调 */
  onCancel: () => void;
  /** 保存事件回调 */
  onConfirm: (
    templateId: AlarmTemplateListItem['id'],
    updateValue: Partial<AlarmTemplateListItem>,
    promiseEvent?: AlarmDeleteConfirmEvent
  ) => void;
}

@Component
export default class AlarmTemplateConfigDialog extends tsc<
  AlarmTemplateConfigDialogProps,
  AlarmTemplateConfigDialogEvents
> {
  /** 激活 dialog 弹窗的类型 */
  @Prop({ type: String }) activeType: 'algorithms' | 'user_group_list';
  /** 默认值 */
  @Prop({ type: Array, default: () => [] }) defaultValue:
    | AlarmTemplateListItem['algorithms']
    | AlarmTemplateListItem['user_group_list'];
  /** 当前操作的模板 id */
  @Prop({ type: Number }) templateId: AlarmTemplateListItem['id'];

  @Ref('form') formRef;

  /** dialog 中操作的值 */
  value: AlarmTemplateListItem['algorithms'] | AlarmTemplateListItem['user_group_list'] = [];
  /** dialog 窗口中loading状态 */
  loading = false;
  // 告警组可选项数据
  alarmGroupList: IAlarmGroupList[] = [];

  alarmGroupLoading = false;

  /** dialog 是否显示 */
  get dialogShow() {
    return this.templateId && ['algorithms', 'user_group_list'].includes(this.activeType);
  }

  /** 告警组id映射map */
  get alarmGroupMap() {
    return (
      this.alarmGroupList?.reduce?.((acc, cur) => {
        acc[cur.id] = cur;
        return acc;
      }, {}) ?? {}
    );
  }

  get rules() {
    if (this.activeType === 'algorithms')
      return {
        value: [
          {
            required: true,
            message: this.$t('检测规则必须开启一个级别'),
            trigger: 'change',
          },
          {
            validator: this.validAlgorithms,
            message: this.$t('检测算法填写不完整，请完善后添加'),
            trigger: 'blur',
          },
        ],
      };
    return {};
  }

  validAlgorithms(value: AlarmTemplateListItem['algorithms']) {
    return value.every(item => {
      if (item.type === AlgorithmEnum.Threshold) {
        return item.config.threshold || item.config.threshold === 0;
      }
      if (item.type === AlgorithmEnum.YearRoundAndRingRatio) {
        return item.config.ceil >= 1 && item.config.ceil <= 100 && item.config.floor >= 1 && item.config.floor <= 100;
      }
      return true;
    });
  }

  @Watch('dialogShow')
  async dialogShowChange() {
    if (!this.dialogShow) {
      this.value = [];
      return;
    }
    if (this.activeType === 'user_group_list') {
      await this.getAlarmGroupList();
    }
    this.value = structuredClone(this.defaultValue || []);
  }

  /**
   * @description 保存事件回调
   */
  async handleConfirm() {
    const valid = await this.formRef?.validate().catch(() => false);
    if (!valid) return;

    this.loading = true;
    let successCallback = null;
    let errorCallback = null;
    const promiseEvent = new Promise((res, rej) => {
      successCallback = res;
      errorCallback = rej;
    })
      .then(() => {
        this.loading = false;
        this.handleCancel();
      })
      .catch(() => {
        this.loading = false;
      });
    this.$emit(
      'confirm',
      this.templateId,
      { [this.activeType]: this.value },
      { promiseEvent, successCallback, errorCallback }
    );
  }

  /**
   * @description 关闭弹窗事件回调
   */
  @Emit('cancel')
  handleCancel() {
    this.loading = false;
    return;
  }

  /**
   * @description 获取告警组数据
   */
  async getAlarmGroupList() {
    this.alarmGroupLoading = true;
    const data = await listUserGroup().catch(() => []);
    this.alarmGroupList = data.map(item => ({
      id: item.id,
      name: item.name,
      receiver: item.users?.map(rec => rec.display_name) || [],
    }));
    this.alarmGroupLoading = false;
  }

  /**
   * @description 默认值改变事件回调(需要特殊处理的单独另外写方法)
   */
  handleDefaultChange(v) {
    this.value = v;
  }

  /**
   * @description 告警组选择事件回调
   */
  handleUserGroupChange(groupIds) {
    this.value = groupIds.map(groupId => {
      const item = this.alarmGroupMap?.[groupId];
      return {
        id: groupId,
        name: item?.name || '',
      };
    });
  }

  getAllTypeComponent() {
    switch (this.activeType) {
      case 'algorithms':
        return (
          <AlgorithmRules
            algorithms={this.value as AlarmTemplateListItem['algorithms']}
            algorithmsUnit={(this.defaultValue as AlarmTemplateListItem['algorithms'])?.[0]?.unit_prefix}
            onChange={this.handleDefaultChange}
          />
        );
      case 'user_group_list':
        if (this.alarmGroupLoading) return <div class='skeleton-element alarm-group-skeleton' />;
        return (
          <AlarmGroup
            hasAddGroup={false}
            isOpenEditNewPage={true}
            list={this.alarmGroupList}
            showAddTip={false}
            value={(this.value as AlarmTemplateListItem['user_group_list'])?.map(item => item.id)}
            onAddGroup={() => this.handleCancel()}
            onChange={data => this.handleUserGroupChange(data)}
          />
        );
      default:
        return null;
    }
  }

  render() {
    /** dialog弹窗配置项 */
    const { title, width } = TYPE_MAP[this.activeType] || {};

    return (
      <bk-dialog
        width={width}
        class='alarm-template-config-dialog'
        escClose={false}
        headerPosition={'left'}
        maskClose={false}
        title={title}
        value={this.dialogShow}
        on-after-leave={this.handleCancel}
        on-confirm={this.handleConfirm}
      >
        <bk-form
          ref='form'
          class='alarm-template-dialog-wrap'
          v-bkloading={{ isLoading: this.loading }}
          {...{
            props: {
              model: {
                value: this.value,
              },
              rules: this.rules,
            },
          }}
          label-width={0}
        >
          <bk-form-item
            error-display-type='normal'
            // label={label}
            property='value'
          >
            {this.getAllTypeComponent()}
          </bk-form-item>
        </bk-form>
        <div slot='footer'>
          <bk-button
            disabled={this.loading}
            loading={this.loading}
            theme='primary'
            onClick={this.handleConfirm}
          >
            {this.$t('保存')}
          </bk-button>
          <bk-button
            loading={this.loading}
            onClick={this.handleCancel}
          >
            {this.$t('取消')}
          </bk-button>
        </div>
      </bk-dialog>
    );
  }
}
