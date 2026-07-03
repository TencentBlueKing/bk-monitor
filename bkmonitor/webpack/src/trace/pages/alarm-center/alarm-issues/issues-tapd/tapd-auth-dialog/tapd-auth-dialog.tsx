/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 THL A29 Limited, a Tencent company.  All rights reserved.
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

import { type PropType, computed, defineComponent, shallowRef } from 'vue';

import { Alert, Button, Dialog, Input } from 'bkui-vue';
import loadingImg from 'monitor-ui/chart-plugins/icons/spinner.svg';
import { useI18n } from 'vue-i18n';

import EmptyStatus, { type EmptyStatusOperationType } from '@/components/empty-status/empty-status';

import type { TapdWorkspaceItem } from '../typing';

import './tapd-auth-dialog.scss';

export default defineComponent({
  name: 'TapdAuthDialog',
  props: {
    show: {
      type: Boolean,
      required: true,
    },
    loading: {
      type: Boolean,
      default: false,
    },
    authUrl: {
      type: String,
      default: '',
    },
    isAuth: {
      type: Boolean,
      default: true,
    },
    revokeAuthLoading: {
      type: Boolean,
      default: false,
    },
    workspaceList: {
      type: Array as PropType<TapdWorkspaceItem[]>,
      default: () => [],
    },
  },
  emits: ['update:show', 'select', 'revokeAuth'],
  setup(props, { emit }) {
    const { t } = useI18n();

    const searchValue = shallowRef('');

    const filterList = computed(() => {
      return props.workspaceList.filter(item => item.workspace_name.includes(searchValue.value));
    });

    const handleShowChange = (isShow: boolean) => {
      emit('update:show', isShow);
    };

    const handleEmptyOperation = (type: EmptyStatusOperationType) => {
      if (type === 'clear-filter') {
        searchValue.value = '';
      }
    };

    const handleWorkspaceClick = (item: TapdWorkspaceItem) => {
      if (item.loading) return;
      console.log('click');
      emit('select', item);
    };

    const renderWorkspaceList = () => {
      if (props.loading) {
        return (
          <div class='workspace-list'>
            {new Array(4).fill(0).map((_, index) => (
              <div
                key={index}
                class='workspace-item skeleton-element'
              />
            ))}
          </div>
        );
      }

      if (!props.authUrl && !props.isAuth) {
        return <span>{t('您没有权限访问该业务的 TAPD 关联功能')}</span>;
      }

      return (
        <div class='tapd-relation-workspace-wrapper'>
          <Alert
            class='tapd-relation-workspace-alert'
            theme='info'
            title={t('请选择有权限的项目，完成蓝鲸监控关联项目的应用授权。')}
          />
          <div class='search-wrapper'>
            <Input
              v-model={searchValue.value}
              placeholder={t('搜索 项目')}
              type='search'
              clearable
            />
          </div>
          <div class='workspace-list'>
            {filterList.value.length ? (
              filterList.value.map(item => (
                <div
                  key={item.workspace_id}
                  class='workspace-item'
                  onClick={() => {
                    handleWorkspaceClick(item);
                  }}
                >
                  <span class='workspace-name'>{item.workspace_name}</span>
                  {item.loading ? (
                    <img
                      class='workspace-item-loading'
                      alt=''
                      src={loadingImg}
                    />
                  ) : (
                    [
                      <Button
                        key='tag'
                        class={['workspace-btn', { bound: item.is_bound === 'bound' }]}
                        theme={item.is_bound === 'bound' ? 'success' : 'primary'}
                        outline
                      >
                        {item.is_bound === 'bound' ? t('已关联') : t('去关联')}
                      </Button>,
                      item.is_bound === 'bound' && (
                        <div
                          key='unlock-btn'
                          class='revoke-relation'
                        >
                          <i class='icon-monitor icon-Unlock' />
                          <span>{t('取消关联')}</span>
                        </div>
                      ),
                    ]
                  )}
                </div>
              ))
            ) : (
              <EmptyStatus
                textMap={{ empty: t('暂无项目') }}
                type={searchValue.value ? 'search-empty' : 'empty'}
                onOperation={handleEmptyOperation}
              />
            )}
          </div>
          <Button
            class='dialog-footer-btn'
            loading={props.revokeAuthLoading}
            size='large'
            onClick={handleRevokeAuth}
          >
            {t('取消授权')}
          </Button>
        </div>
      );
    };

    const handleRevokeAuth = () => {
      emit('revokeAuth');
    };

    return {
      searchValue,
      handleShowChange,
      renderWorkspaceList,
      handleRevokeAuth,
    };
  },
  render() {
    return (
      <Dialog
        width={640}
        class='tapd-auth-dialog'
        v-slots={{
          header: () => (
            <div class='tapd-auth-dialog-header'>
              <div class='dialog-title'>{this.$t('关联项目')}</div>
              <div class='dialog-desc'>{this.$t('蓝鲸监控关联项目')}</div>
            </div>
          ),
          default: () => <div class='tapd-auth-dialog-content'>{this.renderWorkspaceList()}</div>,
          footer: () => null,
        }}
        isShow={this.show}
        onUpdate:isShow={this.handleShowChange}
      />
    );
  },
});
