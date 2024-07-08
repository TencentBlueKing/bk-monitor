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
import { computed, defineComponent, inject, nextTick, Ref, ref } from 'vue';
import { useI18n } from 'vue-i18n';

import { Tag } from 'bkui-vue';

import { IIncident, ICurrentISnapshot } from '../types';

// import TagShow from './tag-show';
import './failure-tags.scss';

export default defineComponent({
  name: 'FailureTags',
  emits: ['collapse', 'chooseTag', 'chooseNode'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const isHover = ref<boolean>(false);
    const isShow = ref<boolean>(false);
    const failureTags = ref<HTMLDivElement>();
    const incidentDetail = inject<Ref<IIncident>>('incidentDetail');
    const playLoading = inject<Ref<boolean>>('playLoading');
    const incidentDetailData = computed(() => {
      return incidentDetail.value;
    });
    const handleCheckChange = (checked, tag) => {
      emit('chooseTag', tag, checked);
    };
    const renderList = [
      {
        label: t('影响空间'),
        renderFn: () => {
          const snapshots = incidentDetailData.value.current_snapshot?.bk_biz_ids || [];
          return snapshots.length === 0 ? (
            <span class='empty-text'>--</span>
          ) : (
            snapshots.map(item => (
              <Tag
                class='business-tag'
                checkable
                onChange={checked => handleCheckChange(checked, item)}
              >
                {`[${item.bk_biz_id}] ${item.bk_biz_name}`}
              </Tag>
            ))
          );
        },
      },
      {
        label: t('故障根因'),
        renderFn: () => {
          const snapshots: ICurrentISnapshot = incidentDetailData.value?.current_snapshot;
          const { incident_name_template } = snapshots?.content || {};
          const { elements = [], template } = incident_name_template || {};
          const replacePlaceholders = (template, replacements) => {
            const parts: Array<JSX.Element | string> = [];
            const regex = /{(.*?)}/g;
            let lastIndex = 0;
            let match;

            while ((match = regex.exec(template)) !== null) {
              const [placeholder, key] = match;
              const startIndex = match.index;

              if (lastIndex < startIndex) {
                parts.push(template.slice(lastIndex, startIndex));
              }

              parts.push(replacements[key] ?? placeholder);
              lastIndex = startIndex + placeholder.length;
            }

            if (lastIndex < template.length) {
              parts.push(template.slice(lastIndex));
            }

            return parts;
          };
          if (template && elements.length > 0) {
            // 替换内容对象
            const replacements = {
              0: (
                <label
                  onClick={() => {
                    emit('chooseNode', [elements[0][1]]);
                  }}
                >
                  (<label class='name-target'>{elements[0][1]}</label>)
                </label>
              ),
              1: elements[1],
            };
            const processedContentArray = replacePlaceholders(template, replacements);
            const tips = replacePlaceholders(template, { 0: elements[0][1], 1: elements[1] });
            return (
              <span
                class={['item-info', { over: isHover.value }]}
                title={tips.join('')}
              >
                {processedContentArray.map(part => (typeof part === 'string' ? part : <>{part}</>))}
              </span>
            );
          }
          return <span class='empty-text'>--</span>;
        },
      },
      {
        label: t('故障负责人'),
        renderFn: () => {
          const list = incidentDetailData.value?.assignees || [];
          // if (!isShow.value) {
          //   return (
          //     <TagShow
          //       styleName={'principal-tag'}
          //       data={principal}
          //     />
          //   );
          // }
          return list.length === 0 ? (
            <span class='empty-text'>--</span>
          ) : (
            list.map(item => <Tag class='principal-tag'>{item}</Tag>)
          );
        },
      },
    ];
    const expandCollapseHandle = () => {
      isShow.value = !isShow.value;
      nextTick(() => {
        emit('collapse', isShow.value, failureTags?.value?.clientHeight);
      });
    };
    return { renderList, expandCollapseHandle, isShow, failureTags, incidentDetailData, playLoading, isHover };
  },
  render() {
    return (
      <div
        ref='failureTags'
        class={['failure-tags', { 'failure-tags-full': this.isShow }]}
        onMouseenter={() => {
          this.isHover = true;
        }}
        onMouseleave={() => {
          this.isHover = false;
        }}
      >
        <div
          style={{
            height: `${this.isHover ? 60 : 40}px`,
          }}
          class='failure-tags-main'
        >
          {this.playLoading && <div class='failure-tags-loading'></div>}
          {this.renderList.map(item => (
            <div class='failure-tags-item'>
              <span class='item-label'>{item.label}：</span>
              <div class='item-main'>{item.renderFn()}</div>
            </div>
          ))}
        </div>
        {/* <i
          class={`icon-monitor icon-double-${this.isShow ? 'up' : 'down'} failure-tags-icon`}
          onClick={this.expandCollapseHandle}
        ></i> */}
      </div>
    );
  },
});
