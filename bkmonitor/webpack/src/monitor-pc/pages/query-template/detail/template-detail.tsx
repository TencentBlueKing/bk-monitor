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

import MonitorTab from '../../../components/monitor-tab/monitor-tab';
import DeleteConfirm, { type DeleteConfirmEvent } from '../components/query-template-table/components/delete-confirm';
import { TemplateDetailTabEnum } from '../constants';
import { fetchQueryTemplateDetail, fetchQueryTemplateRelation } from '../service';
import ConfigPanel from './components/config-panel';
import ConsumePanel from './components/consume-panel';

import type { QueryTemplateListItem } from '../typings';
import type { TemplateDetailTabEnumType } from '../typings/constants';

import './template-detail.scss';

interface TemplateDetailEmits {
  /** 删除查询模板事件回调 */
  onDeleteTemplate: (templateId: string, confirmEvent: DeleteConfirmEvent) => void;
  /** 模板详情 - 编辑按钮点击后回调 */
  onEdit: (id: string) => void;
  /** 模板详情 - 侧弹抽屉展示状态改变回调 */
  onSliderShowChange: (isShow: boolean) => void;
}
interface TemplateDetailProps {
  /** 模板详情 - 侧弹抽屉显示时默认激活的 tab 面板 */
  defaultActiveTab?: TemplateDetailTabEnumType;
  /** 模板详情 - 侧弹抽屉是否可见 */
  sliderShow: boolean;
  /** 模板详情 - 模板 id */
  templateId: QueryTemplateListItem['id'];
}
@Component
export default class TemplateDetail extends tsc<TemplateDetailProps, TemplateDetailEmits> {
  @Ref('deleteConfirmTipRef') deleteConfirmTipRef: InstanceType<typeof DeleteConfirm>;

  /** 模板详情 - 侧弹抽屉显示时默认激活的 tab 面板 */
  @Prop({ type: String, default: TemplateDetailTabEnum.CONFIG }) defaultActiveTab?: TemplateDetailTabEnumType;
  /** 模板详情 - 侧弹抽屉是否可见 */
  @Prop({ type: Boolean, default: false }) sliderShow: boolean;
  /** 模板详情 - 模板 id */
  @Prop({ type: [Number, String] }) templateId: QueryTemplateListItem['id'];

  /** 当前激活的 tab 面板 */
  activeTab: TemplateDetailTabEnumType = TemplateDetailTabEnum.CONFIG;
  /** 查询模板配置信息 */
  templateBaseInfo = null;
  /** 查询模板消费场景列表数据 */
  relationInfo = null;
  /** 删除二次确认 popover 实例 */
  deletePopoverInstance = null;
  /** 删除二次确认 popover 延迟打开定时器 */
  deletePopoverDelayTimer = null;
  /** 是否出于请求删除接口中状态 */
  isDeleteActive = false;
  /** 模板基础信息loading */
  baseLoading = false;
  /** 查询模板消费场景列表 loading */
  relationLoading = false;

  /** 删除按钮是否可以使用 */
  get canDelete() {
    return this.templateBaseInfo?.can_delete && this.relationInfo?.total === 0;
  }

  @Watch('sliderShow')
  sliderShowChange() {
    if (!this.sliderShow) {
      this.templateBaseInfo = null;
      this.relationInfo = null;
      return;
    }
    this.activeTab = this.defaultActiveTab || TemplateDetailTabEnum.CONFIG;
    this.getTemplateDetail();
    this.getRelationInfoList();
  }

  /**
   * @description 模板详情 - 侧弹抽屉展示状态改变回调
   */
  @Emit('sliderShowChange')
  handleSliderShowChange(isShow: boolean) {
    if (this.isDeleteActive) return;
    return isShow;
  }

  @Emit('edit')
  handleEdit() {
    // this.handleSliderShowChange(false);
    return this.templateId;
  }

  /**
   * @description: 显示 删除二次确认 popover
   * @param {MouseEvent} e
   */
  handleDeletePopoverShow(e: MouseEvent) {
    if (this.isDeleteActive) return;
    if (this.deletePopoverInstance || this.deletePopoverDelayTimer) {
      this.handlePopoverHide();
    }
    const instance = this.$bkPopover(e.currentTarget, {
      content: this.deleteConfirmTipRef.$el,
      trigger: 'click',
      animation: false,
      placement: 'bottom',
      maxWidth: 'none',
      arrow: true,
      boundary: 'window',
      interactive: true,
      theme: 'light padding-0 border-1',
      onHide: () => {
        return !this.isDeleteActive;
      },
      onHidden: () => {
        this.handlePopoverHide();
      },
    });
    // @ts-ignore
    instance.deleteConfirmConfig = {
      id: this.templateId,
      templateName: this.templateBaseInfo.name,
    };
    this.deletePopoverInstance = instance;
    const popoverCache = this.deletePopoverInstance;
    this.deletePopoverDelayTimer = setTimeout(() => {
      if (popoverCache === this.deletePopoverInstance) {
        this.deletePopoverInstance?.show?.(0);
      } else {
        popoverCache?.hide?.(0);
        popoverCache?.destroy?.();
      }
    }, 300);
  }

  /**
   * @description: 清除popover
   */
  handlePopoverHide() {
    if (this.isDeleteActive) return;
    this.handleClearTimer();
    this.deletePopoverInstance?.hide?.(0);
    this.deletePopoverInstance?.destroy?.();
    this.deletePopoverInstance = null;
  }
  /**
   * @description: 清除popover延时打开定时器
   *
   */
  handleClearTimer() {
    this.deletePopoverDelayTimer && clearTimeout(this.deletePopoverDelayTimer);
    this.deletePopoverDelayTimer = null;
  }

  /**
   * @description: 删除模板确认回调
   */
  handleDeleteTemplateConfirm(templateId: QueryTemplateListItem['id'], confirmEvent: DeleteConfirmEvent) {
    this.isDeleteActive = true;
    confirmEvent?.confirmPromise
      ?.then(() => {
        this.isDeleteActive = false;
        this.handlePopoverHide();
        this.handleSliderShowChange(false);
      })
      .catch(() => {
        this.isDeleteActive = false;
      });
    this.$emit('deleteTemplate', templateId, confirmEvent);
  }

  /**
   * @description 获取模板详情信息
   */
  async getTemplateDetail() {
    if (!this.sliderShow || !this.templateId || this.templateBaseInfo) return;
    this.baseLoading = true;
    this.templateBaseInfo = await fetchQueryTemplateDetail(this.templateId);
    this.baseLoading = false;
  }

  /**
   * @description 获取模板关联资源列表
   */
  async getRelationInfoList(config?: { forceRefresh: boolean }) {
    if (!config?.forceRefresh && (!this.sliderShow || !this.templateId || this.relationInfo)) return;
    this.relationLoading = true;
    this.relationInfo = await fetchQueryTemplateRelation(this.templateId);
    this.relationLoading = false;
  }

  /**
   * @description 模板详情 - tab 切换回调
   * @param {TemplateDetailTabEnumType} tab 激活的 tab 面板
   */
  handleTabChange(tab: TemplateDetailTabEnumType) {
    this.activeTab = tab || TemplateDetailTabEnum.CONFIG;
    if (this.activeTab === TemplateDetailTabEnum.CONSUME) {
      this.getRelationInfoList();
      return;
    }
    this.getTemplateDetail();
  }

  /**
   * @description: 当删除按钮不可操作时，获取删除提示文案
   */
  getDeleteTip() {
    if (this.relationInfo?.total > 0) {
      return this.$t('当前仍然有关联的消费场景，无法删除') as string;
    }
    if (this.templateBaseInfo?.bk_biz_id === 0) {
      return this.$t('全局模板无法删除') as string;
    }
    if (this.templateBaseInfo?.bk_biz_id !== this.$store.getters.bizId) {
      const bizId = this.templateBaseInfo?.bk_biz_id;
      const bizName = this.$store.getters.bizIdMap.get(bizId)?.name;
      const url = `${location.origin}${location.pathname}?bizId=${bizId}${location.hash}`;
      return (
        <i18n
          class='text'
          path='模板属于业务 {0}，无法删除'
        >
          <a
            style='color: #3a84ff'
            href={url}
            rel='noreferrer'
            target='_blank'
          >
            {bizName}
          </a>
        </i18n>
      );
    }
    return this.$t('无法删除');
  }

  /**
   * @description: 当编辑按钮不可操作时，获取编辑提示文案
   */
  getEditTip() {
    if (this.templateBaseInfo?.bk_biz_id === 0) {
      return this.$t('全局模板无法编辑') as string;
    }
    if (this.templateBaseInfo?.bk_biz_id !== this.$store.getters.bizId) {
      const bizId = this.templateBaseInfo?.bk_biz_id;
      const bizName = this.$store.getters.bizIdMap.get(bizId)?.name;
      const url = `${location.origin}${location.pathname}?bizId=${bizId}${location.hash}`;

      return (
        <i18n
          class='text'
          path='模板属于业务 {0}，无法编辑'
        >
          <a
            style='color: #3a84ff'
            href={url}
            rel='noreferrer'
            target='_blank'
          >
            {bizName}
          </a>
        </i18n>
      );
    }
    return this.$t('无法编辑');
  }

  render() {
    return (
      <bk-sideslider
        width='60vw'
        ext-cls='template-detail'
        is-show={this.sliderShow}
        quick-close={true}
        show-mask={true}
        transfer={true}
        {...{ on: { 'update:isShow': this.handleSliderShowChange } }}
      >
        <div
          class='template-detail-header'
          slot='header'
        >
          <div class='header-info'>
            <div class='header-info-title'>
              <span>{this.$t('模板详情')}</span>
            </div>
            <div class='header-info-division' />
            <div
              class={['header-info-template-name', { alias: this.templateBaseInfo?.alias.length > 0 }]}
              v-bk-tooltips={{
                content: this.templateBaseInfo?.name,
                disabled: !this.templateBaseInfo?.alias,
              }}
            >
              <span>{this.templateBaseInfo?.alias || this.templateBaseInfo?.name || '--'}</span>
            </div>
          </div>
          <div class='header-operations'>
            <bk-popover
              disabled={this.templateBaseInfo?.can_edit}
              placement='right'
            >
              <bk-button
                disabled={!this.templateBaseInfo?.can_edit}
                theme='primary'
                title={this.$t('编辑')}
                onClick={this.handleEdit}
              >
                {this.$t('编辑')}
              </bk-button>
              <span slot='content'>{this.getEditTip()}</span>
            </bk-popover>

            <bk-popover
              disabled={this.canDelete}
              placement='right'
            >
              <bk-button
                disabled={!this.canDelete}
                title={this.$t('删除')}
                onClick={this.handleDeletePopoverShow}
              >
                {this.$t('删除')}
              </bk-button>
              <span slot='content'>{this.getDeleteTip()}</span>
            </bk-popover>
          </div>
        </div>
        <div
          class='template-detail-content'
          slot='content'
        >
          <MonitorTab
            class='template-detail-tabs'
            // @ts-ignore
            active={this.activeTab}
            on-tab-change={v => this.handleTabChange(v)}
          >
            <bk-tab-panel
              label={this.$t('配置信息')}
              name={TemplateDetailTabEnum.CONFIG}
              renderDirective='if'
            >
              <ConfigPanel
                v-bkloading={{ isLoading: this.baseLoading }}
                templateInfo={this.templateBaseInfo}
              />
            </bk-tab-panel>
            <bk-tab-panel
              label={`${this.$t('消费场景')} (${this.relationInfo?.total || 0})`}
              name={TemplateDetailTabEnum.CONSUME}
              renderDirective='if'
            >
              <ConsumePanel
                v-bkloading={{ isLoading: this.relationLoading }}
                relationInfo={this.relationInfo}
                onRefresh={() => this.getRelationInfoList({ forceRefresh: true })}
              />
            </bk-tab-panel>
          </MonitorTab>
          <div style='display: none'>
            <DeleteConfirm
              ref='deleteConfirmTipRef'
              templateId={this.deletePopoverInstance?.deleteConfirmConfig?.id}
              templateName={this.deletePopoverInstance?.deleteConfirmConfig?.templateName}
              onCancel={this.handlePopoverHide}
              onConfirm={this.handleDeleteTemplateConfirm}
            />
          </div>
        </div>
      </bk-sideslider>
    );
  }
}
