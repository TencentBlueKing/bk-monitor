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
import { Component, Emit, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import AlarmGroup from '../../strategy-config/strategy-config-set-new/components/alarm-group';
import VerifyItem from '../../strategy-config/strategy-config-set-new/components/verify-item';
import AlarmGroupSelect from '../components/alarm-group-select';
import { EColumn, ICondtionItem, LEVELLIST } from '../typing';
import { TGroupKeys, TValueMap } from '../typing/condition';

import ConditionFindReplace, { IListItem } from './condition-find-replace';

import './alarm-batch-edit.scss';

type FiledType = EColumn | 'priority' | 'name' | 'notice' | 'alertSeveritySingle';

const configFiled = {
  name: window.i18n.tc('修改组名'),
  priority: window.i18n.tc('修改优先级'),
  userGroups: window.i18n.tc('修改告警组'),
  conditions: window.i18n.tc('查找规则'),
  alertSeverity: window.i18n.tc('批量调整等级'),
  alertSeveritySingle: window.i18n.tc('调整等级'),
  additionalTags: window.i18n.tc('批量追加标签'),
  actionId: window.i18n.tc('修改流程套餐'),
  upgradeConfig: window.i18n.tc('批量设置通知升级'),
  notice: window.i18n.tc('是否开启通知'),
  isEnabled: window.i18n.tc('批量修改状态')
};

interface IEvent {
  onSubmit?: any;
  onFindReplace?: (v: { findData: ICondtionItem[]; replaceData: ICondtionItem[] }) => void;
}

interface IAlarmBatchEditProps {
  filed: FiledType;
  alarmGroupList?: any[];
  processPackage?: any[];
  dataSource: any;
  priorityList: number[];
  alarmDisabledList?: number[];
  conditionProps?: {
    keyList?: IListItem[];
    valueMap: TValueMap;
    groupKeys: TGroupKeys;
    groupKey: string[];
  };
  isListPage?: boolean;
  canDebug?: boolean;
  showAlarmGroupDetail?: (id: number) => void;
  alarmGroupListLoading?: boolean;
  processLoading?: boolean;
  refreshAlarm?: () => void;
  refreshProcess?: () => void;
  addProcess?: () => void;
  close: () => void;
}

@Component({
  name: 'AlarmBatchEdit'
})
export default class AlarmBatchEdit extends tsc<IAlarmBatchEditProps, IEvent> {
  @Prop({ default: 'level', type: String }) filed: FiledType;
  @Prop({ default: '', type: [String, Number, Object, Array] }) dataSource: any;
  @Prop({ default: () => [], type: Array }) alarmGroupList: any;
  @Prop({ default: () => [], type: Array }) processPackage: any;
  @Prop({ default: () => [], type: Array }) priorityList: number[];
  @Prop({ default: () => [], type: Array }) alarmDisabledList: number[];
  @Prop({ default: () => {}, type: Function }) close: () => void;
  @Prop({ default: () => {}, type: Function }) showAlarmGroupDetail: (id: number) => void;
  @Prop({ default: () => {}, type: Function }) refreshAlarm: () => void;
  /* 刷新套餐包 */
  @Prop({ default: () => {}, type: Function }) refreshProcess: () => void;
  /* 新增处理套餐包*/
  @Prop({ default: () => {}, type: Function }) addProcess?: () => void;
  /* 获取告警组刷新loading */
  @Prop({ default: false, type: Boolean }) alarmGroupListLoading: boolean;
  /* 获取告警组刷新loading */
  @Prop({ default: false, type: Boolean }) processLoading: boolean;
  @Prop({ default: () => null, type: Object }) conditionProps: IAlarmBatchEditProps['conditionProps'];
  /* 特殊处理： 告警分派页表页暂不需要调试并生效按钮 */
  @Prop({ default: false, type: Boolean }) isListPage: boolean;
  @Prop({ default: true, type: Boolean }) canDebug: boolean;

  @Ref('alarmGroupSelect') readonly alarmGroupSelectRef: any;
  @Ref('conditionFindReplace') readonly conditionFindReplaceRef: ConditionFindReplace;

  data = {};
  popoverInstance = null;
  errorMsg = {
    name: '',
    userGroups: '',
    upgradeInterval: '',
    addTag: '',
    priorityErrorMsg: ''
  };

  @Emit('submit')
  handleFormChange(value) {
    return value;
  }

  @Watch('filed')
  handleFieldChange() {
    let defaultValue = null;
    if (['notice', 'upgradeConfig'].includes(this.filed)) {
      defaultValue = {
        noticeIsEnabled: true,
        userGroups: [],
        upgradeInterval: 30,
        isEnabled: false
      };
    } else if (this.filed === 'userGroups') {
      defaultValue = [];
    } else if (this.filed === 'additionalTags') {
      defaultValue = [];
    } else if (['alertSeverity', 'alertSeveritySingle', 'priority'].includes(this.filed)) {
      defaultValue = 0;
    } else if (this.filed === 'isEnabled') {
      defaultValue = true;
    }
    this.$set(this.data, this.filed, this.dataSource ? this.dataSource : defaultValue);
  }

  handleSubmit() {
    if (['name'].includes(this.filed)) {
      if (!this.data[this.filed]) {
        this.errorMsg.name = window.i18n.tc('输入规则组名');
        return;
      }
    }
    if (['conditions'].includes(this.filed)) {
      this.handleFindReplace();
      return;
    }
    if (['notice', 'upgradeConfig'].includes(this.filed)) {
      if (this.data[this.filed].isEnabled) {
        if (!this.data[this.filed].upgradeInterval) {
          this.errorMsg.upgradeInterval = window.i18n.tc('选择时间');
          return;
        }

        if (!/^\+?[1-9][0-9]*$/.test(this.data[this.filed].upgradeInterval)) {
          this.errorMsg.upgradeInterval = window.i18n.t('输入正整数') as string;
          return;
        }
        if (!this.data[this.filed].userGroups.length) {
          this.errorMsg.userGroups = window.i18n.tc('选择告警组');
          return;
        }
      }
    }
    /** 优先级校验 */
    if (['priority'].includes(this.filed)) {
      const list = this.priorityList.filter(item => item !== this.dataSource);
      if (list.includes(this.data[this.filed])) return;
    }

    if (['additionalTags'].includes(this.filed)) {
      setTimeout(() => {
        const result = this.handleAdditionalTagsChange(this.data[this.filed]);
        if (!result) return;
        this.handleFormChange(this.data[this.filed]);
        this.handleClearErrorMsg();
        this.close();
      }, 100);
      return;
    }
    this.handleFormChange(this.data[this.filed]);
    this.handleClearErrorMsg();
    this.close();
  }

  /**
   *  优先级步长调整
   * @param value
   * @returns
   */
  handlePriorityChange(value: string | number) {
    if (typeof value === 'string') {
      if (!value) return;

      if (isNaN(Number(value))) {
        this.data[this.filed] = 1;
        (this.$refs.priorityInput as any).curValue = 1;
      } else {
        if (Number(value) >= 10000) {
          this.data[this.filed] = 10000;
          return;
        }
        if (Number(value) === 0) {
          this.data[this.filed] = 1;
          return;
        }
        if (parseFloat(value) === parseInt(value)) {
          this.data[this.filed] = Number(value);
        } else {
          (this.$refs.priorityInput as any).curValue = Math.round(Number(value));
          this.data[this.filed] = Math.round(Number(value));
        }
      }
    } else {
      if (isNaN(value)) {
        this.data[this.filed] = 1;
        (this.$refs.priorityInput as any).curValue = 1;
      } else {
        this.data[this.filed] = value;
      }
    }
    // 不包含它本身的优先级
    const list = this.priorityList.filter(item => item !== this.dataSource);
    if (list.includes(this.data[this.filed])) {
      this.errorMsg.priorityErrorMsg = window.i18n.t('注意: 优先级冲突') as string;
    } else {
      this.errorMsg.priorityErrorMsg = '';
    }
  }

  /**
   *
   * @param value 附加标签
   * @returns
   * @description 附加标签校验
   */
  handleAdditionalTagsChange(value: string[]) {
    // 兼容key:value 和key=value两种模式
    let result = true;
    let errorIndex = null;
    result = value.every((item, index) => {
      // 开头和结尾不能是:或=, 中间必须含有一个:或=
      const reg = /^[^:=]+[:=][^:=]+$/;
      const isTargetTag = reg.test(item);
      if (!isTargetTag) errorIndex = index;
      return isTargetTag;
    });
    const validateErrorTag = (msg: string) => {
      this.errorMsg.addTag = window.i18n.tc(msg);
      this.$nextTick(() => {
        const tagList = (this.$refs.additionalTags as any).$el.getElementsByClassName('key-node');
        tagList[errorIndex].style = 'border: 1px solid red;';
        (this.$refs.additionalTags as any).$el.getElementsByTagName('input')[0].disabled = true;
      });
    };
    if (!result) {
      validateErrorTag('标签格式不正确,格式为key:value 或 key=value');
      return result;
    }

    const keyList = value.map(item => {
      if (item.indexOf('=') > -1) {
        return item.split('=')[0];
      }
      if (item.indexOf(':') > -1) {
        return item.split(':')[0];
      }
      return item;
    });
    const setArr = [...new Set(keyList)];

    if (keyList.length !== setArr.length) {
      result = false;
      errorIndex = keyList.length - 1;
      validateErrorTag('注意: 名字冲突');
    } else {
      this.errorMsg.addTag = '';
      (this.$refs.additionalTags as any).$el.getElementsByTagName('input')[0].disabled = false;
    }

    return result;
  }

  handleVerifyInterval(value: string) {
    if (/^\+?[1-9][0-9]*$/.test(value)) {
      this.errorMsg.upgradeInterval = '';
    } else {
      this.errorMsg.upgradeInterval = window.i18n.t('输入正整数') as string;
    }
  }

  /* 查找替换 */
  @Emit('findReplace')
  handleFindReplace() {
    return {
      findData: this.conditionFindReplaceRef.findData,
      replaceData: this.conditionFindReplaceRef.replaceData
    };
  }

  /** 清楚校验错误 */
  handleClearErrorMsg() {
    this.errorMsg = {
      name: '',
      userGroups: '',
      upgradeInterval: '',
      addTag: '',
      priorityErrorMsg: ''
    };
  }

  /**
   * 字段表单
   * @param filed
   * @returns
   */
  getFieldForm(filed: FiledType) {
    switch (filed) {
      case 'name':
        return (
          <VerifyItem errorMsg={this.errorMsg.name}>
            <bk-input
              v-model={this.data[this.filed]}
              onChange={() => (this.errorMsg.name = '')}
            />
          </VerifyItem>
        );
      case 'priority':
        return (
          <div>
            <bk-input
              ref='priorityInput'
              type='number'
              max={10000}
              min={1}
              onInput={this.handlePriorityChange}
              value={this.data[this.filed]}
              size='small'
            />
            <span style={{ color: this.errorMsg.priorityErrorMsg ? '#ea3636' : '#979BA5' }}>
              {this.errorMsg.priorityErrorMsg
                ? this.errorMsg.priorityErrorMsg
                : this.$t('数值越高优先级越高,最大值为10000')}
            </span>
          </div>
        );
      case 'userGroups':
        return (
          <AlarmGroupSelect
            value={this.data[this.filed]}
            loading={this.alarmGroupListLoading}
            onChange={value => (this.data[this.filed] = value)}
            options={this.alarmGroupList}
            onTagclick={this.showAlarmGroupDetail}
            onRefresh={this.refreshAlarm}
          />
        );

      case 'notice':
      case 'upgradeConfig':
        return (
          <div class='upgrade-config-edit'>
            <bk-checkbox
              v-model={this.data[this.filed].isEnabled}
              disabled={!this.data[this.filed].noticeIsEnabled}
              onChange={() => {
                this.errorMsg.upgradeInterval = '';
                this.errorMsg.userGroups = '';
              }}
            >
              <span class='upgrade-label'>{this.$t('通知升级')} : </span>
            </bk-checkbox>
            <div class='upgrade-form'>
              <VerifyItem errorMsg={this.errorMsg.upgradeInterval}>
                <i18n
                  tag='div'
                  class='text'
                  path='当告警持续时长每超过{0}分种，将逐个按告警组升级通知'
                >
                  <bk-select
                    behavior='simplicity'
                    v-model={this.data[this.filed].upgradeInterval}
                    onChange={value => this.handleVerifyInterval(value)}
                    width={76}
                    disabled={!this.data[this.filed].isEnabled || !this.data[this.filed].noticeIsEnabled}
                    placeholder={this.$t('输入')}
                    zIndex={99999}
                    allow-create={this.data[this.filed].isEnabled && this.data[this.filed].noticeIsEnabled}
                    allow-enter
                    class='notice-select'
                  >
                    <bk-option
                      id={1}
                      name={1}
                    />
                    <bk-option
                      id={5}
                      name={5}
                    />
                    <bk-option
                      id={10}
                      name={10}
                    />
                    <bk-option
                      id={30}
                      name={30}
                    />
                  </bk-select>
                </i18n>
              </VerifyItem>
              <div class='user-group-add'>
                <VerifyItem errorMsg={this.errorMsg.userGroups}>
                  <AlarmGroup
                    v-model={this.data[this.filed].userGroups}
                    onChange={() => {
                      this.errorMsg.userGroups = '';
                    }}
                    isRefresh={true}
                    loading={this.alarmGroupListLoading}
                    onRefresh={this.refreshAlarm}
                    disabled={!this.data[this.filed].isEnabled || !this.data[this.filed].noticeIsEnabled}
                    tagClick={this.showAlarmGroupDetail}
                    disabledList={this.alarmDisabledList}
                    list={this.alarmGroupList}
                    isOpenNewPage={true}
                  />
                </VerifyItem>
              </div>
            </div>
          </div>
        );
      case 'actionId':
        return (
          <bk-select
            v-model={this.data[this.filed]}
            ext-popover-cls={'alarm-dispatch-alarm-group-select-component-pop'}
            zIndex={99999}
          >
            {this.processPackage.map(option => (
              <bk-option
                key={option.id}
                id={option.id}
                name={option.name}
              />
            ))}
            <div
              slot='extension'
              class='extension-wrap'
            >
              <div
                class='add-wrap'
                onClick={this.addProcess}
              >
                <span class='icon-monitor icon-jia'></span>
                <span>{this.$t('创建流程')}</span>
              </div>
              <div
                class='loading-wrap'
                onClick={this.refreshProcess}
              >
                {this.processLoading ? (
                  /* eslint-disable-next-line @typescript-eslint/no-require-imports */
                  <img
                    alt=''
                    src={require('../../../static/images/svg/spinner.svg')}
                    class='status-loading'
                  ></img>
                ) : (
                  <span class='icon-monitor icon-mc-retry'></span>
                )}
              </div>
            </div>
          </bk-select>
        );

      case 'conditions':
        return (
          !!this.conditionProps && (
            <ConditionFindReplace
              ref='conditionFindReplace'
              keyList={this.conditionProps.keyList}
              valueMap={this.conditionProps.valueMap}
              groupKey={this.conditionProps.groupKey}
              groupKeys={this.conditionProps.groupKeys}
            ></ConditionFindReplace>
          )
        );

      case 'additionalTags':
        return (
          <VerifyItem errorMsg={this.errorMsg.addTag}>
            <bk-tag-input
              ref='additionalTags'
              class='mb10'
              v-model={this.data[this.filed]}
              clearable={false}
              allow-auto-match={true}
              tooltip-key='name'
              onChange={this.handleAdditionalTagsChange}
              placeholder={this.$t('填写标签，格式key:value')}
              allow-create={true}
              has-delete-icon={true}
            ></bk-tag-input>
          </VerifyItem>
        );

      case 'alertSeverity':
      case 'alertSeveritySingle':
        return (
          <bk-radio-group
            class='level-radio-group'
            v-model={this.data[this.filed]}
          >
            {LEVELLIST.map(item => (
              <bk-radio value={item.value}>
                {item.icon && (
                  <i
                    class={`${item.icon} icon-level`}
                    style={{ color: item.color }}
                  />
                )}
                {item.name}
              </bk-radio>
            ))}
          </bk-radio-group>
        );
      case 'isEnabled':
        return (
          <bk-switcher
            v-model={this.data[this.filed]}
            theme='primary'
          />
        );
      default:
        return null;
    }
  }

  render() {
    return (
      <div class='alarm-batch-edit-container'>
        {!['conditions'].includes(this.filed) && (
          <div class='alarm-batch-edit-header'>
            {configFiled[this.filed]}
            {['upgradeConfig', 'notice'].includes(this.filed) && (
              <bk-switcher
                theme='primary'
                class='notice-switcher'
                onChange={() => {
                  this.errorMsg.upgradeInterval = '';
                  this.errorMsg.userGroups = '';
                }}
                v-model={this.data[this.filed].noticeIsEnabled}
              />
            )}
          </div>
        )}
        <div class='alarm-batch-edit-content'>{this.filed && this.getFieldForm(this.filed)}</div>
        <div class='alarm-batch-edit-footer'>
          <bk-button
            theme='primary'
            disabled={['priority'].includes(this.filed) && !this.isListPage ? !this.canDebug : false}
            onClick={this.handleSubmit}
          >
            {['priority'].includes(this.filed) && !this.isListPage ? this.$t('调试并生效') : this.$t('确认')}
          </bk-button>
          <bk-button
            onClick={() => {
              this.close();
              this.handleClearErrorMsg();
            }}
          >
            {this.$t('取消')}
          </bk-button>
        </div>
      </div>
    );
  }
}
