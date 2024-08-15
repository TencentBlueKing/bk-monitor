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

import { Component, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

const { $i18n } = window.mainComponent;
import './index.scss';

interface IProps {
  showType: string;
  lightList: Array<[]>;
}

@Component
export default class LogViewControl extends tsc<IProps> {
  @Prop({ default: 'log', type: String }) showType: string;
  @Prop({ default: () => [], type: Array }) lightList: Array<[]>;

  currentViewIndex = 1;
  catchViewIndex = 1;
  highlightHtmlList: Element[] | NodeListOf<Element> = [];
  lightSize = 0;
  colorList = [
    {
      color: [
        {
          dark: '#324260',
          light: '#E1ECFF',
        },
      ],
      name: $i18n.t('默认定位'),
    },
    {
      color: [
        {
          dark: '#553C1B',
          light: '#FFE8C3',
        },
      ],
      name: $i18n.t('上下文命中'),
    },
    {
      color: [
        {
          dark: '#294832',
          light: '#2DCB56',
        },
      ],
      name: $i18n.t('新增'),
    },
    {
      color: [],
      name: $i18n.t('高亮'),
    },
  ];

  get currentShowType() {
    return this.showType === 'log' ? 'light' : 'dark';
  }

  @Watch('lightList', { deep: true })
  watchLightList(v) {
    !!v.length ? this.initLightItemList() : this.clearLightCatch();
  }
  @Watch('showType')
  watchShowType() {
    if (this.lightSize) {
      this.highlightHtmlList[this.currentViewIndex - 1].style.opacity = 1;
    }
  }

  initLightItemList(lightList = this.lightList) {
    this.highlightHtmlList = document.querySelectorAll('[data-index="light"]');
    this.lightSize = this.highlightHtmlList.length;
    if (this.lightSize) {
      const markDom = document.querySelector('.dialog-log-markdown');
      const markTop = markDom.getBoundingClientRect().top;
      let isFindShow = false;
      for (let index = 0; index < this.highlightHtmlList.length; index++) {
        const iItemTop = this.highlightHtmlList[index].getBoundingClientRect().top;
        if (iItemTop > markTop) {
          this.currentViewIndex = Number(index) + 1;
          this.highlightHtmlList[index].style.opacity = 1;
          isFindShow = true;
          break;
        }
      }
      if (!isFindShow) {
        this.currentViewIndex = this.highlightHtmlList.length;
        this.handelChangeLight(this.highlightHtmlList.length);
      }
      this.colorList[3].color = (lightList as any).map(item => item.color);
    }
  }

  handelChangeLight(page: number) {
    const viewIndex = page - 1;
    this.catchViewIndex = this.currentViewIndex;
    const catchIndex = this.catchViewIndex - 1;
    this.highlightHtmlList[viewIndex].scrollIntoView({
      behavior: 'instant',
      block: 'center',
      inline: 'center',
    });
    this.highlightHtmlList[catchIndex].style.opacity = 0.5;
    this.highlightHtmlList[viewIndex].style.opacity = 1;
    this.currentViewIndex = page;
  }

  clearLightCatch() {
    this.lightSize = 0;
    this.currentViewIndex = 1;
    this.catchViewIndex = 1;
    this.highlightHtmlList = [];
  }

  render() {
    return (
      <div class={['markdown-control', `control-${this.currentShowType}`]}>
        <div class='left'>
          {this.colorList.map((item, index) => {
            if (!item.color.length) return undefined;
            return (
              <div class='color-item'>
                {item.color.map(cItem => (
                  <div
                    style={{ backgroundColor: index === 3 ? cItem.dark : cItem[this.currentShowType] }}
                    class='color-block'
                  ></div>
                ))}
                <span>{item.name}</span>
              </div>
            );
          })}
        </div>
        <div class='right'>
          {!!this.lightSize && (
            <div>
              <bk-pagination
                count={this.lightSize}
                current={this.currentViewIndex}
                limit={1}
                limit-list={[1]}
                small
                onChange={this.handelChangeLight}
              />
              <div
                class='jump-btn'
                onClick={() => {
                  if (this.currentViewIndex === 1) return;
                  this.handelChangeLight(this.currentViewIndex - 1);
                }}
              >
                <i class='bk-icon icon-angle-up'></i>
              </div>
              <div
                class='jump-btn next'
                onClick={() => {
                  if (this.currentViewIndex === this.lightSize) return;
                  this.handelChangeLight(this.currentViewIndex + 1);
                }}
              >
                <i class='bk-icon icon-angle-up'></i>
              </div>
            </div>
          )}
        </div>
      </div>
    );
  }
}
