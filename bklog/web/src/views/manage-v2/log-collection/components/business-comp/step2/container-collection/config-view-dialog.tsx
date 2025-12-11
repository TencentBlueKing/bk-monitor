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

import { defineComponent, ref, watch, type PropType } from 'vue';

import EmptyStatus from '@/components/empty-status/index.vue';
import useLocale from '@/hooks/use-locale';

import $http from '@/api';

import './config-view-dialog.scss';

type IViewItem = {
  group: string;
  total: number;
  items: string[];
  isShowTarget: boolean;
};

/**
 * ConfigViewDialog 组件
 * 用于显示配置视图对话框，展示命中的视图内容
 */
export default defineComponent({
  name: 'ConfigViewDialog',
  props: {
    /**
     * 控制对话框是否显示
     */
    isShowDialog: {
      type: Boolean,
      default: false,
    },
    /**
     * 视图查询参数
     */
    viewQueryParams: {
      type: Object as PropType<IViewItem>,
      required: true,
    },
  },
  emits: ['cancel'],
  setup(props, { emit }) {
    const { t } = useLocale();
    /**
     * 视图列表数据
     */
    const viewList = ref<IViewItem[]>([]);
    /**
     * 加载状态
     */
    const loading = ref(false);

    watch(
      () => props.isShowDialog,
      (val: boolean) => {
        if (val) {
          /**
           * 对话框显示时，获取视图数据
           */
          loading.value = true;
          $http
            .request('container/getLabelHitView', {
              data: props.viewQueryParams,
            })
            .then(res => {
              /**
               * 处理返回的数据，添加 isShowTarget 属性
               */
              viewList.value = res.data.map(item => ({
                ...item,
                isShowTarget: true,
              }));
            })
            .finally(() => {
              loading.value = false;
            });
        } else {
          /**
           * 对话框隐藏时，延迟清空视图列表
           */
          setTimeout(() => {
            viewList.value = [];
          }, 1000);
        }
      },
    );

    /**
     * 取消对话框处理函数
     */
    const handelCancelDialog = () => {
      emit('cancel', false);
    };

    /**
     * 点击标题处理函数，切换内容显示/隐藏
     * @param index
     * @param showValue
     */
    const handleClickTitle = (index: number, showValue: boolean) => {
      viewList.value[index].isShowTarget = !showValue;
    };

    return () => (
      <bk-dialog
        width='600'
        auto-close={false}
        header-position='left'
        mask-close={false}
        show-footer={false}
        theme='primary'
        title={t('预览')}
        value={props.isShowDialog}
        onCancel={handelCancelDialog}
      >
        {/* 主内容区域，带加载状态 */}
        <div
          class='config-view-dialog-main'
          v-bkloading={{ isLoading: loading.value }}
        >
          {/* 有视图数据时渲染视图列表 */}
          {viewList.value.length > 0 ? (
            viewList.value.map((item, index) => (
              <div
                key={index}
                class='view-container'
              >
                <div
                  class={['view-title', item.isShowTarget ? '' : 'hidden-bottom'].join(' ')}
                  on-Click={() => handleClickTitle(index, item.isShowTarget)}
                >
                  <div
                    class='match title-overflow'
                    v-bk-overflow-tips
                  >
                    <span>{item.group}</span>
                  </div>
                  <i18n path={t('已命中 {0} 个内容')}>
                    <span class='number'>{item.total}</span>
                  </i18n>
                </div>
                {item.isShowTarget && (
                  <div class='view-target'>
                    {item.items.map((ele, ind) => (
                      <div
                        key={ind}
                        class='title-overflow'
                        v-bk-overflow-tips
                      >
                        <span>{ele}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))
          ) : (
            <EmptyStatus
              empty-type='empty'
              show-text={false}
            >
              <p>{t('暂无命中内容')}</p>
            </EmptyStatus>
          )}
        </div>
      </bk-dialog>
    );
  },
});
