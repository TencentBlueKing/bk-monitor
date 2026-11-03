import {
  RadioGroup as TRadioGroup,
  Radio as TRadio,
  Checkbox as TCheckbox,
  Popup as TPopup,
  Tooltip as TTooltip,
} from 'tdesign-vue-next';
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
import { defineComponent, ref, onMounted, PropType, computed } from 'vue';

import type { FormRules } from 'tdesign-vue-next';
import useLocale from '@/shared/composables/use-locale';
import useStore from '@/shared/composables/use-store';

import AddGroup from '../collect-list/add-group';

import './collect-tool.scss';

export default defineComponent({
  name: 'CollectTool',
  props: {
    isChecked: {
      type: Boolean,
      default: true,
    },
    collapseAll: {
      type: Boolean,
      default: true,
    },
    rules: {
      type: Object as PropType<FormRules>,
      default: () => ({}),
    },
  },
  emits: ['handle'],
  setup(props, { emit, expose }) {
    const { t } = useLocale();
    const store = useStore();
    const isSceneMode = computed(() => store.getters.isSceneMode);
    const addPopoverVisible = ref(false);
    const sortPopoverVisible = ref(false);
    const active = ref('');
    /** 排序列表 */
    const groupSortList = [
      {
        name: t('按名称 {n} 排序', { n: 'A - Z' }),
        id: 'NAME_ASC',
      },
      {
        name: t('按名称 {n} 排序', { n: 'Z - A' }),
        id: 'NAME_DESC',
      },
      {
        name: t('按更新时间排序'),
        id: 'UPDATED_AT_DESC',
      },
    ];
    onMounted(() => {
      active.value = localStorage.getItem('favoriteSortType') || 'NAME_ASC';
    });
    /** 调整排序 */
    const handleSortChange = (val: string) => {
      active.value = val;
      localStorage.setItem('favoriteSortType', val);
    };
    /** 是否仅查看当前索引集 */
    const handleChangeIndex = (val: boolean) => {
      emit('handle', 'change-index', val);
    };
    /** 是否全部收起 */
    const handleCollapseAll = () => {
      emit('handle', 'collapse', !props.collapseAll);
    };
    /** 取消按钮 */
    const handleCancel = (type: 'add' | 'sort') => {
      switch (type) {
        case 'add':
          addPopoverVisible.value = false;
          break;
        case 'sort':
          sortPopoverVisible.value = false;
          break;
      }
    };
    /** 确定按钮 */
    const handleOk = (type: 'add' | 'sort') => {
      emit('handle', 'refresh');
      handleCancel(type);
    };

    const renderBtnGroup = (type: 'add' | 'sort') => (
      <div class='collect-tool-btn-box'>
        <span class='tool-btn-ok' onClick={() => handleOk(type)}>
          {t('确定')}
        </span>
        <span class='tool-btn-cancel' onClick={() => handleCancel(type)}>
          {t('取消')}
        </span>
      </div>
    );
    /** 新增分组Render */
    const renderAddGroup = () => (
      <div class='popover-add-group-box'>
        <AddGroup
          isFormType={true}
          rules={props.rules}
          onCancel={() => handleCancel('add')}
          onSubmit={() => handleOk('add')}
        />
      </div>
    );
    /** 排序Render */
    const renderSort = () => (
      <div class='collect-tool-sort-box'>
        <div class='tool-sort-title'>{t('收藏排序')}</div>
        <TRadioGroup
          class='tool-sort-item'
          value={active.value}
          onChange={(value) => {
            if (typeof value === 'string') handleSortChange(value);
          }}
        >
          {groupSortList.map((item) => (
            <TRadio class='tool-sort-radio' value={item.id}>
              {item.name}
            </TRadio>
          ))}
        </TRadioGroup>
        {renderBtnGroup('sort')}
      </div>
    );
    expose({ handleCancel });

    return () => (
      <div class='collect-tool-box'>
        <span class='tool-checkbox'>
          {!isSceneMode.value && (
            <TCheckbox checked={props.isChecked} onChange={handleChangeIndex}>
              {t('仅查看当前索引集')}
            </TCheckbox>
          )}
        </span>
        <span class='tool-icon-box'>
          {/* 新建收藏分组 */}
          <TPopup
            attach='body'
            placement='bottom-right'
            visible={addPopoverVisible.value}
            onVisibleChange={(value) => (addPopoverVisible.value = value)}
            trigger='click'
            v-slots={{ content: renderAddGroup }}
          >
            <TTooltip content={t('新建收藏分组')}>
              <i class='bklog-icon bklog-xinjianwenjianjia tool-icon' />
            </TTooltip>
          </TPopup>
          {/* 全部收起/展开 */}
          <div>
            <TTooltip content={props.collapseAll ? t('全部展开') : t('全部收起')}>
              <i
                class={`bklog-icon bklog-${props.collapseAll ? 'zhankai-2' : 'shouqi'} tool-icon`}
                onClick={handleCollapseAll}
              />
            </TTooltip>
          </div>

          {/* 调整排序 */}
          <TPopup
            attach='body'
            placement='bottom-right'
            visible={sortPopoverVisible.value}
            onVisibleChange={(value) => (sortPopoverVisible.value = value)}
            trigger='click'
            v-slots={{ content: renderSort }}
          >
            <TTooltip content={t('调整排序')}>
              <i class='bklog-icon bklog-paixu tool-icon' />
            </TTooltip>
          </TPopup>
        </span>
      </div>
    );
  },
});
