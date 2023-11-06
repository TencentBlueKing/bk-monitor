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
import { Button, Checkbox, Input } from 'bk-magic-vue';

import { Debounce } from '../../../../monitor-common/utils';
import { rotationListData } from '../../../../trace/pages/rotation/mock';
import { IGroupListItem } from '../duty-arranges/user-selector';

import DutyNoticeConfig from './duty-notice-config';
import RotationDetail from './rotation-detail';
import RotationPreview from './rotation-preview';
import { IDutyItem, IDutyListItem } from './typing';

import './rotation-config.scss';

const operatorText = {
  bk_bak_operator: window.i18n.t('来自配置平台主机的备份维护人'),
  operator: window.i18n.t('来自配置平台主机的主维护人')
};

interface IProps {
  value?: any;
  defaultGroupList?: IGroupListItem[];
  onChange?: (v: any) => void;
}

@Component
export default class RotationConfig extends tsc<IProps> {
  @Prop({ default: () => [], type: Array }) defaultGroupList: IGroupListItem[];
  @Ref('wrap') wrapRef: HTMLDivElement;

  /* 添加规则弹层实例 */
  popInstance = null;
  /* 添加规则内的搜索 */
  search = '';
  /* 所有值班规则 */
  allDutyList: IDutyListItem[] = [];

  dutyList: IDutyItem[] = [];
  draggedIndex = -1;
  droppedIndex = -1;
  needDrag = false;

  showNotice = false;

  detailData = {
    show: false
  };

  /* 轮值预览下的统计信息 */
  userPreviewList: { name: string; id: string }[] = [];

  /* 用于统计信息 */
  get userGroupData(): {
    display_name: string;
    id: string;
    members: { display_name: string; id: string }[];
  }[] {
    const userGroupData = [];
    this.defaultGroupList.forEach(item => {
      if (item.type === 'group') {
        item.children.forEach(child => {
          userGroupData.push(child);
        });
      }
    });
    return userGroupData;
  }

  created() {
    this.init();
  }

  async init() {
    const list = (await rotationListData().catch(() => [])) as any;
    this.allDutyList = list.map(item => ({
      ...item,
      isCheck: false,
      show: true,
      typeLabel: item.category === 'regular' ? this.$t('固定值班') : this.$t('交替轮值')
    }));
  }

  @Emit('change')
  handleChange() {
    //
  }

  /**
   * @description 拖拽开始
   * @param index
   */
  handleDragStart(index: number) {
    this.draggedIndex = index;
  }
  /**
   * @description 拖拽中
   * @param event
   * @param index
   */
  handleDragOver(event, index) {
    event.preventDefault();
    this.droppedIndex = index;
  }
  /**
   * @description 拖拽结束
   * @returns
   */
  handleDragEnd() {
    if (!this.needDrag) {
      return;
    }
    if (this.draggedIndex !== this.droppedIndex && this.droppedIndex !== -1) {
      const item = this.dutyList.splice(this.draggedIndex, 1)[0];
      this.dutyList.splice(this.droppedIndex, 0, item);
    }
    this.draggedIndex = -1;
    this.droppedIndex = -1;
    this.needDrag = false;
  }
  /**
   * @description 判断是否可拖拽
   */
  handleMouseenter() {
    this.needDrag = true;
  }
  handleMouseleave() {
    if (this.draggedIndex < 0 || this.droppedIndex < 0) {
      this.needDrag = false;
    }
  }
  /**
   * @description 增加值班规则
   * @param event
   */
  handleAddRotation(event: Event) {
    if (!this.popInstance) {
      this.popInstance = this.$bkPopover(event.target, {
        content: this.wrapRef,
        offset: '-31 2',
        trigger: 'click',
        interactive: true,
        theme: 'light common-monitor',
        arrow: false,
        placement: 'bottom-start',
        boundary: 'window',
        hideOnClick: true
      });
    }
    this.popInstance?.show?.();
  }
  /**
   * @description 值班规则搜索
   * @param v
   */
  @Debounce(300)
  handleSearchChange(v: string) {
    this.search = v;
    this.allDutyList.forEach(item => {
      item.show = item.labels.some(l => l === this.search) || item.name.indexOf(this.search) >= 0;
    });
  }
  /**
   * @description 选择复选框
   * @param v
   * @param item
   */
  handleCheckOption(v: boolean, item) {
    this.selectOptions(item, v);
  }
  /**
   * @description 展开通知设置
   */
  handleExpanNotice() {
    this.showNotice = !this.showNotice;
  }
  /**
   * @description 选择选项
   * @param item
   */
  handleSelectOption(item) {
    this.selectOptions(item, !item.isCheck);
  }
  /**
   * @description 选择选项
   * @param item
   * @param v
   */
  selectOptions(item, v: boolean) {
    const checked = [];
    this.allDutyList.forEach(d => {
      if (item.id === d.id) {
        d.isCheck = v;
      }
      if (d.isCheck) {
        checked.push(d);
      }
    });
    this.dutyList = checked.map(c => ({
      ...c
    }));
  }

  /**
   * @description 跳转到新增轮值页
   */
  handleToAddRotation() {
    const url = `${location.origin}${location.pathname}?bizId=${this.$store.getters.bizId}#/trace/rotation-add`;
    window.open(url);
  }
  /**
   * @description 跳转到编辑轮值页
   * @param item
   */
  handleToEditRotation(item) {
    const url = `${location.origin}${location.pathname}?bizId=${this.$store.getters.bizId}#/trace/rotation-edit/${item.id}`;
    window.open(url);
  }

  /**
   * @description 删除操作
   * @param index
   */
  handleDelRotation(index: number) {
    this.dutyList.splice(index, 1);
    const ids = new Set(this.dutyList.map(item => item.id));
    this.allDutyList.forEach(d => {
      d.isCheck = ids.has(d.id);
    });
  }

  handleShowDetail(item) {
    console.log(item);
    this.detailData.show = true;
  }

  render() {
    return (
      <div class='alarm-group-rotation-config-component'>
        <div class='add-wrap'>
          <Button
            outline
            theme='primary'
            onClick={this.handleAddRotation}
          >
            <span class='icon-monitor icon-plus-line'></span>
            <span>{this.$t('值班规则')}</span>
          </Button>
          <span class='icon-monitor icon-tishi'></span>
          <span class='tip-text'>{this.$t('排在前面的规则优先级高')}</span>
        </div>
        <div class='duty-list'>
          <transition-group
            name='list-item'
            tag='div'
          >
            {this.dutyList.map((item, index) => (
              <div
                class='duty-item'
                key={item.id}
                onClick={() => this.handleShowDetail(item)}
                draggable={this.needDrag}
                onDragstart={() => this.handleDragStart(index)}
                onDragover={event => this.handleDragOver(event, index)}
                onDragend={() => this.handleDragEnd()}
              >
                <span
                  class='icon-monitor icon-mc-tuozhuai'
                  onClick={e => e.stopPropagation()}
                  onMouseenter={() => this.handleMouseenter()}
                  onMouseleave={() => this.handleMouseleave()}
                ></span>
                <span class='duty-item-name'>{item.name}</span>
                <span class='duty-item-type'>{item.typeLabel}</span>
                <span
                  class='icon-monitor icon-bianji'
                  onClick={e => {
                    e.stopPropagation();
                    this.handleToEditRotation(item);
                  }}
                ></span>
                <span
                  class='icon-monitor icon-mc-close'
                  onClick={e => {
                    e.stopPropagation();
                    this.handleDelRotation(index);
                  }}
                ></span>
              </div>
            ))}
          </transition-group>
        </div>
        <RotationPreview class='mt-12'></RotationPreview>
        <div
          class='expan-btn mb-6'
          onClick={this.handleExpanNotice}
        >
          <span class={['icon-monitor icon-double-up', { expand: !this.showNotice }]}></span>
          <span class='expan-btn-text'>{this.$t('值班通知设置')}</span>
        </div>
        <DutyNoticeConfig class={{ displaynone: !this.showNotice }}></DutyNoticeConfig>
        <div class='user-preivew'>
          {this.userGroupData.map(
            item =>
              this.userPreviewList.map(u => u.id).includes(item.id) && (
                <div class='text-msg'>
                  {`${item.display_name}(${
                    ['bk_bak_operator', 'operator'].includes(item.id) ? operatorText[item.id] : this.$t('来自配置平台')
                  })`}
                  {(() => {
                    if (!['bk_bak_operator', 'operator'].includes(item.id)) {
                      if (item.members.length) {
                        return (
                          <span>
                            {'，'}
                            {this.$t('当前成员')} {item.members.map(m => `${m.id}(${m.display_name})`).join('; ')}
                          </span>
                        );
                      }
                      return (
                        <span>
                          {'，'}
                          {this.$t('当前成员')}
                          {`(${this.$t('空')})`}
                        </span>
                      );
                    }
                    return undefined;
                  })()}
                </div>
              )
          )}
        </div>
        <RotationDetail
          show={this.detailData.show}
          onShowChange={v => (this.detailData.show = v)}
        ></RotationDetail>
        <div style={{ display: 'none' }}>
          <div
            class='alarm-group-rotation-config-component-add-pop'
            ref='wrap'
          >
            <div class='header-wrap'>
              <Input
                value={this.search}
                placeholder={this.$t('可输入规则名称，标签搜索')}
                left-icon='bk-icon icon-search'
                behavior='simplicity'
                clearable
                onChange={this.handleSearchChange}
              ></Input>
            </div>
            <div class='content-wrap'>
              {this.allDutyList
                .filter(item => !!item.show)
                .map(item => (
                  <div
                    class='duty-select-item'
                    key={item.id}
                    onClick={() => this.handleSelectOption(item)}
                  >
                    <div onClick={(e: Event) => e.stopPropagation()}>
                      <Checkbox
                        value={item.isCheck}
                        onChange={v => this.handleCheckOption(v, item)}
                      ></Checkbox>
                    </div>
                    <span class='item-name'>{item.name}</span>
                    <span class='item-type'>{item.typeLabel}</span>
                    <span class='tags'>
                      {item.labels.map((tag, tagIndex) => (
                        <span
                          class={['item-tag', { active: this.search === tag }]}
                          key={tagIndex}
                        >
                          {tag}
                        </span>
                      ))}
                    </span>
                  </div>
                ))}
            </div>
            <div
              class='del-wrap'
              onClick={this.handleToAddRotation}
            >
              <span class='icon-monitor icon-jia'></span>
              <span>{this.$t('新增轮值排班')}</span>
            </div>
          </div>
        </div>
      </div>
    );
  }
}
