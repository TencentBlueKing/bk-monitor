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

import { type PropType, computed, defineComponent, nextTick, shallowRef, useTemplateRef } from 'vue';

import { Button, Input, Loading, Popover } from 'bkui-vue';
import { EditLine } from 'bkui-vue/lib/icon';
import { renameIssue } from 'monitor-api/modules/issue';
import { useI18n } from 'vue-i18n';

import TemporaryShareNew from '../../../../../components/temporary-share/temporary-share-new';
import { ISSUES_REGRESSION_MAP } from '../../constant';

import type { IssueDetail } from '../../typing';

import './issues-slider-header.scss';

export default defineComponent({
  name: 'IssuesSliderHeader',
  props: {
    detail: {
      type: Object as PropType<IssueDetail>,
      default: () => ({}),
    },
    isFullscreen: {
      type: Boolean,
      default: false,
    },
    showStepBtn: {
      type: Boolean,
      default: true,
    },
    showFullScreenBtn: {
      type: Boolean,
      default: true,
    },
    loading: {
      type: Boolean,
      default: false,
    },
  },
  emits: {
    toggleFullscreen: val => typeof val === 'boolean',
    previous: () => true,
    next: () => true,
    nameChange: (_val: string) => true,
    createTapdSliderShowChange: () => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();

    /** 问题回归状态图标映射配置 */
    const iconMap = computed(() => {
      const isRegression = props.detail?.is_regression;
      const config = ISSUES_REGRESSION_MAP[String(isRegression)];
      return {
        ...config,
        alias: isRegression ? t('回归') : t('新类'),
      };
    });

    /** 编辑名称输入框引用 */
    const editNameInputRef = useTemplateRef<InstanceType<typeof Input>>('editNameInput');
    /** 当前编辑的名称 */
    const editName = shallowRef('');
    /** 是否处于编辑状态 */
    const isEdit = shallowRef(false);
    /** 编辑名称的加载状态 */
    const editNameLoading = shallowRef(false);

    /**
     * 处理编辑名称
     * 进入编辑模式，设置当前名称为问题名称，并聚焦输入框
     */
    const handleEditName = () => {
      isEdit.value = true;
      editName.value = props.detail.name;
      nextTick(() => {
        editNameInputRef.value?.focus();
      });
    };

    /**
     * 处理名称输入框失焦
     * 如果名称有变化则调用API重命名，否则取消编辑
     */
    const handleNameBlur = () => {
      if (editName.value === props.detail.name || !editName.value.trim()) {
        isEdit.value = false;
        return;
      }
      editNameLoading.value = true;
      renameIssue({
        bk_biz_id: props.detail.bk_biz_id,
        issue_id: props.detail.id,
        new_name: editName.value,
      })
        .then(data => {
          isEdit.value = false;
          emit('nameChange', data.name);
        })
        .finally(() => {
          editNameLoading.value = false;
        });
    };

    /** 右侧操作按钮配置列表 */
    const btnGroupObject = computed(() => {
      return [
        {
          id: 'previous',
          title: t('上一个'),
          icon: 'icon-last-one',
          isShow: props.showStepBtn,
        },
        {
          id: 'next',
          title: t('下一个'),
          icon: 'icon-next-one',
          isShow: props.showStepBtn,
        },
        {
          id: 'fullscreen',
          title: props.isFullscreen ? t('退出全屏') : t('全屏'),
          icon: props.isFullscreen ? 'icon-mc-unfull-screen' : 'icon-fullscreen',
          isShow: props.showFullScreenBtn,
        },
      ];
    });

    /**
     * 处理按钮点击
     * @param id 按钮ID
     */
    const handleBtnClick = (id: string) => {
      switch (id) {
        case 'fullscreen':
          emit('toggleFullscreen', !props.isFullscreen);
          break;
        case 'previous':
          emit('previous');
          break;
        case 'next':
          emit('next');
          break;
      }
    };

    const handleCreateTapdSliderShowChange = () => {
      emit('createTapdSliderShowChange');
    };

    return {
      editName,
      isEdit,
      editNameLoading,
      iconMap,
      btnGroupObject,
      handleBtnClick,
      handleEditName,
      handleNameBlur,
      handleCreateTapdSliderShowChange,
    };
  },
  render() {
    if (this.loading)
      return (
        <div class='issues-detail-head-main'>
          <div class='level-tag skeleton-element' />
          <div class='issues-detail-title skeleton-element' />
          <div class='issues-detail-head-btn-group'>
            <div class='btn-item skeleton-element' />
            <div class='btn-item skeleton-element' />
            <div class='btn-item skeleton-element' />
          </div>
        </div>
      );
    return (
      <div class='issues-detail-head-main'>
        <div
          style={{ color: this.iconMap.color, backgroundColor: this.iconMap.bgColor }}
          class='level-tag'
        >
          <i class={['icon-monitor', 'sign-icon', this.iconMap.icon]} />
          <span class='level-tag-text'>{this.iconMap.alias}</span>
        </div>
        <div class={['issues-detail-head-content', { 'edit-name': this.isEdit }]}>
          <div class='issues-detail-title'>
            {this.isEdit ? (
              <Loading
                loading={this.editNameLoading}
                size='small'
              >
                <Input
                  ref='editNameInput'
                  class='edit-name-input'
                  v-model={this.editName}
                  behavior='simplicity'
                  onBlur={this.handleNameBlur}
                  onEnter={this.handleNameBlur}
                />
              </Loading>
            ) : (
              <span
                class='basic-title-name'
                v-overflow-tips
              >
                {this.detail.name}
              </span>
            )}
            {!this.isEdit && (
              <EditLine
                class='edit-icon'
                onClick={this.handleEditName}
              />
            )}
          </div>
          <div class='issues-id'>
            {this.detail.anomaly_message}
            <TemporaryShareNew type='issues' />
          </div>
        </div>
        <div class='issues-detail-head-btn-group'>
          {this.$slots.tools?.()}
          {this.btnGroupObject
            .filter(item => item.isShow)
            .map(item => (
              <div
                key={item.id}
                class='btn-group-item'
                onClick={() => this.handleBtnClick(item.id)}
              >
                <span class={`icon-monitor btn-item-icon ${item.icon}`} />
                <span class='btn-text'>{item.title}</span>
              </div>
            ))}
          <div class='btn-group-item create-tapd'>
            <Popover
              v-slots={{
                content: () => (
                  <div class='create-tapd-menu-popover-content'>
                    <div
                      class='create-tapd-menu-item'
                      onClick={this.handleCreateTapdSliderShowChange}
                    >
                      {this.$t('TAPD 单据')}
                    </div>
                    <div class='create-tapd-menu-item disabled'>Github Issue</div>
                  </div>
                ),
              }}
              arrow={false}
              theme='light create-tapd-menu-popover'
              trigger='click'
            >
              <Button
                class='create-tapd-btn'
                theme='primary'
              >
                <span>{this.$t('创建单据')}</span>
                <i class='icon-monitor icon-arrow-down' />
              </Button>
            </Popover>
          </div>
        </div>
      </div>
    );
  },
});
