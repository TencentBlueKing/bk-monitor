/* Copyright (C) 2021 THL A29 Limited, a Tencent company, MIT License. */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import * as Vue from 'vue';
import { loadTypeScript } from './helpers/load-typescript.mjs';
function fixture(order) {
  const calls=[];
  const store={state:{globals:{fieldTypeMap:{keyword:{name:'Keyword',icon:'icon',color:'red'}}},isNotVisibleFieldsShow:false,indexItem:{sort_list:order?[['level',order]]:[]}},getters:{isUnionSearch:false,unionIndexItemList:[],visibleFields:[{field_name:'level'},{field_name:'log'}]},dispatch:(...args)=>calls.push(['dispatch',...args]),commit:(...args)=>calls.push(['commit',...args])};
  const hook=loadTypeScript(new URL('../src/features/retrieval/workbench/search-result-panel/log-result/use-render-header.ts',import.meta.url),{
    vue:Vue,'tdesign-vue-next':{Tooltip:Vue.defineComponent({setup:(_,ctx)=>()=>ctx.slots.default?.()})},
    '@/shared/utils/typed-record':{asDictionary:x=>x,includesValue:(list,value)=>list.includes(value)},
    '@/shared/composables/use-field-name':{getFieldNameByField:field=>field.field_name},
    '@/shared/composables/use-locale':{__esModule:true,default:()=>({$t:x=>x})},
    '@/app/state/domains/globals-store': {useGlobalsStore:()=>({$state:store.state.globals})},
    '@/shared/composables/use-store':{__esModule:true,default:()=>store},
    '@/features/retrieval/retrieve-helper':{__esModule:true,default:{fire:(...args)=>calls.push(['fire',...args])},RetrieveEvent:{VISIBLE_FIELD_COLUMN_LAYOUT_CHANGE:'layout'}},
  }).default();
  const node=hook.renderHead({field_name:'level',field_type:'keyword',es_doc_values:true},value=>calls.push(['sort',value]));
  return {node,calls};
}
test('native table header click preserves ascending, descending and unsorted transitions',()=>{
  for(const [active,expected]of [[null,'asc'],['asc','desc'],['desc',undefined]]){
    const {node,calls}=fixture(active);
    const arrow={classList:{contains:name=>name==='active'||name===(active==='asc'?'ascending':'descending'),remove:()=>{}}};
    node.props.onClick({target:{parentElement:{querySelectorAll:()=>active?[arrow]:[]}}});
    assert.deepEqual(calls,[['sort',expected]]);assert.equal(node.props.on,undefined);
  }
});
test('remove-field control retains propagation, persistence, state and layout events',()=>{
  const {node,calls}=fixture(null);const tooltip=node.children.at(-1);const icon=tooltip.children.default();let stopped=false;
  assert.equal(tooltip.props.content,'将字段从表格中移除');
  icon.props.onClick({stopPropagation:()=>{stopped=true;}});
  assert.equal(stopped,true);assert.equal(icon.props.on,undefined);assert.equal(icon.props.directives,undefined);
  assert.deepEqual(calls,[['dispatch','userFieldConfigChange',{displayFields:['log']}],['commit','resetVisibleFields',['log']],['commit','updateIsSetDefaultTableColumn'],['fire','layout']]);
});
