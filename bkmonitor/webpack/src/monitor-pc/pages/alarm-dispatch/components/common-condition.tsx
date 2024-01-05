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
import { Component, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { Debounce, random } from '../../../../monitor-common/utils';
import { getEventPaths } from '../../../utils';
import { CONDITIONS, ICondtionItem, METHODS } from '../typing';
import { conditionCompare, conditionsInclues, ISpecialOptions, TGroupKeys, TValueMap } from '../typing/condition';

import './common-condition.scss';

interface IListItem {
  id: string;
  name: string;
  isCheck?: boolean;
  isStrategyId?: boolean;
  first_label_name?: string; // 适用于策略id
  isGroupKey?: boolean;
}

const groupNamesMap = {
  tags: window.i18n.t('标签'),
  dimensions: window.i18n.t('维度')
};

enum TypeEnum {
  input = 'input',
  key = 'key',
  value = 'value',
  method = 'method',
  condition = 'condition',
  null = ''
}

const NULL_NAME = `-${window.i18n.t('空')}-`;
const settingPopClassName = 'common-condition-component-settings-msg';

interface ITagItem {
  type: TypeEnum;
  id: string;
  name: string;
  alias?: string; // 别名， 标签和维度的key 需要有别名
}

interface IProps {
  value: ICondtionItem[];
  keyList?: IListItem[];
  valueList?: IListItem[];
  valueMap?: TValueMap;
  groupKeys?: TGroupKeys;
  groupKey?: string[];
  readonly?: boolean;
  specialOptions?: ISpecialOptions;
  settingsValue?: ICondtionItem[];
  loading?: boolean;
  needValidate?: boolean;
  onChange?: (v: ICondtionItem[]) => void;
  onSettingsChange?: () => void;
  onValidate?: (v: boolean) => void;
  onRepeat?: (v: boolean) => void;
}

@Component
export default class CommonCondition extends tsc<IProps> {
  /* 当前condition */
  @Prop({ default: () => [], type: Array }) value: ICondtionItem[];
  /* 可供选择的key选项 */
  @Prop({ default: () => [], type: Array }) keyList: IListItem[];
  /* key对应的value选项集合 */
  @Prop({ default: () => new Map(), type: Map }) valueMap: TValueMap;
  /* 组合项key 如 dimension.xxx  tags.xxxx*/
  @Prop({ default: () => new Map(), type: Map }) groupKeys: TGroupKeys;
  /* 组合项key前缀，如命中前缀可展开groupKeys内的选项以供选择 */
  @Prop({ default: () => [], type: Array }) groupKey: string[];
  /* 是否为只读模式 */
  @Prop({ default: false, type: Boolean }) readonly: boolean;
  /* 是否包含特殊情况(如果包含的特殊的kv则会添加一些特别的可选项) 暂时只包含维度的特殊选项 */
  @Prop({ default: () => ({}), type: Object }) specialOptions: ISpecialOptions;
  /* 当前统一设置的条件 如有条件 */
  @Prop({ default: () => [], type: Array }) settingsValue: ICondtionItem[];
  @Prop({ default: false, type: Boolean }) loading: boolean;
  /* 是否需要校验 */
  @Prop({ default: false, type: Boolean }) needValidate: boolean;

  @Ref('input') inputRef: HTMLInputElement;
  @Ref('wrap') wrapRef: HTMLDivElement;
  @Ref('settingsMsg') settingsMsgRef: HTMLDivElement;
  @Ref('secondWrap') secondWrapRef: HTMLDivElement;

  /* 数据列表 */
  locaLValue: ICondtionItem[] = [];
  /* 当前输入的文本 */
  inputValue = '';
  /* 当前展开的列表 */
  curList: IListItem[] = [];
  /* 弹出层实例 */
  popInstance = null;
  /* 是否已弹出 */
  isShowPop = false;
  /* 当前tag 列表 */
  tagList: ITagItem[] = [];
  /* 是否显示添加按钮（codition） */
  showAdd = false;
  /* 是否已弹出condition 选项 */
  showPopOfCondition = false;
  /* value选项列表头部的搜索 */
  valueSearch = '';
  /* 当前组件唯一id 用于清除弹出层时的判断 */
  componetId = '';
  /* 添加可被移除的事件监听器 */
  controller: AbortController = null;
  /* 当前弹出类型是否为value */
  isPopTypeOfValue = false;
  /* 当前点击处的下标 */
  curIndex = 0;
  /* 是否点击了tag而弹出选项 */
  isClickTagOfPop = false;
  /* 是否点击key(选项包含删除) */
  isClickKeyTag = false;
  /* 是否点击method */
  isClickMethodTag = false;
  /* 是否点击了condition */
  isClickConditonTag = false;
  /* 是否点击了value tag */
  isClickValueTag = false;
  /* 当前点击后的tag下标 适用于 method condition的切换 */
  curTagIndex = 0;
  /* 缓存当前tagList */
  tagListCache: ITagItem[] = [];
  /* 统一设置提示弹出层实例 */
  settingsPopInstance = null;
  /* key选项二级列表 */
  keyListSecond: IListItem[] = [];
  /* 二级选项pop实例 */
  secondPopInstance = null;
  /* 是否点击了组合key */
  isClickGroupKey = false;
  /* 当前展示的组合key */
  curGroupKey = '';
  /* 是否提示校验 */
  isErr = false;
  /* 是否重复 */
  isRepeat = false;
  /* 是否弹出统一设置弹层 */
  isShowSettingPop = false;

  /* 是否为固定选项 method 及 condition */
  get isAbsoluteOpts() {
    const curList = this.curList.map(item => ({ id: item.id, name: item.name }));
    return (
      JSON.stringify(curList) === JSON.stringify(METHODS) || JSON.stringify(curList) === JSON.stringify(CONDITIONS)
    );
  }

  created() {
    this.componetId = random(8);
    this.locaLValue = [...this.value];
    this.curList = [...this.keyList];
    this.tagList = [{ type: TypeEnum.input, id: '', name: '' }];
    this.handleConditionToTagList();
  }
  destroyed() {
    this.controller?.abort?.();
  }

  handleMouseEnter() {
    this.controller?.abort?.();
    this.controller = new AbortController();
    document.addEventListener('mouseup', this.handleMouseup, { signal: this.controller.signal });
  }

  handleMouseLeave() {
    if (this.popInstance?.show || this.isShowPop) {
      return;
    }
    this.controller?.abort?.();
  }

  @Watch('value')
  handleWatchValue(v) {
    const locaLValue = JSON.stringify(v);
    const propValue = JSON.stringify(v);
    if (locaLValue !== propValue) {
      this.locaLValue = [...this.value];
      if (this.isShowPop) {
        this.inputValue = '';
        this.handlePopoerHidden();
        this.resetInputPosition();
      }
      this.handleConditionToTagList();
    }
  }

  /* 点击组件 */
  handleClickComponent(event?: Event) {
    this.validate(true);
    if (this.readonly) {
      return;
    }
    if (!!this.popInstance?.show) {
      this.handlePopoerHidden();
      return;
    }
    if (!!this.settingsPopInstance?.show) {
      this.handleSettingsPopHidden();
    }
    event.stopPropagation();
    const lastTagItem2 = this.tagList?.[this.tagList.length - 2];
    const lastTagItem = this.tagList[this.tagList.length - 1];
    if (lastTagItem2?.type === TypeEnum.method || lastTagItem2?.type === TypeEnum.value) {
      /* value 类型可多选 */
      this.isPopTypeOfValue = true;
      this.isClickValueTag = false;
      this.curIndex = this.tagList.length - 1;
      const selectedList = this.getTargetIndexValues(this.curIndex);
      const valueList = this.getCurIndexOfValues(this.curIndex);
      this.curList = valueList.map(v => ({
        ...v,
        isCheck: selectedList.includes(v.id)
      }));
    } else if (
      (lastTagItem2?.type === TypeEnum.condition || this.tagList.length === 1) &&
      lastTagItem.type === TypeEnum.input
    ) {
      this.curList = [...this.getFilterKeyList()];
    } else if (lastTagItem2?.type === TypeEnum.key && lastTagItem.type === TypeEnum.input) {
      this.curList = METHODS;
    }
    this.$nextTick(() => {
      this.inputRef?.focus?.();
      this.handleShowPop();
    });
  }

  handBlur() {
    this.inputValue = '';
  }

  /* 监听输入，判断是否输入了组合key的前缀 */
  @Debounce(300)
  handleInput() {
    // console.log('input', this.inputValue);
  }

  @Debounce(100)
  showPopFn(event?: Event) {
    const target = event?.target || this.inputRef;
    this.popInstance = this.$bkPopover(target, {
      content: this.wrapRef,
      trigger: 'manual',
      interactive: true,
      theme: 'light common-monitor',
      arrow: false,
      placement: 'bottom-start',
      boundary: 'window',
      hideOnClick: false
    });
    this.popInstance?.show?.();
  }

  /* 展开选项 */
  handleShowPop(event?: Event) {
    this.isShowPop = true;
    this.showPopFn(event);
  }
  /* 清除弹出层 */
  handlePopoerHidden() {
    this.popInstance?.hide?.(0);
    this.popInstance?.destroy?.();
    this.popInstance = null;
    this.isShowPop = false;
  }

  /* 选择选项 */
  handleOptionClick(item: IListItem) {
    const len = this.tagList.length;
    this.curIndex = this.tagList.findIndex(t => t.type === TypeEnum.input) || len - 1;
    const showPop = () => {
      this.$nextTick(() => {
        this.handleShowPop();
      });
    };
    // 选择key
    const selectKey = () => {
      if (!this.groupKey.includes(item.id)) {
        const opt = {
          type: 'key',
          id: item.id,
          name: item.name
        };
        if (len === 1) {
          this.tagList.unshift(opt as any);
        } else {
          this.tagList.splice(this.curIndex, 0, opt as any);
        }
        this.curList = METHODS;
        showPop();
      } else {
        this.handleHiddenKeySecond();
      }
      // const tempKeys = this.getDimensionKeys() as any;
      // if (this.groupKey.includes(item.id) && !!(this.groupKeys.get(item.id)
      //   || tempKeys
      //   || []).length) {
      //   setTimeout(() => {
      //     this.handleSelectGroupKey(item.id, len === 1 ? 0 : this.curIndex);
      //   }, 50);
      // } else {
      //   showPop();
      // }
    };
    // 选择 method
    const selectMethod = () => {
      this.tagList.splice(this.curIndex, 0, {
        type: TypeEnum.method,
        name: item.name,
        id: item.id
      });
      const valueList = this.getCurIndexOfValues(this.curIndex);
      this.curList = [...valueList];
      if (this.curList.length) {
        showPop();
      } else {
        this.isClickValueTag = true;
      }
    };
    // 选择value
    const selectValue = () => {
      // 选择value 时可多选 弹出时 获取当前已选项
      this.curList = this.curList.map(v => ({
        ...v,
        isCheck: item.id === v.id ? !v?.isCheck : !!v?.isCheck
      }));
      if (!this.curList.length) {
        this.isClickValueTag = true;
      }
    };
    // 选择condition
    const selectCondition = () => {
      this.tagList.splice(this.curIndex, 0, {
        type: TypeEnum.condition,
        name: item.name,
        id: item.id
      });
      this.showAdd = false;
      this.showPopOfCondition = false;
      this.curList = [...this.getFilterKeyList()];
      showPop();
    };
    if (!this.isPopTypeOfValue && !this.isClickValueTag) {
      this.handlePopoerHidden();
    }
    const lastTagItem = this.tagList[this.curIndex];
    const lastTagItem2 = this.tagList?.[this.curIndex - 1];
    // debugger;
    if (!lastTagItem2) {
      selectKey();
      return;
    }
    if (this.showPopOfCondition) {
      selectCondition();
      return;
    }
    if (this.isClickKeyTag) {
      this.tagList.splice(this.curTagIndex, 1, {
        type: TypeEnum.key,
        id: item.id,
        name: item.name
      });
      this.handlePopoerHidden();
      this.isClickKeyTag = false;
      this.resetInputPosition();
      this.handleChange();
      return;
    }
    if (this.isClickValueTag) {
      selectValue();
      return;
    }
    /* 仅点击method与condition弹出的选项用此逻辑 */
    if (this.isClickMethodTag || this.isClickConditonTag) {
      const type = this.isClickMethodTag ? TypeEnum.method : TypeEnum.condition;
      this.tagList.splice(this.curTagIndex, 1, {
        type,
        id: item.id,
        name: item.name
      });
      this.handlePopoerHidden();
      this.isClickMethodTag = false;
      this.isClickConditonTag = false;
      this.resetInputPosition();
      this.handleChange();
      return;
    }
    if (lastTagItem2.type === TypeEnum.condition && lastTagItem.type === TypeEnum.input) {
      selectKey();
    } else if (lastTagItem2.type === TypeEnum.key) {
      selectMethod();
    } else if (lastTagItem2.type === TypeEnum.method || lastTagItem2.type === TypeEnum.value) {
      selectValue();
    }
    this.isPopTypeOfValue = [TypeEnum.method, TypeEnum.key, TypeEnum.value].includes(lastTagItem2.type);
  }

  /* 点击添加按钮并弹出condition选项 */
  handleAddClick(event: Event) {
    event.stopPropagation();
    this.handlePopoerHidden();
    this.isPopTypeOfValue = false;
    this.isClickValueTag = false;
    this.curList = CONDITIONS;
    this.$nextTick(() => {
      this.handleShowPop(event);
      this.showPopOfCondition = true;
    });
  }

  /* 重置输入框位置 */
  resetInputPosition() {
    const inputItemIndex = this.tagList.findIndex(item => item.type === TypeEnum.input);
    if (inputItemIndex > -1 && inputItemIndex !== this.tagList.length - 1) {
      this.tagList.splice(inputItemIndex, 1);
      this.tagList[this.tagList.length - 1].type = TypeEnum.input;
    }
    if (!!this.locaLValue.length) {
      if (this.tagList[this.tagList.length - 2]?.type === TypeEnum.condition) {
        this.tagList.splice(this.tagList.length - 2, 1);
        this.showAdd = true;
      }
    }
    this.inputValue = '';
  }

  /* 收起弹出层 */
  handleMouseup(event: Event) {
    const paths = JSON.parse(JSON.stringify(getEventPaths(event).map(item => item.id)));
    const pathsClass = JSON.parse(JSON.stringify(getEventPaths(event).map(item => item.className)));
    /* 判断统一设置提示弹出hide方式 */
    if (!pathsClass.includes(settingPopClassName)) {
      if (this.isShowSettingPop) {
        this.handleSettingsPopCancel();
      }
    }
    if (paths.includes(this.componetId)) return;
    this.validate();
    if (this.popInstance) {
      this.handlePopoerHidden();
    }
    this.resetInputPosition();
    this.isClickKeyTag = false;
    this.isClickMethodTag = false;
    this.isClickConditonTag = false;
    this.showPopOfCondition = false;
    this.valueSearch = '';
    if (this.isPopTypeOfValue || this.isClickValueTag) {
      let targetIndex = this.curIndex;
      if (this.isClickValueTag) {
        targetIndex = this.curTagIndex;
      }
      const oldSelects = this.getTargetIndexValues(targetIndex);
      const customLabels = [];
      const curListSelects = this.curList
        .filter(c => !!c?.isCheck)
        .map(c => ({ id: c.id, name: c.name, type: TypeEnum.value }));
      const curListIds = this.curList.map(c => c.id);
      oldSelects.forEach(o => {
        if (!curListIds.includes(o)) {
          customLabels.push({
            id: o,
            name: o,
            type: TypeEnum.value
          });
        }
      });
      const valueList = this.getCurIndexOfValues(targetIndex);
      if (valueList.length) {
        this.handleReplaceValue(targetIndex, [...curListSelects, ...customLabels]);
      }
      this.isPopTypeOfValue = false;
      this.isClickValueTag = false;
    }
  }

  /* 根据当前下标获取附近的value值 */
  getTargetIndexValues(index: number, isInput = false): string[] {
    const tempSet = new Set();
    let targetIndex = index;
    if (isInput) {
      targetIndex = index + 1;
    }
    for (let i = targetIndex; i <= this.tagList.length - 1; i++) {
      const item = this.tagList[i];
      if (item?.type !== TypeEnum.value) {
        break;
      }
      tempSet.add(item.id);
    }
    if (isInput) {
      targetIndex = index;
    }
    for (let i = targetIndex - 1; i >= 0; i--) {
      const item = this.tagList[i];
      if (item?.type !== TypeEnum.value) {
        break;
      }
      tempSet.add(item.id);
    }
    return Array.from(tempSet) as string[];
  }

  /* 根据当前下标替换value值 */
  handleReplaceValue(index: number, values: ITagItem[]) {
    /* 判断是否与统一设置匹配 如果匹配则缓存一份数据 */
    let isIncluesSettings = false;
    let oldCondition = null;
    if (this.settingsValue.length) {
      oldCondition = this.getConditionOfIndex(index);
      isIncluesSettings = conditionsInclues(oldCondition, this.settingsValue);
      if (isIncluesSettings) {
        this.tagListCache = JSON.parse(JSON.stringify(this.tagList));
      }
    }
    /* 替换 */
    const targetValues = JSON.parse(JSON.stringify(values));
    const delIndex = values.findIndex(v => v.name === '');
    if (delIndex >= 0) {
      targetValues.splice(delIndex, 1);
    }
    let startIndex = index;
    let endIndex = index;
    for (let i = index; i <= this.tagList.length - 1; i++) {
      const item = this.tagList[i];
      if (item.type !== TypeEnum.value) {
        endIndex = i;
        break;
      }
    }
    for (let i = index - 1; i >= 0; i--) {
      const item = this.tagList[i];
      if (item.type !== TypeEnum.value) {
        break;
      }
      startIndex = i;
    }
    // const isStragety = this.getCurIndexKey(startIndex) === 'alert.strategy_id';
    // if (isStragety) {
    //   // 策略id 需显示id即可
    //   this.tagList.splice(startIndex, endIndex - startIndex, ...targetValues.map(t => ({
    //     ...t,
    //     name: t.id
    //   })));
    // } else {
    //   this.tagList.splice(startIndex, endIndex - startIndex, ...targetValues);
    // }
    if (!(!targetValues.length && endIndex - startIndex === 1 && this.tagList?.[startIndex]?.id === '')) {
      this.tagList.splice(startIndex, endIndex - startIndex, ...targetValues);
    }
    let neeChange = true;
    /* 如果已匹配统一设置并且修改则弹出冲突提示 */
    if (isIncluesSettings) {
      const newCondition = this.getConditionOfIndex(startIndex);
      const oldConditionSort = JSON.parse(JSON.stringify(oldCondition));
      const newConditionSort = JSON.parse(JSON.stringify(newCondition));
      oldConditionSort.value.sort();
      newConditionSort.value.sort();
      if (JSON.stringify(oldConditionSort) !== JSON.stringify(newConditionSort)) {
        neeChange = false;
        setTimeout(() => {
          this.handleSettingsPopShow();
        }, 200);
      }
    }
    this.showAdd = !!targetValues.length;
    if (neeChange) {
      this.handleChange();
    }
  }

  /* 选中key时 */
  handleClickKeyTag(event: Event, item: ITagItem, index: number, keyList: IListItem[] = []) {
    if (this.readonly) {
      return;
    }
    event?.stopPropagation?.();
    this.isClickTagOfPop = true;
    const inputItem = {
      type: TypeEnum.input,
      id: TypeEnum.key,
      name: ''
    };
    if (this.isClickKeyTag || this.isClickValueTag) {
      this.resetInputPosition();
      this.handlePopoerHidden();
      this.isClickKeyTag = false;
      this.isClickValueTag = false;
      return;
    }
    this.isClickKeyTag = true;
    this.isPopTypeOfValue = false;
    this.curTagIndex = index;
    this.tagList[this.tagList.length - 1].type = TypeEnum.null;
    this.tagList.splice(index + 1, 0, inputItem);
    this.curList = (keyList.length ? keyList : [...this.getFilterKeyList()]).map(keyItem => ({
      ...keyItem,
      isCheck: item.id === keyItem.id
    }));
    this.$nextTick(() => {
      this.handleShowPop();
      this.inputRef?.focus?.();
    });
  }

  /* 删除key */
  handleDelKey() {
    let startIndex = this.tagList.findIndex(item => item.type === TypeEnum.input) - 1;
    let endIndex = startIndex;
    let needChange = true;
    this.judgeSettingsConditionChange(startIndex, () => {
      needChange = false;
    });
    this.resetInputPosition();
    for (let i = startIndex + 1; i < this.tagList.length; i++) {
      const tagItem = this.tagList[i];
      if (tagItem.type === TypeEnum.input || tagItem.type === TypeEnum.key || tagItem.type === TypeEnum.condition) {
        endIndex = i;
        break;
      }
    }
    /* 删除key的同时把前面的condition也要删除 */
    startIndex = startIndex > 0 ? startIndex - 1 : startIndex;
    this.tagList.splice(startIndex, endIndex - startIndex);
    if (this.tagList[0].type === TypeEnum.condition) {
      this.tagList.splice(0, 1);
    }
    this.isClickKeyTag = false;
    this.handlePopoerHidden();
    this.resetInputPosition();
    if (this.tagList.length <= 1) {
      this.showAdd = false;
    } else if (this.tagList?.[this.tagList.length - 2]?.type === TypeEnum.value) {
      this.showAdd = true;
    }
    if (needChange) {
      this.handleChange();
    }
  }

  /* 删除value */
  handleDelValueTag(event: Event, item: ITagItem, index: number) {
    let needChange = true;
    this.judgeSettingsConditionChange(index, () => {
      needChange = false;
    });
    const curValues = this.getTargetIndexValues(index + 1);
    event.stopPropagation();
    if (curValues.length > 1) {
      this.tagList.splice(index, 1);
    } else {
      this.tagList.splice(index, 1, {
        id: '',
        name: NULL_NAME,
        type: TypeEnum.value
      });
    }
    if (needChange) {
      this.handleChange();
    }
  }

  /* 点击method 与 condition tag 时触发 */
  handleMOrCTagClick(event: Event, item: ITagItem, index: number) {
    if (this.readonly) {
      return;
    }
    event.stopPropagation();
    this.curTagIndex = index;
    this.isClickKeyTag = false;
    this.isPopTypeOfValue = false;
    this.isClickValueTag = false;
    if (item.type === TypeEnum.condition) {
      this.isClickConditonTag = true;
      this.curList = CONDITIONS.map(c => ({
        ...c,
        isCheck: item.id === c.id
      }));
    } else {
      this.isClickMethodTag = true;
      this.curList = METHODS.map(m => ({
        ...m,
        isCheck: item.id === m.id
      }));
    }
    this.$nextTick(() => {
      this.handleShowPop(event);
    });
  }

  /* 点击value tag */
  handleClickValueTag(event: Event, item: ITagItem, index: number) {
    if (this.readonly) {
      return;
    }
    event.stopPropagation();
    this.isClickValueTag = true;
    this.isClickConditonTag = false;
    this.isClickMethodTag = false;
    if (this.isClickKeyTag) {
      this.resetInputPosition();
      this.handlePopoerHidden();
      this.isClickKeyTag = false;
      return;
    }
    this.curTagIndex = index;
    const oldValueIds = this.getTargetIndexValues(index);
    const valueList = this.getCurIndexOfValues(index);
    this.curList = valueList.map(vItem => ({
      ...vItem,
      isCheck: oldValueIds.includes(vItem.id)
    }));
    this.tagList[this.tagList.length - 1].type = TypeEnum.null;
    if (!(this.tagList[index + 1].type === TypeEnum.input && this.tagList[index + 1].id === TypeEnum.value)) {
      this.tagList.splice(index + 1, 0, {
        type: TypeEnum.input,
        id: TypeEnum.value,
        name: ''
      });
    }
    if (!this.popInstance?.show) {
      this.$nextTick(() => {
        this.handleShowPop();
        this.inputRef?.focus?.();
      });
    }
  }

  /* 输入框操作 */
  handleKeydown(event: Event | any, item: ITagItem, index: number) {
    const keyCode = event?.code || '';
    switch (keyCode) {
      case 'Enter': {
        if (!!this.inputValue) {
          const preTagItem = this.tagList[index - 1];
          if (this.isClickKeyTag) {
            /* 自定义key值 */
            const keyItem = this.keyList.find(kItem => kItem.name === this.inputValue);
            if (keyItem) {
              this.tagList.splice(index - 1, 1, {
                ...keyItem,
                type: TypeEnum.key
              });
            } else {
              this.tagList.splice(index - 1, 1, {
                id: this.inputValue,
                name: this.inputValue,
                type: TypeEnum.key
              });
            }
            this.handlePopoerHidden();
            this.resetInputPosition();
            this.isClickKeyTag = false;
          } else if (this.tagList.length === 1 || preTagItem?.type === TypeEnum.condition) {
            // 没有key 可选项 自定义key值
            const keyItem = this.keyList.find(kItem => kItem.name === this.inputValue);
            const temp = {
              id: keyItem?.id || this.inputValue,
              name: this.inputValue,
              type: TypeEnum.key
            };
            this.tagList.splice(index, 0, temp);
            this.inputValue = '';
            this.curList = METHODS;
            this.isClickValueTag = false;
            this.isPopTypeOfValue = false;
            this.$nextTick(() => {
              this.handleShowPop();
            });
          } else if (preTagItem?.type === TypeEnum.key) {
            const keyItem = this.keyList.find(kItem => kItem.name === this.inputValue);
            const temp = {
              id: keyItem?.id || this.inputValue,
              name: this.inputValue,
              type: TypeEnum.key
            };
            this.tagList.splice(index - 1, 1, temp);
            this.inputValue = '';
            this.curList = METHODS;
            this.isClickValueTag = false;
            this.isPopTypeOfValue = false;
            this.$nextTick(() => {
              this.handleShowPop();
            });
          }
          if (this.isClickValueTag || [TypeEnum.method, TypeEnum.value].includes(preTagItem.type)) {
            /* 自定义value值 */
            const valueList = this.getCurIndexOfValues(index);
            const valueItem = valueList.find(VItem => VItem.name === this.inputValue);
            const oldIds = this.getTargetIndexValues(index, true);
            if (valueItem) {
              if (!oldIds.includes(valueItem.id)) {
                this.tagList.splice(index, 0, {
                  ...valueItem,
                  type: TypeEnum.value
                });
              }
            } else {
              this.tagList.splice(index, 0, {
                id: this.inputValue,
                name: this.inputValue,
                type: TypeEnum.value
              });
            }
            const preTagItem = this.tagList[index - 1];
            if (preTagItem?.type === TypeEnum.value && preTagItem?.id === '' && preTagItem.name === NULL_NAME) {
              this.tagList.splice(index - 1, 1);
            }
            this.handlePopoerHidden();
            this.resetInputPosition();
            this.showAdd = true;
            if (valueList.length) {
              this.isClickValueTag = false;
            } else {
              this.$nextTick(() => {
                this.inputRef?.focus?.();
              });
            }
          }
        }
      }
    }
    this.handleChange();
  }

  /* 转换数据 */
  tagListToConditions() {
    const tagList = JSON.parse(JSON.stringify(this.tagList));
    const conditions: ICondtionItem[] = [];
    const len = tagList.length;
    let tempCondition: ICondtionItem = null;
    const nullCondition = {
      field: '',
      value: [],
      condition: '',
      method: ''
    };
    for (let i = 0; i < len; i++) {
      const tagItem = tagList[i];
      const preTagItem = tagList[i - 1];
      const nextTagItem = tagList[i + 1];
      if (!preTagItem || tagItem.type === TypeEnum.condition) {
        tempCondition = JSON.parse(JSON.stringify(nullCondition)) as any;
        tempCondition.condition = tagItem.type === TypeEnum.key ? CONDITIONS[0].id : (tagItem.id as any);
        tempCondition.field = tagItem.id;
        continue;
      }
      if (tagItem.type === TypeEnum.key) {
        tempCondition.field = tagItem.id;
      }
      if (tagItem.type === TypeEnum.method) {
        tempCondition.method = tagItem.id as any;
      }
      if (tagItem.type === TypeEnum.value) {
        (tempCondition.value as string[]).push(tagItem.id);
      }
      if (!nextTagItem || nextTagItem?.type === TypeEnum.condition) {
        conditions.push(tempCondition);
      }
    }
    return conditions.filter(c => !!c.condition && !!c.field && !!c.method && !!c.value?.length);
  }
  /* 转换数据 tag => condition */
  handleChange() {
    const conditions = this.tagListToConditions();
    this.locaLValue = conditions;
    this.isRepeat = this.getHasRepeatData();
    this.validate();
    this.$emit('change', this.locaLValue);
  }
  /* 转换数据 condition => tag */
  handleConditionToTagList() {
    const keysMap: Map<string, IListItem> = new Map();
    this.keyList.forEach(item => {
      keysMap.set(item.id, item);
    });
    for (const [key, value] of this.groupKeys) {
      value?.forEach((item: any) => {
        keysMap.set(item.id, { ...item, groupName: groupNamesMap[key] });
      });
    }
    const tagList = [];
    let i = 0;
    this.locaLValue.forEach(condition => {
      const valuesMap: Map<string, IListItem> = new Map();
      const valueList = this.valueMap.get(condition.field) || [];
      valueList.forEach(item => {
        valuesMap.set(item.id, item);
      });
      if (condition.field) {
        const keyItem = keysMap.get(condition.field) as any;
        const methodItem = METHODS.find(m => m.id === condition.method);
        const conditionItem = CONDITIONS.find(c => c.id === condition.condition);
        if (i !== 0) {
          tagList.push({
            id: conditionItem?.id || CONDITIONS[0].id,
            name: conditionItem?.name || CONDITIONS[0].name,
            type: TypeEnum.condition
          });
        }
        tagList.push({
          id: keyItem?.id || condition.field,
          name: keyItem?.name || condition.field,
          type: TypeEnum.key,
          alias: !!keyItem?.groupName ? `[${keyItem.groupName}]${keyItem.name}` : undefined
        });
        tagList.push({
          id: methodItem?.id || METHODS[0].id,
          name: methodItem?.name || METHODS[0].name,
          type: TypeEnum.method
        });
        if (condition.value.length) {
          if (condition.value?.length === 1 && condition.value[0] === '') {
            tagList.push({
              id: '',
              name: NULL_NAME,
              type: TypeEnum.value
            });
          } else {
            /* 此数据需要去重，以免引起意料之外的bug */
            const filterValues = [];
            const tempSet = new Set();
            condition.value.forEach(v => {
              if (!tempSet.has(v)) {
                !!v && filterValues.push(v);
              }
              tempSet.add(v);
            });
            filterValues.forEach(vItem => {
              const valueItem = valuesMap.get(vItem);
              tagList.push({
                id: String(valueItem?.id || vItem),
                // name: condition.field === 'alert.strategy_id'
                //   ? String(valueItem?.id || vItem)
                //   : String(valueItem?.name || vItem),
                name: String(valueItem?.name || vItem),
                type: TypeEnum.value
              });
            });
          }
        } else {
          tagList.push({
            id: '',
            name: NULL_NAME,
            type: TypeEnum.value
          });
        }
        i += 1;
        this.showAdd = true;
      }
    });
    tagList.push({
      id: '',
      name: '',
      type: TypeEnum.input
    });
    this.tagList = tagList;
  }

  /* 获取当前筛选已选后的keylist */
  getFilterKeyList() {
    const condition = this.tagListToConditions();
    const selectKeys = condition.map(item => item.field);
    const keyList = this.keyList.filter(item => !selectKeys.includes(item.id));
    const list = keyList.map(item => ({
      ...item,
      isGroupKey: this.groupKey.includes(item.id)
    }));
    return list;
  }

  /* 获取当前value列表 */
  getCurValuesList(key: string) {
    const isStrategyId = key === 'alert.strategy_id';
    const valueMap = this.getDimensionKeys(false) as TValueMap;
    if (valueMap.get(key)?.length) {
      if (isStrategyId) {
        return valueMap.get(key).map(item => ({
          ...item,
          isStrategyId
        }));
      }
      return valueMap.get(key);
    }
    return [];
  }
  /* 获取当前位置所属的key */
  getCurIndexKey(index: number) {
    let key = '';
    for (let i = index; i >= 0; i--) {
      if (this.tagList[i].type === TypeEnum.key) {
        key = this.tagList[i].id;
        break;
      }
    }
    return key;
  }
  /* 根据下标获取当前value值 */
  getCurIndexOfValues(index: number) {
    const key = this.getCurIndexKey(index);
    return this.getCurValuesList(key);
  }

  /* 选中特殊key值时(dimension tags等) 弹出对应的后缀选项 */
  handleSelectGroupKey(key: string, index: number) {
    const keys = this.groupKeys.get(key) || [];
    if (keys.length) {
      this.handleClickKeyTag(null, { id: key } as any, index, keys as any);
    } else {
      if (key === 'dimensions') {
        const tempKeys = this.getDimensionKeys() as any;
        if (tempKeys.length) {
          this.handleClickKeyTag(null, { id: key } as any, index, tempKeys as any);
        }
      }
    }
  }

  /* 特殊选项 */
  getDimensionKeys(isKey = true) {
    let resultKeyList = [];
    let resultValueMap = new Map();
    const kvStrArrSet = new Set();
    this.locaLValue.forEach(item => {
      item.value.forEach(v => {
        kvStrArrSet.add(`${item.field}=${v}`);
      });
    });
    Array.from(kvStrArrSet).forEach((k: string) => {
      if (this.specialOptions[k]) {
        const valueMap = this.specialOptions[k];
        resultKeyList = Array.from(valueMap.keys()).map(key => ({ id: key, name: key }));
        resultValueMap = new Map([...resultValueMap, ...valueMap]);
      }
    });
    resultValueMap = new Map([...this.valueMap, ...resultValueMap]);
    if (isKey) {
      return resultKeyList;
    }
    return resultValueMap;
  }

  /* 根据下标判断当前条件是否与统一设置冲突了 */
  judgeSettingsConditionChange(index: number, show?) {
    if (!this.settingsValue.length) {
      return;
    }
    const curCondition = this.getConditionOfIndex(index);
    let isIncluesSettings = false;
    if (curCondition) {
      isIncluesSettings = conditionsInclues(curCondition, this.settingsValue);
    }
    if (isIncluesSettings) {
      this.tagListCache = JSON.parse(JSON.stringify(this.tagList));
      show();
      setTimeout(() => {
        this.handleSettingsPopShow();
      }, 200);
    }
  }

  /* 根据下标获取当前condition */
  getConditionOfIndex(index: number) {
    const conditions = this.tagListToConditions();
    const key = this.getCurIndexKey(index);
    const condition = conditions.find(c => c.field === key);
    return condition;
  }

  /* 弹出统一设置提示 */
  handleSettingsPopShow() {
    this.settingsPopInstance = this.$bkPopover(this.$el, {
      content: this.settingsMsgRef,
      trigger: 'click',
      theme: 'light common-monitor',
      arrow: true,
      placement: 'bottom-start',
      boundary: 'window',
      interactive: true
    });
    this.settingsPopInstance?.show();
    this.isShowSettingPop = true;
  }
  handleSettingsPopHidden() {
    this.settingsPopInstance?.hide?.(0);
    this.settingsPopInstance?.destroy?.();
    this.settingsPopInstance = null;
    this.isShowSettingPop = false;
  }
  /* 统一设置取消按钮 */
  handleSettingsPopCancel() {
    this.tagList = JSON.parse(JSON.stringify(this.tagListCache));
    this.tagListCache = [];
    this.handleSettingsPopHidden();
    this.$nextTick(() => {
      this.resetInputPosition();
      this.handleChange();
    });
  }
  /* 统一设置确定按钮 */
  handleSettingsPopConfirm() {
    this.$emit('settingsChange');
    this.handleSettingsPopHidden();
    this.handleChange();
  }

  @Debounce(300)
  handleSearchChange(value) {
    this.valueSearch = value;
  }
  /* 展示二级key选项 */
  handleShowkeyListSecond(target, item: IListItem) {
    this.curGroupKey = item.id;
    let keyList = [];
    if (item.id === 'dimensions') {
      const tempKeys = this.getDimensionKeys() as any;
      if (!!tempKeys?.length) {
        keyList = tempKeys;
      }
    } else {
      keyList = this.groupKeys.get(item.id) || [];
    }
    this.keyListSecond = this.getFilterSecondKeyList(keyList) as any;
    this.$nextTick(() => {
      this.secondPopInstance = this.$bkPopover(target, {
        content: this.secondWrapRef,
        trigger: 'manual',
        interactive: true,
        theme: 'light common-monitor',
        arrow: false,
        placement: 'right-start',
        boundary: 'window',
        hideOnClick: false,
        distance: 0
      });
      this.secondPopInstance?.show?.();
    });
  }
  handleHiddenKeySecond() {
    this.secondPopInstance?.hide?.(0);
    this.secondPopInstance?.destroy?.();
    this.secondPopInstance = null;
  }

  /* 弹出二级选项动作 */
  handleOptionMouseEnter(event, item) {
    const isGroupKey = !!item?.isGroupKey;
    if (isGroupKey) {
      this.handleShowkeyListSecond(event.target, item);
    } else {
      this.handleHiddenKeySecond();
    }
  }
  /* 点击二级选项 */
  handleClickSecondKey(item: IListItem) {
    const opt = {
      type: 'key',
      id: item.id,
      name: item.name,
      alias: `[${groupNamesMap[this.curGroupKey]}]${item.name}`
    };
    const len = this.tagList.length;
    this.curIndex = this.tagList.findIndex(t => t.type === TypeEnum.input) || len - 1;
    const lastTagItem2 = this.tagList?.[this.curIndex - 1];
    if (len === 1) {
      this.tagList.unshift(opt as any);
    } else {
      this.tagList.splice(this.curIndex, 0, opt as any);
    }
    this.curList = METHODS;
    this.handlePopoerHidden();
    setTimeout(() => {
      this.handleShowPop();
    }, 50);
    this.isPopTypeOfValue = [TypeEnum.method, TypeEnum.key, TypeEnum.value].includes(lastTagItem2.type);
  }

  /* 二级选项筛选 */
  getFilterSecondKeyList(targetKeyList) {
    const condition = this.tagListToConditions();
    const selectKeys = condition.map(item => item.field);
    const keyList = targetKeyList.filter(item => !selectKeys.includes(item.id));
    const list = keyList.map(item => ({
      ...item,
      isGroupKey: this.groupKey.includes(item.id)
    }));
    return list;
  }

  /* 校验（失焦的时候） */
  validate(isFocus = false) {
    if (!this.needValidate) {
      this.isErr = false;
      this.$emit('validate', this.isErr);
      return;
    }
    if (isFocus) {
      this.isErr = false;
    } else {
      this.isErr = !this.locaLValue.length;
    }
    this.$emit('validate', this.isErr);
  }

  /* 重复数据校验 */
  getHasRepeatData() {
    const len = this.locaLValue.length;
    let isRepeat = false;
    for (let i = 0; i < len; i++) {
      const left = this.locaLValue[i];
      for (let j = i + 1; j < len; j++) {
        const right = this.locaLValue[j];
        if (conditionCompare(left, right)) {
          isRepeat = true;
          break;
        }
      }
      if (isRepeat) {
        break;
      }
    }
    this.$emit('repeat', isRepeat);
    return isRepeat;
  }

  handleDelKeyMouseenter() {
    this.handleHiddenKeySecond();
  }

  render() {
    return (
      <div
        class='common-condition-component'
        v-bkloading={{ isLoading: this.loading, mode: 'spin', size: 'mini' }}
        id={this.componetId}
        onClick={e => this.handleClickComponent(e)}
        onMouseenter={this.handleMouseEnter}
        onMouseleave={this.handleMouseLeave}
      >
        {this.tagList.map((item, index) => {
          switch (item.type) {
            case 'condition':
              return (
                <div
                  class='common-tag tag-condition'
                  key={`${item.id}_${index}`}
                  onClick={e => this.handleMOrCTagClick(e, item, index)}
                >
                  {item.name}
                </div>
              );
            case 'key':
              return (
                <div
                  class='common-tag tag-key'
                  v-bk-tooltips={{
                    content: item.id,
                    placements: ['top'],
                    allowHTML: false
                  }}
                  key={`${item.id}_${index}`}
                  onClick={e => this.handleClickKeyTag(e, item, index)}
                >
                  {item?.alias || item.name}
                </div>
              );
            case 'method':
              return (
                <div
                  class='common-tag tag-method'
                  key={`${item.id}_${index}`}
                  onClick={e => this.handleMOrCTagClick(e, item, index)}
                >
                  {item.name}
                </div>
              );
            case 'value':
              return (
                !!item.name && (
                  <div
                    class='common-tag tag-value'
                    v-bk-tooltips={{
                      content: item.id,
                      placements: ['top'],
                      allowHTML: false
                    }}
                    key={`${item.id}_${index}`}
                    onClick={e => this.handleClickValueTag(e, item, index)}
                  >
                    <span class='tag-value-name'>{item.name}</span>
                    {item.name !== NULL_NAME && !this.readonly && (
                      <span
                        class='icon-monitor icon-mc-close'
                        onClick={e => this.handleDelValueTag(e, item, index)}
                      ></span>
                    )}
                  </div>
                )
              );
            case 'input':
              return (
                !this.readonly && (
                  <div
                    class='input-wrap'
                    key={`${item.id}_${index}`}
                  >
                    <span class='input-value'>{this.inputValue}</span>
                    <input
                      class='input'
                      ref='input'
                      v-model={this.inputValue}
                      onBlur={this.handBlur}
                      onInput={this.handleInput}
                      onKeydown={e => this.handleKeydown(e, item, index)}
                    ></input>
                  </div>
                )
              );
            default:
              return undefined;
          }
        })}
        {this.showAdd && !this.readonly && (
          <div
            class={['tag-add', { active: this.showPopOfCondition }]}
            onClick={e => this.handleAddClick(e)}
          >
            <span class='icon-monitor icon-plus-line'></span>
          </div>
        )}
        <div style={'display: none;'}>
          <div
            class='common-condition-component-pop-wrap'
            ref='wrap'
            id={this.componetId}
          >
            {(this.isPopTypeOfValue || this.isClickValueTag) && (
              <div class='search-wrap'>
                <bk-input
                  value={this.valueSearch}
                  left-icon='bk-icon icon-search'
                  placeholder={window.i18n.t('输入关键字搜索')}
                  behavior={'simplicity'}
                  onChange={this.handleSearchChange}
                ></bk-input>
              </div>
            )}
            <div class='wrap-list'>
              {this.curList.length ? (
                this.curList
                  .filter(item =>
                    this.isPopTypeOfValue || this.isClickValueTag
                      ? item.id.indexOf(this.valueSearch) > -1 || item.name.indexOf(this.valueSearch) > -1
                      : true
                  )
                  .map((item, index) => (
                    <div
                      key={`${item.id}_${index}`}
                      class={[
                        'list-item',
                        { 'is-check': !!item?.isCheck },
                        { 'key-type': this.isClickKeyTag || this.isClickConditonTag || this.isClickMethodTag }
                      ]}
                      v-bk-tooltips={{
                        content: item.id,
                        placements: ['right'],
                        disabled: this.isAbsoluteOpts || !!item?.isGroupKey,
                        allowHTML: false
                      }}
                      onClick={() => this.handleOptionClick(item)}
                      onMouseenter={e => this.handleOptionMouseEnter(e, item)}
                    >
                      {!!item?.isStrategyId ? (
                        <span class='strategy-name'>
                          <span>{item.name}</span>
                          <span class='strategy-name-info'>{`${item.first_label_name} (#${item.id})`}</span>
                        </span>
                      ) : (
                        <span class='left'>{item.name}</span>
                      )}
                      {!!item?.isCheck && <span class='right icon-monitor icon-mc-check-small'></span>}
                      {!!item?.isGroupKey && <span class='right icon-monitor icon-arrow-right'></span>}
                    </div>
                  ))
              ) : (
                <div class='list-item no-hover'>{window.i18n.tc('暂无可选项')}</div>
              )}
            </div>
            {this.isClickKeyTag && (
              <div
                class='del-bottom'
                onClick={this.handleDelKey}
                onMouseenter={this.handleDelKeyMouseenter}
              >
                <span class='icon-monitor icon-mc-delete-line'></span>
                <span class='del-text'>{this.$t('删除')}</span>
              </div>
            )}
          </div>
        </div>
        <div style={'display: none'}>
          <div
            class={settingPopClassName}
            ref='settingsMsg'
          >
            <div class='top'>
              <span class='icon-monitor icon-remind'></span>
              <i18n path='变更当前值将会使 {0}，是否确定变更？'>
                <span class='blod'>{window.i18n.t('统一设置条件失效')}</span>
              </i18n>
            </div>
            <div class='bottom'>
              <span
                class='btn mr14'
                onClick={this.handleSettingsPopConfirm}
              >
                {window.i18n.t('变更')}
              </span>
              <span
                class='btn'
                onClick={this.handleSettingsPopCancel}
              >
                {window.i18n.t('取消')}
              </span>
            </div>
          </div>
        </div>
        <div style={'display: none'}>
          <div
            class='common-condition-component-second-pop-wrap'
            ref='secondWrap'
          >
            {this.keyListSecond.length ? (
              <div class='wrap-list'>
                {this.keyListSecond.map(item => (
                  <div
                    key={item.id}
                    class='list-item key-type'
                    onMousedown={() => this.handleClickSecondKey(item)}
                    v-bk-tooltips={{
                      content: item.id,
                      placements: ['right'],
                      allowHTML: false
                    }}
                  >
                    <span>{item.name}</span>
                  </div>
                ))}
              </div>
            ) : (
              <div class='wrap-list no-data'>
                <div class='list-item'>{window.i18n.t('无选项')}</div>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }
}
