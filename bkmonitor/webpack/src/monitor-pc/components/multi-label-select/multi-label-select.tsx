// import { Tree } from 'bk-magic-vue'
import type { VNode } from 'vue';

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
/*
 * @Date: 2021-06-09 19:29:07
 * @LastEditTime: 2021-06-30 19:22:24
 * @Description:
 */
import { Component, Emit, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { strategyLabelList } from 'monitor-api/modules/strategies';
import { deepClone, transformDataKey } from 'monitor-common/utils/utils';
import { debounce } from 'throttle-debounce';

import LabelTree from './label-tree/label-tree';
import { labelListToTreeData } from './utils';

import type { IAddWrapSize, ITreeItem, TBehavior, TMode } from './types';

import './multi-label-select.scss';

interface IContainerProps {
  allowAutoMatch?: boolean;
  autoGetList?: boolean;
  behavior?: TBehavior;
  checkedNode?: string[];
  mode: TMode;
  readonly?: boolean;
  treeData?: ITreeItem[];
}

interface IEvent {
  onCheckedChange?: string[];
  onListChange?: any;
  onLoading?: boolean;
}

@Component({
  name: 'MultiLabelSelect',
  components: {
    LabelTree,
  },
})
export default class MultiLabelSelect extends tsc<IContainerProps, IEvent> {
  @Prop({ default: 'create', type: String }) private mode: TMode;
  @Prop({ default: () => [] }) private treeData: ITreeItem[];
  @Prop({ default: false, type: Boolean }) private autoGetList: boolean; // 组件内请求列表数据
  @Prop({ default: () => [], type: Array }) private checkedNode: string[];
  @Prop({ default: 'normal', type: String }) private behavior: TBehavior;
  @Prop({ default: false, type: Boolean }) private readonly: boolean;
  @Prop({ default: true, type: Boolean }) private allowAutoMatch: boolean; // 自定义失焦自动生成tag

  @Ref('createLabelTree') private readonly createLabelTreeRef;
  @Ref('wrapper') private readonly wrapperRef;
  @Ref('input') private readonly inputRef;
  @Ref('selectDropdown') private readonly selectDropdownRef;
  @Ref('tagList') private readonly tagListRef;

  private treeLoading = false;
  private isEdit = false;
  private defaultPlaceholder: string = window.i18n.tc('选择或输入');
  private addWrapSize: IAddWrapSize = {
    width: 470,
    height: 357,
    startClientX: 0,
    startClientY: 0,
  };

  private dropDownInstance: any = null;
  private resizeObserver: any = null;
  private popoverContentWidth = 465;
  private localCheckNode: string[] = [];
  private localTreeList: ITreeItem[] = [];
  private localSearchData: any[] = [];
  private inputValue = '';
  private handleOverflowDebounce: Function = null;

  private tippyOptions: any = {
    onHidden: null,
  };

  get filterSearchData() {
    const value = this.removeSpacesInputValue;
    if (value) {
      const res = this.localSearchData
        .map(item => {
          const obj = {
            groupName: item.groupName,
            children: item.children.filter(key => {
              const isSame = key?.toUpperCase().indexOf(value.toUpperCase()) > -1;
              return isSame && !this.localCheckNode.includes(`/${key}/`);
            }),
          };
          return obj;
        })
        .filter(item => item.children.length);
      return res;
    }
    return this.localSearchData;
  }

  // 可以自定义标签
  get isCanCustom() {
    const value = this.removeSpacesInputValue;
    const res = this.localSearchData.some(item => item.children.some(set => set === value));
    return !res;
  }

  /**
   * 去除空格的搜索值
   */
  get removeSpacesInputValue() {
    return this.inputValue.replace(/\s/g, '');
  }

  get menuListDisplay() {
    const noSearch = !this.filterSearchData.find(item => item.children.length);
    const noList = !this.localSearchData.find(item => item.children.length);
    const display = noSearch || noList ? 'none' : 'block';
    return display;
  }

  @Watch('checkedNode', { immediate: true, deep: true })
  checkedNodeChange() {
    this.localCheckNode = deepClone(this.checkedNode);
    this.handleOverflowDebounce?.();
  }

  @Watch('treeData', { immediate: true, deep: true })
  treeDataChange(treeData) {
    this.localTreeList = deepClone(treeData);
    this.mode === 'select' && this.createSearchData(treeData);
  }

  // @Watch('filterSearchData')
  // async filterSearchDataChange (nv) {
  //   if (this.isEdit) {
  //     const leng = nv.length
  //     const fn = leng ? this.showDropdown :  this.hideDropdown
  //     await this.$nextTick()
  //     fn()
  //   }
  // }

  @Emit('listChange')
  localTreeListChange() {
    return deepClone(this.localTreeList);
  }

  @Emit('checkedChange')
  localCheckNodeChange() {
    return deepClone(this.localCheckNode);
  }

  @Emit('loading')
  emitLoading(isLoading: boolean) {
    return isLoading;
  }

  created() {
    this.tippyOptions.onHidden = this.hideDropdownCb;
    this.autoGetList && !this.treeData?.length && this.getLabelListApi(); // 组件内请求列表数据
  }

  mounted() {
    if (this.mode === 'select' && !this.readonly) {
      this.resizeObsever();
      this.dropDownInstance = this.selectDropdownRef?.instance;
      this.handleOverflow();
      this.handleOverflowDebounce = debounce(300, this.handleOverflow);
    }
  }
  beforeDestroy() {
    !this.readonly && this.mode === 'select' && this.resizeObserver.unobserve(this.wrapperRef);
  }

  // 获取列表数据
  getLabelListApi() {
    const params = {
      bk_biz_id: this.mode === 'select' ? this.$store.getters.bizId : 0,
      strategy_id: 0,
    };
    this.emitLoading(true);
    strategyLabelList(params)
      .then(res => {
        let list = [];
        let customData = [];
        const data = transformDataKey(res);
        const globalData = [
          ...data.global,
          ...data.globalParentNodes.map(item => ({ id: item.labelId, labelName: item.labelName })),
        ];
        // 标签选择模式
        if (this.mode === 'select') {
          customData = [
            ...data.custom,
            ...data.customParentNodes.map(item => ({ id: item.labelId, labelName: item.labelName })),
          ];
          list = [
            {
              group: 'global',
              groupName: this.$t('全局标签'),
              children: labelListToTreeData(globalData),
            },
            {
              group: 'custom',
              groupName: this.$t('自定义标签'),
              children: labelListToTreeData(customData),
            },
          ];
        } else {
          // 标签创建模式列表
          list = globalData;
        }
        this.treeDataChange(list);
      })
      .finally(() => this.emitLoading(false));
  }

  /**
   * 新增模式下监听容器的大小变化
   */
  resizeObsever() {
    this.resizeObserver = new ResizeObserver(entries => {
      const rect = entries[0].contentRect;
      this.popoverContentWidth = rect.width;
      this.removeOverflow();
      this.handleOverflowDebounce();
    });
    this.resizeObserver.observe(this.wrapperRef);
  }

  /**
   * 统计标签数目
   * @param group 标签分组名
   */
  //   getLabelCount(groupName: string) {
  //     const res = this.localSearchData.find(item => item.groupName === groupName)
  //     return res ? res.children?.length : 0
  //   }

  /**
   * 创建搜索所需的数据
   * @param list
   */
  createSearchData(list: ITreeItem[]) {
    const res = list.map(item => ({
      group: item.group,
      groupName: item.groupName,
      children: this.getSearchData(item.children),
    }));
    this.localSearchData = res;
  }

  /**
   * 获取各分组下的数据id
   * @param list
   */
  getSearchData(list: ITreeItem[]) {
    const res = [];
    const fn = data => {
      data.forEach(item => {
        if (item.children) {
          fn(item.children);
        } else {
          res.push(item.key);
        }
      });
    };
    fn(list);
    return res;
  }

  /**
   * 展示下拉
   */
  showDropdown() {
    if (this.readonly) return;
    this.dropDownInstance.show();
    this.removeOverflow();
  }

  hideDropdown() {
    this.dropDownInstance.hide();
  }

  /**
   * 下拉隐藏回调
   */
  hideDropdownCb() {
    this.inputValue = '';
    this.isEdit = false;
    this.handleOverflow();
  }

  /**
   * 树形数据更新
   * @param list
   */
  handleLocalTreeListChange(list) {
    this.localTreeList = list;
    this.localTreeListChange();
  }

  /**
   * 新增一级标签
   */
  handleAddFirstLevelLabel() {
    const isCreate = this.localTreeList.some(item => item.isCreate);
    if (isCreate) return;
    this.localTreeList.push({
      id: null,
      key: '',
      name: '',
      parent: null,
      isCreate: true,
    });
    this.$nextTick(() => {
      this.createLabelTreeRef.inputFocus();
    });
  }

  /**
   * 选中标签
   * @param checked
   */
  handleNodeChecked(checked) {
    const change = checked.valueChange;
    if (change.type === 'add') {
      this.localCheckNode.push(change.value);
    } else {
      const index = this.localCheckNode.findIndex(item => item === change.value);
      this.localCheckNode.splice(index, 1);
    }
    this.localCheckNodeChange();
  }

  /**
   * 输入框聚焦
   */
  async focusInputer() {
    if (this.readonly) return;
    this.isEdit = true;
    await this.$nextTick();
    this.inputRef.focus();
    this.showDropdown();
  }

  /**
   * 控制超出省略提示
   */
  async handleOverflow() {
    this.removeOverflow();
    const list = this.tagListRef;
    const childs = list.children;
    const overflowTagWidth = 22;
    const listWidth = list.offsetWidth;
    let totalWidth = 0;
    await this.$nextTick();

    for (const i in childs) {
      const item = childs[i];
      if (!item.className || item.className.indexOf('key-node') === -1) continue;
      totalWidth += item.offsetWidth + (this.behavior === 'simplicity' ? 4 : 5);
      // 超出省略
      if (totalWidth + overflowTagWidth + 3 > listWidth) {
        const hideNum = this.checkedNode.length - +i;
        this.insertOverflow(item, hideNum > 99 ? 99 : hideNum);
        break;
      }
    }
  }

  /**
   * 插入超出提示
   * @param target
   * @param num
   */
  insertOverflow(target, num) {
    if (this.isEdit) return;
    const li = document.createElement('li');
    const div = document.createElement('div');
    li.className = 'tag-overflow';
    div.className = 'tag';
    div.innerText = `+${num}`;
    li.appendChild(div);
    this.tagListRef.insertBefore(li, target);
  }

  /**
   * 移除超出提示
   */
  removeOverflow() {
    const overflowList = this.tagListRef?.querySelectorAll('.tag-overflow');
    if (!overflowList?.length) return;
    overflowList.forEach(item => {
      this.tagListRef.removeChild(item);
    });
  }

  /**
   * 输入框失去焦点
   */
  inputBlur() {
    if (this.allowAutoMatch && this.removeSpacesInputValue && !this.filterSearchData.length) {
      this.createCustomLabel();
      this.isEdit = false;
    }
  }

  /**
   * 鼠标变盘事件
   * @param e
   */
  inputKeydown(e: KeyboardEvent) {
    // Backspace Enter
    const key = e.code;
    const keyFn = {
      Enter: this.handleCustomLabel,
      Backspace: () => {
        if (!this.inputValue.length) {
          const index = this.localCheckNode.length - 1;
          index >= 0 && this.handleRemoveTag(index);
        }
      },
    };
    keyFn[key]?.();
  }

  /**
   * 输入框input
   * @param e
   */
  inputChange(e: any) {
    this.inputValue = e.target.value;
    if (this.filterSearchData.length) {
      this.showDropdown();
    } else {
      // this.hideDropdown()
    }
  }

  // 创建自定义标签
  handleCustomLabel() {
    if (this.removeSpacesInputValue) {
      setTimeout(() => {
        this.createCustomLabel();
        this.inputValue = '';
      }, 0);
    }
  }

  /**
   * 创建标签
   */
  createCustomLabel() {
    const isCreateCustom = this.isCanCustom && this.removeSpacesInputValue;
    if (isCreateCustom) {
      const labelArr = this.removeSpacesInputValue.split('/').filter(item => !!item);
      const id = `/${labelArr.join('/')}/`;
      if (!this.localCheckNode.includes(id)) {
        this.localCheckNode.push(id);
        this.localCheckNodeChange();
      } else {
        this.$bkMessage({
          message: this.$t('注意: 名字冲突'),
          theme: 'error',
        });
      }
    } else {
      const id = `/${this.removeSpacesInputValue}/`;
      !this.localCheckNode.includes(id) && this.localCheckNode.push(id);
    }
  }

  /**
   * 删除标签
   * @param index
   */
  handleRemoveTag(index: number) {
    // e?.stopPropagation()
    if (this.readonly) return;
    this.localCheckNode.splice(index, 1);
    this.localCheckNodeChange();
    // this.localTreeListChange()
  }

  /**
   * 处理搜索高亮
   * @param str
   */
  searchHighlight(str: string) {
    const value = this.removeSpacesInputValue;
    const reg = new RegExp(`${value}`, 'g');
    let res = str.replace(reg, `<span class="hl">${value}</span>`);
    try {
      res = res.replace(/([^<])(\/)([^>])/g, '$1&nbsp;/&nbsp;$3');
    } catch (error) {
      console.log(error);
    }
    return res;
  }

  /**
   * 选中搜索结果
   * @param id
   */
  selectSearchRes(id) {
    this.localCheckNode.push(id);
    this.localCheckNodeChange();
    this.inputValue = '';
    this.isEdit = false;
    this.hideDropdown();
  }

  handleTreeLoading(v) {
    this.treeLoading = v;
  }

  /**
   * 容器大小控制
   * @param e
   */
  handleMouseDown(e: MouseEvent) {
    this.addWrapSize.startClientX = e.clientX;
    this.addWrapSize.startClientY = e.clientY;
    document.addEventListener('mousemove', this.handleMousemove, false);
    document.addEventListener('mouseup', this.handleMouseup, false);
  }
  handleMouseup() {
    this.addWrapSize.startClientX = 0;
    this.addWrapSize.startClientY = 0;
    document.removeEventListener('mousemove', this.handleMousemove, false);
    document.removeEventListener('mouseup', this.handleMousemove, false);
  }
  handleMousemove(e: MouseEvent) {
    if (this.addWrapSize.startClientX === 0) return;
    const offsetX = e.clientX - this.addWrapSize.startClientX;
    const offsetY = e.clientY - this.addWrapSize.startClientY;
    this.addWrapSize.startClientX = e.clientX;
    this.addWrapSize.startClientY = e.clientY;
    this.addWrapSize.width = this.addWrapSize.width + offsetX;
    this.addWrapSize.height = this.addWrapSize.height + offsetY;
  }

  protected render(): VNode {
    return (
      <div
        ref='wrapper'
        class={[
          'multi-label-select',
          { 'simplicit-theme': this.behavior === 'simplicity', 'is-readonly': this.readonly },
        ]}
      >
        {/* 新增模式 */}
        {this.mode === 'create' ? (
          <div class='multi-label-add'>
            <bk-button onClick={this.handleAddFirstLevelLabel}>
              <div class='add-btn-wrap'>
                <i class='icon-monitor icon-mc-add' />
                <span class='text'>{this.$t('添加一级标签')}</span>
              </div>
            </bk-button>
            {this.localTreeList.length ? (
              <div
                style={`width: ${this.addWrapSize.width}px; height: ${this.addWrapSize.height}px;`}
                class='label-tree-contain-wrap'
                v-bkloading={{ isLoading: this.treeLoading }}
              >
                <div class='label-tree-scroll-wrap'>
                  <label-tree
                    ref='createLabelTree'
                    checkedNode={this.localCheckNode}
                    mode='create'
                    treeData={this.localTreeList}
                    onListChange={this.handleLocalTreeListChange}
                    onLoading={this.handleTreeLoading}
                  />
                </div>
                <i class='resize-icon-inner' />
                <i
                  class='resize-icon-wrap'
                  onMousedown={this.handleMouseDown}
                  onMousemove={this.handleMousemove}
                  onMouseup={this.handleMouseup}
                />
              </div>
            ) : (
              ''
            )}
          </div>
        ) : (
          // 选择模式
          <div>
            <bk-popover
              ref='selectDropdown'
              class='multi-label-select-dropdown'
              animation='slide-toggle'
              arrow={false}
              distance={12}
              placement='bottom-start'
              theme='light multi-label-list-wrapper'
              tippyOptions={this.tippyOptions}
              transfer={false}
              trigger='manual'
            >
              <div
                class={['multi-label-input', { 'is-focus': this.isEdit }]}
                onClick={this.focusInputer}
              >
                {!this.localCheckNode.length && !this.isEdit ? (
                  <p class='placeholder'>{this.defaultPlaceholder}</p>
                ) : (
                  ''
                )}
                <ul
                  ref='tagList'
                  class='tag-list'
                >
                  {this.localCheckNode.map((item, index) => (
                    <li
                      key={index}
                      class='key-node'
                    >
                      <div class='tag'>
                        <span class='text'>
                          {item
                            .split('/')
                            .filter(item => item)
                            .join(' / ')}
                        </span>
                      </div>
                      {!this.readonly ? (
                        <i
                          class='icon-monitor icon-mc-close remove-key'
                          onClick={() => this.handleRemoveTag(index)}
                        />
                      ) : undefined}
                    </li>
                  ))}
                  {this.isEdit ? (
                    <li
                      ref='staffInput'
                      class='staff-input'
                    >
                      <span class='input-value'>{this.inputValue}</span>
                      <input
                        ref='input'
                        class='input'
                        type='text'
                        value={this.inputValue}
                        onBlur={this.inputBlur}
                        onClick={e => e.stopPropagation()}
                        onInput={this.inputChange}
                        onKeydown={this.inputKeydown}
                      />
                    </li>
                  ) : (
                    ''
                  )}
                </ul>
                <span class='arrow-down-wrap'>
                  <i class='icon-monitor icon-arrow-down' />
                </span>
              </div>
              <div
                ref='menuList'
                style={`display: ${this.menuListDisplay}; width: ${this.popoverContentWidth}px`}
                class='menu-list-wrap'
                slot='content'
              >
                {
                  // 搜索结果
                  this.removeSpacesInputValue ? (
                    <div class='search-result-wrap'>
                      {this.filterSearchData.map(item => (
                        <div class='group-item'>
                          <div class='group-title'>
                            <div class='title'>{`${item.groupName}( ${item.children.length} )`}</div>
                          </div>
                          <ul class='res-list'>
                            {item.children.map(id => (
                              <li
                                class='res-item'
                                domPropsInnerHTML={this.searchHighlight(id)}
                                onClick={() => this.selectSearchRes(id)}
                              >
                                {id}
                              </li>
                            ))}
                          </ul>
                        </div>
                      ))}
                    </div>
                  ) : (
                    // 标签树
                    <div class='tree-wrap'>
                      {this.localTreeList.map(item =>
                        item.children.length ? (
                          <div class='group-item'>
                            <div class='group-title'>
                              <div class='title'>{`${item.groupName}( ${item.children.length} )`}</div>
                            </div>
                            <label-tree
                              checkedNode={this.localCheckNode}
                              mode='select'
                              treeData={item.children}
                              onCheckedChange={this.handleNodeChecked}
                            />
                          </div>
                        ) : undefined
                      )}
                    </div>
                  )
                }
              </div>
            </bk-popover>
          </div>
        )}
      </div>
    );
  }
}
