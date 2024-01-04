/*
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
 */

import { Component, Emit, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { DetectionRuleTypeEnum, IDetectionTypeRuleData } from '../../../typings';

import './partial-nodes.scss';

interface PartialNodesData {
  count: number;
}

interface PartialNodesProps {
  data?: IDetectionTypeRuleData<PartialNodesData>;
  otherSelectRuleData?: IDetectionTypeRuleData[];
  readonly?: boolean;
  isRealtime?: boolean;
}

interface PartialNodesEvents {
  onDataChange: IDetectionTypeRuleData;
}

@Component({})
export default class PartialNodes extends tsc<PartialNodesProps, PartialNodesEvents> {
  /** 表单回填数据 */
  @Prop({ type: Object }) data: IDetectionTypeRuleData<PartialNodesData>;
  /** 只读 */
  @Prop({ type: Boolean, default: false }) readonly: boolean;
  /** 其他已选择的算法数据 */
  @Prop({ type: Array, default: () => [] }) otherSelectRuleData: IDetectionTypeRuleData[];
  /** 是否是实时选项 */
  @Prop({ type: Boolean, default: false }) isRealtime: boolean;
  /** 表单实例 */
  @Ref() formRef;

  localData: IDetectionTypeRuleData<PartialNodesData> = {
    type: DetectionRuleTypeEnum.PartialNodes,
    level: 1,
    config: {
      count: 1
    }
  };

  errorMsg = '';

  rules = {
    level: [{ required: true, message: this.$t('必填项'), trigger: 'change' }],
    config: [
      {
        validator: this.checkConfig,
        message: this.showMsg,
        trigger: 'change'
      }
    ]
  };

  get otherSelectLevel() {
    return this.otherSelectRuleData.reduce((pre, cur) => {
      if (cur.type === DetectionRuleTypeEnum.PartialNodes) pre.push(cur.level);
      return pre;
    }, []);
  }

  /** 根据其他已选择静态阈值算法的级别，来确定本次可选的级别 */
  get levelList() {
    const list = [
      { id: 1, name: window.i18n.t('致命'), disabled: false, icon: 'icon-danger' },
      { id: 2, name: window.i18n.t('预警'), disabled: false, icon: 'icon-mind-fill' },
      { id: 3, name: window.i18n.t('提醒'), disabled: false, icon: 'icon-tips' }
    ];
    list.forEach(item => {
      item.disabled = this.otherSelectLevel.includes(item.id);
    });
    return list;
  }

  created() {
    if (this.data) {
      this.localData = this.data;
    } else {
      this.initData();
    }
  }

  /** 初始化数据 */
  initData() {
    this.localData.level = this.levelList.find(item => !item.disabled).id;
    this.emitLocalData();
  }

  validate() {
    return new Promise((res, rej) => {
      this.formRef
        .validate()
        .then(validator => res(validator))
        .catch(validator => rej(validator));
    });
  }

  clearError() {
    this.formRef.clearError();
  }

  showMsg() {
    return this.errorMsg;
  }

  checkConfig(value: PartialNodesData) {
    if (this.isRealtime) {
      this.errorMsg = this.$tc('当前实时的查询不支持该检测算法，请删除');
      return false;
    }
    if (value.count >= 1) return true;
    this.errorMsg = this.$tc('检测算法填写不完整，请完善后添加');
    return false;
  }

  @Emit('dataChange')
  emitLocalData() {
    return this.localData;
  }

  render() {
    return (
      <div class='partial-nodes-wrap'>
        <bk-form
          ref='formRef'
          {...{ props: { model: this.localData } }}
          rules={this.rules}
          label-width={126}
        >
          <bk-form-item
            label={this.$t('告警级别')}
            property='level'
            required
          >
            <bk-select
              ext-cls='level-select'
              ext-popover-cls='level-select-popover'
              clearable={false}
              behavior='simplicity'
              v-model={this.localData.level}
              prefix-icon={`icon-monitor ${this.levelList[this.localData.level - 1].icon}`}
              onChange={this.emitLocalData}
            >
              {this.levelList.map(level => (
                <bk-option
                  key={level.id}
                  disabled={level.disabled}
                  id={level.id}
                  name={level.name}
                  v-bk-tooltips={{
                    content: this.$t('已有相同算法,设置为{name}级别', { name: level.name }),
                    disabled: !level.disabled,
                    allowHTML: false
                  }}
                >
                  <i class={`icon-monitor ${level.icon}`}></i>
                  <span class='name'>{level.name}</span>
                </bk-option>
              ))}
            </bk-select>
          </bk-form-item>
          <bk-form-item
            label={this.$t('告警条件')}
            property='config'
            required
            error-display-type='normal'
          >
            <i18n path='满足以上条件的拨测节点数>={0}时触发告警'>
              <bk-input
                class='input-align-center inline-input number-handle-input'
                behavior='simplicity'
                readonly={this.readonly}
                style='width: 78px'
                v-model={this.localData.config.count}
                clearable={false}
                min={1}
                precision={0}
                type='number'
                onChange={this.emitLocalData}
              />
            </i18n>
          </bk-form-item>
        </bk-form>
      </div>
    );
  }
}
