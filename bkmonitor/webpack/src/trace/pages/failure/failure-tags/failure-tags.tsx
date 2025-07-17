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
import { type Ref, computed, defineComponent, inject, onBeforeUnmount, onMounted, onUnmounted, watch } from 'vue';
import { shallowRef } from 'vue';
import { useI18n } from 'vue-i18n';

import { Tag } from 'bkui-vue';
import { debounce } from 'lodash';

import UserDisplayNameTags from '../../../components/collapse-tags/user-display-name-tags';
import { useTagsOverflow } from './tags-utils';

import type { ICurrentISnapshot, IIncident } from '../types';

import './failure-tags.scss';

export default defineComponent({
  name: 'FailureTags',
  emits: ['chooseTag', 'chooseNode', 'toSpan'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const styleOptions = {
      '--icon-size': '16px',
      '--icon-padding-top': '11px',
      '--icon-padding-right': '14px',
      '--animation-timeline': 0.5,
      '--animation-delay': 0.2,
    };
    const isHover = shallowRef<boolean>(false);
    const isShow = shallowRef<boolean>(false);
    const selectCollapseTagsStatus = shallowRef<boolean>(!isHover.value);
    let selectDelayTimer: any = null;
    const failureTags = shallowRef<HTMLDivElement>();
    const tagsRefs = shallowRef([]);
    const collapseTagRef = shallowRef();
    const itemMainRefs = shallowRef([]);
    const incidentDetail = inject<Ref<IIncident>>('incidentDetail');
    const playLoading = inject<Ref<boolean>>('playLoading');
    const incidentResults = inject<Ref<object>>('incidentResults');
    const incidentDetailData = computed(() => incidentDetail.value);
    const failureTagsShowStates = computed(() => (isHover.value ? 'failure-tags-show-all' : 'failure-tags-show-omit'));
    const failureTagsPostionsStates = computed(() =>
      isShow.value ? 'failure-tags-positons-relative' : 'failure-tags-positions-absolute'
    );

    const { canShowIndex, calcOverflow } = useTagsOverflow({
      targetRef: tagsRefs,
      collapseTagRef: collapseTagRef,
      isOverflow: selectCollapseTagsStatus,
    });

    const handleCheckChange = (checked, tag) => {
      emit('chooseTag', tag, checked);
    };
    // 点击跳转到span
    const handleToSpan = () => {
      emit('toSpan');
    };

    const renderList = [
      {
        label: t('影响空间'),
        renderFn: () => {
          const snapshots = incidentDetailData.value.current_snapshot?.bk_biz_ids || [];
          return snapshots.length === 0 ? (
            <span class='empty-text'>--</span>
          ) : (
            [
              ...snapshots.map((item, index) => (
                <Tag
                  key={`${item.bk_biz_id}-${index}`}
                  ref={el => (tagsRefs.value[index] = el)}
                  style={{
                    display:
                      selectCollapseTagsStatus.value && canShowIndex.value && index >= canShowIndex.value ? 'none' : '',
                  }}
                  class='business-tag'
                  checkable
                  onChange={checked => handleCheckChange(checked, item)}
                >
                  {`${item.bk_biz_name} (#${item.bk_biz_id})`}
                </Tag>
              )),
              <Tag
                key='businessTag'
                ref='collapseTagRef'
                style={{
                  display: !!canShowIndex.value && selectCollapseTagsStatus.value ? '' : 'none',
                }}
                class='business-tag business-tag-collapse'
              >
                +{tagsRefs.value?.length - canShowIndex.value}
              </Tag>,
            ]
          );
        },
      },
      {
        label: t('故障根因'),
        class: 'failure-root-tag',
        tag: true,
        renderFn: () => {
          // 判断是否有topo，没有topo的情况下显示incident_reason
          if (!incidentResults.value.incident_topology?.enabled) {
            const { incident_reason } = incidentDetailData.value;
            return <span class={['item-info']}>{incident_reason || '--'}</span>;
          }

          const snapshots: ICurrentISnapshot = incidentDetailData.value?.current_snapshot;
          const { incident_name_template, incident_propagation_graph } = snapshots?.content || {};
          const { elements = [], template } = incident_name_template || {};
          const { entities } = incident_propagation_graph || {};

          const replacePlaceholders = (template, replacements) => {
            const parts: Array<JSX.Element | string> = [];
            const regex = /{(.*?)}/g;
            let lastIndex = 0;
            let match: any;

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
                <span
                  v-bk-tooltips={{ content: t('点击可在拓扑图中高亮该节点') }}
                  onClick={() => {
                    const node = entities.filter(item => item.is_root) || [];
                    node.length > 0 && emit('chooseNode', [node[0].entity_id]);
                  }}
                >
                  (<span class='name-target'>{elements[0][1]}</span>)
                </span>
              ),
              1: elements[1],
            };
            const processedContentArray = replacePlaceholders(template, replacements);
            // const tips = replacePlaceholders(template, { 0: elements[0][1], 1: elements[1] });
            return (
              <span
                class={['item-info']}
                // title={tips.join('')}
              >
                {/* biome-ignore lint/correctness/useJsxKeyInIterable: <explanation> */}
                {processedContentArray.map(part => (typeof part === 'string' ? part : <>{part}</>))}
                {incidentDetailData.value.incident_root?.rca_trace_info?.abnormal_traces_query && (
                  <span
                    class='link-span'
                    onClick={handleToSpan}
                  >
                    <i class='icon-monitor icon-fenxiang' />
                    {t('查看 Span')}
                  </span>
                )}
              </span>
            );
          }
          return <span class='empty-text'>--</span>;
        },
      },
      {
        label: t('故障负责人'),
        renderFn: () => {
          return (
            <UserDisplayNameTags
              class='principal-tag'
              data={incidentDetailData.value?.assignees}
              enableEllipsis={selectCollapseTagsStatus.value}
            />
          );
        },
      },
    ];
    const expandCollapseHandle = () => {
      if (isShow.value) {
        isHover.value = !isShow.value;
        setTimeout(
          () => {
            isShow.value = !isShow.value;
          },
          (styleOptions['--animation-timeline'] - styleOptions['--animation-delay']) * 1000
        );
      } else {
        isShow.value = !isShow.value;
        isHover.value = isShow.value;
      }
    };
    const expandCollapseHandleDebounced = debounce(expandCollapseHandle, 300);
    const expandIsHoverHandle = (v: boolean) => {
      if (isShow.value) return;
      isHover.value = v;
    };

    // 由于使用了组件库中的下拉框，在进行动画效果无法使用css处理保证同步，
    // 所以使用js 定时器来控制
    watch(isHover, val => {
      clearTimeout(selectDelayTimer);
      if (!val) {
        selectDelayTimer = setTimeout(
          () => {
            selectCollapseTagsStatus.value = !val;
          },
          (styleOptions['--animation-timeline'] - styleOptions['--animation-delay']) * 1000
        );
      } else {
        selectCollapseTagsStatus.value = !val;
      }
    });

    const debounceCalcOverflow = debounce(calcOverflow, 150);
    const resizeObserver = new ResizeObserver(() => {
      debounceCalcOverflow();
    });
    onMounted(() => {
      itemMainRefs.value?.[0] && resizeObserver.observe(itemMainRefs.value?.[0]);
    });

    onBeforeUnmount(() => {
      itemMainRefs.value?.[0] && resizeObserver.unobserve(itemMainRefs.value?.[0]);
    });
    onUnmounted(() => {
      clearTimeout(selectDelayTimer);
      selectDelayTimer = null;
    });
    return {
      itemMainRefs,
      styleOptions,
      renderList,
      expandCollapseHandleDebounced,
      expandIsHoverHandle,
      isShow,
      failureTags,
      incidentDetailData,
      playLoading,
      isHover,
      failureTagsShowStates,
      failureTagsPostionsStates,
    };
  },
  render() {
    return (
      <div
        ref='failureTags'
        style={{ ...this.styleOptions }}
        class={['failure-tags', [this.failureTagsShowStates, this.failureTagsPostionsStates]]}
      >
        <div class='failure-tags-container'>
          <div
            class='failure-tags-main'
            onMouseenter={() => this.expandIsHoverHandle(true)}
            onMouseleave={() => this.expandIsHoverHandle(false)}
          >
            {this.playLoading && <div class='failure-tags-loading' />}
            {this.renderList.map((item, index) => (
              <div
                key={`${item.label}-${index}`}
                class='failure-tags-item'
              >
                <span class='item-label'>{item.tag ? <Tag class={item.class}>{item.label}</Tag> : item.label}：</span>
                <div
                  ref={el => (this.itemMainRefs[index] = el)}
                  class='item-main'
                >
                  {item.renderFn()}
                </div>
              </div>
            ))}
          </div>
          <div class={`failure-tags-icon ${this.isShow ? 'failure-tags-icon-collapse' : ''} `}>
            <i
              class='icon-monitor icon-double-down'
              onClick={this.expandCollapseHandleDebounced}
            />
          </div>
        </div>
      </div>
    );
  },
});
