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
import { computed, defineComponent, onMounted, ref } from 'vue';
import { useI18n } from 'vue-i18n';

import { Exception, Input, Loading, Popover } from 'bkui-vue';

import { incidentHandlers } from '../../../../monitor-api/modules/incident';
import { useIncidentInject } from '../utils';

import './handler-list.scss';

interface IHandleListItem {
  alert_count: number;
  id: string;
  index?: number;
  name: string;
  children?: Array<IHandleListItem>;
}
interface IHandleData {
  all: object;
  mine: object;
  not_dispatch: object;
  other: object;
}
export default defineComponent({
  name: 'HandlerList',
  emits: ['click'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const handlersList = ref<IHandleData>({
      all: {},
      mine: {},
      not_dispatch: {},
      other: {},
    });
    const orderByType = ref('abnormal_alert_count');
    const listLoading = ref<boolean>(false);
    const sortRef = ref<HTMLDivElement>();
    const searchText = ref<string>('');
    const incidentId = useIncidentInject();
    const activeId = ref<string>('admin');
    const getIncidentHandlers = () => {
      listLoading.value = true;
      incidentHandlers({
        id: incidentId.value,
        order_by: orderByType.value,
      })
        .then(res => {
          handlersList.value = res;
        })
        .catch(err => {
          console.log(err);
        })
        .finally(() => (listLoading.value = false));
    };
    const filterList = [
      {
        name: t('未恢复告警数'),
        icon: 'AlertSort',
        key: 'abnormal_alert_count',
      },
      {
        name: t('名称 A-Z '),
        icon: 'A-ZSort',
        key: 'bk_username',
      },
    ];
    const searchResult = computed(() => {
      let result = handlersList.value.other?.children || [];
      if (searchText.value !== '') {
        result = (handlersList.value.other?.children || []).filter(operation =>
          operation.id.includes(searchText.value)
        );
      }
      return result;
    });
    const filterListHandle = (key: string) => {
      sortRef.value?.hide();
      orderByType.value = key;
      getIncidentHandlers();
    };
    const handleClickItem = (item: IHandleListItem) => {
      activeId.value = item.id;
      emit('click', item);
    };
    const listFn = (list: Array<IHandleListItem>, isShowEmpty = false) => {
      if (isShowEmpty && list.length === 0) {
        return (
          <Exception
            description={searchText.value !== '' ? t('搜索数据为空') : t('暂无其他告警负责人')}
            scene='part'
            type='empty'
          >
            {searchText.value !== '' && (
              <span
                class='clear-btn'
                onClick={() => (searchText.value = '')}
              >
                {t('清空筛选条件')}
              </span>
            )}
          </Exception>
        );
      }
      return list.map((item: IHandleListItem) => (
        <div
          class={['list-item', { active: item.id === activeId.value }]}
          onClick={() => handleClickItem(item)}
        >
          <span class='item-head'>
            <i class={`icon-monitor icon-mc-${item.id === 'all' ? 'all' : 'user-one'} head-icon`} />
          </span>
          <span
            class='item-name'
            title={item.name}
          >
            {item.name}
          </span>
          {item.alert_count === 0 ? (
            <i class='icon-monitor icon-mc-check-small item-icon'></i>
          ) : (
            <label class='item-total'>{item.alert_count}</label>
          )}
        </div>
      ));
    };
    onMounted(() => {
      getIncidentHandlers();
    });
    return {
      sortRef,
      listFn,
      handlersList,
      t,
      listLoading,
      filterList,
      orderByType,
      filterListHandle,
      searchText,
      searchResult,
    };
  },
  render() {
    const { all = {}, mine = {} } = this.handlersList;
    return (
      <div class='handler-list'>
        <div class='handler-list-head'>
          <Input
            class='head-input'
            v-model={this.searchText}
            placeholder={this.t('搜索 故障处理人')}
            type='search'
            clearable
            show-clear-only-hover
            on-clear={() => (this.searchText = '')}
          />
          <Popover
            ref='sortRef'
            extCls='sort-popover'
            v-slots={{
              content: () =>
                this.filterList.map(item => (
                  <span
                    class={`sort-item ${this.orderByType === item.key ? 'active' : ''}`}
                    onClick={() => this.filterListHandle(item.key)}
                  >
                    <i class={`icon-monitor icon-${item.icon} search-btn-icon`}></i>
                    {item.name}
                  </span>
                )),
            }}
            arrow={false}
            offset={{ mainAxis: 5, crossAxis: 40 }}
            placement='bottom'
            theme='light'
            trigger='click'
          >
            <span class='head-btn'>
              <i
                class={`icon-monitor icon-${
                  this.filterList.filter(item => this.orderByType === item.key)[0].icon
                } head-btn-icon`}
              />
            </span>
          </Popover>
          {/* <Dropdown
            trigger='manual'
            is-show={this.isShowDropdown}
            placement='bottom-start'
            v-slots={{
              content: () => (
                <Dropdown.DropdownMenu extCls={'search-btn-drop'}>
                  {this.filterList.map(item => (
                    <Dropdown.DropdownItem
                      extCls={`${this.orderByType === item.key ? 'active' : ''}`}
                      onClick={() => this.filterListHandle(item.key)}
                    >
                      <i class={`icon-monitor icon-${item.icon} search-btn-icon`}></i>
                      {item.name}
                    </Dropdown.DropdownItem>
                  ))}
                </Dropdown.DropdownMenu>
              ),
            }}
            is-show={this.isShowDropdown}
            placement='bottom-start'
            trigger='manual'
          >
            <span
              class='head-btn'
              onClick={() => (this.isShowDropdown = true)}
            >
              <i
                class={`icon-monitor icon-${
                  this.filterList.filter(item => this.orderByType === item.key)[0].icon
                } head-btn-icon`}
              />
            </span>
          </Dropdown> */}
        </div>
        <Loading loading={this.listLoading}>
          <div class='handler-list-main'>
            {this.listFn([all, mine])}
            <span class='item-line'></span>
            {this.listFn(this.searchResult, true)}
          </div>
        </Loading>
      </div>
    );
  },
});
