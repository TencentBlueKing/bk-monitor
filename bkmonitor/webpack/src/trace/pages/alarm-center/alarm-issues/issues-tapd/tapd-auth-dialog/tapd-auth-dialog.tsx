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

      if (filterList.value.length === 0)
        return (
          <div class='workspace-list'>
            <EmptyStatus
              textMap={{ empty: t('暂无项目') }}
              type={searchValue.value ? 'search-empty' : 'empty'}
              onOperation={handleEmptyOperation}
            />
          </div>
        );

      return (
        <div class='workspace-list'>
          {filterList.value.map(item => (
            <div
              key={item.workspace_id}
              class='workspace-item'
              onClick={() => {
                handleWorkspaceClick(item);
              }}
            >
              <span class='workspace-name'>{item.workspace_name}</span>
              <Button
                class={['workspace-btn', { bound: item.is_bound === 'bound' }]}
                theme={item.is_bound === 'bound' ? 'success' : 'primary'}
                outline
              >
                {item.is_bound === 'bound' ? t('已关联') : t('去关联')}
              </Button>
              {item.is_bound === 'bound' && (
                <div class='revoke-relation'>
                  <span>{t('取消关联')}</span>
                </div>
              )}
            </div>
          ))}
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
          default: () => (
            <div class='tapd-auth-dialog-content'>
              <Alert
                theme='info'
                title={this.$t('请选择有权限的项目，完成蓝鲸监控关联项目的应用授权。')}
              />
              <div class='search-wrapper'>
                <Input
                  v-model={this.searchValue}
                  placeholder={this.$t('搜索 项目')}
                  clearable
                />
              </div>
              {this.renderWorkspaceList()}
              {!this.loading && (
                <Button
                  class='dialog-footer-btn'
                  size='large'
                  onClick={this.handleRevokeAuth}
                >
                  {this.$t('取消授权')}
                </Button>
              )}
            </div>
          ),
          footer: () => null,
        }}
        isShow={this.show}
        onUpdate:isShow={this.handleShowChange}
      />
    );
  },
});
