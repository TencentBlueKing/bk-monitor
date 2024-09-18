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
import { Component, Emit, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { deepClone } from 'monitor-common/utils/utils';

import { SETTINGS_POP_ZINDEX } from '../../utils';
import TabForm from './tab-form';

import type { IBookMark, SettingsTabType } from '../../typings';

import './settings-tab.scss';
/**
 * 页签设置弹窗
 */
@Component
export default class SettingsTab extends tsc<SettingsTabType.IProps, SettingsTabType.IEvents> {
  /** 页签数据 */
  @Prop({ default: () => [], type: Array }) bookMarkData: IBookMark[];
  @Prop({ default: '', type: String }) activeTab: string;
  @Prop({ default: false, type: Boolean }) canAddTab: boolean;
  /** 场景名称 */
  @Prop({ default: '', type: String }) title: string;
  /** 是否为自动添加状态 */
  @Prop({ default: false, type: Boolean }) needAutoAdd: boolean;
  /** 选中tab */
  tabActive = '';
  /** 拖拽数据 */
  dragData: { from: number; to: number } = {
    from: null,
    to: null,
  };
  localTabData: IBookMark[] = [];
  curTabForm: SettingsTabType.ITabForm = {};
  curTabFormCache: SettingsTabType.ITabForm = {};
  drag = {
    active: -1,
  };
  isCreateNewTab = false;
  get pageNameList() {
    return this.bookMarkData.map(data => data.name);
  }

  /** 页签顺序被改变 */
  get tabSortIsDiff(): boolean {
    return JSON.stringify(this.localTabData) !== JSON.stringify(this.bookMarkData);
  }

  /** 当前页签配置是否存在差异 */
  get localTabListIsDiff(): boolean {
    const { curTabForm, curTabFormCache } = this;
    // 当前选中页签编辑表单内容改变
    const isFormChange = JSON.stringify(curTabForm) !== JSON.stringify(curTabFormCache);
    return isFormChange || this.tabSortIsDiff;
  }

  created() {
    this.tabActive = this.activeTab;
    this.updateCurTabFormLocal(this.tabActive);
    if (this.needAutoAdd) {
      this.isCreateNewTab = true;
    }
  }

  @Watch('bookMarkData', { immediate: true, deep: true })
  handleBookMarkDataChange(val) {
    this.localTabData = deepClone(val);
    this.tabActive && this.updateCurTabFormLocal(this.tabActive);
    if (this.isCreateNewTab) {
      this.addTab();
    }
  }

  /**
   * @description: 更新curEditForm
   * @param {string} tab
   */
  updateCurTabFormLocal(tab) {
    const curPageData = this.bookMarkData.find(item => item.id === tab);
    if (curPageData) {
      // eslint-disable-next-line @typescript-eslint/naming-convention
      const { id, name, show_panel_count } = curPageData;
      this.curTabForm = { id, name, show_panel_count };
      this.curTabFormCache = { id, name, show_panel_count };
    }
  }

  /**
   * @description: 新增页签， 自动创建页签时不进行校验
   * @param {boolean} isValid 是否需要检验
   */
  addTab(isValid = false) {
    const cb = () => {
      this.localTabData.unshift({
        id: `custom_${new Date().getTime()}`,
        name: '新页签',
        link: '',
        show_panel_count: true,
        variables: [],
        panels: [],
        panel_count: 0,
      });
      this.tabActive = this.localTabData[0].id;
      this.curTabForm = {
        id: `custom_${new Date().getTime()}`,
        name: '',
        show_panel_count: true,
      };
    };
    if (isValid) {
      this.handleShowTip(cb);
    } else {
      cb();
    }
  }

  /**
   * @description: 选中页签
   * @param {number} index
   * @param {boolean} isValid 是否需要检验
   */
  async handleSelectItem(tab: IBookMark, isValid = false) {
    if (this.tabActive === tab.id) return;

    const cb = () => {
      this.tabActive = tab.id;
      this.updateCurTabFormLocal(this.tabActive);
    };

    if (isValid) {
      this.handleShowTip(cb);
    } else {
      cb();
    }
  }

  /**
   * @description: 切换页签提示
   */
  handleShowTip(cb) {
    if (this.localTabListIsDiff) {
      this.$bkInfo({
        zIndex: SETTINGS_POP_ZINDEX,
        title: this.$t('是否放弃本次操作？'),
        confirmFn: () => {
          this.localTabData = deepClone(this.bookMarkData);
          cb();
        },
      });
    } else {
      cb();
    }
  }

  /**
   * @description: 拖拽开始
   * @param {DragEvent} evt
   * @param {number} index
   */
  handleDragStart(evt: DragEvent, index: number) {
    this.dragData.from = index;

    evt.dataTransfer.effectAllowed = 'move';
  }

  /**
   * @description: 拖拽结束
   */
  handleDragend() {
    // 动画结束后关闭拖拽动画效果
    setTimeout(() => {
      this.dragData.from = null;
      this.dragData.to = null;
    }, 500);
    this.drag.active = -1;
  }

  /**
   * @description: 拖拽放入
   */
  handleDrop() {
    const { from, to } = this.dragData;
    if (from === to || [from, to].includes(null)) return;
    const temp = this.localTabData[from];
    this.localTabData.splice(from, 1);
    this.localTabData.splice(to, 0, temp);
    this.drag.active = -1;
  }

  /**
   * @description: 拖拽进入
   * @param {number} index
   */
  handleDragEnter(index: number) {
    this.dragData.to = index;
  }

  /**
   * @description: 拖拽经过
   * @param {DragEvent} evt
   */
  handleDragOver(evt: DragEvent, index: number) {
    evt.preventDefault();
    this.drag.active = index;
  }

  /**
   * @description: 拖拽离开
   */
  handleDragLeave() {
    this.drag.active = -1;
  }

  handleFiledChange(data) {
    this.curTabForm = data;
    this.localTabData.forEach(item => {
      if (item.id === this.tabActive) {
        item.show_panel_count = data.show_panel_count;
      }
    });
  }

  /**
   * @description: 保存页签
   */
  @Emit('save')
  handleSave(isCreateNewTab: boolean): SettingsTabType.IEvents['onSave'] {
    this.isCreateNewTab = isCreateNewTab;
    const data = {
      id: this.tabActive,
      name: this.curTabForm.name,
      show_panel_count: this.curTabForm.show_panel_count,
      view_order: [],
    };
    if (this.tabSortIsDiff) {
      const tabOrder = this.localTabData.map(tab => tab.id);
      data.view_order = tabOrder;
    }
    return data;
  }

  /**
   * @description: 删除页签
   */
  @Emit('delete')
  handleDeleteChange(id): SettingsTabType.IEvents['onDelete'] {
    return id;
  }

  /**
   * @description: 删除页签
   */
  handleDelete(id: string) {
    if (this.localTabData.length < 2) return;
    this.$bkInfo({
      zIndex: SETTINGS_POP_ZINDEX,
      title: this.$t('确认删除此页签吗？'),
      confirmFn: () => {
        if (this.bookMarkData.some(tab => tab.id === this.curTabForm.id)) {
          this.handleDeleteChange(id);
        } else {
          this.localTabData = this.localTabData.filter(tab => tab.id !== id);
          this.tabActive = this.localTabData[0].id;
          this.updateCurTabFormLocal(this.tabActive);
        }
      },
    });
    this.isCreateNewTab = false;
  }

  render() {
    return (
      <div class='settings-tab'>
        <div class='settings-title'>
          {this.title}
          {this.canAddTab && (
            <div
              class='create-btn'
              onClick={() => this.addTab(true)}
            >
              <i class='bk-icon icon-plus-circle-shape' />
              <span>{this.$t('新增页签')}</span>
            </div>
          )}
        </div>
        <div class='setting-tab-list'>
          <transition-group
            class='tab-list'
            name={this.dragData.from !== null ? 'flip-list' : 'filp-list-none'}
            tag='ul'
          >
            {this.localTabData.map((tab, index) => (
              <li
                key={tab.id}
                class={['drag-item', { 'active-item': this.tabActive === tab?.id || index === this.drag.active }]}
                draggable={true}
                onClick={() => this.handleSelectItem(tab, true)}
                onDragend={this.handleDragend}
                onDragenter={() => this.handleDragEnter(index)}
                onDragleave={this.handleDragLeave}
                onDragover={evt => this.handleDragOver(evt, index)}
                onDragstart={evt => this.handleDragStart(evt, index)}
                onDrop={this.handleDrop}
              >
                <div class='tab-main'>
                  <i class='icon-monitor icon-mc-tuozhuai' />
                  <span class='tab-title'>{tab.name}</span>
                  {tab.show_panel_count && <span class='tab-chart-count'>{tab.panel_count}</span>}
                </div>
              </li>
            ))}
          </transition-group>
        </div>
        <TabForm
          key={this.tabActive}
          bookMarkData={this.bookMarkData}
          canAddTab={this.canAddTab}
          formData={this.curTabForm}
          onChange={this.handleFiledChange}
          // onReset={this.handleReset}
          onDelete={this.handleDelete}
          onSave={this.handleSave}
        />
      </div>
    );
  }
}
