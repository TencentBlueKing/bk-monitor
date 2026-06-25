/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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
import { type PropType, defineComponent, shallowRef } from 'vue';

import { Button, Exception, Message } from 'bkui-vue';
import { createListConfig } from 'monitor-api/modules/incident';
import { useI18n } from 'vue-i18n';

import EmptyDataImg from '../../static/img/empty-data.png';
import NoDataImg from '../../static/img/no-data.svg';

import type { SpaceInfo } from '../data-access';

import './index.scss';

/** 格式化空间名展示文本 */
const formatSpaceName = (space?: SpaceInfo) => (space ? `${space.space_name} (#${space.space_id})` : '');

export default defineComponent({
  name: 'DataAccessEmpty',
  props: {
    /** 空间列表 */
    spaceList: {
      type: Array as PropType<SpaceInfo[]>,
      default: () => [],
    },
    /** 是否暗色背景 */
    isDarkTheme: {
      type: Boolean,
      default: false,
    },
    /** 展示模式：empty-空状态（默认），guide-接入指引 */
    mode: {
      type: String as PropType<'empty' | 'guide'>,
      default: 'empty',
    },
    /** 所选空间总数（guide 模式下用于展示 count） */
    totalCount: {
      type: Number,
      default: 0,
    },
    /** 是否展示"一键开启"按钮 */
    showEnableButton: {
      type: Boolean,
      default: false,
    },
    /** 微信客服链接 */
    wxCsLink: {
      type: String,
      default: '',
    },
    /** 当前选中的空间 ID（用于"一键开启"按钮调用接口） */
    selectedSpaceId: {
      type: Number,
      default: 0,
    },
  },
  emits: ['enabled'],
  setup(props, { emit }) {
    const { t } = useI18n();

    const isBtnLoading = shallowRef(false);

    const handleConfirm = async () => {
      const bkBizId = props.selectedSpaceId || props.spaceList[0]?.space_id;
      if (!bkBizId) return;
      isBtnLoading.value = true;
      try {
        const res = await createListConfig({
          bk_biz_id: bkBizId,
          config_type: 'general_config',
          content_list: [],
          bk_biz_id_config: {
            scope_id_list_open: [bkBizId],
          },
        });
        if (!res.errors.length) {
          emit('enabled');
        }
      } catch (e: any) {
        Message({ theme: 'error', message: e?.message || t('操作失败') });
      } finally {
        isBtnLoading.value = false;
      }
    };

    return () => (
      <div class={['data-access-empty-container', { 'data-access-empty-dark': props.isDarkTheme }]}>
        <Exception
          v-slots={{
            type: () => (
              <img
                class='empty-img'
                alt=''
                src={props.isDarkTheme ? NoDataImg : EmptyDataImg}
              />
            ),
          }}
          scene='part'
          type='empty'
        >
          <div class='empty-content'>
            {props.isDarkTheme ? (
              <div class='empty-title'>{t('当前业务暂无 图谱RCA 分析结果')}</div>
            ) : props.mode === 'guide' ? (
              <div class='empty-title'>
                <i18n-t
                  keypath='以下是所选 {count} 个空间的接入情况'
                  tag='span'
                >
                  {{ count: () => <span class='space-count'>{props.totalCount}</span> }}
                </i18n-t>
              </div>
            ) : props.spaceList.length === 1 ? (
              <div class='empty-tag-title'>
                <span class='space-tag'>{formatSpaceName(props.spaceList[0])}</span>
                <span class='empty-title'>{t('空间未开启故障分析功能')}</span>
              </div>
            ) : (
              <div class='empty-title'>
                <i18n-t
                  keypath='当前所选 {count} 个空间未开启故障分析功能'
                  tag='span'
                >
                  {{ count: () => <span class='space-count error'>{props.spaceList.length}</span> }}
                </i18n-t>
              </div>
            )}
            <div class='empty-desc'>
              <i18n-t
                keypath={
                  props.isDarkTheme
                    ? '参考下表接入数据，如有疑问请联系 {link}'
                    : '请参考下表接入数据，如有疑问请联系 {link}'
                }
                tag='span'
              >
                {{
                  link: () => (
                    <span
                      class='bk-assistant-link'
                      onClick={() => (props.wxCsLink ? window.open(props.wxCsLink, '__blank') : undefined)}
                    >
                      {t('BK 助手')}
                    </span>
                  ),
                }}
              </i18n-t>
            </div>
            {props.showEnableButton && (
              <Button
                class='empty-btn'
                v-bk-tooltips={{
                  content: `(${formatSpaceName(
                    props.selectedSpaceId
                      ? props.spaceList.find(s => s.bk_biz_id === props.selectedSpaceId)
                      : props.spaceList[0]
                  )}) ${t('打开故障功能')}`,
                }}
                loading={isBtnLoading.value}
                theme='primary'
                onClick={() => handleConfirm()}
              >
                {t('一键开启')}
              </Button>
            )}
          </div>
        </Exception>
      </div>
    );
  },
});
