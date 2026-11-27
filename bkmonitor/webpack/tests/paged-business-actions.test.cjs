const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');

const dir = path.resolve(__dirname, '../src');
const row = id => ({ id, bk_biz_id: id, space_id: String(id), space_type_id: 'bkcc', space_name: String(id), text: String(id) });
const tick = () => new Promise(resolve => setImmediate(resolve));
function load(file, window, deps = {}) {
  const code = ts.transpileModule(fs.readFileSync(path.join(dir, file), 'utf8'), {
    fileName: file, compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS,
      jsx: ts.JsxEmit.React, jsxFactory: 'h', jsxFragmentFactory: 'fragment', experimentalDecorators: true },
  }).outputText;
  const exports = {};
  const h = (type, props, ...children) => ({ type, props: props || {}, children: children.flat(Infinity) });
  new Function('require', 'exports', 'window', 'h', 'fragment', code)(id => deps[id] || {}, exports, window, h, 'fragment');
  return exports;
}
function setup(rows, server) {
  const calls = [], posted = [];
  const window = { space_list: [row(2)], space_list_page_supported: true, i18n: {t: x => x, tc: x => x} };
  let failCursor;
  const listSpaces = async params => {
    calls.push(params);
    if (params.cursor != null && params.cursor === failCursor) throw new Error('directory unavailable');
    if (server) return server(params);
    let items = rows;
    if (params.bk_biz_ids) items = items.filter(item => params.bk_biz_ids.split(',').map(Number).includes(item.bk_biz_id));
    if (params.query) items = items.filter(item => item.text.includes(params.query));
    const start = Number(params.cursor || 0);
    const end = start + params.page_size;
    return { items: items.slice(start, end), next_cursor: end < items.length ? String(end) : null };
  };
  const directory = load('monitor-common/utils/space-directory.ts', window, { 'monitor-api/modules/commons': { listSpaces } });
  const selection = load('monitor-common/utils/space-selection.ts', window, { './space-directory': directory });
  const noop = () => () => {};
  const deps = {
    'monitor-common/utils/space-directory': directory, 'monitor-common/utils/space-selection': selection,
    'monitor-common/utils/utils': { Debounce: noop }, 'monitor-api/modules/model': { shareFavorite: async data => posted.push(data) },
    'vue-tsx-support': { Component: class {} },
    'vue-property-decorator': { Component: x => x, Emit: noop, Watch: noop, Prop: noop, Ref: noop, Model: noop },
  };
  return { window, calls, posted, selection, directory, deps, fail: value => { failCursor = value; } };
}
test('saved IDs query batches of 100, drain sparse pages, preserve order, skip known IDs and names outside scope', async () => {
  const rows = Array.from({length: 205}, (_, i) => row(i + 2));
  const h = setup(rows, ({bk_biz_ids, cursor}) => {
    const ids = bk_biz_ids.split(',').map(Number);
    return cursor ? {items: ids.filter(id => id !== 88).map(row), next_cursor: null} : { items: [], next_cursor: 'remaining' };
  });
  const selected = [...rows.map(r => r.id), 2];
  const mapped = await h.selection.resolveSelectedSpaces(selected, [rows[0]]);
  assert.deepEqual(mapped.map(s => s.id), selected.slice(0,-1).filter(id => id !== 88));
  assert.deepEqual(h.calls.map(c => c.bk_biz_ids.split(',').length), [100,100,100,100,4,4]);
  assert.ok(h.calls.every(c => !c.bk_biz_ids.split(',').includes('2')));
});
test('PC favorite shares up to 500 matching IDs, paginates only on request and rejects incomplete results', async () => {
  const h = setup(Array.from({length: 707}, (_, i) => row(i+1)));
  const Dialog = load('monitor-pc/pages/data-retrieval/favorite-container/component/shared-dialog.tsx', h.window, h.deps).default;
  const vm = Object.assign(new Dialog(), {$t: x => x, $tc: x => x, $bkMessage() {}, $store: {getters:{bizId:2}},
    value: true, favoriteConfig: {}, listRef:{selectList:['*']}, handleShowChange() {}});
  vm.handleDirectoryOpen(false);
  assert.equal(h.calls.length, 0);
  vm.handleDirectoryOpen(true); await tick();
  assert.equal(h.calls.length, 1); assert.equal(vm.pages.items.length, 100);
  h.fail('200'); await vm.handleSubmitFormData();
  assert.equal(h.posted.length, 0);
  h.fail(undefined); await vm.handleSubmitFormData();
  assert.deepEqual(h.posted[0].share_bk_biz_ids, Array.from({length:500}, (_,i) => i+1));
  assert.equal(vm.pages.items.length, 100);
  vm.handleBizSearch('707'); await tick(); await vm.handleSubmitFormData();
  assert.deepEqual(h.posted[1].share_bk_biz_ids, [707]);
});
test('Trace select-all covers every matching space without rendering the entire directory', async () => {
  const h = setup(Array.from({length: 707}, (_, i) => row(i+1)));
  const pages = new h.selection.FormSpacePages();
  await pages.search();
  const ids = await pages.allMatching();
  assert.equal(ids.length,707); assert.equal(ids.at(-1),707);
  assert.equal(pages.items.length,100);
  await pages.fetchPage(); assert.equal(pages.items.length,200);
});
test('new search and closing the form discard late pages and in-flight all-selection', async () => {
  let resolveNext;
  const h = setup([], ({query, cursor}) => {
    if (cursor) return new Promise(done => {resolveNext=done;});
    return {items:[row(query === 'new' ? 9 : 2)],next_cursor:'next'};
  });
  const pages = new h.selection.FormSpacePages(500);
  await pages.search('old');
  const old = pages.allMatching(); await tick();
  await pages.search('new'); resolveNext({items:[row(88)],next_cursor:null});
  assert.equal(await old, undefined); assert.deepEqual(pages.items.map(r=>r.id),[9]);
  const more = pages.fetchPage(); await tick(); pages.reset(); resolveNext({items:[row(88)],next_cursor:null});
  assert.equal(await more,false); assert.deepEqual(pages.items,[]);
});
test('APM relation opens on demand, resolves saved values and preserves clear and disabled scalar contracts', async () => {
  const h = setup([row(2), row(7), row(-8)]);
  const Form = load('monitor-pc/components/form-space-select.tsx', h.window, h.deps).default;
  const changes = [];
  const vm = Object.assign(new Form(), {value:-8, disabled:true, extraOptions:[], showIdentifier:true,
    $store:{getters:{bizList:[row(2)]}}, $emit:(event,value)=>changes.push([event,value]), $t:x=>x});
  await vm.resolveValue();
  assert.deepEqual(h.calls.map(q=>q.bk_biz_ids),['-8']);
  assert.equal(vm.render().props.disabled,true);
  vm.render().props.onToggle(true); await tick();
  assert.equal(h.calls.length,2);
  vm.render().props.onChange('');
  assert.deepEqual(changes.slice(-2),[['input',''],['change','']]);
  await vm.render().props['remote-method']('7');
  assert.deepEqual(vm.pages.items.map(r=>r.id),[7]);
});
test('demo guide queries only its visible demo and retains route state when entered via space UID', async () => {
  const h = setup([], () => ({items:[{...row(17), is_demo:true}], next_cursor:null}));
  assert.equal(await h.selection.guideDemoSpace([{name: 'other'}]), undefined);
  assert.equal(h.calls.length, 0);
  assert.equal((await h.selection.guideDemoSpace([{name: 'DEMO'}])).bk_biz_id, 17);
  assert.equal(h.calls[0].include_demo, 1);
  assert.equal(h.calls[0].page_size, 1);
  const target = new URL(h.selection.demoSpaceUrl('https://example.test/path?space_uid=project__test&lang=zh#/apm', 17));
  assert.equal(target.searchParams.has('space_uid'), false);
  assert.equal(target.searchParams.get('lang'), 'zh');
  assert.equal(target.searchParams.get('bizId'), '17');
  assert.equal(target.hash, '#/apm');
});
test('permission tips use the complete point lookup, ignore stale or failed checks and only apply for absent IDs', async () => {
  let fail = false, finish;
  const h = setup([], async ({bk_biz_ids}) => {
    if (fail) throw new Error('offline');
    if (bk_biz_ids === '99') return new Promise(done => {finish=done;});
    return {items: [row(7)], next_cursor:null};
  });
  const requested = [];
  const alarm = {bizIds:[2,7]}, app={bizList:[row(2)]};
  const ui = load('trace/pages/alarm-center/composables/use-legacy-event-center-compat.ts', h.window, {
    ...h.deps, vue:{computed:fn=>({get value(){return fn();}}),shallowRef:value=>({value}),watch(){}},
    'monitor-common/utils':{docCookies:{getItem(){}},random:()=>''},'vue-router':{useRoute:()=>({})},
    '../typings/constants':{MY_AUTH_BIZ_ID:0,MY_ALARM_BIZ_ID:-1,AlertAllActionEnum:{}},
    '@/store/modules/alarm-center':{useAlarmCenterStore:()=>alarm},'@/store/modules/app':{useAppStore:()=>app},
    '@/store/modules/authority':{useAuthorityStore:()=>({getIntanceAuthDetail(){}})},
    'monitor-api/modules/iam':{checkAllowed:async data=>{requested.push(data);return {};}},
  }).useLegacyEventCenterCompat();
  await ui.computeShowPermissionTips(); assert.equal(ui.showPermissionTips.value,false);
  alarm.bizIds=[99]; const late=ui.computeShowPermissionTips(); await tick();
  alarm.bizIds=[0,-1,7,8]; fail=true; await ui.computeShowPermissionTips(); assert.equal(ui.showPermissionTips.value,false);
  fail=false; await ui.computeShowPermissionTips(); assert.equal(ui.showPermissionTips.value,true);
  finish({items:[row(99)],next_cursor:null}); await late; assert.equal(ui.showPermissionTips.value,true);
  await ui.handleApplyPermission();
  assert.deepEqual(requested.map(v=>v.resources), [[{id:8,type:'space'}]]);
  assert.equal(requested[0].bk_biz_id,2);
});

test('partial results retain confirmed names, prevent false denial and stop select-all until retry', async () => {
  let partial = true;
  const h = setup([], () => ({items:[row(7)], next_cursor:null, partial}));
  assert.deepEqual((await h.selection.resolveSelectedSpaces([7,8])).map(row => row.id),[7]);
  await assert.rejects(h.selection.resolveSelectedSpaces([7,8],[],true));
  assert.equal((await h.selection.resolveSelectedSpaces([7],[],true))[0].id,7);
  const pages = new h.selection.FormSpacePages(500);
  await pages.search();
  assert.equal(pages.items[0].id,7);
  assert.equal(await pages.allMatching(), undefined);
  assert.equal(pages.failed, true);
  partial = false;
  await pages.retryOrNext();
  assert.deepEqual(await pages.allMatching(),[7]);
});

function incidentVue() {
  const vue = require('../src/trace/node_modules/vue');
  const scope = vue.effectScope();
  let mount, dispose;
  return {
    vue: {...vue, onMounted: fn => { mount = fn; }, onBeforeUnmount: fn => { dispose = fn; }},
    run: fn => scope.run(fn), mount: () => mount(), close: () => { dispose?.(); scope.stop(); },
  };
}
test('incident tab counts both virtual scopes with zero directory calls; concrete and legacy scopes retain exact authorized names', async t => {
  const target = {...row(-12),space_type_id:'bkci',space_id:'project',space_uid:'bkci__project'};
  let partial = false;
  const h = setup([], () => ({items:partial ? [] : [target], next_cursor:null, partial}));
  const v = incidentVue(); t.after(v.close);
  const alarm = v.vue.reactive({alarmType:'incident',bizIds:[-1]});
  const app = v.vue.reactive({bizList:[row(2)],noAuthBizIds:[]});
  const total = v.vue.ref(132338), enabled = v.vue.ref([2,2]);
  const make = load('trace/pages/alarm-center/composables/use-incident-guide-scope.ts', h.window, {
    ...h.deps, vue:v.vue, '../typings/constants':{AlarmType:{INCIDENT:'incident'},MY_AUTH_BIZ_ID:-1,MY_ALARM_BIZ_ID:-2},
    '@/store/modules/alarm-center':{useAlarmCenterStore:()=>alarm}, '@/store/modules/app':{useAppStore:()=>app},
  }).useIncidentGuideScope;
  const ui = v.run(() => make(total,enabled,v.vue.ref(true)));
  assert.equal(ui.showAccessGuideTip.value,true); assert.equal(ui.accessGuideTipCount.value,132337);
  alarm.bizIds=[-2]; total.value=undefined; await tick();
  assert.equal(ui.accessGuideTipCount.value,undefined); assert.equal(ui.showAccessGuideTip.value,false);
  assert.equal(h.calls.length,0);
  alarm.bizIds=[2,-12]; await tick();
  assert.deepEqual(h.calls.map(q=>q.bk_biz_ids),['-12']);
  assert.equal(ui.sidesliderSpaceList.value[1].space_uid,'bkci__project');
  assert.equal(ui.accessGuideTipCount.value,1); assert.equal(ui.showAccessGuideTip.value,true);
  partial=true; alarm.bizIds=[-12]; await tick(); assert.equal(ui.guideLookupFailed.value,true);
  assert.equal(ui.showDataAccessDirect.value,false);
  partial=false; ui.reloadGuideSpaces(); await tick(); assert.equal(ui.showDataAccessDirect.value,true);
  h.window.space_list_page_supported=false; app.bizList=[row(2),target,row(9)]; app.noAuthBizIds=[9]; alarm.bizIds=[-1]; await tick();
  assert.deepEqual(ui.sidesliderSpaceList.value.map(r=>r.id),[2,-12]); assert.equal(ui.accessGuideTipCount.value,1);
  assert.equal(h.calls.length,3);
});
test('opening an incident guide reads one bounded page and handles a sparse cursor, search and retry without losing the selection', async t => {
  const h=setup([], ({cursor,query}) => query ? {items:[row(12)],next_cursor:null}
    : cursor ? {items:[row(7)],next_cursor:null} : {items:[],next_cursor:'second'});
  const v=incidentVue(); t.after(v.close);
  const Select=Object.assign(()=>{}, {Option:'option'});
  const component=load('trace/pages/alarm-center/components/paged-incident-guide.tsx',h.window,{
    ...h.deps, vue:v.vue, 'vue-i18n':{useI18n:()=>({t:key=>key})},
    'bkui-vue':{Select,Button:'button',Loading:'loading'}, '../../../components/data-access':{default:'access'},
  }).default;
  const render=v.run(()=>component.setup({authorizedSpaceCount:290,enabledBizIds:[7]}, {emit(){}}));
  assert.deepEqual(h.calls,[]); await v.mount(); assert.equal(h.calls.length,1); assert.equal(h.calls[0].page_size,100);
  h.fail('second'); await render().children[0].props.onClick(); assert.equal(render().children[0].children[0],'重试');
  h.fail(undefined); await render().children[0].props.onClick();
  assert.equal(render().props.totalCount,290); assert.equal(render().props.spaceList[0].id,7);
  const select=()=>render().props['v-slots'].spacePicker().children[0];
  await select().props.remoteMethod('12'); assert.equal(render().props.spaceList[0].id,7);
  select().props['onUpdate:modelValue']('12'); assert.equal(render().props.spaceList[0].id,12);
  assert.deepEqual(h.calls.map(q=>[q.cursor,q.query]),[[undefined,undefined],['second',undefined],['second',undefined],[undefined,'12']]);
});
test('the incident knowledge link uses the selected authorized non-CMDB scope, including topology snapshots with just a business ID', async t => {
  const target={...row(-12),space_type_id:'bkci',space_id:'test-project',space_uid:'bkci__test-project'};
  const h=setup([],()=>({items:[target],next_cursor:null}));
  const urls=[]; Object.assign(h.window,{bk_incident_saas_host:'https://incident.example.test/',open:url=>urls.push(url)});
  function find(node, predicate) {
    if (!node || typeof node !== 'object') return;
    if (predicate(node)) return node;
    for (const item of node.children || []) { const found=find(item,predicate); if(found)return found; }
  }
  for (const space of [target,{bk_biz_id:-12,space_id:-12,space_name:'from snapshot'}]) {
    const v=incidentVue(); t.after(v.close);
    const data=load('trace/components/data-access/index.tsx',h.window,{
      ...h.deps,vue:v.vue,'vue-i18n':{useI18n:()=>({t:key=>key})},'../../store/modules/app':{useAppStore:()=>({bizList:[row(2)]})},
      'monitor-api/modules/incident':{fetchConfigList:async()=>({objects:[{content:{config:[{name:'knowledge'}]}}]}),fetchGlobalVariables:async()=>({})},
    }).default;
    const render=v.run(()=>data.setup({spaceList:[space],enabledBizIds:[],forceUnmetCells:{}},{slots:{},emit(){}}));
    v.mount(); await tick();
    find(render(), el=>el.type==='th' && el.props.key==='knowledge').props.onClick();
  }
  assert.deepEqual(urls, Array(2).fill('https://incident.example.test/bkci_test-project/space/setting/knowledge'));
  assert.deepEqual(h.calls.map(q=>q.bk_biz_ids),['-12']);
});
