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
import { type PropType, computed, defineComponent, reactive, ref, watch } from 'vue';

import { Button, Exception, Form, Input, Loading, Popover } from 'bkui-vue';
import { queryBkDataToken } from 'monitor-api/modules/apm_meta';
import { useI18n } from 'vue-i18n';

import { useDocumentLink } from '../../../hooks';

import type { ApplicationItem, ApplicationList, ServiceItem } from '../typings';

import './application-cascade.scss';

export default defineComponent({
  name: 'ApplicationCascade',
  props: {
    list: {
      type: Object as PropType<ApplicationList>,
      default: () => ({ normal: [], no_data: [] }),
    },
    value: {
      type: Object as PropType<string[]>,
      required: true,
    },
    loading: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['change'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const { handleGotoLink } = useDocumentLink();
    const token = ref('');
    const tokenLoading = ref(false);
    /** 筛选 */
    const searchKey = ref('');
    /** 应用列表 */
    const appList = computed<ApplicationList>(() => {
      const list = { normal: [], no_data: [] };
      list.normal = props.list.normal.filter(item => {
        if (item.app_name.includes(searchKey.value)) return true;
        if (item.services.some(service => service.name.includes(searchKey.value))) return true;
        return false;
      });
      list.no_data = props.list.no_data.filter(item => {
        return item.app_name.includes(searchKey.value);
      });
      return list;
    });
    // 是否搜索为空
    const isSearchEmpty = computed(() => {
      const { normal, no_data } = appList.value;
      const normalLen = (normal || []).length;
      const noDataLen = (no_data || []).length;
      return normalLen === 0 && noDataLen === 0 && !!searchKey.value;
    });

    /** 应用是否有数据 */
    const hasData = computed(() => {
      if (props.list.normal.find(item => item.app_name === selectValue.appName)) return true;
      return false;
    });

    /** 已选择的应用 */
    const appData = computed(() => {
      if (hasData.value) {
        return props.list.normal.find(item => item.app_name === selectValue.appName);
      }
      return props.list.no_data.find(item => item.app_name === selectValue.appName);
    });

    /** 服务列表 */
    const serviceList = computed(() => {
      if (!appData.value) return [];
      return appData.value.services;
    });

    const selectValue = reactive({
      /** 应用名称 */
      appName: null,
      /** 服务名称 */
      serviceName: null,
    });

    const inputText = ref('');

    watch(
      () => props.value,
      val => {
        selectValue.appName = val[0] || '';
        selectValue.serviceName = val[1] || '';
        if (!!selectValue.appName && !!selectValue.serviceName) {
          inputText.value = `${selectValue.appName} / ${selectValue.serviceName}`;
        }
      },
      {
        immediate: true,
      }
    );

    const showPopover = ref(false);
    function handlePopoverShowChange({ isShow }) {
      if (isShow) {
        selectValue.appName = props.value[0] || '';
        selectValue.serviceName = props.value[1] || '';
      }
      showPopover.value = isShow;
    }

    /**
     * 选择应用
     * @param val 选项值
     */
    function handleAppClick(val: ApplicationItem) {
      if (val.app_name === selectValue.appName) return;
      selectValue.appName = val.app_name;
      if (selectValue.appName === (props.value[0] || '')) {
        selectValue.serviceName = props.value[1] || '';
      } else {
        selectValue.serviceName = null;
      }
      token.value = '';
    }
    /**
     * 选择服务
     * @param val 选项值
     */
    function handleServiceClick(val: ServiceItem) {
      if (val.name === selectValue.serviceName) return;
      selectValue.serviceName = val.name;
      showPopover.value = false;
      inputText.value = `${selectValue.appName} / ${selectValue.serviceName}`;
      emit('change', [selectValue.appName, selectValue.serviceName]);
    }

    /** 查看token */
    async function handleViewToken() {
      tokenLoading.value = true;
      token.value = await queryBkDataToken(appData.value.application_id).catch(() => {});
      tokenLoading.value = false;
    }

    /** 查看应用  */
    function handleViewApp() {
      const hash = `#/apm/home?queryString=${appData.value.app_name}`;
      const url = location.href.replace(location.hash, hash);
      window.open(url, '_self');
    }

    /** 新增接入 */
    function jumpToApp() {
      const hash = '#/apm/home?is_enabled_profiling=false';
      const url = location.href.replace(location.hash, hash);
      window.open(url, '_self');
    }

    return {
      t,
      tokenLoading,
      token,
      searchKey,
      hasData,
      selectValue,
      appList,
      appData,
      serviceList,
      inputText,
      showPopover,
      handleAppClick,
      handleViewToken,
      handleServiceClick,
      handlePopoverShowChange,
      handleViewApp,
      jumpToApp,
      handleGotoLink,
      isSearchEmpty,
    };
  },
  render() {
    return (
      <div class='application-cascade-component'>
        <Popover
          arrow={false}
          is-show={this.showPopover}
          placement='bottom-start'
          theme='light application-cascade-popover'
          trigger='click'
          onAfterHidden={val => this.handlePopoverShowChange(val)}
          onAfterShow={val => this.handlePopoverShowChange(val)}
        >
          {{
            default: () => (
              <div class={['trigger-wrap', this.showPopover ? 'active' : '']}>
                <Input
                  modelValue={this.inputText}
                  placeholder={this.t('选择应用/服务')}
                  readonly
                >
                  {{ suffix: () => <span class='icon-monitor icon-arrow-down' /> }}
                </Input>
              </div>
            ),
            content: () => (
              <div class='application-cascade-popover-content'>
                {!this.loading ? (
                  <>
                    <div class='search-wrap'>
                      <i class='icon-monitor icon-mc-search search-icon' />
                      <Input
                        class='search-input'
                        v-model={this.searchKey}
                        placeholder={this.t('输入关键字')}
                      />
                    </div>
                    <div class='select-wrap'>
                      {this.isSearchEmpty ? (
                        <Exception
                          class='exception-wrap-item'
                          scene='part'
                          type='search-empty'
                        >
                          {this.t('暂无搜索结果')}
                        </Exception>
                      ) : (
                        <>
                          <div class='first panel'>
                            {/* <div class='group-title'>{this.t('有数据应用')}</div> */}
                            <div class='group-wrap'>
                              {this.appList.normal.map(item => (
                                <div
                                  key={item.application_id}
                                  class={{ 'group-item': true, active: item.app_name === this.selectValue.appName }}
                                  onClick={() => this.handleAppClick(item)}
                                >
                                  <i class='icon-monitor icon-mc-menu-apm' />
                                  <span
                                    class='name'
                                    v-overflow-tips={{
                                      text: `${item.app_name} (${item.app_alias})`,
                                      placement: 'right',
                                    }}
                                  >
                                    {item.app_name}
                                    <span class='desc'>({item.app_alias})</span>
                                  </span>

                                  <i class='icon-monitor icon-arrow-right' />
                                </div>
                              ))}
                            </div>
                            {/* <div class='group-title'>{this.t('无数据应用')}</div> */}
                            {this.appList.no_data.map((item, index) => (
                              <div
                                key={`${item.app_name}_${index}`}
                                class={{ 'group-item': true, active: item.app_name === this.selectValue.appName }}
                                onClick={() => this.handleAppClick(item)}
                              >
                                {/* <i class='icon-monitor icon-mc-menu-apm' /> */}
                                <span class='menu-apm-point' />
                                <span
                                  class='name'
                                  v-overflow-tips={{
                                    text: `${item.app_name} (${item.app_alias})`,
                                    placement: 'right',
                                  }}
                                >
                                  {item.app_name}
                                  <span class='desc'>({item.app_alias})</span>
                                </span>
                              </div>
                            ))}
                          </div>
                          {this.selectValue.appName ? (
                            <div class='second panel'>
                              {this.hasData ? (
                                <div class='has-data-wrap'>
                                  {this.serviceList.map((item, index) => (
                                    <div
                                      key={index}
                                      class={{
                                        'group-item': true,
                                        active: item.name === this.selectValue.serviceName,
                                      }}
                                      onClick={() => this.handleServiceClick(item)}
                                    >
                                      <i class='icon-monitor icon-mokuai' />
                                      <span class='name'>{item.name}</span>
                                    </div>
                                  ))}
                                </div>
                              ) : (
                                <div class='no-data-wrap'>
                                  <Loading
                                    loading={this.tokenLoading}
                                    mode='spin'
                                    theme='primary'
                                  >
                                    <Form labelWidth={100}>
                                      <Form.FormItem label={this.t('应用名')}>{this.appData.app_name}</Form.FormItem>
                                      <Form.FormItem label={this.t('应用别名')}>{this.appData.app_alias}</Form.FormItem>
                                      <Form.FormItem label={this.t('描述')}>{this.appData.description}</Form.FormItem>
                                      <Form.FormItem label='Token'>
                                        <span class='password'>{this.token || '●●●●●●●●●●'}</span>
                                        {!this.token && (
                                          <Button
                                            theme='primary'
                                            text
                                            onClick={this.handleViewToken}
                                          >
                                            {this.t('点击查看')}
                                          </Button>
                                        )}
                                      </Form.FormItem>
                                    </Form>
                                    <div
                                      class='btn'
                                      onClick={() => this.handleGotoLink('profiling_docs')}
                                    >
                                      <span class='link'>{this.t('Profile 接入指引')}</span>
                                      <i class='icon-monitor icon-fenxiang' />
                                    </div>
                                    <div
                                      class='btn'
                                      onClick={this.handleViewApp}
                                    >
                                      <span>{this.t('查看应用')}</span>
                                      <i class='icon-monitor icon-fenxiang' />
                                    </div>
                                  </Loading>
                                </div>
                              )}
                            </div>
                          ) : (
                            <div class='second panel no-select'>
                              <div class='no-select-text'>{this.t('请先在左侧选择应用')}</div>
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  </>
                ) : (
                  <div class='loading-wrap'>
                    <Loading
                      loading={true}
                      mode='spin'
                      size='small'
                      theme='primary'
                    >
                      <div class='loading-spin' />
                    </Loading>
                    <div class='loading-text'>{this.t('应用加载中，请耐心等候…')}</div>
                  </div>
                )}
                <div class='footer-wrap'>
                  <div
                    class='jump-btn'
                    onClick={this.jumpToApp}
                  >
                    <i class='icon-monitor icon-jia' />
                    <span>{this.t('新增接入')}</span>
                  </div>
                </div>
              </div>
            ),
          }}
        </Popover>
      </div>
    );
  },
});
