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
import { computed, defineComponent, PropType, reactive, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { Button, Form, Input, Popover } from 'bkui-vue';

import './application-cascade.scss';

export default defineComponent({
  name: 'ApplicationCascade',
  props: {
    list: {
      type: Array as PropType<any>,
      default: () => []
    },
    value: {
      type: [String, Number],
      required: true
    }
  },
  emits: ['change'],
  setup(props, { emit }) {
    const { t } = useI18n();

    /** 筛选 */
    const searchKey = ref('');
    /** 一级选项列表 */
    const selectList = computed(() => {
      const list = { hasData: [], noData: [] };
      props.list.forEach(item => {
        if (!item.name.includes(searchKey.value)) return;
        if (item.children?.length) {
          list.hasData.push(item);
        } else {
          list.noData.push(item);
        }
      });
      return list;
    });
    /** 二级选项列表 */
    const secondList = ref([]);

    /** 一级选项是否有数据应用 */
    const hasData = ref(true);
    const selectValue = reactive({
      /** 一级选项id */
      firstId: null,
      /** 一级选项数据 */
      firstData: null,
      /** 二级选项id */
      secondId: null,
      /** 二级选项数据 */
      secondData: null
    });
    const inputText = computed(() => {
      if (!selectValue.firstData || !selectValue.secondData) return '';
      return `${selectValue.firstData.name} / ${selectValue.secondData.name}`;
    });

    watch(
      () => props.value,
      val => {
        if (val) {
          /** 根据二级选项id找到父级 */
          selectValue.secondId = val;
          hasData.value = true;
          props.list.forEach(item => {
            item.children?.forEach(child => {
              if (child.id === val) {
                selectValue.secondData = child;
                selectValue.firstData = item;
                selectValue.firstId = item.id;
                secondList.value = item.children;
              }
            });
          });
        } else {
          hasData.value = false;
          selectValue.firstId = null;
          selectValue.firstData = null;
          selectValue.secondId = null;
          selectValue.secondData = null;
        }
      },
      {
        immediate: true
      }
    );

    const showPopover = ref(false);
    function handlePopoverShowChange({ isShow }) {
      showPopover.value = isShow;
    }

    /**
     * 一级选项选中触发事件
     * @param val 选项值
     */
    function handleFirstClick(val) {
      if (val.id === selectValue.firstId) return;
      /** 切换一级选项清空二级选项数据 */
      selectValue.secondId = null;
      selectValue.secondData = null;
      selectValue.firstId = val.id;
      selectValue.firstData = val;
      hasData.value = val.children.length > 0;
      secondList.value = val.children || [];
    }
    /**
     * 二级选项选中触发事件
     * @param val 选项值
     */
    function handleSecondClick(val) {
      if (val.id === selectValue.secondId) return;
      selectValue.secondId = val.id;
      selectValue.secondData = val;
      showPopover.value = false;
      emit('change', val.id, val);
    }

    return {
      t,
      searchKey,
      hasData,
      selectValue,
      selectList,
      secondList,
      inputText,
      showPopover,
      handleFirstClick,
      handleSecondClick,
      handlePopoverShowChange
    };
  },
  render() {
    return (
      <div class='application-cascade-component'>
        <Popover
          placement='bottom-start'
          arrow={false}
          theme='light application-cascade-popover'
          trigger='click'
          is-show={this.showPopover}
          onAfterShow={val => this.handlePopoverShowChange(val)}
          onAfterHidden={val => this.handlePopoverShowChange(val)}
        >
          {{
            default: () => (
              <div class={['trigger-wrap', this.showPopover ? 'active' : '']}>
                <Input
                  modelValue={this.inputText}
                  placeholder={this.t('选择应用/服务')}
                  readonly
                >
                  {{ suffix: () => <span class='icon-monitor icon-arrow-down'></span> }}
                </Input>
              </div>
            ),
            content: () => (
              <div class='application-cascade-popover-content'>
                <div class='search-wrap'>
                  <i class='icon-monitor icon-mc-search search-icon'></i>
                  <Input
                    v-model={this.searchKey}
                    class='search-input'
                    placeholder={this.t('输入关键字')}
                  ></Input>
                </div>
                <div class='select-wrap'>
                  <div class='first panel'>
                    <div class='group-title'>{this.t('有数据应用')}</div>
                    <div class='group-wrap'>
                      {this.selectList.hasData.map(item => (
                        <div
                          class={{ 'group-item': true, active: item.id === this.selectValue.firstId }}
                          onClick={() => this.handleFirstClick(item)}
                          key={item.id}
                        >
                          <div class='left'>
                            <i class='icon-monitor icon-mc-menu-apm'></i>
                            <span class='name'>{item.name}</span>
                            <span class='desc'>{item.desc}</span>
                          </div>
                          <i class='icon-monitor icon-arrow-right'></i>
                        </div>
                      ))}
                    </div>
                    <div class='group-title'>{this.t('无数据应用')}</div>
                    {this.selectList.noData.map(item => (
                      <div
                        class={{ 'group-item': true, active: item.id === this.selectValue.firstId }}
                        onClick={() => this.handleFirstClick(item)}
                      >
                        <i class='icon-monitor icon-mc-menu-apm'></i>
                        <span class='name'>{item.name}</span>
                      </div>
                    ))}
                  </div>
                  {this.selectValue.firstId && (
                    <div class='second panel'>
                      {this.hasData ? (
                        <div class='has-data-wrap'>
                          {this.secondList.map(item => (
                            <div
                              class={{ 'group-item': true, active: item.id === this.selectValue.secondId }}
                              onClick={() => this.handleSecondClick(item)}
                            >
                              <i class='icon-monitor icon-mc-grafana-home'></i>
                              <span class='name'>{item.name}</span>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div class='no-data-wrap'>
                          <Form labelWidth={100}>
                            <Form.FormItem label={this.t('应用名')}>trace_agg_scene</Form.FormItem>
                            <Form.FormItem label={this.t('应用别名')}>应用1</Form.FormItem>
                            <Form.FormItem label={this.t('描述')}>我是描述我是描述我是描述</Form.FormItem>
                            <Form.FormItem label='Token'>
                              <span class='password'>●●●●●●●●●●</span>
                              <Button
                                text
                                theme='primary'
                              >
                                {this.t('点击查看')}
                              </Button>
                            </Form.FormItem>
                          </Form>
                          <div class='btn'>
                            <span>{this.t('Profile 接入指引')}</span>
                            <i class='icon-monitor icon-fenxiang'></i>
                          </div>
                          <div class='btn'>
                            <span>{this.t('查看应用')}</span>
                            <i class='icon-monitor icon-fenxiang'></i>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
                <div class='footer-wrap'>
                  <div class='jump-btn'>
                    <i class='icon-monitor icon-jia'></i>
                    <span class=''>{this.t('新增接入')}</span>
                  </div>
                </div>
              </div>
            )
          }}
        </Popover>
      </div>
    );
  }
});
