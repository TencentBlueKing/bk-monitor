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
import { TranslateResult } from 'vue-i18n';
import { Component, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { listUsersUser } from '../../../../monitor-api/modules/model';
import { Debounce, deepClone, random } from '../../../../monitor-common/utils';
import HorizontalScrollContainer from '../../../pages/strategy-config/strategy-config-set-new/components/horizontal-scroll-container';
import { getEventPaths } from '../../../utils';
import { CONDITIONS, deepCompare, ICondtionItem, METHODS, TContionType, TMthodType } from '../typing';
import {
  conditionCompare,
  conditionsInclues,
  EKeyTags,
  ISpecialOptions,
  KEY_FILTER_TAGS,
  KEY_TAG_MAPS,
  NOTICE_USERS_KEY,
  TGroupKeys,
  TValueMap
} from '../typing/condition';

import './common-condition-new.scss';

const NULL_NAME = `-${window.i18n.t('空')}-`;

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
  isOnlyAdd?: boolean;
  isFormMode?: boolean;
  onChange?: (v: ICondtionItem[]) => void;
  onSettingsChange?: () => void;
  onValidate?: (v: boolean) => void;
  onRepeat?: (v: boolean) => void;
  onValueMapChange?: (v: { key: string; values: { id: string; name: string }[] }) => void;
  replaceData?: IListItem[];
}

interface IListItem {
  id: string;
  name: string;
  isCheck?: boolean;
  isStrategyId?: boolean;
  first_label_name?: string; // 适用于策略id
  isGroupKey?: boolean; // 是否为二级选项
  alias?: string; // 别名， 标签和维度的key 需要有别名
  show?: boolean;
}

enum TypeEnum {
  input = 'input',
  key = 'key',
  value = 'value',
  method = 'method',
  condition = 'condition',
  null = ''
}

interface ITag {
  type: TypeEnum;
  id: string;
  name: string;
  alias?: string; // 别名， 标签和维度的key 需要有别名
  active?: boolean;
}
interface ITagItem {
  condition: ICondtionItem;
  tags: ITag[];
  isReplace?: boolean;
}

const defaultCondition: ICondtionItem = {
  field: '',
  method: 'eq',
  value: [],
  condition: 'and'
};

const inputTag = {
  id: '____INPUT___TAG__',
  name: '',
  type: TypeEnum.input
};

const nullOption = {
  id: '',
  name: `-${window.i18n.tc('空')}-`,
  type: TypeEnum.value,
  isCheck: false
};

const groupNamesMap = {
  tags: window.i18n.t('标签'),
  dimensions: window.i18n.t('维度'),
  set: window.i18n.t('集群属性'),
  module: window.i18n.t('模块属性'),
  host: window.i18n.t('主机属性')
};

const strategyField = 'alert.strategy_id';

const settingPopClassName = 'common-condition-component-settings-msg';

@Component
export default class CommonCondition extends tsc<IProps> {
  /* 当前condition */
  @Prop({ default: () => [], type: Array }) value: ICondtionItem[];
  /* 可供选择的key选项 */
  @Prop({ default: () => [], type: Array }) keyList: IListItem[];
  /* key对应的value选项集合 */
  @Prop({ default: () => new Map(), type: Map }) valueMap: TValueMap;
  /* 组合项key前缀，如命中前缀可展开groupKeys内的选项以供选择 暂且只有[dimension, tags] */
  @Prop({ default: () => [], type: Array }) groupKey: string[];
  /* 组合项key 如 dimension.xxx  tags.xxxx*/
  @Prop({ default: () => new Map(), type: Map }) groupKeys: TGroupKeys;
  /* 是否为只读模式 */
  @Prop({ default: false, type: Boolean }) readonly: boolean;
  /* 是否包含特殊情况(如果包含的特殊的kv(如策略选择会影响维度选项)则会添加一些特别的可选项) 暂时只包含维度的特殊选项 */
  @Prop({ default: () => ({}), type: Object }) specialOptions: ISpecialOptions;
  /* 当前统一设置的条件 如有条件 */
  @Prop({ default: () => [], type: Array }) settingsValue: ICondtionItem[];
  /* 获取选项数据时的loading */
  @Prop({ default: false, type: Boolean }) loading: boolean;
  /* 是否需要校验 */
  @Prop({ default: false, type: Boolean }) needValidate: boolean;
  /* 是否只有and连接符 */
  @Prop({ default: true, type: Boolean }) isOnlyAdd: boolean;
  /* 编辑模式是否为表单模式 */
  @Prop({ default: true, type: Boolean }) isFormMode: boolean;

  @Prop({ default: () => [], type: Array }) replaceData: IListItem[];

  @Ref('input') inputRef: HTMLInputElement;
  @Ref('wrap') wrapRef: HTMLDivElement;
  @Ref('secondWrap') secondWrapRef: HTMLDivElement;
  @Ref('settingsMsg') settingsMsgRef: HTMLDivElement;

  /* 当前条件数据 */
  locaLValue: ICondtionItem[] = [];
  /* 缓存的数据（用于统一设置的提示） */
  locaLValueCache: ITagItem[] = [];
  /* 当前渲染的数据  */
  tagList: ITagItem[] = [];
  /* 输入框的值 */
  inputValue = '';
  /* 当前组件唯一id 用于清除弹出层时的判断 */
  componentId = '';
  /* 搜索 */
  searchValue = '';
  /* 当前弹出选项类型 */
  selectType: TypeEnum = TypeEnum.null;
  /* 点击谁弹出弹出层的 */
  clickType: TypeEnum = TypeEnum.null;
  /* 当前展开的列表 */
  curList: IListItem[] = [];
  /* 弹出层实例 */
  popInstance = null;
  /* 二级选项弹出层实例 */
  secondPopInstance = null;
  /* 统一设置提示弹出层实例 */
  settingsPopInstance = null;
  /* 当前下标 [行，列] */
  curIndex = [0, 0];
  /* 添加可被移除的事件监听器 */
  controller: AbortController = null;
  /* 是否点击了添加按钮 */
  addActive = false;
  /* key选项二级列表 */
  keyListSecond: IListItem[] = [];
  /* 当前二级展开的key */
  curGroupKey = '';
  /* 是否弹出统一设置弹层 */
  isShowSettingPop = false;
  /* 是否提示校验 */
  isErr = false;
  /* 是否重复 */
  isRepeat = false;
  /* 当前光标类型 策略需做特殊处理 */
  focusType = '';

  /* 校验提示 */
  errorMsg: string | TranslateResult = '';
  /* 二级选项搜索 */
  secondSearch = '';
  /* 当前key选项分类标签 */
  keyTypeTag = EKeyTags.all;
  /* 是否为通知人员 需要展示远程的人员搜索 */
  isUserKey = false;
  /* 远程搜索的loading */
  searchLoading = false;

  /* 是否不可点击(只读状态) */
  get canNotClick() {
    return this.readonly || this.loading;
  }

  @Watch('replaceData', { deep: true, immediate: true })
  handleReplaceData(value) {
    this.$nextTick(() => {
      this.tagList = this.tagList.map(item => {
        value.forEach(config => {
          if (deepCompare(deepClone(item.condition), deepClone(config))) {
            item.isReplace = true;
          }
        });
        return item;
      });
    });
  }

  created() {
    this.componentId = random(8);
    this.locaLValue = [...this.value];
    this.handleConditionToTagList();
    this.validateConditionsRepeatKey();
  }

  /* condition => tags */
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
    this.locaLValue.forEach((condition, index) => {
      const valuesMap: Map<string, IListItem> = new Map();
      const valueList = this.valueMap.get(condition.field) || [];
      valueList.forEach(item => {
        valuesMap.set(item.id, item);
      });
      const tempCondition = JSON.parse(JSON.stringify(condition || defaultCondition));
      const tempTags = [];
      if (condition.field) {
        const keyItem = keysMap.get(condition.field) as any;
        const methodItem = METHODS.find(m => m.id === condition.method);
        const conditionItem = CONDITIONS.find(c => c.id === (condition.condition || 'and'));
        if (!(conditionItem.id === 'and' && index === 0)) {
          tempTags.push({
            ...conditionItem,
            type: TypeEnum.condition
          });
        }
        tempTags.push({
          id: keyItem?.id || condition.field,
          name: keyItem?.name || condition.field,
          type: TypeEnum.key,
          alias: !!keyItem?.groupName ? `[${keyItem.groupName}]${keyItem.name}` : undefined
        });
        tempTags.push({
          id: methodItem?.id || METHODS[0].id,
          name: methodItem?.name || METHODS[0].name,
          type: TypeEnum.method
        });
        if (condition.value.length) {
          if (condition.value?.length === 1 && condition.value[0] === '') {
            tempTags.push({
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
              tempTags.push({
                id: String(valueItem?.id || vItem),
                name: String(valueItem?.name || vItem),
                type: TypeEnum.value
              });
            });
          }
        } else {
          tempTags.push({
            id: '',
            name: NULL_NAME,
            type: TypeEnum.value
          });
        }
        tagList.push({
          condition: tempCondition,
          tags: tempTags
        });
      }
    });
    if (!this.locaLValue.length) {
      tagList.push({
        condition: null,
        tags: []
      });
    }
    this.tagList = tagList;
  }

  /* 判断如何清除弹出实例 */
  handleMouseEnter() {
    this.controller?.abort?.();
    this.controller = new AbortController();
    document.addEventListener('mousedown', this.handleMousedown, { signal: this.controller.signal });
  }
  handleMouseLeave() {
    if (this.popInstance || this.settingsPopInstance) {
      return;
    }
    this.controller?.abort?.();
  }
  /* 清除弹出层 */
  handleMousedown(event: Event) {
    const paths = JSON.parse(JSON.stringify(getEventPaths(event).map(item => item.id)));
    const pathsClass = JSON.parse(JSON.stringify(getEventPaths(event).map(item => item.className)));
    /* 判断统一设置提示弹出hide方式 */
    if (!pathsClass.includes(settingPopClassName)) {
      if (this.isShowSettingPop) {
        this.handleSettingsPopCancel();
      }
    }
    if (paths.includes(this.componentId) || pathsClass.includes('common-condition-component-second-pop-wrap')) return;
    if (this.popInstance) {
      this.handlePopoverHidden();
    }
  }
  /* 点击组件 */
  handleComponentClick() {
    if (this.canNotClick) {
      return;
    }
    if (!!this.popInstance?.show) {
      this.handlePopoverHidden();
    }
  }
  /* 输入框失焦 */
  handBlur() {
    if (!this.popInstance?.show && !this.inputValue) {
      this.resetInputPosition();
    }
    this.inputValue = '';
  }
  /* 点击某一行 */
  handleClickLineWrap(event: MouseEvent, index: number) {
    if (this.canNotClick) {
      return;
    }
    event?.stopPropagation?.();
    if (!!this.popInstance?.show) {
      this.handlePopoverHidden();
      return;
    }
    if (!this.tagList[index].tags.some(item => item.type === TypeEnum.input)) {
      this.tagList[index].tags.push(inputTag);
    }
    if (!!this.tagList[index].condition) {
      const len = this.tagList[index].tags.length;
      const lastTag = this.tagList[index].tags[len - 2];
      if (lastTag.type === TypeEnum.key) {
        this.curList = [...METHODS];
        this.curIndex = [index, len - 1];
        this.selectType = TypeEnum.method;
      } else if (lastTag.type === TypeEnum.method) {
        const key = this.tagList[index].condition.field;
        this.isUserKey = key === NOTICE_USERS_KEY;
        const values = this.getCurValuesList(key);
        this.curList = values.map(item => ({
          ...item,
          isCheck: false
        }));
        this.curList.unshift({ ...nullOption, isCheck: false });
        this.curIndex = [index, len - 1];
        this.selectType = TypeEnum.value;
        this.setInputFocus();
        this.focusType = key;
        /* 策略不能自定义输入 */
        // if (key !== strategyField) {
        //   this.setInputFocus();
        // }
      } else if (lastTag.type === TypeEnum.condition) {
        this.curList = [...this.filterKeyList()];
        this.curIndex = [index, 1];
        this.selectType = TypeEnum.key;
        this.setInputFocus();
      } else if (lastTag.type === TypeEnum.value) {
        const key = this.tagList[index].condition.field;
        this.isUserKey = key === NOTICE_USERS_KEY;
        const values = this.getCurValuesList(key);
        this.curIndex = [index, len - 1];
        this.curList = values.map(item => ({
          ...item,
          isCheck: this.tagList[index].condition.value.includes(item.id)
        }));
        this.curList.unshift({ ...nullOption, isCheck: this.tagList[index].condition.value.includes(nullOption.id) });
        this.selectType = TypeEnum.value;
        this.setInputFocus();
        this.focusType = key;
        /* 策略不能自定义输入 */
        // if (key !== strategyField) {
        //   this.setInputFocus();
        // }
      }
    } else {
      this.curList = [...this.filterKeyList()];
      this.curIndex = [index, 0];
      this.selectType = TypeEnum.key;
      this.setInputFocus();
    }
    this.$nextTick(() => {
      this.showPopFn();
    });
  }
  /* 点击key tag */
  handleClickKeyTag(event: Event, index: number, tagIndex: number) {
    if (this.canNotClick) {
      return;
    }
    event.stopPropagation();
    if (!!this.popInstance?.show) {
      this.handlePopoverHidden();
      return;
    }
    this.curList = [...this.filterKeyList()];
    this.curIndex = [index, tagIndex];
    // this.tagList[index].tags.splice(tagIndex + 1, 0, inputTag);
    this.selectType = TypeEnum.key;
    this.clickType = TypeEnum.key;
    this.setInputFocus();
    this.$nextTick(() => {
      this.showPopFn(event);
    });
  }
  /* 点击method tag */
  handleClickTagMethod(event: Event, index: number, tagIndex: number) {
    if (this.canNotClick) {
      return;
    }
    event.stopPropagation();
    if (!!this.popInstance?.show) {
      this.handlePopoverHidden();
      return;
    }
    this.curList = [...METHODS];
    this.curIndex = [index, tagIndex];
    this.selectType = TypeEnum.method;
    this.clickType = TypeEnum.method;
    this.$nextTick(() => {
      this.showPopFn(event);
    });
  }
  /* 点击value tag */
  handleClickTagValue(event: Event, index: number, tagIndex: number) {
    if (this.canNotClick) {
      return;
    }
    event.stopPropagation();
    if (!!this.popInstance?.show) {
      this.handlePopoverHidden();
      return;
    }
    const key = this.tagList[index].condition.field;
    const values = this.getCurValuesList(key);
    this.curList = values.map(item => ({
      ...item,
      isCheck: this.tagList[index].condition.value.includes(item.id)
    }));
    this.curList.unshift({ ...nullOption, isCheck: this.tagList[index].condition.value.includes(nullOption.id) });
    this.selectType = TypeEnum.value;
    this.clickType = TypeEnum.value;
    this.tagList[index].tags.splice(tagIndex + 1, 0, inputTag);
    this.curIndex = [index, tagIndex + 1];
    this.setInputFocus();
    this.focusType = key;
    /* 策略不能自定义输入 */
    // if (key !== strategyField) {
    //   this.setInputFocus();
    // }
    this.$nextTick(() => {
      this.showPopFn();
    });
  }

  @Debounce(300)
  handleSearchChange(v) {
    this.searchValue = v;
    if (this.isUserKey) {
      this.searchLoading = true;
      listUsersUser({
        app_code: 'bk-magicbox',
        page: 1,
        page_size: 20,
        fuzzy_lookups: this.searchValue
      })
        .then(data => {
          this.curList = data.results.map(item => {
            return {
              name: item.display_name,
              id: item.username,
              isCheck: this.tagList[this.curIndex[0]].condition.value.includes(item.username)
            };
          });
        })
        .finally(() => {
          this.searchLoading = false;
        });
    }
  }
  @Debounce(300)
  handleSecondSearchChange(v) {
    this.secondSearch = v;
  }
  /* 删除此条件 */
  handleDelKey() {
    if (this.tagList.length > 1) {
      this.tagList.splice(this.curIndex[0], 1);
    } else {
      this.tagList[this.curIndex[0]].condition = null;
      this.tagList[this.curIndex[0]].tags = [];
    }
    this.handlePopoverHidden();
    this.handleChange();
    this.validateConditionsRepeatKey();
  }

  /* 选择key */
  handleSelectKey(keyItem: IListItem) {
    const tempItem = Object.assign(
      {},
      {
        id: keyItem.id,
        name: keyItem.name,
        type: TypeEnum.key
      },
      !!keyItem?.alias ? { alias: keyItem.alias } : {}
    );
    if (this.clickType === TypeEnum.key) {
      /* 通过点击keytag触发的 */
      this.tagList[this.curIndex[0]].tags[this.curIndex[1]] = tempItem;
      this.tagList[this.curIndex[0]].condition.field = keyItem.id;
      this.handlePopoverHidden();
      this.handleChange();
      return;
    }
    this.tagList[this.curIndex[0]].tags.splice(this.curIndex[1], 0, tempItem);
    if (!!this.tagList[this.curIndex[0]].condition) {
      this.tagList[this.curIndex[0]].condition.field = keyItem.id;
    } else {
      this.tagList[this.curIndex[0]].condition = {
        ...JSON.parse(JSON.stringify(defaultCondition)),
        field: keyItem.id
      };
    }
    this.handleChange();
    this.handlePopoverHidden();
    /* 自动弹出 */
    setTimeout(() => {
      this.handleClickLineWrap(null, this.curIndex[0]);
    }, 100);
  }
  /* 选择method */
  handleSelectMethod(keyItem: IListItem) {
    if (this.clickType === TypeEnum.method) {
      this.tagList[this.curIndex[0]].tags[this.curIndex[1]] = {
        id: keyItem.id,
        name: keyItem.name,
        type: TypeEnum.method
      };
    } else {
      this.tagList[this.curIndex[0]].tags.splice(this.curIndex[1], 0, {
        id: keyItem.id,
        name: keyItem.name,
        type: TypeEnum.method
      });
    }
    this.tagList[this.curIndex[0]].condition.method = keyItem.id as TMthodType;
    this.handleChange();
    this.handlePopoverHidden();
    setTimeout(() => {
      this.handleClickLineWrap(null, this.curIndex[0]);
    }, 100);
  }
  /* 选择condition */
  handleSelectCondition(keyItem: IListItem) {
    if (this.addActive) {
      this.tagList.push({
        condition: {
          ...JSON.parse(JSON.stringify(defaultCondition)),
          field: '',
          value: []
        },
        tags: [{ id: keyItem.id, name: keyItem.name, type: TypeEnum.condition }]
      });
    }
    this.handleChange();
    this.handlePopoverHidden();
  }
  /* 选择value */
  handleSelectValue(keyItem: IListItem) {
    if (keyItem.id === nullOption.id && !keyItem?.isCheck) {
      // 空选项情况 空选项与其他选项互斥
      this.curList.forEach(item => {
        item.isCheck = item.id === nullOption.id;
      });
      const oldTags = JSON.parse(JSON.stringify(this.tagList[this.curIndex[0]]?.tags || [])) as ITag[];
      const newTags = oldTags.filter(item => item.type !== TypeEnum.value);
      const methodIndex = newTags.findIndex(item => item.type === TypeEnum.method);
      newTags.splice(methodIndex + 1, 0, {
        id: nullOption.id,
        name: nullOption.name,
        type: TypeEnum.value
      });
      this.tagList[this.curIndex[0]].condition.value = [''];
      this.tagList[this.curIndex[0]].tags = newTags;
      this.handleChange();
      this.$nextTick(() => {
        this.popInstance?.show?.();
      });
      return;
    }
    const curValues = JSON.parse(JSON.stringify(this.tagList[this.curIndex[0]].condition.value || []));
    /* 可选项的tag */
    const tags = [];
    /* 自定义tag */
    const customTags = [];
    const idSet = new Set();
    this.curList.forEach(item => {
      idSet.add(item.id);
      if (keyItem.id === item.id) {
        item.isCheck = !item.isCheck;
      }
      if (item.isCheck) {
        tags.push({
          id: item.id,
          name: item.name,
          type: TypeEnum.value
        });
      }
      if (item.id === nullOption.id) {
        item.isCheck = false;
      }
    });
    if (curValues.length) {
      curValues.forEach(v => {
        if (!idSet.has(v)) {
          customTags.push({
            id: v,
            name: v,
            type: TypeEnum.value
          });
        }
      });
    }
    const resultSet = new Set();
    const result = [...tags, ...customTags];
    this.tagList[this.curIndex[0]].condition.value = result.map(item => {
      resultSet.add(item.id);
      return item.id;
    });
    /* 后半部分只删不增 */
    const next = [];
    const curTags = this.tagList[this.curIndex[0]].tags;
    let inputIndex = curTags.findIndex(item => item.type === TypeEnum.input);
    for (let i = inputIndex; i < curTags.length; i++) {
      const tagItem = curTags[i];
      if (tagItem.type === TypeEnum.value) {
        if (resultSet.has(tagItem.id)) {
          next.push(tagItem);
        }
      }
    }
    /* 前半部分又增又删 */
    const pre = [];
    for (let i = inputIndex; i >= 0; i--) {
      const tagItem = curTags[i];
      if (tagItem.type === TypeEnum.value) {
        if (resultSet.has(tagItem.id)) {
          pre.push(tagItem);
        }
      }
    }
    const tempSet = new Set([...next, ...pre].map(item => item.id));
    const tempPre = [];
    Array.from(resultSet).forEach(id => {
      if (!tempSet.has(id)) {
        const findItem = this.curList.find(item => item.id === id);
        if (findItem) {
          tempPre.push({
            id: findItem.id,
            name: findItem.name,
            type: TypeEnum.value
          });
        } else {
          tempPre.push({
            id,
            name: id,
            type: TypeEnum.value
          });
        }
      }
    });
    pre.push(...tempPre);
    const methodIndex = curTags.findIndex(item => item.type === TypeEnum.method);
    let lastIndex = curTags.length - 1;
    curTags.splice(methodIndex + 1, inputIndex - methodIndex - 1, ...pre);
    lastIndex = curTags.length - 1;
    inputIndex = curTags.findIndex(item => item.type === TypeEnum.input);
    curTags.splice(inputIndex + 1, lastIndex - inputIndex, ...next);
    const findNullItemIndex = curTags.findIndex(item => item.id === nullOption.id);
    if (findNullItemIndex >= 0) {
      /* 剔除空选项 空选项与其他选项互斥 */
      curTags.splice(findNullItemIndex, 1);
      this.tagList[this.curIndex[0]].condition.value = this.tagList[this.curIndex[0]].condition.value.filter(
        item => !!item
      );
    }
    this.handleChange();
    this.$nextTick(() => {
      this.popInstance?.show?.();
    });
  }
  /* 删除value */
  handDelValue(event: Event, index: number, tagIndex: number) {
    event.stopPropagation();
    this.tagList[index].tags.splice(tagIndex, 1);
    this.tagList[index].condition.value = this.tagList[index].tags
      .filter(item => item.type === TypeEnum.value)
      .map(item => item.id);
    this.curIndex = [index, 0];
    this.handleChange();
  }
  /* 根据key获取value可选项 */
  getCurValuesList(key: string) {
    const isStrategyId = key === 'alert.strategy_id';
    const valueMap = this.getDimensionKeys(false) as TValueMap;
    // const { valueMap } = this;
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
  /* 清除输入框 */
  resetInputPosition() {
    this.tagList.forEach(item => {
      item.tags = item.tags.filter(tag => tag.type !== TypeEnum.input);
    });
    this.inputValue = '';
  }
  /* 展开弹层 */
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
  /* 清除弹出层 */
  handlePopoverHidden(isOnlyHide = false) {
    this.popInstance?.hide?.(0);
    this.popInstance?.destroy?.();
    this.searchValue = '';
    this.isUserKey = false;
    this.handleSecondPopHidden();
    if (isOnlyHide) return;
    this.popInstance = null;
    this.addActive = false;
    this.clickType = TypeEnum.null;
    this.$nextTick(() => {
      this.resetInputPosition();
    });
  }
  /* 二级选项弹层 */
  @Debounce(100)
  showSecondPopfn(event, isGroupKey = true, item?) {
    const props = {
      trigger: 'manual',
      interactive: true,
      arrow: false,
      placement: 'right-start',
      boundary: 'window',
      hideOnClick: false
    };
    if (isGroupKey) {
      this.secondPopInstance = this.$bkPopover(event.target, {
        ...props,
        content: this.secondWrapRef,
        distance: 0,
        theme: 'light common-monitor'
      });
    } else {
      this.secondPopInstance = this.$bkPopover(event.target, {
        ...props,
        content: item.id || '',
        trigger: 'mouseenter',
        arrow: true,
        duration: [0, 0],
        theme: '',
        extCls: 'common-condition-component-second-pop-wrap-tip'
      });
    }
    this.secondPopInstance?.show?.(isGroupKey ? undefined : 300);
  }
  /* 清除弹层 */
  handleSecondPopHidden() {
    this.secondPopInstance?.hide?.(0);
    this.secondPopInstance?.destroy?.();
    this.secondPopInstance = null;
    this.secondSearch = '';
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
  /* 弹出二级选项 */
  handleKeyMouseEnter(event: Event, item) {
    this.handleSecondPopHidden();
    const isGroupKey = !!item?.isGroupKey;
    if (isGroupKey) {
      this.curGroupKey = item.id;
      let keyList = [];
      if (item.id === 'dimensions') {
        const tempKeys = this.getDimensionKeys() as any;
        if (!!tempKeys?.length) {
          keyList = tempKeys;
        } else {
          keyList = this.groupKeys.get(item.id) || [];
        }
      } else {
        keyList = this.groupKeys.get(item.id) || [];
      }
      const selectKeysSet = new Set();
      this.tagList.forEach(t => {
        if (!!t.condition?.field) {
          selectKeysSet.add(t.condition.field);
        }
      });
      this.keyListSecond = keyList.filter(k => !selectKeysSet.has(k.id));
      this.$nextTick(() => {
        this.showSecondPopfn(event);
      });
    } else {
      this.showSecondPopfn(event, false, item);
    }
  }
  /* 点击二级选项 */
  handleClickSecondKey(item: IListItem) {
    this.handleSelectKey({
      ...item,
      alias: `[${groupNamesMap[this.curGroupKey]}]${item.name}`
    });
  }

  /* 添加 */
  handleAdd(event: Event) {
    if (this.canNotClick) {
      return;
    }
    event.stopPropagation();
    if (this.isOnlyAdd) {
      this.tagList.push({
        condition: {
          ...JSON.parse(JSON.stringify(defaultCondition)),
          condition: CONDITIONS[0].id as TContionType
        },
        tags: [
          {
            id: CONDITIONS[0].id,
            name: CONDITIONS[0].name,
            type: TypeEnum.condition
          }
        ]
      });
      if (!this.tagList[this.tagList.length - 1].tags.some(item => item.type === TypeEnum.input)) {
        this.tagList[this.tagList.length - 1].tags.push(inputTag);
      }
      const len = this.tagList.length;
      this.curList = [...this.filterKeyList()];
      this.curIndex = [len - 1, 1];
      this.selectType = TypeEnum.key;
      this.setInputFocus();
    } else {
      this.addActive = true;
      this.curList = CONDITIONS;
      this.selectType = TypeEnum.condition;
    }
    this.$nextTick(() => {
      this.showPopFn();
    });
  }
  handleAddFirst(event: Event) {
    if (this.canNotClick) {
      return;
    }
    event.stopPropagation();
    this.addActive = true;
    this.curList = [...this.filterKeyList()];
    this.curIndex = [0, 0];
    this.selectType = TypeEnum.key;
    this.$nextTick(() => {
      this.showPopFn(event);
    });
  }
  /* 删除条件 */
  handleDelCondition(event: Event, index: number) {
    if (this.canNotClick) {
      return;
    }
    event.stopPropagation();
    if (this.tagList.length > 1) {
      this.tagList.splice(index, 1);
    } else {
      this.tagList[index].condition = null;
      this.tagList[index].tags = [];
    }
    this.curIndex = [index, 0];
    this.handleChange();
  }

  /* 筛选key选项 */
  filterKeyList() {
    const keySet = new Set();
    this.tagList.forEach(item => {
      keySet.add(item.condition?.field || '');
    });
    return this.keyList
      .filter(
        item =>
          !keySet.has(item.id) &&
          (this.keyTypeTag === EKeyTags.all ? true : !!KEY_TAG_MAPS[this.keyTypeTag]?.includes(item.id))
      )
      .map(item => ({
        ...item,
        isGroupKey: this.groupKey.includes(item.id)
      }));
  }

  /* 派出数据 */
  handleChange() {
    let isChange = true;
    this.judgeSettingsConditionChange(() => {
      isChange = false;
    });
    if (isChange) this.emitValue();
  }

  emitValue() {
    try {
      this.locaLValue = JSON.parse(
        JSON.stringify(this.tagList.filter(item => !!item.condition?.value?.length).map(item => item.condition))
      );
      if (JSON.stringify(this.locaLValue) !== JSON.stringify(this.value)) {
        this.$emit('change', this.locaLValue);
      }
      if (this.needValidate) {
        this.validate();
        this.isRepeat = this.getHasRepeatData();
      }
    } catch (e) {
      console.log(e);
    }
  }

  /* 聚焦输入框 */
  setInputFocus() {
    this.$nextTick(() => {
      this.inputRef?.focus?.();
    });
  }
  /* 自定义输入 */
  handleInputKeydown(event: KeyboardEvent, index: number, tagIndex: number) {
    const hiddenFn = (isOnlyHide = false) => {
      this.handlePopoverHidden(isOnlyHide);
    };
    if (event.key === 'Enter') {
      if (this.selectType === TypeEnum.key) {
        if (!!this.inputValue) {
          const keyItem = this.keyList.find(kItem => kItem.name === this.inputValue);
          if (tagIndex === 0) {
            this.tagList[index].condition = {
              ...JSON.parse(JSON.stringify(defaultCondition)),
              field: keyItem?.id || this.inputValue
            };
            this.tagList[index].tags.push({
              id: keyItem?.id || this.inputValue,
              name: keyItem?.name || this.inputValue,
              type: TypeEnum.key
            });
          } else {
            /* 多行 */
            this.tagList[index].condition.field = this.inputValue;
            this.tagList[index].tags.splice(tagIndex, 1, {
              id: keyItem?.id || this.inputValue,
              name: keyItem?.name || this.inputValue,
              type: TypeEnum.key
            });
          }
          this.curIndex = [index, 0];
          this.handleChange();
          /* 自动弹出 */
          setTimeout(() => {
            this.handleClickLineWrap(null, this.curIndex[0]);
          }, 100);
        }
      } else if (this.selectType === TypeEnum.value) {
        if (!!this.inputValue) {
          const curValues = this.tagList[index].condition.value;
          if (!curValues.includes(this.inputValue)) {
            const key = this.tagList[index].condition.field;
            const values = this.getCurValuesList(key);
            const valueItem = values.find(vItem => vItem.id === this.inputValue);
            this.tagList[index].condition.value.push(this.inputValue);
            this.tagList[index].tags.splice(tagIndex, 0, {
              id: valueItem?.id || this.inputValue,
              name: valueItem?.name || this.inputValue,
              type: TypeEnum.value
            });
            if (this.tagList[index].condition.value.includes(nullOption.id)) {
              /* 清除空选项 */
              const delIndex = this.tagList[index].condition.value.findIndex(v => v === nullOption.id);
              const tagDelIndex = this.tagList[index].tags.findIndex(
                t => t.type === TypeEnum.value && t.id === nullOption.id
              );
              if (delIndex > -1) {
                this.tagList[index].condition.value.splice(delIndex, 1);
              }
              if (tagDelIndex > -1) {
                this.tagList[index].tags.splice(tagDelIndex, 1);
              }
            }
            this.curIndex = [index, 0];
            this.handleChange();
          }
        }
      }
      this.inputValue = '';
      hiddenFn();
    } else if (event.key === 'Backspace') {
      if (!this.inputValue) {
        const typeList = this.tagList[index].tags.map(item => item.type);
        // 删除到key时
        if (!typeList.includes(TypeEnum.method) && !typeList.includes(TypeEnum.value)) {
          // 只剩一行是
          if (this.tagList.length > 1) {
            this.tagList.splice(index, 1);
            this.curIndex = [index - 1, 0];
          } else {
            this.tagList[index].condition = null;
            this.tagList[index].tags = [];
            this.curIndex = [0, 0];
          }
        } else {
          this.tagList[index].tags.splice(tagIndex - 1, 1);
          this.tagList[index].condition.value = this.tagList[index].tags
            .filter(item => item.type === TypeEnum.value)
            .map(item => item.id);
          this.curIndex = [index, 0];
        }

        this.handlePopoverHidden(true);
        this.setInputFocus();
        this.handleChange();
      }
    } else {
      hiddenFn(true);
    }
  }

  handleInput() {
    if (this.focusType === strategyField) {
      this.inputValue = '';
    }
  }

  /* 根据下标判断当前条件是否与统一设置冲突了 */
  judgeSettingsConditionChange(show?: () => void) {
    if (!this.settingsValue.length) {
      return;
    }
    try {
      const curCondition = JSON.parse(JSON.stringify(this.locaLValue?.[this.curIndex[0]]));
      let isIncluesSettings = false;
      curCondition.value = [...new Set(curCondition.value)];
      if (!!curCondition) {
        isIncluesSettings = conditionsInclues(curCondition, this.settingsValue);
      }
      if (isIncluesSettings) {
        show?.();
        this.locaLValueCache = JSON.parse(JSON.stringify(this.locaLValue));
        setTimeout(() => {
          this.handleSettingsPopShow();
        }, 200);
      }
    } catch (e) {
      console.log(e);
    }
  }
  /* 确认变更 */
  handleSettingsPopConfirm() {
    this.$emit('settingsChange');
    this.handleSettingsPopHidden();
    this.emitValue();
  }
  /* 取消变更 */
  handleSettingsPopCancel() {
    this.locaLValue = JSON.parse(JSON.stringify(this.locaLValueCache));
    this.handleConditionToTagList();
    this.locaLValueCache = [];
    this.handleSettingsPopHidden();
    this.emitValue();
  }
  /* 校验是否为空 */
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
      this.errorMsg = !this.locaLValue.length ? this.$t('注意: 必填字段不能为空') : '';
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

  /** 检验条件是否有相同的key */
  validateConditionsRepeatKey() {
    if (this.readonly) return;
    const keyList = this.locaLValue.map(item => item.field);
    const newKeyList = [...new Set(keyList)];
    if (keyList.length !== newKeyList.length) {
      this.isErr = true;
      this.$emit('validate', this.isErr);
      this.errorMsg = this.$t('注意: 名字冲突');
      return;
    }
    this.errorMsg = '';
  }

  handleClickKeyTypeTag(tag: { id: EKeyTags }) {
    if (this.keyTypeTag !== tag.id) {
      this.keyTypeTag = tag.id;
      this.curList = [...this.filterKeyList()];
      this.handleSecondPopHidden();
    }
  }

  render() {
    return (
      <div
        class={['common-condition-new-component', { 'is-err': this.isErr || this.isRepeat }]}
        v-bkloading={{ isLoading: this.loading, mode: 'spin', size: 'mini', zIndex: 10 }}
        id={this.componentId}
        onMouseenter={this.handleMouseEnter}
        onMouseleave={this.handleMouseLeave}
        onClick={this.handleComponentClick}
      >
        {/* 校验提示信息 */}
        {this.isRepeat && <div class='repeat-tag'>{this.$t('重复')}</div>}
        {this.isErr && (
          <div
            class='err-tag'
            v-bk-tooltips={{
              content: this.errorMsg,
              placements: ['top'],
              allowHTML: false
            }}
          >
            <span class='icon-monitor icon-mind-fill'></span>
          </div>
        )}
        {this.tagList.map((item, index) => (
          <div
            key={index}
            class='line-wrap'
            style={{ height: this.tagList.length > 1 ? 'auto' : '100%' }}
            onClick={(event: MouseEvent) => this.handleClickLineWrap(event, index)}
          >
            <div class={['rule-line-item', { 'is-replace': item.isReplace }]}>
              {item.tags.map((tag, tagIndex) => {
                switch (tag.type) {
                  // case TypeEnum.condition: {
                  //   return <div key={`${index}_${tagIndex}`}
                  //     class="common-tag tag-condition"
                  //     v-bk-tooltips={{
                  //       content: tag.id,
                  //       placements: ['top'],
                  //       delay: [500, 0]
                  //     }}>
                  //     <span>{tag.name}</span>
                  //   </div>;
                  // }
                  case TypeEnum.key: {
                    return (
                      <div
                        key={`${index}_${tagIndex}`}
                        class='common-tag tag-key'
                        v-bk-tooltips={{
                          content: tag.id,
                          placements: ['top'],
                          delay: [500, 0],
                          allowHTML: false
                        }}
                        onClick={e => this.handleClickKeyTag(e, index, tagIndex)}
                      >
                        <span>{tag?.alias || tag.name}</span>
                      </div>
                    );
                  }
                  case TypeEnum.method: {
                    return (
                      <div
                        key={`${index}_${tagIndex}`}
                        class='common-tag tag-method'
                        v-bk-tooltips={{
                          content: tag.id,
                          placements: ['top'],
                          delay: [500, 0],
                          allowHTML: false
                        }}
                        onClick={e => this.handleClickTagMethod(e, index, tagIndex)}
                      >
                        <span>{tag.name}</span>
                      </div>
                    );
                  }
                  case TypeEnum.value: {
                    return (
                      <div
                        key={`${index}_${tagIndex}`}
                        class='common-tag tag-value'
                        v-bk-tooltips={{
                          content: tag.id,
                          placements: ['top'],
                          delay: [500, 0],
                          allowHTML: false
                        }}
                        onClick={e => this.handleClickTagValue(e, index, tagIndex)}
                      >
                        <span class='tag-value-name'>{tag.name}</span>
                        {tag.name !== NULL_NAME && !this.readonly && (
                          <span
                            class='icon-monitor icon-mc-close'
                            onClick={e => this.handDelValue(e, index, tagIndex)}
                          ></span>
                        )}
                      </div>
                    );
                  }
                  case TypeEnum.input: {
                    return (
                      <div
                        key={`${index}_input`}
                        class='input-wrap'
                      >
                        <span class='input-value'>{this.inputValue}</span>
                        <input
                          class='input'
                          ref='input'
                          v-model={this.inputValue}
                          onBlur={this.handBlur}
                          onInput={this.handleInput}
                          onKeydown={e => this.handleInputKeydown(e, index, tagIndex)}
                        ></input>
                      </div>
                    );
                  }
                  default: {
                    return undefined;
                  }
                }
              })}
              {(() => {
                if (this.readonly) {
                  return undefined;
                }
                if (this.tagList.length <= 1 && !this.tagList?.[0]?.condition) {
                  if (this.isFormMode) {
                    return !this.inputValue && <span class='placeholder-txt'>{this.$t('选择条件')}</span>;
                  }
                  return (
                    <div
                      class={['tag-add no-dispaly-none', { active: this.addActive }]}
                      onClick={this.handleAddFirst}
                    >
                      <span class='icon-monitor icon-plus-line'></span>
                    </div>
                  );
                }
                return undefined;
              })()}
            </div>

            {/* {!!item.condition?.field && !this.readonly && <div class="common-tag tag-del" key="del" v-bk-tooltips={{
            content: this.$t('删除当前条件'),
            placements: ['top'],
            delay: [500, 0]
          }}
          onClick={e => this.handleDelCondition(e, index)}>
            <span class="icon-monitor icon-mc-delete-line"></span>
          </div>} */}
          </div>
        ))}
        {!!this.tagList[this.tagList.length - 1]?.condition?.value?.length && !this.readonly && (
          <div
            key='add'
            class='line-wrap add-type'
            onClick={this.handleAdd}
          >
            <div
              class={['tag-add', { active: this.addActive }, { permanent: !this.isFormMode }]}
              onClick={this.handleAdd}
            >
              <span class='icon-monitor icon-plus-line'></span>
            </div>
          </div>
        )}
        <div style={'display: none;'}>
          <div
            class={['common-condition-component-pop-wrap', { 'key-type': this.selectType === TypeEnum.key }]}
            ref='wrap'
            id={this.componentId}
          >
            {/* value搜索输入框 */}
            {[TypeEnum.value, TypeEnum.key].includes(this.selectType) && (
              <div class='search-wrap'>
                <bk-input
                  value={this.searchValue}
                  left-icon='bk-icon icon-search'
                  placeholder={window.i18n.t('输入关键字搜索')}
                  behavior={'simplicity'}
                  onChange={this.handleSearchChange}
                ></bk-input>
              </div>
            )}
            {/* key选项类型筛选栏  */}
            {this.selectType === TypeEnum.key && (
              <div class='type-list-wrap'>
                <HorizontalScrollContainer
                  isWatchWidth={true}
                  smallBtn={true}
                >
                  <div class='type-list'>
                    {KEY_FILTER_TAGS.map(tag => (
                      <div
                        class={['type-list-item', { active: this.keyTypeTag === tag.id }]}
                        key={tag.id}
                        onClick={() => this.handleClickKeyTypeTag(tag)}
                      >
                        {tag.name}
                      </div>
                    ))}
                  </div>
                </HorizontalScrollContainer>
              </div>
            )}
            <div class='wrap-list'>
              {(() => {
                /* key可选项列表 */
                if (this.selectType === TypeEnum.key) {
                  const results = this.curList.filter(
                    item => item.id.indexOf(this.searchValue) > -1 || item.name.indexOf(this.searchValue) > -1
                  );
                  return results.length ? (
                    results.map((item, index) => (
                      <div
                        key={index}
                        class={['list-item', { mt1: !!item?.isGroupKey }]}
                        // v-bk-tooltips={{
                        //   content: item.id,
                        //   placements: ['right'],
                        //   disabled: !!item?.isGroupKey,
                        //   delay: [300, 0]
                        // }}
                        onMousedown={() => this.handleSelectKey(item)}
                        onMouseenter={e => this.handleKeyMouseEnter(e, item)}
                      >
                        <span>{item.name}</span>
                        {!!item?.isGroupKey && <span class='right icon-monitor icon-arrow-right'></span>}
                      </div>
                    ))
                  ) : (
                    <div class='no-data-item'>{this.$t('暂无数据')}</div>
                  );
                }
                /* 连接符可选项 */
                if (this.selectType === TypeEnum.method || this.selectType === TypeEnum.condition) {
                  return this.curList.map((item, index) => (
                    <div
                      key={index}
                      class={['list-item']}
                      v-bk-tooltips={{
                        content: item.id,
                        placements: ['right'],
                        delay: [300, 0],
                        allowHTML: false
                      }}
                      onMousedown={() =>
                        this.selectType === TypeEnum.method
                          ? this.handleSelectMethod(item)
                          : this.handleSelectCondition(item)
                      }
                    >
                      <span>{item.name}</span>
                    </div>
                  ));
                }
                /* value可选项列表 */
                if (this.selectType === TypeEnum.value) {
                  if (this.tagList[this.curIndex[0]]?.condition?.field === strategyField) {
                    /* 策略的样式特殊 */
                    const results = this.curList.filter(
                      item => item.id.indexOf(this.searchValue) > -1 || item.name.indexOf(this.searchValue) > -1
                    );
                    return results.length ? (
                      results.map((item, index) => (
                        <div
                          key={index}
                          class={['list-item', { 'is-check': !!item?.isCheck }]}
                          v-bk-tooltips={{
                            content: item.id,
                            placements: ['right'],
                            delay: [300, 0],
                            disabled: !item.id,
                            allowHTML: false
                          }}
                          onMousedown={() => this.handleSelectValue(item)}
                        >
                          <span>
                            <span>{item.name}</span>
                            {!!item.id && (
                              <span class='strategy-name-info'>{`${item.first_label_name || ''} (#${item.id})`}</span>
                            )}
                          </span>
                          {!!item?.isCheck && <span class='right icon-monitor icon-mc-check-small'></span>}
                        </div>
                      ))
                    ) : (
                      <div class='no-data-item'>{this.$t('暂无数据')}</div>
                    );
                  }
                  const results = this.curList.filter(
                    item => item.id.indexOf(this.searchValue) > -1 || item.name.indexOf(this.searchValue) > -1
                  );
                  return results.length ? (
                    results.map((item, index) => (
                      <div
                        key={index}
                        class={['list-item', { 'is-check': !!item?.isCheck }]}
                        v-bk-tooltips={{
                          content: item.id,
                          placements: ['right'],
                          delay: [300, 0],
                          disabled: !item.id,
                          allowHTML: false
                        }}
                        onMousedown={() => this.handleSelectValue(item)}
                      >
                        <span>{item.name}</span>
                        {!!item?.isCheck && <span class='right icon-monitor icon-mc-check-small'></span>}
                      </div>
                    ))
                  ) : (
                    <div class='no-data-item'>{this.$t('暂无数据')}</div>
                  );
                }
              })()}
            </div>
            {/* 删除条件 */}
            {this.selectType === TypeEnum.key && (
              <div
                class='del-bottom'
                onClick={this.handleDelKey}
              >
                <span class='icon-monitor icon-mc-delete-line'></span>
                <span class='del-text'>{this.$t('删除')}</span>
              </div>
            )}
          </div>
        </div>
        {/* 二级选项列表 */}
        <div style={'display: none'}>
          <div
            class='common-condition-component-second-pop-wrap'
            ref='secondWrap'
          >
            <div class='search-wrap'>
              <bk-input
                value={this.secondSearch}
                left-icon='bk-icon icon-search'
                placeholder={window.i18n.t('输入关键字搜索')}
                behavior={'simplicity'}
                onChange={this.handleSecondSearchChange}
              ></bk-input>
            </div>
            {this.keyListSecond.length ? (
              <div class='wrap-list'>
                {this.keyListSecond
                  .filter(item => item.id.indexOf(this.secondSearch) > -1 || item.name.indexOf(this.secondSearch) > -1)
                  .map(item => (
                    <div
                      key={item.id}
                      class='list-item key-type'
                      onMousedown={() => this.handleClickSecondKey(item)}
                      v-bk-tooltips={{
                        content: item.id,
                        placements: ['right'],
                        delay: [300, 0],
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
        {/* 统一设置提示 */}
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
      </div>
    );
  }
}
