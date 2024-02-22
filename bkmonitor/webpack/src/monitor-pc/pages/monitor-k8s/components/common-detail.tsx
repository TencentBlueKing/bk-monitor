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
import { Component, Emit, InjectReactive, Prop, ProvideReactive, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import MonitorDrag from '../../../../fta-solutions/pages/event/monitor-drag';
import { CancelToken } from '../../../../monitor-api/index';
import { copyText, Debounce, random } from '../../../../monitor-common/utils/utils';
import { IViewOptions, PanelModel } from '../../../../monitor-ui/chart-plugins/typings';
import { isShadowEqual } from '../../../../monitor-ui/chart-plugins/utils';
import { VariablesService } from '../../../../monitor-ui/chart-plugins/utils/variable';
import EmptyStatus from '../../../components/empty-status/empty-status';
import { EmptyStatusOperationType, EmptyStatusType } from '../../../components/empty-status/types';
import { resize } from '../../../components/ip-selector/common/observer-directive';
import MonitorResizeLayout, {
  ASIDE_COLLAPSE_HEIGHT,
  ASIDE_DEFAULT_HEIGHT,
  IUpdateHeight
} from '../../../components/resize-layout/resize-layout';
import { TimeRangeType } from '../../../components/time-range/time-range';
import { handleTransformToTimestamp } from '../../../components/time-range/utils';
import { Storage } from '../../../utils/index';
import IndexList, { IIndexListItem } from '../../data-retrieval/index-list/index-list';
import { ITableItem } from '../typings';
import { IDetailItem } from '../typings/common-detail';

import Aipanel from './ai-panel/ai-panel';
import HostDetailView from './host-detail-view/host-detail-view';
import ShowModeButton, { ShowModeButtonType } from './show-mode-button/show-mode-button';
import { type ShowModeType } from './common-page-new';

import './common-detail.scss';

const DEFAULT_WIDTH = 280;
// const FILTER_DEFALUT_WIDTH = 400;
// const MAX_WIDTH = 500;
// const APM_MAX_WIDTH = 800;
/** 索引列表最小高度 */
const INDEX_LIST_MIN_HEIGHT = 40;
/** 缓存侧栏的高度、展开状态和位置 */
export const INDEX_LIST_DEFAULT_CONFIG_KEY = 'INDEX_LIST_DEFAULT_CONFIG_KEY';
/** 缓存侧栏宽度 */
const COMMON_DETAIL_WIDTH_KEY = 'COMMON_DETAIL_WIDTH_KEY';
const MIN_DASHBOARD_WIDTH = 640;
const MIN_PANEL_WIDTH = 100;
interface ICommonDetailProps {
  // 标题
  title?: string;
  // detail 数据
  data?: [];
  panel?: PanelModel;
  aiPanel?: PanelModel;
  enableResizeListener?: boolean;
  startPlacement?: string;
  placement?: string;
  minWidth?: number;
  maxWidth?: number;
  toggleSet?: boolean;
  resetDragPosKey?: string;
  needShrinkBtn?: boolean;
  lineText?: string;
  showAminate?: boolean;
  needIndexSelect?: boolean;
  needOverflow?: boolean;
  indexList?: IIndexListItem[];
  selectorPanelType?: string;
  showMode?: ShowModeType;
  specialDrag?: boolean;
  collapse?: boolean;
  defaultWidth?: number;
  scencId?: string;
  allPanelId?: string[];
}
interface ICommonDetailEvent {
  onShrink: MouseEvent;
  onShowChange: (show: boolean, width: number) => void;
  onTitleChange: string;
  onLinkToDetail: ITableItem<'link'>;
  onWidthChange: (showMode: ShowModeType) => void;
}

interface IScopeSlots {
  default: {
    contentHeight: number;
    width: number;
  };
}

@Component({
  directives: {
    resize
  }
})
export default class CommonDetail extends tsc<ICommonDetailProps, ICommonDetailEvent, IScopeSlots> {
  @Prop({ default: '', type: String }) readonly title: string;
  @Prop({ default: null, type: Object }) readonly panel: PanelModel;
  //
  @Prop({ default: null, type: Object }) readonly aiPanel: PanelModel;
  /** 是否需要开启监听内容区域的高度 */
  @Prop({ default: false, type: Boolean }) readonly enableResizeListener: boolean;
  /** 拖拽工具的位置 */
  @Prop({ default: 'right', type: String }) readonly startPlacement: string;
  /** 组件出现在容器的位置 区分左右 */
  @Prop({ default: 'left', type: String }) readonly placement: string;
  /** 组件最小宽度 */
  @Prop({ default: 100, type: Number }) readonly minWidth: number;
  /** 组件最大宽度 */
  @Prop({ type: Number }) readonly maxWidth: number;
  @Prop({ default: false, type: Boolean }) readonly toggleSet: boolean;
  @Prop({ default: true, type: Boolean }) readonly needOverflow: boolean;
  @Prop({ default: '', type: String }) readonly resetDragPosKey: string;
  /** 是否需要收起按钮 */
  @Prop({ default: true, type: Boolean }) readonly needShrinkBtn: boolean;
  @Prop({ type: String, default: window.i18n.tc('详情') }) lineText: string;
  // 展示动态
  @Prop({ type: Boolean, default: false }) showAminate: boolean;
  /** 是否需要指标维度索引面板 */
  @Prop({ type: Boolean, default: false }) needIndexSelect: boolean;
  @Prop({ type: Boolean, default: false }) specialDrag: boolean;
  @Prop({ type: Boolean, default: false }) collapse: boolean;
  /** 索引列表 */
  @Prop({ type: Array, default: () => [] }) indexList: any[];
  /* common-page左侧操作栏类型 */
  @Prop({ default: '', type: String }) selectorPanelType: string;
  // 显示模式
  @Prop({ default: 'default', type: String }) showMode: ShowModeType;
  // 场景id
  @Prop({ default: '', type: String }) scencId: string;
  // 默认宽度
  @Prop({ default: DEFAULT_WIDTH, type: Number }) defaultWidth: number;
  // 所有的图表id
  @Prop({ default: () => [], type: Array }) allPanelId: string[];

  @Ref() resizeLayoutRef: MonitorResizeLayout;
  @Ref() indexListRef: IndexList;
  @InjectReactive('viewOptions') readonly viewOptions!: IViewOptions;
  // 是否只读模式
  @InjectReactive('readonly') readonly readonly: boolean;
  @InjectReactive('timeRange') readonly timeRange!: TimeRangeType;
  @ProvideReactive('width') width = DEFAULT_WIDTH;

  data: IDetailItem[] = [];
  loading = false;
  isShow = true;
  /** 是否出现索引搜索框 */
  showIndexSearchInput = false;
  /** 索引搜索关键字 */
  indexSearchKeyword = '';
  // /** 组件的宽度 */
  // width = DEFAULT_WIDTH;
  /** 内容区域的高度 */
  contentHeight = 0;
  indexListHeight = 500;
  cancelToken: Function = null;
  oldParams: Record<string, any> = null;
  /** 索引列表位置 */
  indexListPlacement = 'bottom';
  // 索引列表空状态
  indexListEmptyStatusType: EmptyStatusType = 'empty';
  /** 是否展开索引列表 */
  expandIndexList = true;

  /** 缓存 */
  storage = new Storage();
  activeName = [];

  /** 组件是否为活跃状态 */
  isActived = false;
  // hack reflesh conputed
  refleshMaxWidthKey = random(10);
  /** 索引列表类型 */
  get indexListType() {
    return this.indexList.some(item => !!item.children?.length) ? 'tree' : 'list';
  }
  get localWidthKey() {
    if (!this.scencId) return COMMON_DETAIL_WIDTH_KEY;
    return `${this.scencId.toLocaleUpperCase()}_${COMMON_DETAIL_WIDTH_KEY}`;
  }
  /** 根据场景区分最大宽度 */
  get maxWidthVal() {
    if (this.refleshMaxWidthKey) {
      if (!this.maxWidth) {
        // eslint-disable-next-line no-nested-ternary
        return (
          window.innerWidth -
          (window.source_app === 'monitor' || window.__POWERED_BY_BK_WEWEB__ ? (this.toggleSet ? 260 : 60) : 0) -
          16
        );
      }
      return this.maxWidth;
    }
  }

  /** 索引列表可拉伸最大高度 */
  get maxIndexListHeight() {
    return this.$el?.clientHeight ? this.$el?.clientHeight - 48 : this.indexListHeight;
  }
  get showModeButtonActive() {
    if (this.showMode === 'dashboard') {
      return 'right';
    }
    if (this.showMode === 'list') {
      return 'left';
    }
    return undefined;
  }
  created() {
    this.getPanelData();
  }
  activated() {
    window.addEventListener('resize', this.handleWindowResize);
    this.width < this.defaultWidth && (this.width = this.defaultWidth);
    this.initIndexListHeight();
    this.isActived = true;
    this.getPanelData();
  }
  deactivated() {
    window.removeEventListener('resize', this.handleWindowResize);
    this.isActived = false;
    this.oldParams = null;
  }
  @Watch('collapse', { immediate: true })
  collapseChange() {
    this.isShow = !this.collapse;
  }
  @Watch('toggleSet')
  toggleSetUpdate(val) {
    this.refleshMaxWidthKey = random(10);
    if (this.specialDrag) return;
    this.isShow = val;
    this.handleShowChange();
  }
  @Watch('viewOptions')
  // 用于配置后台图表数据的特殊设置
  handleFieldDictChange(val: IViewOptions, old: IViewOptions) {
    if (!this.panel || !val) return;
    if (JSON.stringify(val) === JSON.stringify(old)) return;
    /** isActived 防止组件在keep-alive下触发 */
    if (isShadowEqual(val, old) || !this.isActived) return;
    this.getPanelData();
  }
  @Watch('panel')
  handlePanelChange(val, old) {
    if (val && JSON.stringify(val) !== JSON.stringify(old)) {
      if (isShadowEqual(val, old) || !this.isActived) return;
      // this.oldParams = null;
      this.getPanelData();
    }
  }
  @Watch('showMode', { immediate: true })
  handleShowModeChange() {
    if (!this.specialDrag) return;
    if (this.showMode === 'list') {
      this.width = this.maxWidthVal;
    } else if (this.showMode === 'default') {
      this.initContainerWidth();
    } else if (this.showMode === 'dashboard') {
      this.width = 0;
    }
  }
  @Emit('shrink')
  handleClickShrink(val?: boolean) {
    this.isShow = val ?? !this.isShow;
    if (!this.isShow) this.width = this.defaultWidth;
    this.updateWidthStorage();
    this.handleShowChange();
    return this.isShow;
  }
  // @Debounce(500)
  async getPanelData() {
    if (this.panel?.targets?.[0]) {
      this.loading = true;
      const [item] = this.panel.targets;
      const [start_time, end_time] = handleTransformToTimestamp(this.timeRange);
      const variablesService = new VariablesService({
        ...this.viewOptions,
        ...this.viewOptions.filters,
        ...this.viewOptions.variables,
        start_time,
        end_time
      });
      const params: any = variablesService.transformVariables(item.data);
      // magic code
      if (
        (this.$route.name !== 'performance-detail' &&
          Object.values(params || {}).some(v => typeof v === 'undefined')) ||
        (this.oldParams && isShadowEqual(params, this.oldParams))
      ) {
        this.loading = false;
        return;
      }
      if (this.cancelToken) {
        this.cancelToken?.();
        this.cancelToken = null;
      }
      this.oldParams = { ...params };
      const data = await (this as any).$api[item.apiModule]
        [item.apiFunc](params, {
          cancelToken: new CancelToken((cb: Function) => (this.cancelToken = cb))
        })
        .catch(() => []);
      this.data =
        data.map?.(item => {
          if (item.type === 'list') {
            item.isExpand = false;
            item.isOverflow = false;
          }
          return item;
        }) || [];
      this.loading = false;
      const nameObj = data.find?.(item => item.key === 'name');
      if (!!nameObj) {
        /* k8s 导航subname 需要设置为名称加id */
        let id =
          this.selectorPanelType === 'list-cluster' ? data?.find?.(item => item.key.includes('id'))?.value || '' : '';
        if (id === (nameObj.value.value || nameObj.value)) {
          id = '';
        }
        this.handleTitleChange(`${nameObj.value.value || nameObj.value}${!!id ? `(${id})` : ''}`);
      }
    }
  }

  @Debounce(300)
  handleResize(el: HTMLElement) {
    /** 存在索引列表，优先使用其计算列表高度方法 */
    if (this.indexList.length) return;
    this.contentHeight = el.clientHeight - 48;
  }
  handleWindowResize() {
    this.refleshMaxWidthKey = random(10);
    if (this.showMode === 'list') {
      this.width = this.maxWidthVal;
    }
  }
  /** 拖拽改变组件宽度 */
  handleDragChange(width: number, swipeRight: boolean, cancelFn: Function) {
    if (this.specialDrag) {
      let showMode: ShowModeType = 'default';
      if (swipeRight && width < this.maxWidthVal - 3) {
        if (this.showMode === 'list' || width >= this.maxWidthVal || this.width >= this.maxWidthVal) {
          this.width = Math.min(this.maxWidthVal, this.width);
          cancelFn();
          showMode = 'list';
        } else {
          this.width = width;
          this.updateWidthStorage();
          showMode = this.showMode;
        }
      } else {
        if (this.showMode === 'default' && this.maxWidthVal - width < MIN_DASHBOARD_WIDTH) {
          this.width = 0;
          cancelFn();
          showMode = 'dashboard';
        } else if (this.showMode === 'list' || this.maxWidthVal - width < MIN_DASHBOARD_WIDTH) {
          this.width = this.maxWidthVal - MIN_DASHBOARD_WIDTH - 100;
          cancelFn();
          showMode = 'default';
        } else if (width <= MIN_PANEL_WIDTH) {
          this.width = 0;
          showMode = 'dashboard';
        } else {
          this.width = width;
          this.updateWidthStorage();
          showMode = this.showMode;
        }
      }
      this.$emit('widthChange', showMode);
    } else {
      this.width = width;
      if (this.width <= this.minWidth) {
        this.handleClickShrink(false);
      }
    }
  }

  @Emit('titleChange')
  handleTitleChange(name: string) {
    return name;
  }

  handleShowChange() {
    this.$emit('showChange', this.isShow, this.width);
  }
  /** 文本复制 */
  handleCopyText(text: string) {
    let msgStr = this.$tc('复制成功');
    copyText(text, errMsg => {
      msgStr = errMsg as string;
    });
    this.$bkMessage({ theme: 'success', message: msgStr });
  }
  /**
   * 控制展开、收起索引列表
   */
  handleExpandIndexList() {
    this.expandIndexList = !this.expandIndexList;
    const height = this.expandIndexList ? ASIDE_DEFAULT_HEIGHT : ASIDE_COLLAPSE_HEIGHT;
    this.resizeLayoutRef.updateAside({ height });
    this.updateStorage(height);
  }

  /** 拖拽索引列表更新高度 */
  @Debounce(300)
  handleResizeContentHeight(data: IUpdateHeight) {
    // if (!this.expandIndexList) return;
    this.contentHeight = data.mainHeight - 48;
    this.indexListHeight = Math.max(data.asideHeight, INDEX_LIST_MIN_HEIGHT);
  }

  /**
   * 根据索引定位到图表位置
   */
  handleScrollToIndex(item: IIndexListItem) {
    document.querySelector('.dashboard-panel .scroll-in')?.classList.remove('scroll-in');
    const dom = document.getElementById(`${item.id}__key__`);
    if (!dom) return;
    dom.scrollIntoView?.();
    dom.classList.add('scroll-in');
  }

  /**
   * 初始化索引列表高度
   */
  initIndexListHeight() {
    if (!!this.indexList.length && this.$el) {
      const data = this.storage.get(INDEX_LIST_DEFAULT_CONFIG_KEY);
      this.indexListHeight = this.$el.clientHeight / 2;
      if (!!data) {
        this.indexListHeight = data.height;
        this.indexListPlacement = data.placement;
        this.expandIndexList = data.expand;
      }
      this.resizeLayoutRef.updateAside({ height: this.indexListHeight }, false);
    }
  }
  /**
   * 初始化容器宽度
   */
  initContainerWidth() {
    const data = this.storage.get(this.localWidthKey);
    if (!!data) {
      if (data.width >= this.maxWidthVal - 740) {
        this.width = Math.max(this.maxWidthVal - 740, 0);
        return;
      }
      this.width = data.width;
    } else {
      this.width = this.defaultWidth;
    }
  }
  /**
   * 拖动缓存位置
   */
  hanldeResizing({ asideHeight }) {
    this.updateStorage(asideHeight);
  }
  /** 切换视角 */
  handleTogglePlacement(placement) {
    this.indexListPlacement = placement;
    this.updateStorage(this.resizeLayoutRef.asideHeight);
  }
  /**
   * 更新侧栏索引的缓存
   * @param asideHeight 索引侧栏的高度
   */
  updateStorage(asideHeight = this.indexListHeight) {
    this.storage.set(INDEX_LIST_DEFAULT_CONFIG_KEY, {
      height: asideHeight,
      placement: this.indexListPlacement,
      expand: this.expandIndexList
    });
  }
  /**
   * 更新侧栏宽度的缓存
   * @param asideHeight 索引侧栏的高度
   */
  updateWidthStorage(width = this.width) {
    if (this.width < this.maxWidthVal - 740 && this.width > 200) {
      this.storage.set(this.localWidthKey, { width });
    }
  }
  /**
   * 拖动到最小值，触发吸顶/底效果
   */
  handleTriggerMinIndexList(data: IUpdateHeight) {
    this.expandIndexList = false;
    this.resizeLayoutRef.updateAside({ height: ASIDE_COLLAPSE_HEIGHT });
    this.contentHeight = data.mainHeight - 48;
    this.indexListHeight = Math.max(data.asideHeight, INDEX_LIST_MIN_HEIGHT);
    this.$nextTick(() => {
      this.updateStorage(ASIDE_COLLAPSE_HEIGHT);
    });
  }
  @Debounce(300)
  handleInputSearch() {
    this.indexListEmptyStatusType = this.indexSearchKeyword ? 'search-empty' : 'empty';
    this.indexListRef.handleFilterItem(this.indexSearchKeyword);
  }
  handleBlurSearch() {
    if (this.indexSearchKeyword === '') {
      this.showIndexSearchInput = false;
    }
  }
  handleShowModeClick(btnType: ShowModeButtonType) {
    if (this.width <= 1 && btnType === 'right') {
      this.width = 400;
      this.$emit('widthChange', 'default');
    } else if (this.width >= this.maxWidthVal && btnType === 'left') {
      this.width = this.defaultWidth;
      this.$emit('widthChange', 'default');
    } else if (this.showMode === 'default') {
      this.width = btnType === 'left' ? 0 : this.maxWidthVal;
      this.$emit('widthChange', btnType === 'left' ? 'dashboard' : 'list');
    }
  }

  handleIndexListEmptyOperation(type: EmptyStatusOperationType) {
    if (type === 'clear-filter') {
      this.indexSearchKeyword = '';
      this.handleInputSearch();
      return;
    }
  }
  render() {
    const mainTpl = (
      <div class='selector-list-main'>
        <div class='common-detail-title'>
          {this.title}
          {!!this.$slots.titleEnd && <span class='title-end-content'>{this.$slots.titleEnd}</span>}
          {this.needShrinkBtn ?? (
            <i
              class='bk-icon icon-minus detail-shrink'
              onClick={() => this.handleClickShrink()}
              v-bk-tooltips={{ content: this.$t('收起'), delay: 200, boundary: 'window' }}
            ></i>
          )}
        </div>
        <div class={`common-detail-panel ${this.needOverflow ? 'need-overflow' : ''}`}>
          {this.$scopedSlots.default ? (
            this.$scopedSlots.default?.({ contentHeight: this.contentHeight, width: this.width })
          ) : (
            <HostDetailView
              data={this.data}
              width={this.width}
              onLinkToDetail={v => this.$emit('linkToDetail', v)}
            ></HostDetailView>
          )}
          {this.aiPanel && (
            <Aipanel
              panel={this.aiPanel}
              allPanelId={this.allPanelId}
            />
          )}
        </div>
      </div>
    );
    const styles: any = {};
    if (this.showMode === 'list') {
      styles.overflow = 'hidden';
      styles.marginRight = '16px';
    }
    return (
      <div
        class={[
          'common-detail',
          {
            'with-animate': this.showAminate,
            'hide-aside': this.showMode === 'list' || !this.indexList.length
          }
        ]}
        style={{ width: this.isShow ? `${this.width}px` : 0, ...styles }}
        v-bkloading={{ isLoading: this.isShow && this.loading }}
        v-resize={{ disabled: !this.enableResizeListener, handler: this.handleResize }}
      >
        <div class='common-detail-main'>
          {!this.showAminate ? (
            // && !!this.indexList.length
            <MonitorResizeLayout
              ref='resizeLayoutRef'
              disabled={!this.expandIndexList}
              min={INDEX_LIST_MIN_HEIGHT}
              max={this.maxIndexListHeight}
              default={!!this.indexList.length ? ASIDE_DEFAULT_HEIGHT : 0}
              placement={this.indexListPlacement}
              toggleBefore={() => this.expandIndexList}
              onUpdateHeight={this.handleResizeContentHeight}
              onResizing={this.hanldeResizing}
              onTogglePlacement={this.handleTogglePlacement}
              onTriggerMin={this.handleTriggerMinIndexList}
            >
              <div
                slot='main'
                class='selector-list-slot'
              >
                {mainTpl}
              </div>
              <div
                slot='aside'
                class='index-tree-wrap'
              >
                {/* 拉到顶 出现浅阴影 */}
                {this.maxIndexListHeight < this.indexListHeight && <div class='shadow-bar'></div>}
                <div
                  class='index-tree-header'
                  onClick={this.handleExpandIndexList}
                >
                  <span class={['icon-monitor icon-arrow-down', { active: this.expandIndexList }]}></span>
                  <span class='index-tree-header-text'>{this.$t('索引')}</span>
                  <div
                    class={['index-search-bar', { 'full-width': this.showIndexSearchInput }]}
                    onClick={e => e.stopPropagation()}
                  >
                    {this.showIndexSearchInput ? (
                      <bk-input
                        v-model={this.indexSearchKeyword}
                        behavior='simplicity'
                        right-icon='bk-icon icon-search'
                        class='index-search-input'
                        clearable
                        onInput={this.handleInputSearch}
                        onBlur={this.handleBlurSearch}
                      />
                    ) : (
                      <i
                        slot='prefix'
                        class='bk-icon icon-search'
                        onClick={() => (this.showIndexSearchInput = true)}
                      ></i>
                    )}
                  </div>
                </div>
                <div
                  class='index-tree-main'
                  style={{
                    height: `${this.indexListHeight - 40}px`
                  }}
                >
                  {this.indexList.length ? (
                    <IndexList
                      ref='indexListRef'
                      list={this.indexList}
                      type={this.indexListType}
                      onSelect={this.handleScrollToIndex}
                      emptyStatusType={this.indexListEmptyStatusType}
                      onEmptyStatusOperation={this.handleIndexListEmptyOperation}
                      // height="100%"
                    />
                  ) : (
                    <EmptyStatus type='empty' />
                  )}
                </div>
              </div>
            </MonitorResizeLayout>
          ) : (
            mainTpl
          )}
        </div>
        {!this.showAminate && (
          <MonitorDrag
            theme={this.specialDrag ? 'line-round' : 'line'}
            lineText={this.lineText}
            isShow={this.isShow}
            minWidth={this.minWidth}
            maxWidth={this.maxWidthVal}
            toggleSet={this.toggleSet}
            resetPosKey={this.resetDragPosKey}
            startPlacement={this.startPlacement}
            onMove={this.handleDragChange}
            onTrigger={() => this.handleClickShrink()}
          >
            {this.specialDrag && (
              <ShowModeButton
                style={{ right: this.showMode === 'list' ? '0px' : '-16px' }}
                active={this.showModeButtonActive}
                onChange={this.handleShowModeClick}
              />
            )}
          </MonitorDrag>
        )}
      </div>
    );
  }
}
