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
/* eslint-disable no-param-reassign */
/* eslint-disable @typescript-eslint/no-misused-promises */
import { TranslateResult } from 'vue-i18n';
import { Component, Emit, InjectReactive, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import { addListener, removeListener } from '@blueking/fork-resize-detector';

import { docCookies, LANGUAGE_COOKIE_KEY } from '../../../monitor-common/utils';
import { getEventPaths } from '../../../monitor-pc/utils';
import debounceDecorator from '../../common/debounce-decorator';
import EventModuleStore from '../../store/modules/event';

import { FilterInputStatus, ICommonItem, SearchType } from './typings/event';

import './filter-input.scss';

type PanelType = 'history' | 'field' | 'favorite';
type PanelShowType = false | 'method' | 'field' | 'condition' | 'value';
interface IFocusData {
  show?: PanelShowType;
  replaceStart?: number;
  nextText?: string;
  filedId?: string;
}
interface IListItem extends ICommonItem {
  queryString?: string;
  edit?: boolean;
  fakeName?: string;
  special?: boolean;
}
interface IFilterInputProps {
  value: string;
  searchType?: SearchType;
  inputStatus?: FilterInputStatus;
  valueMap?: Record<string, ICommonItem[]>;
  isFillId?: Boolean;
}
interface IFilterInputEvent {
  onBlur: string;
  onClear: string;
  onFavorite: string;
  onChange: string;
}
const textTypeList = ['field', 'method', 'value', 'condition'];

/* 处理字符串数组不能连续两个冒号 */
const valueListTidy = (list: string[]) => {
  const tempList = [];
  list.forEach(str => {
    const strArr = str.split('');
    strArr.forEach(s => {
      tempList.push(s);
    });
  });
  const tempArr = [];
  tempList.forEach(str => {
    const tempLen = tempArr.length;
    const lastThreeStr = `${tempArr[tempLen - 1]}${tempArr[tempLen - 2]}${tempArr[tempLen - 3]}`;
    if (!([' ', ':'].includes(str) && lastThreeStr === ' : ')) {
      tempArr.push(str);
    }
  });
  return tempArr;
};
class FilterText {
  endOffset: number;
  separator = ' ';
  fieldKey: FilterText;
  fieldValue: FilterText;
  constructor(
    public text: string,
    public startOffset: number,
    public dataType: string,
    separator?: string
  ) {
    this.endOffset = startOffset + text.length;
    this.separator = separator || ' ';
    if (dataType === 'field' && /\./.test(text)) {
      const list = text.split('.');
      const [fieldKey, fieldValue] = list;
      this.fieldKey = new FilterText(fieldKey, startOffset, 'fieldKey', '.');
      this.fieldValue = new FilterText(fieldValue, startOffset + fieldKey.length + 1, 'fieldValue');
    }
  }
  get joinText() {
    return `${this.text}${this.separator}`;
  }
  appendText(text: string) {
    this.text += ` ${text}`;
    this.endOffset += text.length + 1;
  }
}
@Component
export default class FilerInput extends tsc<IFilterInputProps, IFilterInputEvent> {
  @Prop({ default: '', required: true }) value: string;
  @Prop({ default: 'alert', type: String }) searchType: SearchType;
  @Prop({ default: 'success', type: String }) inputStatus: FilterInputStatus;
  // top n数据列表 用于构造
  @Prop({ default: () => ({}), type: Object }) valueMap: Record<string, ICommonItem[]>;
  @Prop({ default: false, type: Boolean }) isFillId: Boolean; // 选择候选值时填id还是填name
  @Ref('filterPanel') filterPanelRef: HTMLDivElement;
  @Ref('filterSearch') filterSearchRef: HTMLDivElement;
  @Ref('menuPanel') menuPanelRef: HTMLDivElement;
  @Ref('preText') preTextRef: HTMLDivElement;
  @Ref('input') inputRef: HTMLInputElement;
  // 是否是只读模式
  @InjectReactive('readonly') readonly readonly: boolean;
  inputValue = '';
  panelWidth = 0;
  popoverInstance: any = null;
  popoverMenuInstance: any = null;
  alertFieldList: IListItem[] = [];
  actionFieldList: IListItem[] = [];
  eventFieldList: IListItem[] = [];
  historyList: IListItem[] = [];
  favoriteList: IListItem[] = [];
  blurInPanel = false;
  methodList: IListItem[] = [
    {
      id: ':',
      name: ':'
    }
  ];
  conditionList: IListItem[] = [
    {
      id: 'AND',
      name: 'AND'
    },
    {
      id: 'OR',
      name: 'OR'
    }
  ];
  focusData: IFocusData = {};
  isManualInput = false; // 是否手动输入
  textList: FilterText[] = [];
  isEn = docCookies.getItem(LANGUAGE_COOKIE_KEY) === 'en';
  /* 添加可被移除的事件监听器 */
  mouseDowncontroller: AbortController = null;
  get menuList() {
    if (this.focusData.show === 'condition') return this.conditionList;
    if (this.focusData.show === 'method') return this.methodList;
    if (this.focusData.show === 'value') return this.valueMap?.[this.focusData.filedId] || [];
    return [];
  }
  get fieldList() {
    let list = [];
    switch (this.searchType) {
      case 'alert':
        list = this.alertFieldList;
        break;
      case 'action':
        list = this.actionFieldList;
        break;
      case 'event':
        list = this.eventFieldList;
        break;
    }
    return this.isEn ? list.map(item => ({ ...item, name: item.id })) : list;
  }

  get favoriteDisable() {
    return !Boolean(this.inputValue.length);
  }

  @Watch('value', { immediate: true })
  handleValueChange(v: string) {
    this.inputValue = v;
    if (!v) {
      this.isManualInput = false;
    }
  }
  @Watch('searchType', { immediate: true })
  handleSearchTypeChange() {
    this.handleGetSearchHistory();
    this.handleGetSearchFavorite();
  }
  created() {
    // 告警建议字段列表
    this.alertFieldList = [
      {
        id: 'id',
        name: this.$t('告警ID')
      },
      {
        id: 'alert_name',
        name: this.$t('告警名称')
      },
      {
        id: 'status',
        name: this.$t('状态')
      },
      {
        id: 'description',
        name: this.$t('告警内容')
      },
      {
        id: 'severity',
        name: this.$t('级别')
      },
      {
        id: 'metric',
        name: this.$t('指标ID')
      },
      {
        id: 'ip',
        name: this.$t('目标IP')
      },
      {
        id: 'ipv6',
        name: this.$t('目标IPv6')
      },
      {
        id: 'bk_host_id',
        name: this.$t('主机ID')
      },
      {
        id: 'bk_cloud_id',
        name: this.$t('目标云区域ID')
      },
      {
        id: 'bk_service_instance_id',
        name: this.$t('目标服务实例ID')
      },
      {
        id: 'appointee',
        name: this.$t('负责人')
      },
      {
        id: 'assignee',
        name: this.$t('通知人')
      },
      {
        id: 'follower',
        name: this.$t('关注人')
      },
      {
        id: 'strategy_name',
        name: this.$t('策略名称')
      },
      {
        id: 'strategy_id',
        name: this.$t('策略ID')
      },
      {
        id: 'labels',
        name: this.$t('策略标签')
      },
      {
        id: 'tags',
        name: this.$t('维度'),
        special: true
      },
      {
        id: 'action_id',
        name: `${this.$t('处理记录')}ID`
      },
      {
        id: 'plugin_id',
        name: this.$t('告警源')
      }
    ];
    // 事件建议字段列表
    this.eventFieldList = [
      {
        id: 'id',
        name: this.$t('全局事件ID')
      },
      {
        id: 'event_id',
        name: this.$t('事件ID')
      },
      {
        id: 'plugin_id',
        name: this.$t('插件ID')
      },
      {
        id: 'alert_name',
        name: this.$t('告警名称')
      },
      {
        id: 'status',
        name: this.$t('状态')
      },
      {
        id: 'description',
        name: this.$t('描述')
      },
      {
        id: 'severity',
        name: this.$t('级别')
      },
      {
        id: 'metric',
        name: this.$t('指标ID')
      },
      {
        id: 'assignee',
        name: this.$t('负责人')
      },
      {
        id: 'strategy_name',
        name: this.$t('策略名称')
      },
      {
        id: 'strategy_id',
        name: this.$t('策略ID')
      },
      {
        id: 'target_type',
        name: this.$t('目标类型')
      },
      {
        id: 'target',
        name: this.$t('目标')
      },
      {
        id: 'category',
        name: this.$t('分类')
      }
    ];
    // 处理记录建议字段列表
    this.actionFieldList = [
      {
        id: 'id',
        name: this.$t('处理记录ID')
      },
      {
        id: 'action_name',
        name: this.$t('套餐名称')
      },
      {
        id: 'action_config_id',
        name: this.$t('套餐ID')
      },
      {
        id: 'strategy_name',
        name: this.$t('策略名称')
      },
      {
        id: 'alerts',
        name: this.$t('关联告警')
      },
      {
        id: 'status',
        name: this.$t('状态')
      },
      {
        id: 'bk_biz_name',
        name: this.$t('业务名')
      },
      {
        id: 'bk_biz_id',
        name: this.$t('业务ID')
      },
      {
        id: 'operate_target_string',
        name: this.$t('执行对象')
      },
      // {
      //   id: 'bk_target_display',
      //   name: this.$t('目标')
      // },
      // {
      //   id: 'bk_set_names',
      //   name: this.$t('集群名称')
      // },
      // {
      //   id: 'bk_module_names',
      //   name: this.$t('模块名称')
      // },
      {
        id: 'action_plugin_type',
        name: this.$t('套餐类型')
      },
      {
        id: 'operator',
        name: this.$t('负责人')
      },
      {
        id: 'create_time',
        name: this.$t('开始时间')
      },
      {
        id: 'end_time',
        name: this.$t('结束时间')
      }
    ];
    this.isManualInput = false;
  }
  mounted() {
    addListener(this.filterSearchRef, this.handleUpdateResizePanel);
  }
  beforeDestroy() {
    this.destroyPopoverInstance();
    removeListener(this.filterSearchRef, this.handleUpdateResizePanel);
    this.mouseDowncontroller?.abort?.();
  }
  /**
   * @description 只适用于收藏部分的交互
   * @param event
   */
  handleMouseDown(event: Event) {
    const pathsClass = JSON.parse(JSON.stringify(getEventPaths(event).map(item => item.className)));
    if (
      !pathsClass.includes('filter-input-wrap') &&
      !pathsClass.includes('search-input') &&
      this.favoriteList.every(item => !item.edit)
    ) {
      this.destroyPopoverInstance();
    }
  }
  // 获取最近搜索记录
  async handleGetSearchHistory() {
    const data = await EventModuleStore.getListSearchHistory({ search_type: this.searchType });
    this.historyList = data
      ?.filter(item => item?.params?.query_string)
      .map((item, id) => ({ id, name: item.params.query_string }));
  }

  /**
   * @description: 收藏
   * @param {*}
   * @return {*}
   */
  async handleGetSearchFavorite() {
    const data = await EventModuleStore.getListSearchFavorite({ search_type: this.searchType });
    this.favoriteList = data
      ?.filter(item => item?.params?.query_string)
      .map(item => ({
        id: item.id,
        name: item.name,
        queryString: item.params.query_string,
        edit: false,
        fakeName: item.name
      }));
  }
  /**
   * @description: 创建收藏
   * @param {*}
   * @return {*}
   */
  async handleCreateSearchFavorite() {
    const data = await EventModuleStore.createSearchFavorite({
      search_type: this.searchType,
      name: this.inputValue,
      params: {
        query_string: this.inputValue
      }
    });
    this.$bkMessage({
      message: data ? this.$t('收藏成功') : this.$t('收藏失败'),
      theme: data ? 'success' : 'error'
    });
    if (data) {
      this.favoriteList.push({
        id: data.id,
        name: data.name,
        fakeName: data.name,
        queryString: data.params?.query_string || '',
        edit: false
      });
    }
  }
  /**
   * @description: 选择猪panel触发
   * @param {MouseEvent} e
   * @param {PanelType} id
   * @param {IListItem} item
   * @return {*}
   */
  handleSelectPanelItem(e: MouseEvent, id: PanelType, item: IListItem) {
    e.preventDefault();
    e.stopPropagation();
    if (id === 'field') {
      if (!this.inputValue?.length) {
        this.inputValue = item.special ? `${item.id}.` : `${item.name} : `;
        setTimeout(() => {
          this.handleInputFocus();
        }, 20);
        return;
      }
      this.handleReplaceInputValue(
        item.special ? `${item.id}.` : `${item.name.toString()} : `,
        item.special ? '' : ' '
      );
    } else if (id === 'history') {
      this.inputValue = String(item.name);
      this.blurInPanel = false;
      this.handleChange();
    } else if (id === 'favorite') {
      this.inputValue = item.queryString;
      this.blurInPanel = false;
      this.handleChange();
    }
  }
  /**
   * @description: 配置input输入与弹窗之间关系
   * @param {*}
   * @return {*}
   */
  handleSetInputValue(): Promise<IFocusData> {
    let valueText = this.inputValue.trimStart();
    while (/\s\s/g.test(valueText)) {
      valueText = valueText.replace(/\s\s/g, ' ');
    }
    this.inputValue = valueText;
    return new Promise(resolve => {
      setTimeout(() => {
        const offset = this.inputRef.selectionStart;
        const textList = this.handleGetTextList(valueText);
        this.textList = textList;
        const filterItemIndex = textList.findIndex(item => offset >= item.startOffset && offset <= item.endOffset);
        const filterItem = filterItemIndex > -1 ? textList[filterItemIndex] : null;
        if (!filterItem) {
          if (textList.length) {
            const item = textList[textList.length - 1];
            const index = textTypeList.findIndex(t => t === item.dataType) + 1;
            const dataType = textTypeList[index % 4];
            if (dataType === 'value') {
              for (let i = textList.length - 1; i >= 0; i--) {
                if (textList[i].dataType === 'field') {
                  const fieldItem = textList[i];
                  let filedId =
                    this.fieldList.find(set => set.id === fieldItem.text || set.name === fieldItem.text)?.id || '';
                  if (!filedId && fieldItem.fieldKey) {
                    filedId = fieldItem.text;
                  }
                  resolve({
                    show: dataType as PanelShowType,
                    replaceStart: item.endOffset + 1,
                    nextText: '',
                    filedId
                  });
                  break;
                }
              }
            } else {
              resolve({
                show: textTypeList[index % 4] as PanelShowType,
                replaceStart: item.endOffset + 1,
                nextText: ''
              });
            }
          } else {
            resolve({
              show: 'field',
              replaceStart: 0,
              nextText: ''
            });
          }
        } else {
          if (filterItem.dataType === 'value') {
            for (let i = filterItemIndex; i >= 0; i--) {
              if (textList[i].dataType === 'field') {
                const item = textList[i];
                let filedId = this.fieldList.find(set => set.id === item.text || set.name === item.text)?.id || '';
                if (!filedId && item.fieldKey) {
                  filedId = item.text;
                }
                resolve({
                  show: filterItem.dataType as PanelShowType,
                  replaceStart: filterItem.startOffset,
                  nextText: filterItem.text,
                  filedId
                });
                break;
              }
            }
          } else {
            const list = this[`${filterItem.dataType}List`] as IListItem[];
            const item = list.find(
              item => item.id.trim() === filterItem.text || item.name.toString().trim() === filterItem.text
            );
            if (item) {
              resolve({
                show: filterItem.dataType as PanelShowType,
                replaceStart: filterItem.startOffset,
                nextText: filterItem.text
              });
            } else if (filterItem.dataType === 'field' && filterItem.fieldKey) {
              if (offset >= filterItem.fieldKey.startOffset && offset <= filterItem.fieldKey.endOffset) {
                resolve({
                  show: 'field',
                  replaceStart: filterItem.startOffset,
                  nextText: filterItem.text
                });
              } else if (
                filterItem.fieldValue &&
                offset >= filterItem.fieldValue.startOffset &&
                offset <= filterItem.fieldValue.endOffset
              ) {
                resolve({
                  show: 'value',
                  replaceStart: filterItem.fieldValue.startOffset,
                  nextText: filterItem.fieldValue.text,
                  filedId: filterItem.fieldKey.text
                });
              }
            }
          }
          resolve({
            show: false,
            replaceStart: -1,
            nextText: ''
          });
        }
      }, 20);
    });
  }
  handleGetTextList(valueText: string) {
    const list = valueText.split(/\s(and|or)/i);
    const textList: FilterText[] = [];
    let startOffset = 0;
    list
      .filter(t => t.length)
      .forEach((text, index) => {
        if (['and', 'or'].includes(text.toLocaleLowerCase())) {
          textList.push(new FilterText(text, startOffset, 'condition'));
        } else {
          const tlist = text.trim().split(' ');
          const hasCondition = index > 0 ? textList[textList.length - 1].dataType === 'condition' : true;
          let tOffset = startOffset;
          tlist
            .filter(t => t.length)
            .forEach((t, i) => {
              // eslint-disable-next-line no-nested-ternary
              const dataType = hasCondition ? (i === 0 ? 'field' : i === 1 ? 'method' : 'value') : 'value';
              if (t) {
                if (dataType === 'value' && textList[textList.length - 1].dataType === 'value') {
                  textList[textList.length - 1].appendText(t);
                } else {
                  textList.push(new FilterText(t, tOffset, dataType));
                }
              }
              tOffset += t.length + 1;
            });
        }
        startOffset += text.trim().length + 1;
        startOffset = Math.min(startOffset, valueText.length);
      });
    return textList;
  }
  /**
   * @description: 用于变更input值
   * @param {string} name
   * @return {*}
   */
  handleReplaceInputValue(name: string, seperator = ' ') {
    const { show, nextText, replaceStart } = this.focusData;
    const valueList = this.inputValue.split('');
    let selection = 0;
    if (show) {
      if (nextText) {
        valueList.splice(replaceStart, nextText.length, name).join('');
        selection = replaceStart + name.length + 1;
      } else {
        valueList.splice(replaceStart, 0, `${name}${seperator}`).join('');
        selection = replaceStart + `${name}${seperator}`.length;
      }
      this.inputValue = valueListTidy(valueList).join('');
      if (this.inputValue.length < selection) {
        this.inputValue = this.inputValue + seperator;
      }
    } else {
      this.inputValue += `${name}${seperator}`;
      selection = this.inputValue.length;
    }
    this.inputRef.selectionStart = selection;
    this.inputRef.selectionEnd = selection;
    setTimeout(() => {
      this.inputRef.selectionStart = selection;
      this.inputRef.selectionEnd = selection;
      this.handleInputFocus();
    }, 20);
  }
  /**
   * @description: input focus时触发
   * @param {*}
   * @return {*}
   */
  async handleInputFocus() {
    if (this.inputValue?.trim?.().length < 1) {
      this.handleMainPopoverShow();
      return;
    }
    const ret = await this.handleSetInputValue();
    if (ret.show === 'field') {
      this.focusData = ret;
      this.handleMainPopoverShow();
    } else if (['method', 'condition', 'value'].includes(ret.show.toString())) {
      this.focusData = ret;
      if (ret.show.toString() === 'value' && !this.menuList.length) {
        this.destroyMenuPopoverInstance();
        this.destroyPopoverInstance();
        return;
      }
      this.handleMenuPopoverShow();
    } else {
      this.destroyMenuPopoverInstance();
      this.destroyPopoverInstance();
      this.focusData = {};
    }
  }
  @debounceDecorator(20)
  handleUpdateResizePanel() {
    if (this.popoverInstance?.state?.isShown) {
      this.panelWidth = this.filterSearchRef.getBoundingClientRect().width - 64;
      this.popoverInstance.set({
        content: this.filterPanelRef
      });
      this.popoverInstance.popperInstance?.update?.();
      this.popoverInstance.show?.(100);
    }
  }
  /**
   * @description: 主弹窗弹出触发
   * @param {function} onShown
   * @return {*}
   */
  handleMainPopoverShow(onShown?: () => void) {
    this.destroyMenuPopoverInstance();
    this.panelWidth = this.filterSearchRef.getBoundingClientRect().width - 64;
    if (!this.popoverInstance) {
      this.popoverInstance = this.$bkPopover(this.filterSearchRef, {
        content: this.filterPanelRef,
        trigger: 'manul',
        theme: 'light common-monitor',
        arrow: false,
        offset: '-32, 0',
        placement: 'bottom',
        hideOnClick: false,
        interactive: true,
        onShown: () => {
          typeof onShown === 'function' && onShown();
        }
      });
    } else {
      this.popoverInstance.set({
        content: this.filterPanelRef,
        onShown: () => {
          typeof onShown === 'function' && onShown();
        }
      });
    }
    this.popoverInstance?.popperInstance?.update?.();
    this.popoverInstance?.show?.(100);
    this.mouseDowncontroller = new AbortController();
    document.addEventListener('mousedown', this.handleMouseDown, { signal: this.mouseDowncontroller.signal });
  }
  /**
   * @description: menu弹窗触发
   * @param {*}
   * @return {*}
   */
  handleMenuPopoverShow() {
    this.destroyPopoverInstance();
    setTimeout(() => {
      const rect = this.preTextRef.getBoundingClientRect();
      const offsetX = rect.width + 40;
      const offsetY = -2;
      if (!this.popoverMenuInstance) {
        this.popoverMenuInstance = this.$bkPopover(this.filterSearchRef, {
          content: this.menuPanelRef,
          arrow: false,
          flip: false,
          flipBehavior: 'bottom',
          trigger: 'manul',
          placement: 'bottom-start',
          theme: 'light common-monitor',
          hideOnClick: false,
          interactive: true,
          offset: `${offsetX}, ${offsetY}`
        });
      } else {
        this.popoverMenuInstance.set({
          offset: `${offsetX}, ${offsetY}`
        });
      }
      this.popoverMenuInstance?.popperInstance?.update?.();
      this.popoverMenuInstance?.show?.(100);
    }, 20);
  }
  destroyPopoverInstance() {
    this.blurInPanel = false;
    this.popoverInstance?.hide?.(0);
    this.popoverInstance?.destroy?.();
    this.popoverInstance = null;
    this.mouseDowncontroller?.abort?.();
  }
  destroyMenuPopoverInstance() {
    this.blurInPanel = false;
    this.popoverMenuInstance?.hide?.(0);
    this.popoverMenuInstance?.destroy?.();
    this.popoverMenuInstance = null;
  }
  /**
   * @description: 用户输入时触发
   * @param {any} e
   * @return {*}
   */
  handleInput(e: any) {
    this.inputValue = e.target.value;
  }
  /**
   * @description: 失焦时触发
   * @param {*}
   * @return {*}
   */
  handleBlur() {
    if (!this.blurInPanel) {
      this.$emit('blur', this.inputValue);
      this.handleChange();
    }
  }
  /**
   * @description: 搜索条件变更时触发
   * @param {*}
   * @return {*}
   */
  handleChange() {
    if (!this.blurInPanel) {
      this.popoverInstance?.hide?.(0);
      this.popoverMenuInstance?.hide?.(0);
      this.handleGetSearchHistory();
      this.$emit('change', this.inputValue);
    }
  }
  /**
   * @description: key down事件
   * @param {KeyboardEvent} e
   * @return {*}
   */
  handleKeydown(e: KeyboardEvent) {
    if (e.code === 'Enter') {
      e.preventDefault();
      e.stopPropagation();
      this.handleChange();
    } else if (e.code === 'Space' || e.code === 'Backspace') {
      setTimeout(() => {
        this.handleInputFocus();
      }, 16);
    } else {
      // 是否手动输入
      this.isManualInput = true;
    }
  }
  /**
   * @description: 选择 condition method时触发
   * @param {MouseEvent} e
   * @param {IListItem} item
   * @return {*}
   */
  handleSelectMenuItem(e: MouseEvent, item: IListItem) {
    e.preventDefault();
    e.stopPropagation();
    this.handleReplaceInputValue(this.isFillId ? item.id.toString() : item.name.toString());
  }
  /**
   * @description: 点击收藏触发
   * @param {MouseEvent} e
   * @return {*}
   */
  handleSetFavorite(e: MouseEvent) {
    if (this.favoriteDisable) return;
    e.preventDefault();
    if (this.inputValue?.length) {
      this.handleRemoveNewFavorite();
      this.inputValue &&
        this.favoriteList.unshift({
          name: '',
          id: 'favorite',
          fakeName: '',
          queryString: '',
          edit: true
        });
      this.favoriteList.forEach(item => {
        if (!!item.name) {
          item.edit = false;
          item.fakeName = String(item.name);
        }
      });
      this.handleMainPopoverShow(() => {
        setTimeout(() => {
          this.blurInPanel = true;
          (this.$refs['favorite-input-favorite'] as any)?.focus();
        }, 20);
      });
      this.$emit('favorite');
    } else {
      this.handleMainPopoverShow();
    }
    // this.inputValue && this.handleCreateSearchFavorite()
  }
  @Emit('clear')
  handleClear(e: MouseEvent) {
    e.preventDefault();
    this.inputValue = '';
    this.isManualInput = false;
    return '';
  }
  /**
   * @description: 编辑收藏条件时触发
   * @param {MouseEvent} e
   * @param {IListItem} item
   * @return {*}
   */
  handleEidtFavorite(e: MouseEvent, item: IListItem) {
    e.preventDefault();
    e.stopPropagation();
    this.blurInPanel = true;
    item.edit = true;
    setTimeout(() => {
      (this.$refs[`favorite-input-${item.id}`] as any)?.focus();
    }, 20);
  }
  /**
   * @description: 清空上次收藏内容
   * @param {*}
   * @return {*}
   */
  handleRemoveNewFavorite() {
    const index = this.favoriteList.findIndex(item => item.id === 'favorite');
    index > -1 && this.favoriteList.splice(index, 1);
  }
  /**
   * @description: 编辑收藏触发
   * @param {MouseEvent} e
   * @param {IListItem} item
   * @return {*}
   */
  async handleUpdateFavorite(e: MouseEvent, item: IListItem) {
    if (!item?.fakeName?.trim?.().length) {
      e.preventDefault();
      e.stopPropagation();
      return;
    }
    if (/(\ud83c[\udf00-\udfff])|(\ud83d[\udc00-\ude4f\ude80-\udeff])|[\u2600-\u2B55]/g.test(item.fakeName)) {
      this.$bkMessage({
        message: this.$t('不能输入emoji表情'),
        theme: 'error'
      });
      e.preventDefault();
      e.stopPropagation();
      return;
    }
    if (item.fakeName !== item.name) {
      // 新建收藏
      if (item.id === 'favorite') {
        if (this.favoriteList.some(f => f.name === item.fakeName)) {
          this.$bkMessage({
            message: this.$t('名称重复'),
            theme: 'error'
          });
          e.preventDefault();
          e.stopPropagation();
          return;
        }
        const data = await EventModuleStore.createSearchFavorite({
          search_type: this.searchType,
          name: item.fakeName,
          params: {
            query_string: this.inputValue
          }
        });
        this.$bkMessage({
          message: data ? this.$t('收藏成功') : this.$t('收藏失败'),
          theme: data ? 'success' : 'error'
        });
        if (data) {
          this.favoriteList.unshift({
            id: data.id,
            name: data.name,
            fakeName: data.name,
            queryString: data.params?.query_string || '',
            edit: false
          });
        }
        item.edit = !data;
      } else {
        const data = await EventModuleStore.updateSearchFavorite({
          id: item.id,
          params: {
            name: item.fakeName
          }
        });
        this.$bkMessage({
          message: data ? this.$t('更新成功') : this.$t('更新失败'),
          theme: data ? 'success' : 'error'
        });
        item.name = data ? item.fakeName : item.name;
        item.edit = !data;
      }
    }
  }
  // 删除收藏触发
  async handleDeleteFavorite(e: MouseEvent, item: IListItem, index: number) {
    e.stopPropagation();
    this.blurInPanel = true;
    const data = await EventModuleStore.destroySearchFavorite(item.id);
    this.$bkMessage({
      message: data ? this.$t('删除成功') : this.$t('删除失败'),
      theme: data ? 'success' : 'error'
    });
    if (data) {
      this.favoriteList.splice(index, 1);
      item.edit = false;
    }
    await this.$nextTick();
    this.inputRef.focus();
    this.blurInPanel = false;
  }
  handleFavoriteInputBlur(e: MouseEvent, item: IListItem) {
    if (item.id === 'favorite') {
      this.blurInPanel = false;
      // this.inputRef.focus();
      // this.handleInputFocus();
    }
    this.handleRemoveNewFavorite();
    item.edit = false;
  }
  commonPanelComponent(id: PanelType, list: IListItem[]) {
    return (
      <ul class='panel-list'>
        {list.map((item, index) => (
          <li
            onMousedown={e => !item.edit && this.handleSelectPanelItem(e, id, item)}
            class={[
              'panel-list-item',
              {
                'item-active':
                  id === 'field' &&
                  this.focusData.show === 'field' &&
                  (item.id === this.focusData.nextText || item.name === this.focusData.nextText)
              }
            ]}
            key={item.id}
          >
            {!item.edit && <span>{item.name}</span>}
            {id === 'field' && !item.edit && !this.isEn && <span class='item-id'>({item.id})</span>}
            {id === 'favorite' &&
              !item.edit && [
                <i
                  class='icon-monitor icon-bianji edit-icon'
                  onMousedown={e => this.handleEidtFavorite(e, item)}
                />,
                <i
                  class='icon-monitor icon-mc-close close-icon'
                  onMousedown={e => this.handleDeleteFavorite(e, item, index)}
                />
              ]}
            {id === 'favorite' &&
              item.edit && [
                <bk-input
                  ref={`favorite-input-${item.id}`}
                  class='favorite-input'
                  type='text'
                  v-model={item.fakeName}
                  placeholder={this.$t('输入收藏名称')}
                  on-blur={e => this.handleFavoriteInputBlur(e, item)}
                />,
                <i
                  class={[
                    'icon-monitor icon-mc-check-small check-icon',
                    { 'is-diabled': !item?.fakeName?.trim?.().length }
                  ]}
                  /*  */
                  onMousedown={e => this.handleUpdateFavorite(e, item)}
                />
              ]}
          </li>
        ))}
      </ul>
    );
  }
  panelEmptyComponent(content?: string | TranslateResult) {
    return <div class='panel-empty'>{content || this.$t('暂无数据')}</div>;
  }
  render() {
    return (
      <div
        class='filter-input-wrap'
        ref='filterSearch'
      >
        <div
          class='filter-search'
          style={{ borderColor: this.inputStatus === 'error' ? '#ff5656' : '#c4c6cc' }}
        >
          <i class='icon-monitor icon-filter-fill filter-icon' />
          <input
            ref='input'
            class='search-input'
            spellcheck={false}
            placeholder={String(this.$t('输入搜索条件'))}
            onMousedown={this.handleInputFocus}
            onInput={this.handleInput}
            onBlur={this.handleBlur}
            onKeydown={this.handleKeydown}
            v-model={this.inputValue}
          ></input>
          <span
            ref='preText'
            class='pre-text'
          >
            {this.inputValue.slice(0, this.focusData.replaceStart)}
          </span>
          <i
            class='icon-monitor icon-mc-close-fill filter-clear'
            style={{ display: this.inputValue?.trim().length ? 'flex' : 'none' }}
            v-bk-tooltips={this.$t('清空搜索条件')}
            onMousedown={this.handleClear}
          />
        </div>
        <span
          class={['filter-favorites', { 'is-disable': this.favoriteDisable }]}
          v-en-class='en-lang'
          onMousedown={this.handleSetFavorite}
        >
          <i class='icon-monitor icon-mc-uncollect favorite-icon'></i>
          {this.$t('收藏')}
        </span>
        <div style='display: none;'>
          <div
            class='filter-input-panel'
            ref='filterPanel'
            style={{ width: `${this.panelWidth}px` }}
          >
            <div class='field-panel common-panel'>
              <div class='panel-title'>{this.$t('建议字段')}</div>
              {this.fieldList?.length ? this.commonPanelComponent('field', this.fieldList) : this.panelEmptyComponent()}
            </div>
            <div class='search-panel common-panel'>
              <div class='panel-title'>{this.$t('最近搜索')}</div>
              {this.historyList?.length
                ? this.commonPanelComponent('history', this.historyList)
                : this.panelEmptyComponent(this.$t('暂无搜索'))}
            </div>
            <div class='favorite-panel common-panel'>
              <div class='panel-title'>{this.$t('收藏')}</div>
              {this.favoriteList?.length
                ? this.commonPanelComponent('favorite', this.favoriteList)
                : this.panelEmptyComponent(this.$t('暂无收藏'))}
            </div>
          </div>
        </div>
        <div style='display: none;'>
          <ul
            class='condition-list'
            ref='menuPanel'
          >
            {this.menuList.length
              ? this.menuList.map(item => (
                  <li
                    key={item.id}
                    class={[
                      'condition-list-item',
                      {
                        'item-active': item.id === this.focusData.nextText || item.name === this.focusData.nextText
                      }
                    ]}
                    onMousedown={e => this.handleSelectMenuItem(e, item)}
                  >
                    {item.name.toString().replace(/"/gm, '')}
                  </li>
                ))
              : undefined}
          </ul>
        </div>
      </div>
    );
  }
}
