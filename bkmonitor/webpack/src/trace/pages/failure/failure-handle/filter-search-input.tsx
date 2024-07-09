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
import { computed, defineComponent, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import { Input, Message } from 'bkui-vue';
import { $bkPopover } from 'bkui-vue/lib/popover';

import { ICommonItem } from '../../../../fta-solutions/pages/event/typings/event';
import { listSearchHistory } from '../../../../monitor-api/modules/alert';
import {
  createSearchFavorite,
  destroySearchFavorite,
  partialUpdateSearchFavorite,
} from '../../../../monitor-api/modules/model';
import { docCookies, LANGUAGE_COOKIE_KEY } from '../../../../monitor-common/utils';
import { getEventPaths } from '../../../../monitor-pc/utils';
import debounceDecorator from '../../common/debounce-decorator';

import './filter-search-input.scss';

type PanelType = 'favorite' | 'field' | 'history';
type PanelShowType = 'condition' | 'field' | 'method' | 'value' | false;
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
export default defineComponent({
  name: 'FilterSearchInput',
  props: {
    value: {
      type: String,
      default: '',
      required: true,
    },
    searchType: {
      type: String,
      default: 'alert',
    },
    inputStatus: {
      type: String,
      default: 'success',
    },
    valueMap: {
      type: Object,
      default: () => ({}),
    },
    isFillId: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['change', 'blur', 'favorite', 'clear'],
  setup(props, { emit }) {
    const textTypeList = ['field', 'method', 'value', 'condition'];
    const { t } = useI18n();
    const inputValue = ref<string>('');
    const focusData = ref<IFocusData>({});
    const panelWidth = ref<number>(700);
    const blurInPanel = ref<boolean>(false);
    const popoverInstance = ref(null);
    const popoverMenuInstance = ref(null);
    const filterPanelRef = ref(null);
    const filterSearchRef = ref(null);
    const inputRef = ref(null);
    const isEn = ref(docCookies.getItem(LANGUAGE_COOKIE_KEY) === 'en');
    const historyList = ref([]);
    const favoriteList = ref([]);
    const isManualInput = ref<boolean>(false);
    const menuPanelRef = ref(null);
    const favoriteInputRef = ref(null);
    const preTextRef = ref(null);
    const textListArr = ref([]);
    /* 添加可被移除的事件监听器 */
    const mouseDownController = ref(null);
    const methodList = ref([
      {
        id: ':',
        name: ':',
      },
    ]);
    // 告警建议字段列表
    const alertFieldList = ref([
      {
        id: 'id',
        name: t('告警ID'),
      },
      {
        id: 'alert_name',
        name: t('告警名称'),
      },
      {
        id: 'status',
        name: t('状态'),
      },
      {
        id: 'description',
        name: t('告警内容'),
      },
      {
        id: 'severity',
        name: t('级别'),
      },
      {
        id: 'metric',
        name: t('指标ID'),
      },
      {
        id: 'ip',
        name: t('目标IP'),
      },
      {
        id: 'ipv6',
        name: t('目标IPv6'),
      },
      {
        id: 'bk_host_id',
        name: t('主机ID'),
      },
      {
        id: 'bk_cloud_id',
        name: t('目标云区域ID'),
      },
      {
        id: 'bk_service_instance_id',
        name: t('目标服务实例ID'),
      },
      {
        id: 'appointee',
        name: t('负责人'),
      },
      {
        id: 'assignee',
        name: t('通知人'),
      },
      {
        id: 'strategy_name',
        name: t('策略名称'),
      },
      {
        id: 'strategy_id',
        name: t('策略ID'),
      },
      {
        id: 'labels',
        name: t('策略标签'),
      },
      {
        id: 'tags',
        name: t('标签'),
        special: true,
      },
      {
        id: 'action_id',
        name: `${t('处理记录')}ID`,
      },
      {
        id: 'plugin_id',
        name: t('告警源'),
      },
    ]);
    // 故障建议字段列表
    const incidentFieldList = ref([
      {
        id: 'id',
        name: t('故障UUID'),
      },
      {
        id: 'incident_id',
        name: t('故障内部ID'),
      },
      {
        id: 'incident_name',
        name: t('故障名称'),
      },
      {
        id: 'incident_reason',
        name: t('故障原因'),
      },
      {
        id: 'bk_biz_id',
        name: t('业务ID'),
      },
      {
        id: 'status',
        name: t('故障状态'),
      },
      {
        id: 'level',
        name: t('故障级别'),
      },
      {
        id: 'assignees',
        name: t('负责人'),
      },
      {
        id: 'handlers',
        name: t('处理人'),
      },
      {
        id: 'labels',
        name: t('标签'),
      },
      {
        id: 'create_time',
        name: t('故障检出时间'),
      },
      {
        id: 'update_time',
        name: t('故障更新时间'),
      },
      {
        id: 'begin_time',
        name: t('故障开始时间'),
      },
      {
        id: 'end_time',
        name: t('故障结束时间'),
      },
      {
        id: 'snapshot',
        name: t('故障图谱快照'),
      },
    ]);
    // 处理记录建议字段列表
    const actionFieldList = ref([
      {
        id: 'id',
        name: t('处理记录ID'),
      },
      {
        id: 'action_name',
        name: t('套餐名称'),
      },
      {
        id: 'action_config_id',
        name: t('套餐ID'),
      },
      {
        id: 'strategy_name',
        name: t('策略名称'),
      },
      {
        id: 'alerts',
        name: t('关联告警'),
      },
      {
        id: 'status',
        name: t('状态'),
      },
      {
        id: 'bk_biz_name',
        name: t('业务名'),
      },
      {
        id: 'bk_biz_id',
        name: t('业务ID'),
      },
      {
        id: 'operate_target_string',
        name: t('执行对象'),
      },
      {
        id: 'action_plugin_type',
        name: t('套餐类型'),
      },
      {
        id: 'operator',
        name: t('负责人'),
      },
      {
        id: 'create_time',
        name: t('开始时间'),
      },
      {
        id: 'end_time',
        name: t('结束时间'),
      },
    ]);
    // 事件建议字段列表
    const eventFieldList = ref([
      {
        id: 'id',
        name: t('全局事件ID'),
      },
      {
        id: 'event_id',
        name: t('事件ID'),
      },
      {
        id: 'plugin_id',
        name: t('插件ID'),
      },
      {
        id: 'alert_name',
        name: t('告警名称'),
      },
      {
        id: 'status',
        name: t('状态'),
      },
      {
        id: 'description',
        name: t('描述'),
      },
      {
        id: 'severity',
        name: t('级别'),
      },
      {
        id: 'metric',
        name: t('指标ID'),
      },
      {
        id: 'assignee',
        name: t('负责人'),
      },
      {
        id: 'strategy_name',
        name: t('策略名称'),
      },
      {
        id: 'strategy_id',
        name: t('策略ID'),
      },
      {
        id: 'target_type',
        name: t('目标类型'),
      },
      {
        id: 'target',
        name: t('目标'),
      },
      {
        id: 'category',
        name: t('分类'),
      },
    ]);
    const conditionList = ref([
      {
        id: 'AND',
        name: 'AND',
      },
      {
        id: 'OR',
        name: 'OR',
      },
    ]);
    const favoriteDisable = computed(() => {
      return !Boolean(inputValue.value.length);
    });
    const fieldList = computed(() => {
      let list = [];
      switch (props.searchType) {
        case 'alert':
          list = alertFieldList.value;
          break;
        case 'action':
          list = actionFieldList.value;
          break;
        case 'event':
          list = eventFieldList.value;
          break;
        case 'incident':
          list = incidentFieldList.value;
          break;
      }
      return isEn.value ? list.map(item => ({ ...item, name: item.id })) : list;
    });
    const menuList = computed(() => {
      if (focusData.value.show === 'condition') return conditionList;
      if (focusData.value.show === 'method') return methodList;
      if (focusData.value.show === 'value') return props.valueMap?.[focusData.value.filedId] || [];
      return [];
    });
    debounceDecorator(20);
    /**
     * @description: input focus时触发
     * @param {*}
     * @return {*}
     */
    const handleInputFocus = async () => {
      if (inputValue.value?.trim?.().length < 1) {
        handleMainPopoverShow();
        return;
      }
      const ret = await handleSetInputValue();
      if (ret.show === 'field') {
        focusData.value = ret;
        handleMainPopoverShow();
      } else if (['method', 'condition', 'value'].includes(ret.show.toString())) {
        focusData.value = ret;
        if (ret.show.toString() === 'value' && !menuList.value.length) {
          destroyMenuPopoverInstance();
          destroyPopoverInstance();
          return;
        }
        handleMenuPopoverShow();
      } else {
        destroyMenuPopoverInstance();
        destroyPopoverInstance();
        focusData.value = {};
      }
    };
    /**
     * @description: 配置input输入与弹窗之间关系
     * @param {*}
     * @return {*}
     */
    const handleSetInputValue = () => {
      let valueText = inputValue.value.trimStart();
      while (/\s\s/g.test(valueText)) {
        valueText = valueText.replace(/\s\s/g, ' ');
      }
      inputValue.value = valueText;
      return new Promise<IFocusData>(resolve => {
        setTimeout(() => {
          const offset = inputRef.value.selectionStart;
          const textList = handleGetTextList(valueText);
          textListArr.value = textList;
          const filterItemIndex = textList.findIndex(item => {
            return offset >= item.startOffset && offset <= item.endOffset;
          });
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
                      fieldList.value.find(set => set.id === fieldItem.text || set.name === fieldItem.text)?.id || '';
                    if (!filedId && fieldItem.fieldKey) {
                      filedId = fieldItem.text;
                    }
                    resolve({
                      show: dataType as PanelShowType,
                      replaceStart: item.endOffset + 1,
                      nextText: '',
                      filedId,
                    });
                    break;
                  }
                }
              } else {
                resolve({
                  show: textTypeList[index % 4] as PanelShowType,
                  replaceStart: item.endOffset + 1,
                  nextText: '',
                });
              }
            } else {
              resolve({
                show: 'field',
                replaceStart: 0,
                nextText: '',
              });
            }
          } else {
            if (filterItem.dataType === 'value') {
              for (let i = filterItemIndex; i >= 0; i--) {
                if (textList[i].dataType === 'field') {
                  const item = textList[i];
                  let filedId = fieldList.value.find(set => set.id === item.text || set.name === item.text)?.id || '';
                  if (!filedId && item.fieldKey) {
                    filedId = item.text;
                  }
                  resolve({
                    show: filterItem.dataType as PanelShowType,
                    replaceStart: filterItem.startOffset,
                    nextText: filterItem.text,
                    filedId,
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
                  nextText: filterItem.text,
                });
              } else if (filterItem.dataType === 'field' && filterItem.fieldKey) {
                if (offset >= filterItem.fieldKey.startOffset && offset <= filterItem.fieldKey.endOffset) {
                  resolve({
                    show: 'field',
                    replaceStart: filterItem.startOffset,
                    nextText: filterItem.text,
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
                    filedId: filterItem.fieldKey.text,
                  });
                }
              }
            }
            resolve({
              show: false,
              replaceStart: -1,
              nextText: '',
            });
          }
        }, 20);
      });
    };
    const handleGetTextList = (valueText: string) => {
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
    };
    const handleMainPopoverShow = (onShown?: () => void) => {
      destroyMenuPopoverInstance();
      panelWidth.value = filterSearchRef.value.getBoundingClientRect().width - 64;
      if (!popoverInstance.value) {
        popoverInstance.value = $bkPopover({
          maxWidth: 800,
          always: false,
          target: filterSearchRef.value,
          content: filterPanelRef.value,
          arrow: false,
          trigger: 'manual',
          placement: 'bottom',
          theme: 'light common-monitor',
          isShow: false,
          disabled: false,
          width: 700,
          height: 'auto',
          maxHeight: '300',
          allowHtml: true,
          renderType: 'auto',
          padding: 0,
          offset: 0,
          zIndex: 9999,
          disableTeleport: false,
          autoPlacement: false,
          autoVisibility: false,
          disableOutsideClick: false,
          disableTransform: false,
          modifiers: [],
          popoverDelay: 0,
          extCls: 'filter-search-input-popover',
          componentEventDelay: 0,
          forceClickoutside: false,
          immediate: false,
        });
        popoverInstance.value.onShow = () => {
          typeof onShown === 'function' && onShown();
        };
        popoverInstance.value.onAfterHidden = () => {
          popoverInstance.value.destroy();
          popoverInstance.value = null;
        };
      } else {
        popoverInstance.value.content = filterPanelRef.value;
        popoverInstance.value.onShow = () => {
          typeof onShown === 'function' && onShown();
        };
      }
      popoverInstance.value?.popperInstance?.update?.();
      popoverInstance.value?.show?.(1000);
      mouseDownController.value = new AbortController();
      document.addEventListener('mousedown', handleMouseDown, { signal: mouseDownController.value.signal });
    };
    const handleMouseDown = (event: Event) => {
      const pathsClass = JSON.parse(JSON.stringify(getEventPaths(event).map(item => item.className)));
      if (
        !pathsClass.includes('filter-input-wrap') &&
        !pathsClass.includes('search-input') &&
        favoriteList.value.every(item => !item.edit)
      ) {
        destroyPopoverInstance();
      }
    };
    const destroyMenuPopoverInstance = () => {
      blurInPanel.value = false;
      popoverMenuInstance.value?.hide?.(0);
      popoverMenuInstance.value?.destroy?.();
      popoverMenuInstance.value = null;
    };
    const destroyPopoverInstance = () => {
      blurInPanel.value = false;
      popoverInstance.value?.hide?.(0);
      popoverInstance.value?.destroy?.();
      popoverInstance.value = null;
      mouseDownController.value?.abort?.();
    };
    const handleMenuPopoverShow = () => {
      destroyPopoverInstance();
      setTimeout(() => {
        const rect = preTextRef.value.getBoundingClientRect();
        const offsetX = rect.width + 40;
        const offsetY = -2;
        if (!popoverMenuInstance.value) {
          popoverInstance.value = $bkPopover({
            maxWidth: 400,
            always: false,
            target: filterSearchRef.value,
            content: menuPanelRef.value,
            arrow: false,
            trigger: 'manual',
            placement: 'bottom',
            theme: 'light common-monitor',
            isShow: false,
            disabled: false,
            width: 300,
            height: 'auto',
            maxHeight: '300',
            allowHtml: true,
            renderType: 'auto',
            padding: 0,
            offset: { mainAxis: offsetX, crossAxis: offsetY },
            zIndex: 9999,
            disableTeleport: false,
            autoPlacement: false,
            autoVisibility: false,
            disableOutsideClick: false,
            disableTransform: false,
            modifiers: [],
            popoverDelay: 0,
            extCls: 'filter-menu-popover',
            componentEventDelay: 0,
            forceClickoutside: false,
            immediate: false,
          });
        } else {
          popoverMenuInstance.value.set({
            offset: `${offsetX}, ${offsetY}`,
          });
        }
        popoverMenuInstance.value?.popperInstance?.update?.();
        popoverMenuInstance.value?.show?.(100);
      }, 20);
    };
    const handleInput = (e: any) => {
      inputValue.value = e.target.value;
    };
    /**
     * @description: 搜索条件变更时触发
     * @param {*}
     * @return {*}
     */
    const handleChange = () => {
      if (!blurInPanel.value) {
        popoverInstance.value?.hide?.(0);
        popoverMenuInstance.value?.hide?.(0);
        handleGetSearchHistory();
        emit('change', inputValue.value);
      }
    };
    const handleGetSearchHistory = async () => {
      const data = await listSearchHistory({ search_type: props.searchType });
      historyList.value = data
        ?.filter(item => item?.params?.query_string)
        .map((item, id) => ({ id, name: item.params.query_string }));
    };
    const handleBlur = () => {
      if (!blurInPanel.value) {
        emit('blur', inputValue.value);
        handleChange();
      }
    };
    /**
     * @description: key down事件
     * @param {KeyboardEvent} e
     * @return {*}
     */
    const handleKeydown = (e: KeyboardEvent) => {
      if (e.code === 'Enter') {
        e.preventDefault();
        e.stopPropagation();
        handleChange();
      } else if (e.code === 'Space' || e.code === 'Backspace') {
        setTimeout(() => {
          handleInputFocus();
        }, 16);
      } else {
        // 是否手动输入
        isManualInput.value = true;
      }
    };
    /**
     * @description: 用于变更input值
     * @param {string} name
     * @return {*}
     */
    const handleReplaceInputValue = (name: string, seperator = ' ') => {
      const { show, nextText, replaceStart } = focusData.value;
      const valueList = inputValue.value.split('');
      let selection = 0;
      if (show) {
        if (nextText) {
          valueList.splice(replaceStart, nextText.length, name).join('');
          selection = replaceStart + name.length + 1;
        } else {
          valueList.splice(replaceStart, 0, `${name}${seperator}`).join('');
          selection = replaceStart + `${name}${seperator}`.length;
        }
        inputValue.value = valueListTidy(valueList).join('');
        if (inputValue.value.length < selection) {
          inputValue.value = inputValue.value + seperator;
        }
      } else {
        inputValue.value += `${name}${seperator}`;
        selection = inputValue.value.length;
      }
      inputRef.value.selectionStart = selection;
      inputRef.value.selectionEnd = selection;
      setTimeout(() => {
        inputRef.value.selectionStart = selection;
        inputRef.value.selectionEnd = selection;
        handleInputFocus();
      }, 20);
    };
    const handleEidtFavorite = (e: MouseEvent, item: IListItem) => {
      e.preventDefault();
      e.stopPropagation();
      blurInPanel.value = true;
      item.edit = true;
      setTimeout(() => {
        // (this.$refs[`favorite-input-${item.id}`] as any)?.focus();
      }, 20);
    };
    // 删除收藏触发
    const handleDeleteFavorite = async (e: MouseEvent, item: IListItem, index: number) => {
      e.stopPropagation();
      blurInPanel.value = true;
      const data = await destroySearchFavorite(item.id);
      Message({
        message: data ? t('删除成功') : t('删除失败'),
        theme: data ? 'success' : 'error',
      });
      if (data) {
        favoriteList.value.splice(index, 1);
        item.edit = false;
      }
      //   await this.$nextTick();
      inputRef.value.focus();
      blurInPanel.value = false;
    };
    const handleFavoriteInputBlur = (e: MouseEvent, item: IListItem) => {
      if (item.id === 'favorite') {
        blurInPanel.value = false;
      }
      item.edit = false;
    };
    /**
     * @description: 编辑收藏触发
     * @param {MouseEvent} e
     * @param {IListItem} item
     * @return {*}
     */
    const handleUpdateFavorite = async (e: MouseEvent, item: IListItem) => {
      if (!item?.fakeName?.trim?.().length) {
        e.preventDefault();
        e.stopPropagation();
        return;
      }
      if (/(\ud83c[\udf00-\udfff])|(\ud83d[\udc00-\ude4f\ude80-\udeff])|[\u2600-\u2B55]/g.test(item.fakeName)) {
        Message({
          message: t('不能输入emoji表情'),
          theme: 'error',
        });
        e.preventDefault();
        e.stopPropagation();
        return;
      }
      if (item.fakeName !== item.name) {
        // 新建收藏
        if (item.id === 'favorite') {
          if (favoriteList.value.some(f => f.name === item.fakeName)) {
            Message({
              message: t('名称重复'),
              theme: 'error',
            });
            e.preventDefault();
            e.stopPropagation();
            return;
          }
          const data = await createSearchFavorite({
            search_type: props.searchType,
            name: item.fakeName,
            params: {
              query_string: inputValue.value,
            },
          });
          Message({
            message: data ? t('收藏成功') : t('收藏失败'),
            theme: data ? 'success' : 'error',
          });
          if (data) {
            favoriteList.value.unshift({
              id: data.id,
              name: data.name,
              fakeName: data.name,
              queryString: data.params?.query_string || '',
              edit: false,
            });
          }
          item.edit = !data;
        } else {
          const data = await partialUpdateSearchFavorite({
            id: item.id,
            params: {
              name: item.fakeName,
            },
          });
          Message({
            message: data ? t('更新成功') : t('更新失败'),
            theme: data ? 'success' : 'error',
          });
          item.name = data ? item.fakeName : item.name;
          item.edit = !data;
        }
      }
    };
    const handleSelectPanelItem = (e: MouseEvent, id: PanelType, item: IListItem) => {
      e.preventDefault();
      e.stopPropagation();
      if (id === 'field') {
        if (!inputValue.value?.length) {
          inputValue.value = item.special ? `${item.id}.` : `${item.name} : `;
          setTimeout(() => {
            handleInputFocus();
          }, 20);
          return;
        }
        handleReplaceInputValue(item.special ? `${item.id}.` : `${item.name.toString()} : `, item.special ? '' : ' ');
      } else if (id === 'history') {
        inputValue.value = String(item.name);
        blurInPanel.value = false;
        handleChange();
      } else if (id === 'favorite') {
        inputValue.value = item.queryString;
        blurInPanel.value = false;
        handleChange();
      }
    };
    const commonPanelComponent = (id: PanelType, list: any[]) => {
      return (
        <ul class='panel-list'>
          {list.map((item, index) => (
            <li
              key={item.id}
              class={[
                'panel-list-item',
                {
                  'item-active':
                    id === 'field' &&
                    focusData.value.show === 'field' &&
                    (item.id === focusData.value.nextText || item.name === focusData.value.nextText),
                },
              ]}
              onMousedown={e => !item.edit && handleSelectPanelItem(e, id, item)}
            >
              {!item.edit && <span>{item.name}</span>}
              {id === 'field' && !item.edit && !isEn.value && <span class='item-id'>({item.id})</span>}
              {id === 'favorite' &&
                !item.edit && [
                  <i
                    class='icon-monitor icon-bianji edit-icon'
                    onMousedown={e => handleEidtFavorite(e, item)}
                  />,
                  <i
                    class='icon-monitor icon-mc-close close-icon'
                    onMousedown={e => handleDeleteFavorite(e, item, index)}
                  />,
                ]}
              {id === 'favorite' &&
                item.edit && [
                  <Input
                    ref={`favorite-input-${item.id}`}
                    class='favorite-input'
                    v-model={item.fakeName}
                    placeholder={t('输入收藏名称')}
                    type='text'
                    on-blur={e => handleFavoriteInputBlur(e, item)}
                  />,
                  <i
                    class={[
                      'icon-monitor icon-mc-check-small check-icon',
                      { 'is-diabled': !item?.fakeName?.trim?.().length },
                    ]}
                    onMousedown={e => handleUpdateFavorite(e, item)}
                  />,
                ]}
            </li>
          ))}
        </ul>
      );
    };
    const panelEmptyComponent = (content?: string) => {
      return <div class='panel-empty'>{content || t('暂无数据')}</div>;
    };
    /**
     * @description: 选择 condition method时触发
     * @param {MouseEvent} e
     * @param {IListItem} item
     * @return {*}
     */
    const handleSelectMenuItem = (e: MouseEvent, item: IListItem) => {
      e.preventDefault();
      e.stopPropagation();
      handleReplaceInputValue(props.isFillId ? item.id.toString() : item.name.toString());
    };
    /**
     * @description: 点击收藏触发
     * @param {MouseEvent} e
     * @return {*}
     */
    const handleSetFavorite = (e: MouseEvent) => {
      if (favoriteDisable.value) return;
      e.preventDefault();
      if (inputValue.value?.length) {
        handleRemoveNewFavorite();
        inputValue.value &&
          favoriteList.value.unshift({
            name: '',
            id: 'favorite',
            fakeName: '',
            queryString: '',
            edit: true,
          });
        favoriteList.value.forEach(item => {
          if (!!item.name) {
            item.edit = false;
            item.fakeName = String(item.name);
          }
        });
        handleMainPopoverShow(() => {
          setTimeout(() => {
            blurInPanel.value = true;
            favoriteInputRef.value?.focus();
          }, 20);
        });
        emit('favorite');
      } else {
        handleMainPopoverShow();
      }
    };
    /**
     * @description: 清空上次收藏内容
     * @param {*}
     * @return {*}
     */
    const handleRemoveNewFavorite = () => {
      const index = favoriteList.value.findIndex(item => item.id === 'favorite');
      index > -1 && favoriteList.value.splice(index, 1);
    };
    const handleClear = () => {
      inputValue.value = '';
      isManualInput.value = false;
      emit('clear', '');
    };
    watch(
      () => props.value,
      (val: string) => {
        inputValue.value = val;
        if (!val) {
          isManualInput.value = false;
        }
      },
      { immediate: true }
    );
    watch(
      () => props.searchType,
      () => {
        handleGetSearchHistory();
        // handleGetSearchFavorite();
      },
      { immediate: true }
    );
    return {
      t,
      handleClear,
      menuList,
      commonPanelComponent,
      panelEmptyComponent,
      filterSearchRef,
      filterPanelRef,
      inputRef,
      favoriteDisable,
      inputValue,
      focusData,
      panelWidth,
      handleInputFocus,
      handleInput,
      handleBlur,
      handleKeydown,
      alertFieldList,
      incidentFieldList,
      actionFieldList,
      eventFieldList,
      historyList,
      favoriteList,
      fieldList,
      handleSelectMenuItem,
      handleSetFavorite,
      preTextRef,
      menuPanelRef,
    };
  },
  render() {
    return (
      <div
        ref='filterSearchRef'
        class='filter-input-wrap'
      >
        <div class='filter-search'>
          <Input
            ref='inputRef'
            style={{ borderColor: this.$props.inputStatus === 'error' ? '#ff5656' : '#c4c6cc' }}
            v-model={this.inputValue}
            v-slots={{
              prefix: () => <i class='icon-monitor icon-filter-fill filter-icon' />,
              suffix: () => (
                <span
                  class={['filter-favorites', { 'is-disable': this.favoriteDisable }]}
                  onMousedown={this.handleSetFavorite}
                >
                  <i class='icon-monitor icon-mc-uncollect favorite-icon'></i>
                  {this.t('收藏')}
                </span>
              ),
            }}
            clearable={true}
            placeholder={String(this.t('输入搜索条件'))}
            onBlur={this.handleBlur}
            onClear={this.handleClear}
            onFocus={this.handleInputFocus}
            onInput={this.handleInput}
            onKeydown={this.handleKeydown}
          />
        </div>
        <div style='display: none;'>
          <div
            ref='filterPanelRef'
            style={{ width: `${this.panelWidth}px` }}
            class='filter-input-panel'
          >
            <div class='field-panel common-panel'>
              <div class='panel-title'>{this.t('建议字段')}</div>
              {this.fieldList?.length ? this.commonPanelComponent('field', this.fieldList) : this.panelEmptyComponent()}
            </div>
            <div class='search-panel common-panel'>
              <div class='panel-title'>{this.t('最近搜索')}</div>
              {this.historyList?.length
                ? this.commonPanelComponent('history', this.historyList)
                : this.panelEmptyComponent(this.t('暂无搜索'))}
            </div>
            <div class='favorite-panel common-panel'>
              <div class='panel-title'>{this.t('收藏')}</div>
              {this.favoriteList?.length
                ? this.commonPanelComponent('favorite', this.favoriteList)
                : this.panelEmptyComponent(this.t('暂无收藏'))}
            </div>
          </div>
        </div>
        <div style='display: none;'>
          <ul
            ref='menuPanelRef'
            class='condition-list'
          >
            {this.menuList.length
              ? this.menuList.map(item => (
                  <li
                    key={item.id}
                    class={[
                      'condition-list-item',
                      {
                        'item-active': item.id === this.focusData.nextText || item.name === this.focusData.nextText,
                      },
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
  },
});
