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
import { type PropType, defineComponent, reactive, ref, watch } from 'vue';

import { PrimaryTable } from '@blueking/tdesign-ui';
import { Button, Popover, Radio } from 'bkui-vue';
import { random } from 'monitor-common/utils';
import { useI18n } from 'vue-i18n';

import CommonTip from '../../components/common-tip/common-tip';
import AlarmShieldIpv6 from './components/alarm-shield-ipv6';
import FormItem from './components/form-item';
import { Ipv6FieldMap } from './typing';

import './alarm-shield-config-scope.scss';

export const scopeData = () => {
  return {
    key: random(8),
    biz: {
      list: [],
      value: '',
    },
    tableData: [],
    labelMap: {
      ip: window.i18n.t('主机'),
      instance: window.i18n.t('服务实例'),
      node: window.i18n.t('节点名称'),
      dynamic_group: window.i18n.t('动态分组'),
      biz: window.i18n.t('业务'),
    },
    shieldDesc: '',
    bkGroup: {
      list: [
        { name: window.i18n.t('button-服务实例'), id: 'instance' },
        { name: window.i18n.t('button-主机'), id: 'ip' },
        { name: window.i18n.t('button-拓扑节点'), id: 'node' },
        { name: window.i18n.t('动态分组'), id: 'node' },
        { name: window.i18n.t('button-业务'), id: 'biz' },
      ],
      value: '',
    },
    targetError: false,
    showIpv6Dialog: false,
    ipv6Value: {},
    originIpv6Value: {},
    initialized: true,
  };
};

export default defineComponent({
  name: 'AlarmShieldConfigScope',
  props: {
    show: {
      type: Boolean,
      default: false,
    },
    isEdit: {
      type: Boolean,
      default: false,
    },
    value: {
      type: Object,
      default: () => scopeData(),
    },
    filterTypes: {
      type: Array,
      default: () => [],
    },
    require: {
      type: Boolean,
      default: true,
    },
    onChange: {
      type: Function as PropType<(v: any) => void>,
      default: () => {},
    },
  },
  setup(props) {
    const { t } = useI18n();
    const radioRef = ref<InstanceType<typeof Radio>>(null);
    const tipsMap = {
      instance: t('服务实例屏蔽: 屏蔽告警中包含该实例的通知'),
      ip: t('主机屏蔽: 屏蔽告警中包含该IP通知,包含对应的实例'),
      node: t('节点屏蔽: 屏蔽告警中包含该节点下的所有IP和实例的通知'),
      dynamic_group: t('动态分组屏蔽: 屏蔽告警中包含该动态分组下的所有IP和实例的通知'),
      biz: t('本空间屏蔽: 屏蔽告警中包含该空间的所有通知'),
    };
    const scopeList = [
      {
        id: 'instance',
        name: t('button-服务实例'),
      },
      {
        id: 'ip',
        name: t('物理主机'),
      },
      {
        id: 'node',
        name: t('CMDB拓扑'),
      },
      {
        id: 'dynamic_group',
        name: t('动态分组'),
      },
      // {
      //   id: 'k8s',
      //   name: t('容器拓扑')
      // },
      {
        id: 'biz',
        name: t('本空间'),
      },
    ];

    const popRefs = reactive({
      instance: {
        show: false,
      },
      ip: {
        show: false,
      },
      node: {
        show: false,
      },
      dynamic_group: {
        show: false,
      },
      biz: {
        show: false,
      },
    });
    // const scopeType = ref('');
    const scopeState = reactive(scopeData());
    const isBiz = ref(false);
    const isClone = ref(false);

    const errMsg = reactive({
      target: '',
    });

    watch(
      () => props.value.key,
      key => {
        if (key === scopeState.key) {
          return;
        }
        Object.keys(props.value).forEach(key => {
          scopeState[key] = props.value[key];
        });
      },
      {
        immediate: true,
      }
    );

    function handleValueChange({ value }) {
      clearErrMsg();
      scopeState.ipv6Value = { ...scopeState.ipv6Value, ...value };
      handleChange();
    }
    function handleIpv6DialogChange() {
      scopeState.targetError = false;
      scopeState.showIpv6Dialog = false;
    }
    function handleChangeScope(id) {
      if (hasIpv6Value() && scopeState.bkGroup.value !== id) {
        popRefs[id].show = true;
      } else {
        clearErrMsg();
        isBiz.value = false;
        if (radioRef.value) {
          radioRef.value.isChecked = false;
        }
        scopeState.bkGroup.value = id;
        scopeState.showIpv6Dialog = true;
      }
      handleChange();
    }

    function handleChange() {
      props.onChange(scopeState);
    }

    /**
     * @description 清除校验
     */
    function clearErrMsg() {
      Object.keys(errMsg).forEach(key => {
        errMsg[key] = '';
      });
    }
    /**
     * @description 校验
     */
    function validate() {
      const data = scopeState.ipv6Value?.[Ipv6FieldMap[scopeState.bkGroup.value]];
      clearErrMsg();
      if (!data?.length && !isBiz.value) {
        errMsg.target = t('选择屏蔽目标');
      }
      return !Object.keys(errMsg).some(key => !!errMsg[key]);
    }
    /**
     * @description 隐藏弹窗
     * @param id
     */
    function handleClickoutside(id) {
      popRefs[id].show = false;
    }
    /**
     * @description 选中业务选项
     * @param id
     */
    function handleSelectItem(id) {
      if (hasIpv6Value()) {
        popRefs[id].show = true;
        setTimeout(() => {
          isBiz.value = false;
          radioRef.value.isChecked = false;
        }, 50);
      } else {
        isBiz.value = true;
        clearErrMsg();
        scopeState.bkGroup.value = 'biz';
        scopeState.showIpv6Dialog = false;
        handleChange();
      }
    }
    /**
     * @description 是否包含已选择的屏蔽范围
     * @returns
     */
    function hasIpv6Value() {
      return Object.keys(scopeState.ipv6Value).some(key => !!scopeState.ipv6Value[key]?.length);
    }
    /**
     * @description 重置屏蔽范围
     */
    function ipv6Init() {
      Object.keys(scopeState.ipv6Value).forEach(key => {
        scopeState.ipv6Value[key] = [];
      });
    }
    /**
     * @description 点击提示弹窗的取消
     */
    function handleCancelPop() {
      Object.keys(popRefs).forEach(key => {
        popRefs[key].show = false;
      });
    }

    /**
     * @description 点击提示弹窗的确定
     * @param id
     */
    function handleConfirmPop(id) {
      popRefs[id].show = false;
      if (id === 'biz') {
        isBiz.value = true;
        clearErrMsg();
        scopeState.bkGroup.value = 'biz';
        scopeState.showIpv6Dialog = false;
        ipv6Init();
      } else {
        ipv6Init();
        isBiz.value = false;
        if (radioRef.value) {
          radioRef.value.isChecked = false;
        }
        scopeState.bkGroup.value = id;
        scopeState.showIpv6Dialog = true;
      }
      handleChange();
    }

    return {
      scopeState,
      validate,
      isBiz,
      t,
      errMsg,
      scopeList,
      popRefs,
      tipsMap,
      isClone,
      handleClickoutside,
      handleSelectItem,
      radioRef,
      handleChangeScope,
      handleConfirmPop,
      handleCancelPop,
      handleValueChange,
      handleIpv6DialogChange,
    };
  },
  render() {
    return (
      <div class={['alarm-shield-config-scope-component', { show: this.show }]}>
        <FormItem
          class='mt24 max-w1000'
          errMsg={this.errMsg.target}
          label={this.t('屏蔽范围')}
          require={this.require}
        >
          <div class='mt8'>
            {!this.isEdit && (
              <div class='scope-list'>
                {this.scopeList
                  .filter(item => (this.filterTypes.length ? this.filterTypes.includes(item.id) : true))
                  .map(item => {
                    return (
                      <Popover
                        key={item.id}
                        width={216}
                        extCls='alarm-shield-config-scope-pop'
                        arrow={true}
                        isShow={this.popRefs[item.id].show}
                        placement='bottom-start'
                        theme='light'
                        trigger='manual'
                        onClickoutside={() => this.handleClickoutside(item.id)}
                      >
                        {{
                          default: () => {
                            if (item.id === 'biz') {
                              return (
                                <span
                                  class='scope-list-item'
                                  onClick={() => this.handleSelectItem(item.id)}
                                >
                                  <Radio
                                    ref='radioRef'
                                    label={true}
                                    modelValue={this.isBiz}
                                  >
                                    {item.name}
                                  </Radio>
                                </span>
                              );
                            }

                            return (
                              <span
                                key={item.id}
                                class='scope-list-item'
                                onClick={() => this.handleChangeScope(item.id)}
                              >
                                <span class='icon-monitor icon-jia' />
                                <span class='item-text'>{item.name}</span>
                              </span>
                            );
                          },
                          content: () => (
                            <div class='scope-pop-content'>
                              <span class='msg'>{this.t('添加新的屏蔽范围将会覆盖之前的屏蔽内容，确定覆盖？')}</span>
                              <div class='operate'>
                                <Button
                                  class='mr-8'
                                  text={true}
                                  theme='primary'
                                  onClick={() => this.handleConfirmPop(item.id)}
                                >
                                  {this.t('确定')}
                                </Button>
                                <Button
                                  text={true}
                                  theme='primary'
                                  onClick={this.handleCancelPop}
                                >
                                  {this.t('取消')}
                                </Button>
                              </div>
                            </div>
                          ),
                        }}
                      </Popover>
                    );
                  })}
              </div>
            )}
            {!this.isEdit && !!this.scopeState.bkGroup.value && (
              <CommonTip
                class='mt8 min-w940'
                content={this.tipsMap[this.scopeState.bkGroup.value] || ''}
              />
            )}
            {this.scopeState.bkGroup.value !== 'biz' && !this.isEdit && !!this.scopeState.initialized && (
              <AlarmShieldIpv6
                checkedValue={this.scopeState.ipv6Value}
                originCheckedValue={this.scopeState.originIpv6Value}
                shieldDimension={this.scopeState.bkGroup.value}
                showDialog={this.scopeState.showIpv6Dialog}
                showViewDiff={this.isClone}
                onChange={this.handleValueChange}
                onCloseDialog={this.handleIpv6DialogChange}
              />
            )}
            {!!this.isEdit &&
              (this.scopeState.bkGroup.value !== 'biz' ? (
                <div class='w-836'>
                  <PrimaryTable
                    columns={[
                      {
                        colKey: 'name',
                        title: this.scopeState?.labelMap?.[this.scopeState?.bkGroup?.value] || '',
                        ellipsis: {
                          popperOptions: {
                            strategy: 'fixed',
                          },
                        },
                      },
                    ]}
                    bordered={true}
                    data={this.scopeState.tableData}
                    maxHeight={450}
                    resizable={true}
                    rowKey='name'
                  />
                </div>
              ) : (
                <span>{this.t('业务')}</span>
              ))}
          </div>
        </FormItem>
      </div>
    );
  },
});
