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

import {createApp, defineComponent, h, ref} from 'vue';
import {Button} from 'tdesign-vue-next';
import '../src/platform/compat/tdesign/runtime-contract';
import i18n from '../src/platform/i18n/i18n';
import {ServicesInstance} from '../src/platform/services';
import logTooltip from '../src/shared/directives/log-tooltip';
import type {ITagItem} from '../src/features/collection/current/components/common-comp/tag-more';
import 'tdesign-vue-next/es/style/index.css';
import '../src/shared/assets/resources/vendor/bk-icon/iconfont.css';

window.$t = i18n.t;
// The legacy state constants read the application translator during import.
Object.defineProperty(window, 'mainComponent', {value: {$t: i18n.t}, configurable: true});
const [{default: TagMore}, {default: store}, {default: StopTypeDialog}, {default: AddIndexSet}, {default: EmptyStatus}, {default: EsNodesDialog}, {default: EsSlider}] = await Promise.all([
  import('../src/features/collection/current/components/common-comp/tag-more'),
  import('../src/app/state/index'),
  import('../src/features/collection/current/components/list-main/stop-type-dialog'),
  import('../src/features/collection/current/components/business-comp/step2/add-index-set'),
  import('../src/shared/ui/empty-status/index.vue'),
  import('../src/features/clusters/current/cluster-manage/es-dialog'),
  import('../src/features/clusters/current/cluster-manage/es-slider'),
]);
store.state.spaceUid = 'fixture-space';
store.commit('globals/setGlobalsData', {es_source_type:[{id:'other',name:'Other'}],storage_duration_time:[{id:7,name:'7'},{id:14,name:'14'}]});
store.state.userMeta.username = 'fixture-user';
store.state.bkBizId = 5000140;
const initialLabels: ITagItem[] = [
  {tag_id: 1, name: '已有标签'},
  {tag_id: 2, name: '可选标签'},
  {tag_id: 3, name: '内置标签', is_built_in: true},
];
type Call = {method: string; options: unknown};
const calls = ref<Call[]>([]), labels = ref<ITagItem[]>([...initialLabels]);
let createdLabel: ITagItem | undefined;
// Controlled component contract only. These methods never invoke HTTP.
Object.defineProperty(ServicesInstance, 'unionSearch', {value: {
  unionCreateLabel: async (options: {data: {name: string; space_uid: string}}) => {
    calls.value.push({method: 'create', options});
    createdLabel = {tag_id: 4, name: options.data.name};
    return {data: {tag_id: 4}};
  },
  unionAddLabel: async (options: unknown) => {calls.value.push({method: 'add', options});return {data: {}};},
  unionDeleteLabel: async (options: unknown) => {calls.value.push({method: 'delete', options});return {data: {}};},
}});
Object.defineProperty(ServicesInstance, 'collect', {value: {
  addIndexGroup: async (options: unknown) => {calls.value.push({method:'group-create',options});return {result:true};},
  updateIndexGroup: async (options: unknown) => {calls.value.push({method:'group-update',options});return {result:true};},
}});
Object.defineProperty(ServicesInstance, 'source', {value: {
  getProperty:async()=>{calls.value.push({method:'property-read',options:null});return {data:[]};},
  connectivityDetect:async(options:unknown)=>{calls.value.push({method:'connectivity-read',options});return {data:true};},
  getNodeAttrs:async(options:unknown)=>{calls.value.push({method:'node-attrs-read',options});return {data:[
    {id:'fixture-hot',name:'hot',host:'192.0.2.1',attr:'tier',value:'hot'},
    {id:'fixture-cold',name:'cold',host:'192.0.2.2',attr:'tier',value:'cold'},
    {id:'fixture-cold2',name:'cold2',host:'192.0.2.3',attr:'tier',value:'cold'},
  ]};},
}});
const Fixture = defineComponent({
  setup() {
    const clusterSliderVisible = ref(false), clusterSliderEvents = ref<string[]>([]);
    const nodesVisible = ref(false), nodesType = ref('hot'), nodeEvents = ref<boolean[]>([]);
    const openNodes = (type: string) => {nodesType.value=type;nodeEvents.value=[];nodesVisible.value=true;};
    const groupVisible = ref(false), groupIsAdd = ref(true), groupRevision = ref(0), groupEvents = ref<unknown[]>([]), groupBubbles = ref(0);
    const openGroup = (isAdd: boolean) => {groupIsAdd.value=isAdd;groupEvents.value=[];groupBubbles.value=0;groupRevision.value++;groupVisible.value=true;};
    const emptyType = ref('empty'), emptyScene = ref('part'), emptyTextVisible = ref(true), emptyCustom = ref(false), emptyOperations = ref<string[]>([]);
    const stopVisible = ref(false), stopEvents = ref<unknown[]>([]);
    const tags = ref<ITagItem[]>([initialLabels[0], initialLabels[2]]), terminated = ref(false), revision = ref(0);
    const reset = () => {
      tags.value = [initialLabels[0], initialLabels[2]];labels.value = [...initialLabels];calls.value = [];
      terminated.value = false;createdLabel = undefined;revision.value++;clusterSliderVisible.value=false;clusterSliderEvents.value=[];nodesVisible.value=false;nodeEvents.value=[];groupVisible.value=false;stopVisible.value=false;emptyType.value='empty';emptyScene.value='part';emptyTextVisible.value=true;emptyCustom.value=false;emptyOperations.value=[];
    };
    return () => h('main', {style: {width: '600px', margin: '32px auto'}}, [
      h('h2', '采集标签组件契约（隔离接口）'),
      h(Button,{onClick:()=>{clusterSliderEvents.value=[];clusterSliderVisible.value=true;}},()=> 'Open cluster create'),
      h(EsSlider,{showSlider:clusterSliderVisible.value,editClusterId:null,clusterType:'elasticsearch',onHandleCancelSlider:()=>{clusterSliderEvents.value.push('cancel');clusterSliderVisible.value=false;}}),
      h('output',{'data-testid':'cluster-slider-events'},JSON.stringify(clusterSliderEvents.value)),
      ...['hot','warm','missing'].map(type => h(Button, {onClick:()=>openNodes(type)}, ()=>`打开节点 ${type}`)),
      h(EsNodesDialog, {value:nodesVisible.value,type:nodesType.value,formData:{hot_attr_name:'tier',hot_attr_value:'hot',warm_attr_name:'tier',warm_attr_value:nodesType.value==='missing'?'missing':1},list:[
        {id:'node-hot',name:'热节点',host:'192.0.2.1',attr:'tier',value:'hot'},
        {id:'node-warm-number',name:'冷节点数字',host:'192.0.2.2',attr:'tier',value:1},
        {id:'node-warm-string',name:'冷节点字符串',host:'192.0.2.3',attr:'tier',value:'1'},
        {id:'node-other',name:'其他属性',host:'192.0.2.4',attr:'other',value:'hot'},
      ], onHandleValueChange:(value:boolean)=>{nodeEvents.value.push(value);nodesVisible.value=value;}}),
      h('output',{'data-testid':'node-events'},JSON.stringify(nodeEvents.value)),
      h('p', '仅验证真实业务组件；所有服务调用由夹具记录，不连接业务后端。'),
      h(Button, {onClick: reset}, () => '重置标签夹具'),
      h(Button, {onClick: () => {terminated.value = !terminated.value;}}, () => '切换停用状态'),
      h('div', {style: {width: '200px', marginTop: '20px'}, 'data-testid': 'label-cell'}, [h(TagMore, {
        key: revision.value, maxRows: 2, mode: 'label', tags: tags.value, selectLabelList: labels.value,
        rowData: {index_set_id: 'fixture-index', status: terminated.value ? 'terminated' : 'normal'},
        onUpdateTags: (next: ITagItem[]) => {tags.value = next;},
        onRefreshLabelList: () => {if (createdLabel) labels.value = [...labels.value, createdLabel];},
      }, {trigger: ({content, triggerRef}: {content: ReturnType<typeof h>[]; triggerRef: unknown}) => h('div', {
        ref: triggerRef, class: 'tag-more-label-select-trigger', style: {minHeight: '58px', display: 'flex', alignItems: 'center'},
      }, content)})]),
      h(Button, {onClick: () => {stopEvents.value = [];stopVisible.value = true;}}, () => '打开停用预览'),
      h(StopTypeDialog, {showDialog: stopVisible.value, onCancel: (value: boolean) => {stopEvents.value.push({event:'cancel',value});stopVisible.value = false;}, onUpdate: (value: boolean) => {stopEvents.value.push({event:'update',value});}}),
      h('pre', {'data-testid': 'stop-events'}, JSON.stringify(stopEvents.value)),
      h(Button, {onClick: () => openGroup(true)}, () => '打开索引集新增'),
      h(Button, {onClick: () => openGroup(false)}, () => '打开索引集重命名'),
      groupVisible.value ? h('div', {'data-testid':'index-group-editor', onKeydown: (event: KeyboardEvent) => {if(event.key==='Enter')groupBubbles.value++;}}, [h(AddIndexSet, {
        key: groupRevision.value, isAdd: groupIsAdd.value, isFrom: true,
        data: groupIsAdd.value ? {index_set_name:''} : {index_set_id:'fixture-group',index_set_name:'旧索引集'},
        onSubmit: (value: unknown) => {groupEvents.value.push({event:'submit',value});groupVisible.value=false;},
        onCancel: () => {groupEvents.value.push({event:'cancel'});groupVisible.value=false;},
      })]) : null,
      h('pre', {'data-testid':'group-events'}, JSON.stringify(groupEvents.value)),
      h('output', {'data-testid':'group-bubbles'}, String(groupBubbles.value)),
      h('section', {style:{marginTop:'24px'}}, [
        ...['empty','search-empty','500','403','404','building','login'].map(type => h(Button,{onClick:()=>{emptyType.value=type;emptyOperations.value=[];}},()=>`切换空态 ${type}`)),
        h(Button,{onClick:()=>{emptyScene.value=emptyScene.value==='part'?'page':'part';}},()=> '切换空态尺寸'),
        h(Button,{onClick:()=>{emptyTextVisible.value=!emptyTextVisible.value;}},()=> '切换空态标题'),
        h(Button,{onClick:()=>{emptyCustom.value=!emptyCustom.value;}},()=> '切换空态插槽'),
        h('div',{'data-testid':'empty-component'},[h(EmptyStatus,{emptyType:emptyType.value,scene:emptyScene.value,showText:emptyTextVisible.value,showOperation:false,onOperation:(operation:string)=>{emptyOperations.value.push(operation);}},emptyCustom.value?{default:()=>h('span','自定义空态说明')}:undefined)]),
        h('output',{'data-testid':'empty-operations'},JSON.stringify(emptyOperations.value)),
        h('output',{'data-testid':'empty-custom-state'},String(emptyCustom.value)),
      ]),
      h('output', {'data-testid': 'label-names'}, tags.value.map(item => item.name).join(',')),
      h('pre', {'data-testid': 'label-calls'}, JSON.stringify(calls.value)),
    ]);
  },
});
const app = createApp(Fixture);app.use(i18n);app.directive('log-tooltip', logTooltip);app.mount('#collection-label-contract');
