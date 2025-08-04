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
import { defineComponent, nextTick, onBeforeUnmount, ref, shallowRef, watch } from 'vue';

import { addListener, removeListener } from '@blueking/fork-resize-detector';
import { Exception, Popover } from 'bkui-vue';
import dayjs from 'dayjs';
// import mermaid from '../../../../mermaid/packages/mermaid/dist/mermaid.core.mjs';
import mermaid from 'fork-mermaid';
import { traceDiagram } from 'monitor-api/modules/apm_trace.js';
import { random } from 'monitor-common/utils/utils';
import { debounce } from 'throttle-debounce';
import { useI18n } from 'vue-i18n';

import GraphTools from '../flame-graph/graph-tools/graph-tools';
import ViewLegend from '../view-legend/view-legend';
import { defaultConfig } from './mermaid';

// import mermaid  from './dist/mermaid.core.mjs';
import './sequence-graph.scss';

const boxStartId = 'box_';
const MaxNoteTextLength = 88;
const MaxImgWidth = 240;
const MaxImgHeight = 240;
mermaid.initialize(defaultConfig);
export default defineComponent({
  name: 'SequenceGraph',
  props: {
    traceId: {
      type: String,
      required: true,
    },
    appName: {
      type: String,
      required: true,
    },
    filters: {
      type: Array,
      required: false,
    },
  },
  emits: ['update:loading', 'spanListChange', 'showSpanDetail'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const mermaidRef = ref<HTMLElement>();
    const thumbnailRef = ref<HTMLCanvasElement>();
    const sequenceGraphRef = ref<HTMLElement>();
    const sequenceGraphWrapRef = ref<HTMLElement>();
    const sequenceThumbnailRef = ref<HTMLElement>();
    const graphDefinition = ref(''); // mermaid图表定义
    const graphId = `mermaid-${random(10)}`; // mermaid图表id
    const showException = ref(false); // 是否展示异常
    const connectionList = shallowRef([]); // 连接线列表
    const participantList = shallowRef([]); // 参与者列表
    const showThumbnail = ref(false); // 是否展示缩略图
    const showLegend = ref(false); // 是否展示图例
    const svgString = ref('');
    // const hasDraw = false;
    const thumbnailRect = ref({ width: 0, height: 0 });
    const thumbnailSvgRect = ref({ width: 0, height: 0 });
    const thumbnailViewRect = ref({
      width: 0,
      height: 0,
      left: 0,
      top: 0,
    });
    const graphScale = ref(100); // 缩放比例
    const rawSvgRect = ref({ width: 0, height: 0 }); // 原始svg尺寸
    function addId(data: Record<string, any>[]) {
      // 为数据添加id
      return data?.map(item => ({ ...item, id: random(10) })) || [];
    }
    function splitStr(str: string) {
      if (str.length <= MaxNoteTextLength) return str;
      let tagStr = '';
      let i = 0;
      while (i < str.length) {
        tagStr += `${i !== 0 ? '<br/>' : ''}${str.slice(i, i + MaxNoteTextLength)}`;
        i += MaxNoteTextLength;
      }
      return tagStr.replace(/\n/gim, '<br/>');
    }
    function transformData(data: any) {
      // 转换数据
      let { connections, participants } = data;
      let participantsStr = '';
      let connectionsStr = '';
      const boxParticipants = {};
      const globalParticipants = {};
      const boxParticipantsMap = {};
      connections = addId(connections);
      participants = addId(participants);
      connectionList.value = connections;
      participantList.value = participants;
      participants.forEach((item: any) => {
        if (!item.span_id) {
          if (!globalParticipants[item.name]) {
            participantsStr += `participant ${item.name} as ${item.name} is ${item.id}\n`;
            globalParticipants[item.name] = true;
          }
        } else {
          if (!boxParticipantsMap[item.name]) {
            boxParticipantsMap[item.name] = {
              [item.component_name]: true,
            };
            boxParticipants[item.component_name] = [
              ...(boxParticipants[item.component_name] || []),
              `participant ${item.name} as ${item.display_name} is ${item.id}\n`,
            ];
          } else {
            if (!boxParticipantsMap[item.name][item.component_name]) {
              boxParticipantsMap[item.name] = {
                ...boxParticipantsMap[item.name],
                [item.component_name]: `${item.name} as ${item.display_name} is ${item.id}`,
              };
              boxParticipants[item.component_name] = [
                ...(boxParticipants[item.component_name] || []),
                `participant ${boxParticipantsMap[item.name][item.component_name]}\n`,
              ];
            }
          }
        }
      });
      const parallelStart = 'par\n';
      const parallelEnd = 'end\n';
      const parallelAnd = 'and\n';
      const paralletStak = [];
      const collapseMap = new Map();
      const noteMap = new Map();
      connections.forEach((item: any, index: number) => {
        const isDottedLine = item.hyphen === '-->>-';
        const collapseKey =
          !item.parallel_id && !item.parallel_path?.length && item.group_info?.id
            ? `${item.group_info.id}_${item.hyphen}`
            : '';
        // 处理并发
        if (item.parallel_id) {
          // 处理回归多少个并发结束
          const diffIndex = paralletStak.findIndex((stack, i) => stack !== item.parallel_path[i]);
          if (diffIndex >= 0) {
            // 有不相同并行
            const stackLen = paralletStak.length - diffIndex;
            connectionsStr += Array(stackLen).fill(parallelEnd).join('');
            paralletStak.splice(diffIndex);
            paralletStak.push(...item.parallel_path.slice(diffIndex));
            connectionsStr += Array(item.parallel_path.length - diffIndex)
              .fill(parallelStart)
              .join('');
          } else {
            // 全部相同
            if (item.parallel_id === paralletStak[paralletStak.length - 1] && !isDottedLine) {
              connectionsStr += parallelAnd;
            } else if (!paralletStak.includes(item.parallel_id)) {
              connectionsStr += parallelStart;
              paralletStak.push(item.parallel_id);
            }
          }
        } else if (paralletStak.length && !item.parallel_path.length) {
          connectionsStr += Array(paralletStak.length).fill(parallelEnd).join('');
          paralletStak.splice(0);
        }
        // 折叠合并结束
        if (!collapseKey || collapseMap.get(collapseKey) !== true) {
          // 标记已折叠
          collapseKey && collapseMap.set(collapseKey, true);
          let collapseCountMsg = '';
          if (collapseKey && !isDottedLine) {
            const collapseCount = item.group_info.members.filter(spanId =>
              connections.some(
                connection =>
                  connection.original.span_id === spanId && !connection.parallel_id && !connection.parallel_path?.length
              )
            ).length;
            collapseCountMsg = collapseCount > 1 ? ` x${collapseCount} ` : '';
          }
          connectionsStr += `${item.from} ${item.hyphen} ${item.to}${
            item.message?.trim().length ? `: ${item.message}` : ':'
          }${collapseCountMsg} is ${item.id}\n`;
          // 判断错误的span 添加 notes
          if (item.original.status?.code === 2 && !noteMap.has(item.original.span_id)) {
            noteMap.set(item.original.span_id, true);
            const tags = Object.keys(item.original.attributes || {}).reduce((pre, cur) => {
              const tag = item.original.attributes[cur].toString().replace(/[,;:]/gim, '');
              pre += `<br/>${cur}: ${splitStr(tag)}`;
              return pre;
            }, '');
            connectionsStr += `Note right of ${item.to}: ${`Errors: ${
              tags || splitStr(item.original.status.message)
            }`}\n`;
          }
          if (index === connections.length - 1 && paralletStak.length) {
            connectionsStr += Array(paralletStak.length).fill(parallelEnd).join('');
            paralletStak.splice(0);
          }
        }
      });
      // 处理 box
      Object.keys(boxParticipants).forEach((key: string) => {
        if (boxParticipants[key].length > 0) {
          participantsStr += `box ${key} is ${boxStartId}${key}\n`;
          boxParticipants[key].forEach((item: string, index: number) => {
            participantsStr += item;
            if (index === boxParticipants[key].length - 1) {
              participantsStr += 'end \n';
            }
          });
        }
      });
      return `sequenceDiagram
${participantsStr}
${connectionsStr.replace(/^par\nend\n^/gm, '')}
`;
    }
    function setSvgScaleSize() {
      const svgDom = mermaidRef.value?.querySelector('svg');
      if (svgDom) {
        svgDom.style.width = `${rawSvgRect.value.width * (graphScale.value / 100)}px`;
        svgDom.style.height = `${rawSvgRect.value.height * (graphScale.value / 100)}px`;
      }
    }
    watch(
      [() => props.traceId, () => props.appName, () => props.filters],
      debounce(16, async () => {
        emit('update:loading', true);
        showException.value = false;
        resetThumbnailRect();
        // hasDraw = false;
        showThumbnail.value = false;
        showLegend.value = false;
        try {
          const data = await traceDiagram(
            {
              app_name: props.appName,
              trace_id: props.traceId,
              diagram_type: 'sequence',
              with_original: true,
              show_attrs: 0,
              displays: props.filters,
            },
            {
              needCancel: true,
            }
          ).catch(() => false);
          if (!data.diagram_data) {
            showException.value = true;
            emit('update:loading', false);
            return;
          }
          showException.value = false;
          await nextTick();
          const rest = transformData(data.diagram_data);
          graphDefinition.value = rest || '';
          const { svg } = await mermaid.render(graphId, graphDefinition.value);
          svgString.value = svg;
          mermaidRef.value!.innerHTML = svg.replace(/max-width/gim, 'width');
          setTimeout(() => {
            drawThumbnail();
            addListener(sequenceGraphWrapRef.value!, handleResize);
            sequenceGraphRef.value.addEventListener('scroll', handleSequenceGraphScroll);
            // setTimeout(() => handleShowThumbnail(), 500);
            const svgDom = mermaidRef.value!.querySelector('svg');
            if (svgDom) {
              const { width, height } = svgDom.getBoundingClientRect();
              svgDom.style.width = `${width * (graphScale.value / 100)}px`;
              svgDom.style.height = `${height * (graphScale.value / 100)}px`;
              rawSvgRect.value = {
                width,
                height,
              };
            }
            emit('update:loading', false);
          }, 16);
        } catch (e) {
          console.error(e);
          showException.value = true;
        } finally {
          emit('update:loading', false);
        }
      }),
      { immediate: true }
    );
    /**
     *
     * @param dataId data-id
     */
    const toggleDataIdActive = (dataId: string | undefined) => {
      sequenceGraphRef.value.querySelectorAll('.is-active')?.forEach(item => {
        item.classList.remove('is-active');
      });
      dataId &&
        sequenceGraphRef.value.querySelectorAll(`[data-id="${dataId}"]`)?.forEach(item => {
          item.classList.toggle('is-active');
        });
    };
    /**
     * @param e mouse event
     * @returns spanIdList
     */
    const handleClickSvg = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      const dataId = target.dataset.id;
      let serviceName = '';
      let spanIdList = [];
      toggleDataIdActive(dataId);
      if (dataId) {
        // click service box
        if (dataId.startsWith(boxStartId)) {
          const componentName = dataId.replace(new RegExp(`^${boxStartId}`), '');
          const item = participantList.value.find(item => item.component_name === componentName && item.span_id);
          if (item) {
            serviceName = componentName;
            spanIdList = participantList.value
              .filter(item => item.span_id && item.component_name === componentName)
              .map(item => item.span_id);
          }
        } else {
          // time span
          if (target.classList.length && target.classList.value.includes('activation')) {
            const connection = connectionList.value.find(item => item.id === dataId);
            if (connection.group_info?.id) {
              spanIdList = connection.group_info.members;
              serviceName = `${connection.original.span_name} x${spanIdList.length}`;
            } else {
              spanIdList = [connection.original.span_id];
              serviceName = connection.original.span_name;
            }
          } else if (participantList.value.some(item => item.id === dataId)) {
            // service or actor
            const participant = participantList.value.find(item => item.id === dataId);
            serviceName = participant.display_name || participant.component_name || '';
            if (serviceName === 'Start' && participantList.value[0].component_name === serviceName) {
              return;
            }
            const excludeList = participantList.value
              .filter(
                item =>
                  item.span_id &&
                  participant.component_name === item.component_name &&
                  (!participant.span_id || participant.display_name === item.display_name)
              )
              .map(item => item.span_id);
            spanIdList = excludeList;
            if (!participant.span_id) {
              const allList = connectionList.value
                .filter(item => item.to === participant.component_name)
                .map(item => item.original.span_id);
              spanIdList = allList.filter(id => !excludeList.includes(id));
            }
          } else if (connectionList.value.some(item => item.id === dataId)) {
            // line
            const connection = connectionList.value.find(item => item.id === dataId);
            if (connection.parent_merged) {
              spanIdList = [connection.original.span_id, connection.original.parent_span_id];
              serviceName = connection.original.span_name;
            } else if (connection.group_info?.id) {
              spanIdList = connection.group_info.members;
              serviceName = `${connection.original.span_name} x${spanIdList.length}`;
            } else {
              spanIdList = [connection.original.span_id];
              serviceName = connection.original.span_name;
            }
            // const index = connectionList.value.findIndex(item => item.id === dataId);
            // spanIdList.push(connectionList.value[index].original.span_id);
            // let i = index;
            // while (i >= 0 && i < connectionList.value.length) {
            //   const item = connectionList.value[i];
            //   const pre = connectionList.value[i - 1];
            //   if (isCollapseItem(item, pre)) {
            //     spanIdList.push(pre.original.span_id);
            //     i -= 1;
            //   } else {
            //     i = -1;
            //   }
            // }
          }
        }
        // console.info(target.classList.value, dataId, Array.from(new Set(spanIdList)), '==============');
      }
      spanIdList = Array.from(new Set(spanIdList));
      if (spanIdList.length === 1) {
        emit('showSpanDetail', spanIdList[0]);
      }
      emit('spanListChange', spanIdList, serviceName, toggleDataIdActive);
    };

    /**
     * @param svgString svg string
     * @param canvas
     */
    function convertSvgToCanvas(svgString: string, canvas: HTMLCanvasElement) {
      const ctx = canvas.getContext('2d');
      const dpr = window.devicePixelRatio;
      // 创建一个新的 Image 元素
      const img = new Image(thumbnailSvgRect.value.width * dpr, thumbnailSvgRect.value.height * dpr);
      // 当 Image 元素加载完成时执行回调函数
      img.onload = function () {
        // 清空画布并设置画布尺寸
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        // 将 SVG 渲染到 Canvas
        ctx.drawImage(img, 0, 0, thumbnailSvgRect.value.width * dpr, thumbnailSvgRect.value.height * dpr);
      };
      // 设置 Image 的源为 SVG 字符串
      img.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svgString)}`;
    }

    /**
     * @description: show thumbnail
     */
    function handleShowThumbnail() {
      // if (!hasDraw) {
      //   convertSvgToCanvas(svgString.value, thumbnailRef.value);
      //   hasDraw = true;
      // }
      showThumbnail.value = !showThumbnail.value;
      if (showThumbnail.value) {
        showLegend.value = false;
        setTimeout(() => {
          drawThumbnail();
        }, 100);
      }
    }
    /**
     * @param e 事件
     * @description: thumbnail view mouse down
     */
    function handleThumbnailViewMouseDown(event: MouseEvent) {
      sequenceGraphRef.value.removeEventListener('scroll', handleSequenceGraphScroll);
      const { clientX, clientY } = event;
      const mainDom = sequenceGraphRef.value;
      const { top, left } = thumbnailViewRect.value;
      const { width: thumbnailWidth, height: thumbnailHeight } = thumbnailRect.value;
      const { width: thumbnailViewWidth, height: thumbnailViewHeight } = thumbnailViewRect.value;

      const xMultiple = mainDom.scrollWidth / thumbnailWidth;
      const yMultiple = mainDom.scrollHeight / thumbnailHeight;

      function handleMouseMove(e: MouseEvent) {
        const diffY = clientY - e.clientY;
        const diffX = clientX - e.clientX;
        const boundTop = Math.min(Math.max(top - diffY, 0), thumbnailHeight - thumbnailViewHeight);
        const boundLeft = Math.min(Math.max(left - diffX, 0), thumbnailWidth - thumbnailViewWidth);

        thumbnailViewRect.value.top = boundTop;
        thumbnailViewRect.value.left = boundLeft;
        mainDom.scrollTo({
          top: Math.floor(boundTop * yMultiple),
          left: Math.floor(boundLeft * xMultiple),
          behavior: 'auto',
        });
      }
      function handleMouseUp() {
        document.removeEventListener('mousemove', handleMouseMove);
        document.removeEventListener('mouseup', handleMouseUp);
        sequenceGraphRef.value.addEventListener('scroll', handleSequenceGraphScroll);
      }
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
    }
    /**
     * @description: reset thumbnail rect
     */
    function resetThumbnailRect() {
      showThumbnail.value = false;
      thumbnailSvgRect.value = {
        width: 0,
        height: 0,
      };
      thumbnailRect.value = {
        width: 0,
        height: 0,
      };
      thumbnailViewRect.value = {
        width: 0,
        height: 0,
        top: 0,
        left: 0,
      };
    }
    /**
     * @description: draw thumbnail
     */
    function drawThumbnail() {
      const svg = mermaidRef.value.querySelector('svg');
      const svgRect = svg?.getBoundingClientRect();
      if (!svgRect?.width) {
        resetThumbnailRect();
        return;
      }
      const mainDom = sequenceGraphRef.value;
      const { width: mainWidth, height: mainHeight } = mainDom.getBoundingClientRect();
      const xMultiple = mainDom.scrollWidth / mainWidth;
      const yMultiple = mainDom.scrollHeight / mainHeight;
      const useWidthScale = xMultiple > 1 || yMultiple > 1 ? xMultiple > yMultiple : mainWidth > mainHeight;
      let thumbnailWidth = useWidthScale ? MaxImgWidth : mainDom.scrollWidth / (mainDom.scrollHeight / MaxImgHeight);

      let thumbnailHeight = useWidthScale ? mainDom.scrollHeight / (mainDom.scrollWidth / MaxImgWidth) : MaxImgHeight;
      if (thumbnailWidth > MaxImgWidth) {
        thumbnailWidth = MaxImgWidth;
        thumbnailHeight = mainDom.scrollHeight / (mainDom.scrollWidth / MaxImgWidth);
      }
      const thumbnailViewWidth = thumbnailWidth * (mainWidth / mainDom.scrollWidth);
      const thumbnailViewHeight = thumbnailHeight * (mainHeight / mainDom.scrollHeight);
      const thumbnailSvgWidth = thumbnailWidth * (svgRect.width / mainDom.scrollWidth);
      const thumbnailSvgHeight = thumbnailHeight * (svgRect.height / mainDom.scrollHeight);
      thumbnailSvgRect.value = {
        width: +thumbnailSvgWidth,
        height: +thumbnailSvgHeight,
      };
      thumbnailRect.value = {
        width: +thumbnailWidth,
        height: +thumbnailHeight,
      };
      thumbnailViewRect.value = {
        left: thumbnailViewRect.value.left,
        top: thumbnailViewRect.value.top,
        width: +thumbnailViewWidth,
        height: +thumbnailViewHeight,
      };
      if (showThumbnail.value) {
        // hasDraw = false;
        convertSvgToCanvas(svgString.value, thumbnailRef.value);
        // hasDraw = true;
      }
    }
    const handleResize = debounce(100, () => {
      if (showThumbnail.value) drawThumbnail();
    });
    function handleSequenceGraphScroll() {
      if (!thumbnailRect.value.width) return;
      const { scrollTop, scrollLeft, scrollWidth, scrollHeight } = sequenceGraphRef.value;
      const xMultiple = scrollWidth / thumbnailRect.value.width;
      const yMultiple = scrollHeight / thumbnailRect.value.height;
      thumbnailViewRect.value.top = scrollTop / yMultiple;
      thumbnailViewRect.value.left = scrollLeft / xMultiple;
    }
    function handleScaleChange(v: number) {
      graphScale.value = v;
      setSvgScaleSize();
      drawThumbnail();
    }
    function downloadSvgAsImage() {
      const svg = mermaidRef.value.querySelector('svg');
      if (!svg) return;
      const { id } = svg;
      const canvas = document.createElement('canvas');
      const svgSize = svg.getBoundingClientRect();
      canvas.width = svgSize.width;
      canvas.height = svgSize.height;
      const image = new Image();
      const str = svgString.value.replace('<style>', `<style>#${id}{background-color: #fff;}`);
      image.src = `data:image/svg+xml;base64,${btoa(unescape(encodeURIComponent(str)))}`;
      image.onload = () => {
        canvas.getContext('2d')?.drawImage(image, 0, 0);
        const a = document.createElement('a');
        a.download = `${props.traceId}_${dayjs.tz().format('YYYY-MM-DD HH:mm:ss')}`;
        a.href = canvas.toDataURL('image/png');
        a.click();
      };
    }
    function handleShowLegend() {
      showLegend.value = !showLegend.value;
      if (showLegend.value) {
        showThumbnail.value = false;
        thumbnailRect.value = {
          width: 120,
          height: 300,
        };
      }
    }
    onBeforeUnmount(() => {
      sequenceGraphWrapRef.value && removeListener(sequenceGraphWrapRef.value, handleResize);
      toggleDataIdActive(undefined);
      emit('update:loading', false);
    });
    return {
      graphDefinition,
      svgString,
      graphScale,
      mermaidRef,
      thumbnailRef,
      sequenceThumbnailRef,
      sequenceGraphRef,
      sequenceGraphWrapRef,
      thumbnailViewRect,
      thumbnailRect,
      thumbnailSvgRect,
      graphId,
      showThumbnail,
      showLegend,
      showException,
      toggleDataIdActive,
      handleClickSvg,
      handleShowThumbnail,
      downloadSvgAsImage,
      handleScaleChange,
      handleThumbnailViewMouseDown,
      handleShowLegend,
      t,
    };
  },
  render() {
    if (this.showException)
      return (
        <Exception
          description={this.t('暂无数据')}
          type='empty'
        />
      );
    return (
      <div
        ref='sequenceGraphWrapRef'
        class='sequence-graph-wrapper'
      >
        <div
          ref='sequenceGraphRef'
          class='sequence-graph'
        >
          <div id={this.graphId} />
          <div
            ref='mermaidRef'
            class='sequence-graph-ref'
            onClick={this.handleClickSvg}
          />
        </div>
        <div class='sequence-tools'>
          {
            <Popover
              width={this.thumbnailRect.width}
              height={this.thumbnailRect.height}
              extCls='sequence-thumbnail-popover'
              allowHtml={false}
              arrow={false}
              boundary={'parent'}
              content={this.sequenceThumbnailRef}
              isShow={this.showThumbnail || this.showLegend}
              placement='top-start'
              renderType='auto'
              theme='light'
              trigger='manual'
              zIndex={300001}
            >
              {{
                default: () => (
                  <GraphTools
                    class='sequence-graph-tools'
                    legendActive={this.showLegend}
                    minScale={10}
                    scaleStep={10}
                    scaleValue={this.graphScale}
                    thumbnailActive={this.showThumbnail}
                    onScaleChange={this.handleScaleChange}
                    onShowLegend={this.handleShowLegend}
                    onShowThumbnail={this.handleShowThumbnail}
                    onStoreImg={this.downloadSvgAsImage}
                  />
                ),
                content: () => [
                  this.showLegend ? (
                    <ViewLegend key={0} />
                  ) : (
                    <div
                      id='sequence-thumbnail'
                      key={1}
                      ref='sequenceThumbnailRef'
                      class='sequence-thumbnail'
                    >
                      <div
                        style={{
                          left: `${this.thumbnailViewRect.left}px`,
                          top: `${this.thumbnailViewRect.top}px`,
                          width: `${this.thumbnailViewRect.width}px`,
                          height: `${this.thumbnailViewRect.height}px`,
                        }}
                        class='sequence-thumbnail-view'
                        onMousedown={this.handleThumbnailViewMouseDown}
                      />
                      <canvas
                        id='thumbnail-canvas'
                        ref='thumbnailRef'
                        style={{
                          transform: `scale(${1 / window.devicePixelRatio})`,
                        }}
                        width={this.thumbnailRect.width * window.devicePixelRatio}
                        height={this.thumbnailRect.height * window.devicePixelRatio}
                        class='sequence-thumbnail-canvas'
                      />
                    </div>
                  ),
                ],
              }}
            </Popover>
          }
        </div>
      </div>
    );
  },
});
