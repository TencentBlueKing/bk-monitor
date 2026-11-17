/* Copyright (C) 2021 THL A29 Limited, a Tencent company, MIT License. */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import * as Vue from 'vue';
import ts from 'typescript';
import { loadTypeScript } from './helpers/load-typescript.mjs';
const settle = async () => { for (let i=0;i<16;i++) await Promise.resolve(); await Vue.nextTick(); };
const common = {
  vue: { ...Vue, onMounted() {}, onUnmounted() {}, onBeforeUnmount() {} },
  '@/app/state/domains/application-store': { useApplicationStore: () => ({ bkBizId: 'synthetic-space', spaceUid: 'synthetic-space' }) },
  '@/shared/composables/use-locale': { t: value => value },
  '@/shared/ui/time-range/utils': { handleTransformToTimestamp: range => range },
};
const options = { jsx: ts.JsxEmit.ReactJSX, jsxImportSource: 'vue' };
function find(node, type) {
  if (!node || typeof node !== "object") return;
  if (node?.type === type) return node;
  for (const child of [node?.children].flat(Infinity)) { const result = find(child, type); if (result) return result; }
}
test('selected file URL restores selection without filtering; explicit and legacy searches retain conditions and timezone', async () => {
  const previous=globalThis.window; globalThis.window={timezone:'UTC'};
  try {
    const component=loadTypeScript(new URL('../src/features/client-logs/search/search-bar/index.tsx',import.meta.url), {
      ...common,'tdesign-vue-next':{Button:'button'},axios:{},'@/platform/services':{ServicesInstance:{}},
      '@/shared/ui/time-range/time-range':{__esModule:true,default:'time'},
    },options).default;
    for (const [state, expected] of [
      [{fileName:'synthetic-selected.zip'},[]],
      [{file_name:'synthetic-filter.zip'},[{key:'file_name',value:'synthetic-filter.zip'}]],
      [{keyword:'synthetic-keyword.zip'},[{key:'file_name',value:'synthetic-keyword.zip'}]],
    ]) {
      const events=[];let exposed;
      const render=component.setup({initialUrlState:state,loading:false},{emit:(...args)=>events.push(args),expose:value=>exposed=value});
      await exposed.reSearch(false);await settle();
      assert.deepEqual(events.at(-1)[1].conditions,expected);
      assert.deepEqual(events.at(-1)[1].timeRange,['now-6h','now']);
      find(render(),'time').props.onTimezoneChange('Asia/Shanghai');await settle();
      assert.equal(events.at(-1)[1].timezone,'Asia/Shanghai');
      assert.deepEqual(events.at(-1)[1].conditions,expected);
    }
  } finally { globalThis.window=previous; }
});
test('task restoration, paging retry, batch download and source changes keep correct requests and ignore stale responses',async()=>{
  const previous=globalThis.window;globalThis.window={timezone:'UTC',setTimeout:()=>1,clearTimeout(){}};
  const pending=[],downloads=[],collections=[];
  const childIds=['./search-bar/index','./user-info-card/index','./task-list-panel/index','./task-list-panel/batch-download-dialog','./log-detail-panel/index'];
  const component=loadTypeScript(new URL('../src/features/client-logs/search/index.tsx',import.meta.url),{
    ...common,...Object.fromEntries(childIds.map(id=>[id,{__esModule:true,default:id}])),
    './types':{MAX_BATCH_DOWNLOAD_TASKS:20},
    './loading-skeleton':{__esModule:true,default:'client-loading'},
    'vue-router':{useRoute:()=>({query:{}}),useRouter:()=>({replace(){}})},
    './use-url-sync':{__esModule:true,default:()=>({getUrlState:()=>({fileName:'synthetic-b.zip'}),syncUrlParams(){},clearUrlParams(){}})},
    '@/platform/services':{ServicesInstance:{clientLog:{getTaskList:args=>new Promise((resolve,reject)=>pending.push({args,resolve,reject})),getClientInfo:async()=>({data:{}})},collect:{syncUserReport:async args=>collections.push(args)}}},
    '@/shared/lib/authority-map':{},'@/shared/composables/use-feature-toggle':{},'@/app/router/helper':{},
    '../management/hooks/use-download-file':{useDownloadFile:()=>({downloadFiles:(...args)=>downloads.push(args)})},
  },options).default;
  const scope=Vue.effectScope();
  try {
    const render=scope.run(()=>component.setup());const child=id=>find(render(),id)?.props;
    const panel=()=>child('./task-list-panel/index');
    const tasks=()=>['a','b'].map((id,i)=>({id:i,file_name:`synthetic-${id}.zip`,source:'report',process_status:'success',openid:''}));
    assert.ok(find(render(),'client-loading'));
    assert.equal(child('./task-list-panel/index'),undefined);
    assert.equal(find(render(),'bk-exception'),undefined);
    child('./search-bar/index').onSearch({conditions:[],timeRange:['start','end'],timezone:'UTC'});
    assert.ok(find(render(),'client-loading'));
    assert.equal(child('./task-list-panel/index'),undefined);
    pending[0].resolve({data:{list:tasks(),total:4}});await settle();
    assert.ok(find(render(),'client-loading').props.leaving, 'data renders during the skeleton fade');
    assert.equal(panel().selectedLogItem.file_name,'synthetic-b.zip');assert.equal(panel().taskList.length,2);
    assert.equal(pending[0].args.query.file_name,undefined);
    panel().onLoadMore();assert.equal(pending[1].args.query.page,2);
    pending[1].reject(new Error('synthetic failure'));await settle();
    panel().onLoadMore();assert.equal(pending[2].args.query.page,2);
    pending[2].resolve({data:{list:[],total:2}});await settle();
    panel().onSelectionChange(panel().taskList[0],true);panel().onSelectAllCollected();panel().onDownloadSelected();
    const dialog=child('./task-list-panel/batch-download-dialog');assert.equal(dialog.visible,true);assert.equal(dialog.selectedItems.length,2);
    dialog.onConfirm();assert.deepEqual(downloads[0][0],['synthetic-a.zip','synthetic-b.zip']);assert.equal(panel().selectedItems.length,0);
    const item=panel().taskList[0];
    await child('./log-detail-panel/index').onCollect(item);
    assert.equal(item.process_status,'running');
    assert.deepEqual(collections[0].data.file_name_list,['synthetic-a.zip']);
    panel().onSourceChange('task');assert.equal(pending[3].args.query.source,'task');assert.equal(pending[3].args.query.page,1);
    child('./search-bar/index').onSearch({conditions:[],timeRange:['start','end'],timezone:'UTC'});
    pending[4].resolve({data:{list:[],total:0}});await settle();assert.equal(panel().selectedLogItem,null);
    pending[3].resolve({data:{list:tasks(),total:2}});await settle();assert.equal(panel().taskList.length,0);
    panel().onSourceChange('');
    assert.equal(find(render(),'bk-exception'),undefined, 'empty result must not render during a request');
    pending[5].resolve({data:{list:[],total:0}});await settle();
    assert.ok(find(render(),'bk-exception'), 'empty result renders only after the response');
  }finally{scope.stop();globalThis.window=previous;}
});

test('collected logs use the native file tree and preserve URL file selection, expansion and filtering', async () => {
  const previous=globalThis.window;globalThis.window={timezone:'UTC'};
  const calls=[],events=[],treeComponent={name:'NativeFileTree'},detailSkeleton={name:'DetailSkeleton'},logViewer={name:'LogViewer'};
  const scope=Vue.effectScope();
  try {
    const component=loadTypeScript(new URL('../src/features/client-logs/search/log-detail-panel/index.tsx',import.meta.url),{
      ...common,
      'tdesign-vue-next':{Tree:treeComponent,Button:{name:'Button'},MessagePlugin(){}},
      '@/shared/ui/loading/native':{Loading:{name:'Loading'}},
      '@/shared/ui/empty-status/index.vue':{__esModule:true,default:{name:'Empty'}},
      '../../management/hooks/use-download-file':{useDownloadFile:()=>({downloadFile(){}})},
      '../loading-skeleton':{ClientLogDetailSkeleton:detailSkeleton},
      './log-viewer/index':{__esModule:true,default:logViewer},
      './toolbar/index':{__esModule:true,default:'toolbar'},
      '@/platform/services':{ServicesInstance:{retrieve:{
        getAggsTerms:async args=>{calls.push(['files',args]);return{data:{aggs_items:{file:['synthetic/a.log','synthetic/b.log']}}};},
        getLogTableList:async args=>{calls.push(['logs',args]);return{data:{list:[{message:'Synthetic log entry'}]}};},
      }}},
    },options).default;
    const props=Vue.reactive({selectedLogItem:{file_name:'synthetic-archive.zip',process_status:'success'},indexSetId:'synthetic-index',initialUrlState:{fileId:'synthetic/b.log'},timezone:'UTC',searchTimeRange:['start','end']});
    const render=scope.run(()=>component.setup(props,{emit:(...args)=>events.push(args)}));
    assert.ok(find(render(),detailSkeleton).props.files, 'file loading stays inside the navigator');
    assert.ok(find(render(),'toolbar'), 'loading must not replace the toolbar');
    await settle();
    assert.ok(find(render(),logViewer), 'log data renders while skeletons fade');
    let tree=find(render(),treeComponent);assert.ok(tree,'a registered native component must own the scoped slot');
    assert.equal(tree.props.keys.value,'id');
    assert.equal(calls.find(([name])=>name==='logs')[1].data.addition.find(item=>item.field==='file').value[0],'synthetic/b.log');
    const folder=tree.props.data[0].children[0],leaf=folder.children[0];
    assert.doesNotThrow(()=>tree.props['v-slots'].label({node:{data:leaf}}));
    tree.props.onExpand(['root']);tree=find(render(),treeComponent);assert.deepEqual(tree.props.expanded,['root']);
    tree.props.onClick({node:{data:folder}});await settle();assert.equal(calls.filter(([name])=>name==='logs').length,1);
    tree.props.onClick({node:{data:leaf}});await settle();
    assert.equal(events.find(([name,value])=>name==='url-sync'&&value.fileId===leaf.id)[1].fileId,'synthetic/a.log');
    assert.equal(calls.at(-1)[1].data.addition.find(item=>item.field==='file').value[0],'synthetic/a.log');
    find(render(),'toolbar').props.onHandleFilter('filterKey',['synthetic needle']);await settle();
    assert.ok(calls.at(-1)[1].data.addition.some(item=>item.field==='message'));
  }finally{scope.stop();globalThis.window=previous;}
});
