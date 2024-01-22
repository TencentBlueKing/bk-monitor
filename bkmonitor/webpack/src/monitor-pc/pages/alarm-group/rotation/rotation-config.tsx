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

import { listDutyRule } from '../../../../monitor-api/modules/model';
import { previewUserGroupPlan } from '../../../../monitor-api/modules/user_groups';
import { Debounce, random } from '../../../../monitor-common/utils';
import loadingIcon from '../../../../monitor-ui/chart-plugins/icons/spinner.svg';
import { EStatus, getEffectiveStatus, statusMap } from '../../../../trace/pages/rotation/typings/common';
import { IGroupListItem } from '../duty-arranges/user-selector';

import { dutyNoticeConfigToParams, paramsToDutyNoticeConfig } from './data';
import DutyNoticeConfig, { initData as noticeData } from './duty-notice-config';
import RotationDetail from './rotation-detail';
import RotationPreview from './rotation-preview';
import { IDutyItem, IDutyListItem } from './typing';
import { getCalendarOfNum, setPreviewDataOfServer } from './utils';

import './rotation-config.scss';

const operatorText = {
  bk_bak_operator: window.i18n.t('来自配置平台主机的备份维护人'),
  operator: window.i18n.t('来自配置平台主机的主维护人')
};

interface IProps {
  dutyArranges?: (number | string)[];
  dutyNotice?: any;
  defaultGroupList?: IGroupListItem[];
  rendreKey?: string;
  alarmGroupId?: string | number;
  dutyPlans?: any[];
  onNoticeChange?: (_v) => void;
  onDutyChange?: (v: number[]) => void;
}

@Component
export default class RotationConfig extends tsc<IProps> {
  @Prop({ default: () => [], type: Array }) defaultGroupList: IGroupListItem[];
  /* 轮值规则 */
  @Prop({ default: () => [], type: Array }) dutyArranges: (number | string)[];
  /* 值班通知设置数据 */
  @Prop({ default: () => [], type: Object }) dutyNotice: any;
  @Prop({ default: '', type: String }) rendreKey: string;
  @Prop({ type: [Number, String], default: '' }) alarmGroupId: string | number;
  /* 轮值历史 */
  @Prop({ default: () => [], type: Array }) dutyPlans: any[];
  @Ref('wrap') wrapRef: HTMLDivElement;
  @Ref('noticeConfig') noticeConfigRef: DutyNoticeConfig;

  /* 添加规则弹层实例 */
  popInstance = null;
  /* 添加规则内的搜索 */
  search = '';
  /* 所有值班规则 */
  allDutyList: IDutyListItem[] = [];
  dutyList: IDutyItem[] = [];
  /* 轮值规则按钮的loading */
  dutyLoading = false;
  cacheDutyList = '[]';
  /* 预览数据 */
  previewData = [];
  /* 预览loading */
  previewLoading = false;
  /* 排序退拽相关 */
  draggedIndex = -1;
  droppedIndex = -1;
  needDrag = false;
  /* 是否展开值班通知设置 */
  showNotice = false;
  /* 轮值详情侧栏数据 */
  detailData = {
    id: '',
    show: false
  };

  noticeConfig = noticeData();
  noticeRenderKey = random(8);

  /* 轮值预览下的统计信息 */
  userPreviewList: { name: string; id: string }[] = [];
  previewStartTime = '';

  errMsg = '';

  refreshLoading = false;

  /* 即将跳转到轮值编辑页的轮值规则id */
  curToEditDutyId = 0;

  previewDutyRules = [];

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

  get showNoData() {
    return !this.allDutyList.filter(item => !!item.show && item.status !== EStatus.Deactivated).length;
  }

  created() {
    this.init();
    document.addEventListener('visibilitychange', this.handleDocumentvisibilitychange);
  }

  destroyed() {
    document.removeEventListener('visibilitychange', this.handleDocumentvisibilitychange);
  }

  async init() {
    if (!this.allDutyList.length) {
      this.dutyLoading = true;
      const list = (await listDutyRule().catch(() => [])) as any;
      this.allDutyList = list.map(item => ({
        ...item,
        isCheck: false,
        show: true,
        typeLabel: item.category === 'regular' ? this.$t('固定值班') : this.$t('交替轮值'),
        status: getEffectiveStatus([item.effective_time, item.end_time], item.enabled)
      }));
      this.setDutyList();
      this.dutyLoading = false;
    }
  }

  @Watch('rendreKey', { immediate: true })
  handleWatchrRendreKey() {
    this.setDutyList();
    this.noticeConfig = paramsToDutyNoticeConfig(this.dutyNotice);
    this.showNotice = !!(this.noticeConfig?.isSend || this.noticeConfig?.needNotice);
    this.noticeRenderKey = random(8);
  }

  setDutyList() {
    const dutyList = [];
    const sets = new Set(this.dutyArranges);
    this.allDutyList.forEach(item => {
      if (sets.has(item.id)) {
        item.isCheck = true;
        dutyList.push(item);
      }
    });
    this.dutyList = this.dutyArranges
      .map(l => {
        const temp = dutyList.find(d => String(d.id) === String(l));
        return temp;
      })
      .filter(l => !!l);
    if (this.dutyList.length) {
      this.getPreviewData();
    }
  }

  async getPreviewData() {
    if (this.cacheDutyList === JSON.stringify(this.dutyList.map(d => d.id))) {
      return;
    }
    this.cacheDutyList = JSON.stringify(this.dutyList.map(d => d.id));
    const startTime = getCalendarOfNum()[0];
    const beginTime = this.previewStartTime || `${startTime.year}-${startTime.month}-${startTime.day} 00:00:00`;
    const params = {
      source_type: 'API',
      days: 7,
      begin_time: beginTime,
      config: {
        duty_rules: this.dutyList.map(d => d.id)
      },
      id: !!this.alarmGroupId ? this.alarmGroupId : undefined
    };
    this.handleDutyChange();
    this.previewLoading = true;
    const data = await previewUserGroupPlan(params).catch(() => []);
    this.previewDutyRules = data;
    /* 获取轮值组人员预览 */
    const tempSet = new Set();
    const userPreviewList = [];
    data.forEach(d => {
      d.duty_plans.forEach(p => {
        p.users.forEach(u => {
          if (u.type === 'group') {
            if (!tempSet.has(u.id)) {
              tempSet.add(u.id);
              userPreviewList.push({
                ...u,
                name: u.display_name
              });
            }
          }
        });
      });
    });
    this.userPreviewList = userPreviewList;
    /* --- */
    this.previewLoading = false;
    this.previewData = setPreviewDataOfServer(data, this.dutyList);
  }
  /**
   * @description 周期切换
   * @param startTime
   */
  async handleStartTimeChange(startTime) {
    this.previewStartTime = startTime;
    const params = {
      source_type: 'API',
      days: 7,
      begin_time: startTime,
      config: {
        duty_rules: this.dutyList.map(d => d.id)
      },
      id: !!this.alarmGroupId ? this.alarmGroupId : undefined
    };
    this.previewLoading = true;
    const data = await previewUserGroupPlan(params).catch(() => []);
    this.previewDutyRules = data;
    this.previewLoading = false;
    this.previewData = setPreviewDataOfServer(data, this.dutyList);
  }

  noticeConfigOfDutyChange() {
    this.noticeConfig.rotationId = [];
    this.noticeRenderKey = random(8);
  }

  @Emit('dutyChange')
  handleDutyChange() {
    this.errMsg = '';
    return this.dutyList.map(item => item.id);
  }
  @Emit('noticeChange')
  handleNoticeChange() {
    return dutyNoticeConfigToParams(this.noticeConfig);
  }

  async validate() {
    if (!this.dutyList.length) {
      this.errMsg = this.$t('请选择值班规则') as string;
    }
    const noticeValidate = await this.noticeConfigRef.validate();
    return !this.errMsg && noticeValidate;
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
    this.getPreviewData();
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
        offset: '-31,2',
        trigger: 'click',
        interactive: true,
        theme: 'light common-monitor',
        arrow: false,
        placement: 'bottom-start',
        boundary: 'window',
        hideOnClick: true,
        onHide: () => {
          if (this.dutyList.length) {
            this.noticeConfigOfDutyChange();
            this.getPreviewData();
          }
        }
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
      item.show = item.labels.some(l => l.indexOf(this.search) >= 0) || item.name.indexOf(this.search) >= 0;
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
    const url = `${location.origin}${location.pathname}?bizId=${this.$store.getters.bizId}#/trace/rotation/add`;
    window.open(url);
  }
  /**
   * @description 跳转到编辑轮值页
   * @param item
   */
  handleToEditRotation(item) {
    const url = `${location.origin}${location.pathname}?bizId=${this.$store.getters.bizId}#/trace/rotation/edit/${item.id}`;
    this.curToEditDutyId = item.id;
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
    this.noticeConfigOfDutyChange();
    if (this.dutyList.length) {
      this.getPreviewData();
    }
  }

  handleShowDetail(item) {
    this.detailData.id = item.id;
    this.detailData.show = true;
  }

  handleNoticeConfigChange(value) {
    this.noticeConfig = value;
    this.handleNoticeChange();
  }

  /**
   * @description 刷新轮值列表数据
   * @param e
   * @returns
   */
  async handleRefresh(e?: Event) {
    e?.stopPropagation?.();
    if (this.refreshLoading) {
      return;
    }
    this.refreshLoading = true;
    const list = (await listDutyRule().catch(() => [])) as any;
    const ids = this.dutyList.map(item => item.id);
    const sets = new Set(ids);
    const maps = new Map();
    const allSets = new Set();
    this.allDutyList = list.map(item => {
      allSets.add(item.id);
      const obj = {
        ...item,
        isCheck: sets.has(item.id),
        show: item.labels.some(l => l.indexOf(this.search) >= 0) || item.name.indexOf(this.search) >= 0,
        typeLabel: item.category === 'regular' ? this.$t('固定值班') : this.$t('交替轮值'),
        status: getEffectiveStatus([item.effective_time, item.end_time], item.enabled)
      };
      maps.set(item.id, obj);
      return obj;
    });
    this.dutyList = this.dutyList
      .filter(item => allSets.has(item.id))
      .map(item => ({
        ...maps.get(item.id)
      }));
    if (!e) {
      this.cacheDutyList = '';
    }
    this.getPreviewData();
    this.refreshLoading = false;
  }

  /**
   * @description 监听切换到当前浏览器标签页
   */
  handleDocumentvisibilitychange() {
    if (!document.hidden) {
      if (!!this.curToEditDutyId) {
        this.handleRefresh().catch(() => []);
        // this.curToEditDutyId = 0;
      }
    }
  }

  render() {
    return (
      <div class='alarm-group-rotation-config-component'>
        <div class='add-wrap'>
          <bk-button
            outline
            theme='primary'
            loading={this.dutyLoading}
            onClick={e => !this.dutyLoading && this.handleAddRotation(e)}
          >
            <span class='icon-monitor icon-plus-line'></span>
            <span class='fs-12'>{this.$t('值班规则')}</span>
          </bk-button>
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
                <span
                  class='duty-item-name'
                  v-bk-overflow-tips
                >
                  {item.name}
                </span>
                <span class='duty-item-type'>{item.typeLabel}</span>
                {[EStatus.NoEffective, EStatus.Deactivated].includes(item.status) && (
                  <span class={['duty-item-status', item.status.toLowerCase()]}>
                    <span>{statusMap[item.status]}</span>
                  </span>
                )}
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
        {!!this.errMsg && <div class='err-msg'>{this.errMsg}</div>}
        {!!this.dutyList.length && (
          <RotationPreview
            class='mt-12'
            v-bkloading={{ isLoading: this.previewLoading }}
            value={this.previewData}
            alarmGroupId={this.alarmGroupId}
            dutyPlans={this.dutyPlans}
            previewDutyRules={this.previewDutyRules}
            onStartTimeChange={this.handleStartTimeChange}
            onInitStartTime={v => (this.previewStartTime = v)}
          ></RotationPreview>
        )}
        <div
          class='expan-btn mb-6'
          onClick={this.handleExpanNotice}
        >
          <span class={['icon-monitor icon-double-up', { expand: !this.showNotice }]}></span>
          <span class='expan-btn-text'>{this.$t('值班通知设置')}</span>
        </div>
        <DutyNoticeConfig
          ref='noticeConfig'
          class={{ displaynone: !this.showNotice }}
          value={this.noticeConfig}
          renderKey={this.noticeRenderKey}
          dutyList={this.dutyList as any[]}
          onChange={this.handleNoticeConfigChange}
        ></DutyNoticeConfig>
        {!!this.userPreviewList.length && (
          <div class='user-preivew'>
            {this.userGroupData.map(
              item =>
                this.userPreviewList.map(u => u.id).includes(item.id) && (
                  <div class='text-msg'>
                    {`${item.display_name}(${
                      ['bk_bak_operator', 'operator'].includes(item.id)
                        ? operatorText[item.id]
                        : this.$t('来自配置平台')
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
        )}
        <RotationDetail
          id={this.detailData.id}
          show={this.detailData.show}
          onShowChange={v => (this.detailData.show = v)}
        ></RotationDetail>
        <div style={{ display: 'none' }}>
          <div
            class='alarm-group-rotation-config-component-add-pop'
            ref='wrap'
          >
            <div class='header-wrap'>
              <bk-input
                value={this.search}
                placeholder={this.$t('可输入规则名称，标签搜索')}
                left-icon='bk-icon icon-search'
                behavior='simplicity'
                clearable
                onChange={this.handleSearchChange}
              ></bk-input>
            </div>
            <div class='content-wrap'>
              {!this.showNoData ? (
                this.allDutyList
                  .filter(item => !!item.show && item.status !== EStatus.Deactivated)
                  .map(item => (
                    <div
                      class='duty-select-item'
                      key={item.id}
                      onClick={() => this.handleSelectOption(item)}
                    >
                      <div onClick={(e: Event) => e.stopPropagation()}>
                        <bk-checkbox
                          value={item.isCheck}
                          onChange={v => this.handleCheckOption(v, item)}
                        ></bk-checkbox>
                      </div>
                      <span
                        class='item-name'
                        v-bk-overflow-tips
                      >
                        {item.name}
                      </span>
                      <span class='item-type'>{item.typeLabel}</span>
                      <span class='tags'>
                        {item.labels.map((tag, tagIndex) => (
                          <span
                            class={['item-tag', { active: !!this.search && tag.indexOf(this.search) >= 0 }]}
                            key={tagIndex}
                            v-bk-overflow-tips
                          >
                            {tag}
                          </span>
                        ))}
                      </span>
                    </div>
                  ))
              ) : (
                <div class='no-data'>{this.$t('无匹配数据')}</div>
              )}
            </div>
            <div
              class='del-wrap'
              onClick={this.handleToAddRotation}
            >
              <span class='icon-monitor icon-jia'></span>
              <span>{this.$t('新增轮值排班')}</span>
              <div
                class='refresh-wrap'
                onClick={e => this.handleRefresh(e)}
              >
                {this.refreshLoading ? (
                  <img
                    class='loading-icon'
                    src={loadingIcon}
                    alt=''
                  ></img>
                ) : (
                  <span class='icon-monitor icon-zhongzhi1'></span>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }
}
