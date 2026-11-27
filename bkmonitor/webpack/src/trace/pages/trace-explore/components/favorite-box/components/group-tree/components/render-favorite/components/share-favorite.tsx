import { type PropType, computed, defineComponent, reactive, watch } from 'vue';
import { shallowRef } from 'vue';

import { Button, Checkbox, Dialog, Exception, Input, Message, Radio } from 'bkui-vue';
import { shareFavorite } from 'monitor-api/modules/model';
import { ETagsType, SPACE_TYPE_MAP } from 'monitor-common/utils/biz';
/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
import { supportsSpaceDirectoryPages } from 'monitor-common/utils/space-directory';
import { FormSpacePages } from 'monitor-common/utils/space-selection';
import { useI18n } from 'vue-i18n';

import useFavoriteType from '../../../../../hooks/use-favorite-type';
import { useAppStore } from '@store/modules/app';

import type { IFavoriteGroup } from '../../../../../types';

import './share-favorite.scss';

export const makeMap = (list: Array<number> = []): Record<number, boolean> => {
  const map = Object.create(null);
  for (const item of list) {
    map[item] = true;
  }
  return map;
};

export default defineComponent({
  props: {
    data: {
      type: Object as PropType<IFavoriteGroup['favorites'][number]>,
      required: true,
    },
    isShow: {
      type: Boolean,
    },
  },
  emits: ['close', 'success'],
  setup(props, context) {
    const store = useAppStore();
    const { t } = useI18n();
    const favoriteType = useFavoriteType();

    const spaceSearchKey = shallowRef('');
    const duplicateMode = shallowRef('skip');
    const shareBizIdList = shallowRef([]);
    const isSubmiting = shallowRef(false);

    const remote = supportsSpaceDirectoryPages();
    const pages = reactive(new FormSpacePages());
    const loadedSpaces = shallowRef<typeof store.bizList>();
    const selectingAll = shallowRef(false);
    let lastAllIds: null | number[] = null;
    let selectionRequest = 0;
    const renderBizList = computed(() => {
      const keyword = spaceSearchKey.value.trim().toLocaleLowerCase();
      return (remote ? pages.items : (loadedSpaces.value ?? store.bizList))
        .filter(
          bizItem =>
            remote ||
            bizItem.space_name.toLocaleLowerCase().includes(keyword) ||
            String(bizItem.id).includes(keyword) ||
            String(bizItem.space_id).toLocaleLowerCase().includes(keyword)
        )
        .map(bizItem => {
          const tagList = [{ id: bizItem.space_type_id, name: bizItem.type_name, type: bizItem.space_type_id }];
          if (bizItem.space_type_id === 'bkci' && bizItem.space_code) {
            tagList.push({
              id: 'bcs',
              name: t('容器项目'),
              type: 'bcs',
            });
          }
          return {
            ...bizItem,
            tagList,
          };
        });
    });

    const isBizSelectAll = computed(() => {
      if (remote && pages.hasMore) return lastAllIds === shareBizIdList.value;
      if (remote ? pages.loading : !loadedSpaces.value && window.space_list_state === 'deferred') return false;
      const selectIdMap = makeMap(shareBizIdList.value);
      return renderBizList.value.length > 0 && renderBizList.value.every(item => selectIdMap[item.id]);
    });

    watch(
      () => props.isShow,
      () => {
        selectionRequest++;
        lastAllIds = null;
        selectingAll.value = false;
        loadedSpaces.value = undefined;
        spaceSearchKey.value = '';
        if (remote) {
          if (props.isShow) void pages.search();
          else pages.reset();
        }
      },
      { immediate: true }
    );
    watch(spaceSearchKey, keyword => {
      lastAllIds = null;
      if (remote && props.isShow) void pages.search(keyword);
    });

    const handleBizAllChange = async (checked: boolean) => {
      const request = ++selectionRequest;
      if (!checked) {
        selectingAll.value = false;
        shareBizIdList.value = [];
        return;
      }
      const keyword = spaceSearchKey.value;
      selectingAll.value = true;
      try {
        if (remote) {
          const ids = await pages.allMatching();
          if (ids && request === selectionRequest && props.isShow && keyword === spaceSearchKey.value) {
            lastAllIds = ids;
            shareBizIdList.value = ids;
          }
          return;
        }
        if (window.space_list_state === 'deferred' && window.loadSpaceDirectory) {
          const spaces = await window.loadSpaceDirectory();
          if (request !== selectionRequest || !props.isShow || keyword !== spaceSearchKey.value) return;
          loadedSpaces.value = spaces;
        }
        shareBizIdList.value = renderBizList.value.map(item => item.id);
      } catch {
        if (request === selectionRequest) Message({ theme: 'error', message: t('空间目录加载失败，请刷新页面重试') });
      } finally {
        if (request === selectionRequest) selectingAll.value = false;
      }
    };

    const handleSubmitEdit = async () => {
      isSubmiting.value = true;
      try {
        await shareFavorite({
          bk_biz_id: store.bizId,
          type: favoriteType.value,
          share_bk_biz_ids: shareBizIdList.value,
          duplicate_mode: duplicateMode.value,
          name: props.data.name,
          config: props.data.config,
        });
        context.emit('close');
        Message({
          theme: 'success',
          message: t('操作成功'),
        });
      } finally {
        isSubmiting.value = false;
      }
    };

    const handleClose = () => {
      context.emit('close');
    };

    return () => (
      <Dialog
        width={480}
        class='favorite-box-share-favorite-dialog'
        v-slots={{
          footer: () => (
            <>
              <Button
                disabled={selectingAll.value}
                loading={isSubmiting.value}
                theme='primary'
                onClick={handleSubmitEdit}
              >
                {t('确定')}
              </Button>
              <Button
                style='margin-left: 8px'
                onClick={handleClose}
              >
                {t('取消')}
              </Button>
            </>
          ),
        }}
        is-show={props.isShow}
        title={t('共享')}
        onClosed={handleClose}
      >
        <div class='space-wrapper'>
          <div class='space-search'>
            <Input
              v-model={spaceSearchKey.value}
              placeholder={t('搜索 空间名')}
            />
          </div>
          <div class='space-list'>
            <div class='space-item'>
              <Checkbox
                disabled={selectingAll.value || (remote && pages.loading)}
                modelValue={isBizSelectAll.value}
                onChange={handleBizAllChange}
              >
                {t('全选')}
              </Checkbox>
            </div>
            <Checkbox.Group
              v-model={shareBizIdList.value}
              disabled={selectingAll.value}
            >
              {renderBizList.value.map(item => (
                <div
                  key={item.id}
                  class='space-item'
                >
                  <Checkbox label={item.id}>
                    {item.space_name}
                    <span
                      class='space-id'
                      v-overflow-tips
                    >
                      ({item.space_type_id === ETagsType.BKCC ? `#${item.id}` : item.space_id || item.space_code})
                    </span>
                  </Checkbox>
                  <div class='space-tag-wrapper'>
                    {item.tagList.map(tag => (
                      <div
                        key={tag.id}
                        style={{ ...SPACE_TYPE_MAP[tag.id]?.light }}
                        class='space-tag'
                      >
                        {tag.name}
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </Checkbox.Group>
            {remote && (pages.hasMore || pages.failed) && (
              <Button
                loading={pages.loading}
                text
                onClick={() => pages.retryOrNext()}
              >
                {t(pages.failed ? '重试' : '加载更多')}
              </Button>
            )}
            {spaceSearchKey.value && renderBizList.value.length < 1 && (
              <Exception
                style='margin-top: 60px'
                description={t('搜索为空')}
                scene='part'
                type='search-empty'
              />
            )}
          </div>
        </div>
        <div style='margin-top: 30px'>
          <div
            class='rename-title'
            v-bk-tooltips={t('该规则仅针对重名内容生效')}
          >
            {t('重命名规则')}
          </div>
          <div>
            <Radio.Group v-model={duplicateMode.value}>
              <Radio label='skip'>{t('不共享')}</Radio>
              <Radio label='copy'>{t('创建副本')}</Radio>
              <Radio label='overwrite'>{t('覆盖')}</Radio>
            </Radio.Group>
          </div>
        </div>
      </Dialog>
    );
  },
});
