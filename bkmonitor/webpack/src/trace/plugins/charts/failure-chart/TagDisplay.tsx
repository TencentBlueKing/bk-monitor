/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
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
import { type PropType, computed, defineComponent, onBeforeUnmount, onMounted, ref } from 'vue';

import './TagDisplay.scss';

interface ITagItem {
  display_key: string;
  display_value: string;
  key: string;
  value: string;
}

export default defineComponent({
  name: 'TagDisplay',
  props: {
    tagsList: {
      type: Array as PropType<ITagItem[]>,
      required: true,
    },
    tipsName: {
      type: String,
    },
  },
  setup(props) {
    const tags = ref<ITagItem[]>(props.tagsList);
    const isAllShown = ref(true);
    const tagContainerWidth = ref(0);

    const displayedTags = computed(() => {
      if (isAllShown.value) {
        return tags.value;
      }
      return tags.value.slice(0, visibleTagCount.value);
    });

    const showMoreIndicator = computed(() => {
      return tags.value.length > visibleTagCount.value;
    });

    const remainingCount = computed(() => {
      return tags.value.length - visibleTagCount.value;
    });

    const visibleTagCount = computed(() => {
      const containerWidth = tagContainerWidth.value || tagContainer.value?.offsetWidth || 0;
      const tagsWidths = tags.value.map(tag => {
        const tempSpan = document.createElement('span');
        tempSpan.innerText = `${tag.display_key} = ${tag.display_value}`;
        tempSpan.style.visibility = 'hidden';
        tagContainer.value?.appendChild(tempSpan);
        const width = tempSpan.offsetWidth;
        tagContainer.value?.removeChild(tempSpan);
        return width;
      });
      let count = 0;
      let sumWidth = 0;
      for (const width of tagsWidths) {
        sumWidth += width;
        if (sumWidth > containerWidth - 30) {
          break;
        }
        count++;
      }
      return count;
    });

    const tagContainer = ref(null);

    onMounted(() => {
      tagContainerWidth.value = tagContainer.value?.offsetWidth;
      window.addEventListener('resize', handleResize);
    });

    onBeforeUnmount(() => {
      window.removeEventListener('resize', handleResize);
    });

    const handleResize = () => {
      tagContainerWidth.value = tagContainer.value?.offsetWidth;
      isAllShown.value = tags.value.length <= visibleTagCount.value;
    };
    /** 渲染tag的tips */
    const renderTagToolTips = (list: ITagItem[]) => {
      return (
        <div>
          {props.tipsName}
          <br />
          {list.map(item => (
            <div style={{ marginTop: '5px' }}>
              {item.display_key} = {item.display_value}
            </div>
          ))}
        </div>
      );
    };
    return {
      tagContainer,
      remainingCount,
      displayedTags,
      visibleTagCount,
      showMoreIndicator,
      renderTagToolTips,
    };
  },
  render() {
    return (
      <div
        ref='tagContainer'
        class='display-tag-container'
      >
        {this.displayedTags.slice(0, this.visibleTagCount).map(item => (
          <span
            class='tag-item'
            v-bk-tooltips={{
              content: this.renderTagToolTips([item]),
            }}
          >
            {item.display_key} = {item.display_value}
          </span>
        ))}
        {this.showMoreIndicator && (
          <span
            class='more-indicator'
            v-bk-tooltips={{
              content: this.renderTagToolTips(this.displayedTags.slice(this.visibleTagCount)),
            }}
          >
            {this.remainingCount > 0 ? `+${this.remainingCount}` : ''}
          </span>
        )}
      </div>
    );
  },
});
