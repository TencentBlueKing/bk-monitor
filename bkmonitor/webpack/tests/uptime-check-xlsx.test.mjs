import { chromium } from '@playwright/test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { after, before, test } from 'node:test';
import { crc32, deflateRawSync } from 'node:zlib';
import ts from 'typescript';

const root = path.resolve(import.meta.dirname, '..');
const componentDir = path.join(root, 'src/monitor-pc/pages/uptime-check/uptime-check-task/uptime-check-import');
const spreadsheetNS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main';
const relationshipNS = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships';
const packageNS = 'http://schemas.openxmlformats.org/package/2006/relationships';
let browser;
let page;

before(async () => {
  browser = await chromium.launch({ headless: true });
  page = await browser.newPage();
  await page.addScriptTag({ path: path.join(root, 'src/monitor-pc/node_modules/vue/dist/vue.js') });
  const { outputText } = ts.transpileModule(fs.readFileSync(path.join(componentDir, 'parse-xlsx.ts'), 'utf8'), {
    compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS },
  });
  await page.addScriptTag({ content: `globalThis.exports = {};\n${outputText}` });
  const script = fs
    .readFileSync(path.join(componentDir, 'uptime-check-import.vue'), 'utf8')
    .match(/<script>([\s\S]*?)<\/script>/)[1];
  await page.addScriptTag({
    content: `(() => { const parseXlsx = exports.parseXlsx;\n${script.replace(/^import .*;\n/gm, '').replace('export default', 'globalThis.importComponent =')} })();`,
  });
  assert.equal(await page.evaluate(() => typeof globalThis.importComponent?.methods.parseFile), 'function');
  const template = fs.readFileSync(path.join(componentDir, 'uptime-check-import.vue'), 'utf8').match(/<template>([\s\S]*?)<\/template>\s*<script>/)[1];
  await page.evaluate(template => {
    globalThis.process = { env: { NODE_ENV: 'production' } };
    window.static_url = '/static/';
    Vue.prototype.$t = value => value;
    Vue.prototype.$bkMessage = function (message) { this.testMessages.push(message); };
    Vue.component('bk-sideslider', { render(h) { return h('aside', this.$slots.content); } });
    Vue.component('bk-table', { render(h) { return h('div'); } });
    Vue.component('bk-button', { props: ['disabled'], render(h) { return h('button', { attrs: { disabled: this.disabled } }, this.$slots.default); } });
    globalThis.createImportVm = () => {
      const vm = new Vue({ ...importComponent, ...Vue.compile(template), propsData: { options: { isShow: true } } });
      vm.testMessages = [];
      vm.getRules = async () => ({ success: true, data: [
        { cnkey: '任务名称（必填）', enkey: 'name', required: true },
        { cnkey: '协议（必填）', enkey: 'protocol', required: true },
      ] });
      vm.importTask = async () => ({ success: { total: 1 } });
      vm.$mount();
      document.body.appendChild(vm.$el);
      return vm;
    };
  }, template);
});

after(async () => browser?.close());

// 用 Node 的 ZIP/CRC 基础能力构造输入，测试不依赖已移除的 xlsx。
function zip(files, { method = 8, descriptor = false, comment = '' } = {}) {
  const localFiles = [];
  const directory = [];
  let offset = 0;
  for (const [name, text] of Object.entries(files)) {
    const nameBytes = Buffer.from(name);
    const data = Buffer.from(text);
    const compressed = method === 8 ? deflateRawSync(data) : data;
    const crc = crc32(data);
    const local = Buffer.alloc(30);
    local.writeUInt32LE(0x04034b50);
    local.writeUInt16LE(20, 4);
    local.writeUInt16LE(descriptor ? 8 : 0, 6);
    local.writeUInt16LE(method, 8);
    if (!descriptor) {
      local.writeUInt32LE(crc, 14);
      local.writeUInt32LE(compressed.length, 18);
      local.writeUInt32LE(data.length, 22);
    }
    local.writeUInt16LE(nameBytes.length, 26);
    const trailer = Buffer.alloc(descriptor ? 16 : 0);
    if (descriptor) {
      trailer.writeUInt32LE(0x08074b50);
      trailer.writeUInt32LE(crc, 4);
      trailer.writeUInt32LE(compressed.length, 8);
      trailer.writeUInt32LE(data.length, 12);
    }
    const central = Buffer.alloc(46);
    central.writeUInt32LE(0x02014b50);
    central.writeUInt16LE(20, 4);
    central.writeUInt16LE(20, 6);
    central.writeUInt16LE(descriptor ? 8 : 0, 8);
    central.writeUInt16LE(method, 10);
    central.writeUInt32LE(crc, 16);
    central.writeUInt32LE(compressed.length, 20);
    central.writeUInt32LE(data.length, 24);
    central.writeUInt16LE(nameBytes.length, 28);
    central.writeUInt32LE(offset, 42);
    localFiles.push(local, nameBytes, compressed, trailer);
    directory.push(central, nameBytes);
    offset += local.length + nameBytes.length + compressed.length + trailer.length;
  }
  const central = Buffer.concat(directory);
  const end = Buffer.alloc(22);
  const count = Object.keys(files).length;
  end.writeUInt32LE(0x06054b50);
  end.writeUInt16LE(count, 8);
  end.writeUInt16LE(count, 10);
  end.writeUInt32LE(central.length, 12);
  end.writeUInt32LE(offset, 16);
  end.writeUInt16LE(Buffer.byteLength(comment), 20);
  return Buffer.concat([...localFiles, central, end, Buffer.from(comment)]);
}

const inline = (ref, text) => `<c r="${ref}" t="inlineStr"><is><t>${text}</t></is></c>`;
const numeric = (ref, value) => `<c r="${ref}"><v>${value}</v></c>`;
const sheet = (rows, dimension = '') =>
  `<worksheet xmlns="${spreadsheetNS}">${dimension ? `<dimension ref="${dimension}"/>` : ''}<sheetData>${rows}</sheetData></worksheet>`;
const simpleSheet = sheet(
  `<row r="1">${inline('A1', '任务名称（必填）')}${inline('B1', '协议（必填）')}</row><row r="2">${inline('A2', '测试任务')}${inline('B2', 'TCP')}</row>`,
  'A1:B2'
);

function files(worksheet = simpleSheet, strings) {
  const result = {
    '_rels/.rels': `<Relationships xmlns="${packageNS}"><Relationship Id="root" Type="${relationshipNS}/officeDocument" Target="xl/workbook.xml"/></Relationships>`,
    'xl/workbook.xml': `<workbook xmlns="${spreadsheetNS}" xmlns:r="${relationshipNS}"><sheets><sheet name="导入" sheetId="9" r:id="first"/><sheet name="忽略" sheetId="1" r:id="second"/></sheets></workbook>`,
    'xl/_rels/workbook.xml.rels': `<Relationships xmlns="${packageNS}"><Relationship Id="second" Type="${relationshipNS}/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="first" Type="${relationshipNS}/worksheet" Target="/xl/worksheets/sheet9.xml"/>${strings ? `<Relationship Id="strings" Type="${relationshipNS}/sharedStrings" Target="strings.xml"/>` : ''}</Relationships>`,
    'xl/worksheets/sheet1.xml': sheet('<row r="1"><c r="A1" t="inlineStr"><is><t>不应读取这张表</t></is></c></row>'),
    'xl/worksheets/sheet9.xml': worksheet,
  };
  if (strings) result['xl/strings.xml'] = `<sst xmlns="${spreadsheetNS}">${strings}</sst>`;
  return result;
}

const parse = async buffer =>
  JSON.parse(
    await page.evaluate(
      async bytes => JSON.stringify(await exports.parseXlsx(Uint8Array.from(bytes).buffer)),
      Array.from(buffer)
    )
  );
const expectedSimple = [{ '任务名称（必填）': '测试任务', '协议（必填）': 'TCP' }];

for (const [protocol, columns] of [
  ['http', 14],
  ['tcp', 14],
  ['udp', 17],
  ['icmp', 13],
]) {
  test(`读取原有 ${protocol.toUpperCase()} 模板，保留字段和数字类型`, async () => {
    const buffer = fs.readFileSync(
      path.join(root, '../static/example/uptime_check', `bk_monitor_${protocol}_template.xlsx`)
    );
    const rows = await parse(buffer);
    assert.equal(rows.length, 1);
    assert.equal(Object.keys(rows[0]).length, columns);
    assert.equal(rows[0]['协议（必填）'], protocol === 'http' ? 'HTTP(S)' : protocol.toUpperCase());
    assert.equal(rows[0]['周期（默认分钟）'], 1);
    assert.equal(rows[0][protocol === 'icmp' ? '超时时间（ms）' : '期望响应时间（ms）'], 3000);
    assert.equal(typeof rows[0]['任务名称（必填）'], 'string');
    if (protocol === 'http') assert.equal(typeof JSON.parse(rows[0].头信息), 'object');
  });
}

for (const options of [{ method: 0 }, { method: 8 }, { method: 8, descriptor: true, comment: 'archive comment' }]) {
  test(`按工作簿顺序读取第一张表：${JSON.stringify(options)}`, async () => {
    assert.deepEqual(await parse(zip(files(), options)), expectedSimple);
  });
}

test('空列不移位，保留 0、false、空字符串和公式缓存，跳过空行及无缓存公式', async () => {
  const xml = sheet(
    `<row r="1">${inline('A1', '名称')}${inline('B1', '可选')}${inline('C1', '数值')}${inline('D1', '开关')}${inline('E1', '计算')}${inline('F1', '未计算')}</row>
    <row r="2">${inline('A2', '')}${numeric('C2', 0)}<c r="D2" t="b"><v>0</v></c><c r="E2"><f>1+2</f><v>3</v></c><c r="F2"><f>4+5</f></c></row>
    <row r="3"><c r="A3"/></row>
    <row r="5">${inline('A5', '末行')}</row>`,
    'A1:F5'
  );
  assert.deepEqual(await parse(zip(files(xml))), [{ 名称: '', 数值: 0, 开关: false, 计算: 3 }, { 名称: '末行' }]);
});

test('共享/内联富文本、注音、XML 转义、换行和 OOXML 转义字符', async () => {
  const strings =
    '<si><t>内容</t></si><si><r><t xml:space="preserve"> 中文 </t></r><rPh><t>zhongwen</t></rPh><r><t>&amp;值_x000A_第二行</t></r></si>';
  const xml = sheet(
    '<row r="1"><c r="A1" t="s"><v>0</v></c></row><row r="2"><c r="A2" t="s"><v>1</v></c></row><row r="3"><c r="A3" t="inlineStr"><is><r><t>_x005F_x0041_</t></r><r><t>&lt;tag&gt;</t></r></is></c></row>'
  );
  assert.deepEqual(await parse(zip(files(xml, strings))), [{ 内容: ' 中文 &值\n第二行' }, { 内容: '_x0041_<tag>' }]);
});

test('重复/空表头生成独立字段，保留 JSON 文本且原型属性不污染对象', async () => {
  const xml = sheet(
    `<row r="1">${inline('A1', '重复')}${inline('B1', '重复')}${inline('D1', '__proto__')}</row><row r="2">${inline('A2', '{&quot;key&quot;:&quot;a,b&quot;}')}${inline('B2', '换行\n内容')}${numeric('C2', 7)}${inline('D2', '安全文本')}</row>`,
    'A1:D2'
  );
  const rows = await parse(zip(files(xml)));
  assert.deepEqual(rows, [
    JSON.parse('{"重复":"{\\"key\\":\\"a,b\\"}","重复_1":"换行\\n内容","__EMPTY":7,"__proto__":"安全文本"}'),
  ]);
});

test('工作表允许非 A1 起点及缺省行列坐标，空表返回空数组', async () => {
  const xml = sheet(`<row r="3">${inline('B3', '名称')}</row><row r="4">${inline('B4', '任务')}</row>`, 'B3:B4');
  assert.deepEqual(await parse(zip(files(xml))), [{ 名称: '任务' }]);
  assert.deepEqual(
    await parse(
      zip(
        files(
          sheet(
            '<row><c t="inlineStr"><is><t>名称</t></is></c></row><row><c t="inlineStr"><is><t>任务</t></is></c></row>'
          )
        )
      )
    ),
    [{ 名称: '任务' }]
  );
  assert.deepEqual(await parse(zip(files(sheet('', 'A1')))), []);
});

test('单点 dimension 不能覆盖实际数据范围并导致导入结果为空', async () => {
  const xml = sheet(
    `<row r="1">${inline('A1', '任务名称（必填）')}${inline('B1', '协议（必填）')}</row>` +
    [2, 3, 4, 5].map(index => `<row r="${index}">${inline(`A${index}`, `任务${index}`)}${inline(`B${index}`, 'ICMP')}${numeric(`M${index}`, 68)}</row>`).join(''),
    'M5'
  );
  const rows = await parse(zip(files(xml)));
  assert.equal(rows.length, 4);
  assert.equal(rows[0]['任务名称（必填）'], '任务2');
  assert.equal(rows[3]['协议（必填）'], 'ICMP');
});

test('通过关系文件读取非默认路径及 UTF-16 XML', async () => {
  const source = files();
  source['xl/worksheets/sheet9.xml'] = Buffer.concat([Buffer.from([0xff, 0xfe]), Buffer.from(simpleSheet, 'utf16le')]);
  source['_rels/.rels'] = source['_rels/.rels'].replace('xl/workbook.xml', '/xl/workbook.xml');
  assert.deepEqual(await parse(zip(source)), expectedSimple);
});

test('拒绝截断、CRC 不匹配、加密及解压长度伪造的 ZIP', async () => {
  const original = zip(files());
  await assert.rejects(parse(original.subarray(0, -5)));
  await assert.rejects(parse(Buffer.from('not a workbook')));
  const directory = original.readUInt32LE(original.length - 6);
  for (const [relativeOffset, value, bytes] of [
    [16, 0, 4],
    [8, 1, 2],
    [24, 1, 4],
    [24, 101 * 1024 * 1024, 4],
  ]) {
    const corrupt = Buffer.from(original);
    corrupt.writeUIntLE(value, directory + relativeOffset, bytes);
    await assert.rejects(parse(corrupt));
  }
});

test('拒绝损坏 XML、DTD、外部工作表关系及非法共享字符串索引', async () => {
  await assert.rejects(parse(zip(files('<worksheet>'))));
  await assert.rejects(parse(zip(files(`<!DOCTYPE worksheet [<!ENTITY value "unexpected">]>${simpleSheet}`))));
  const external = files();
  external['xl/_rels/workbook.xml.rels'] = external['xl/_rels/workbook.xml.rels'].replace(
    'Id="first"',
    'Id="first" TargetMode="External"'
  );
  await assert.rejects(parse(zip(external)));
  await assert.rejects(
    parse(zip(files(sheet('<row r="1"><c r="A1" t="s"><v>7</v></c></row>'), '<si><t>仅一个字符串</t></si>')))
  );
});

test('组件解析成功保留结果结构，损坏文件结束解析并反馈错误', async () => {
  const result = await page.evaluate(
    async bytes => {
      const file = new File([Uint8Array.from(bytes)], 'template.xlsx');
      const messages = [];
      const context = {
        file,
        status: 'uploading',
        uploadProcess: 0,
        $t: value => value,
        $bkMessage: value => messages.push(value),
      };
      const success = await importComponent.methods.parseFile.call(context, file);
      const progress = context.uploadProcess;
      const corrupt = new File(['invalid'], 'corrupt.xlsx');
      context.file = corrupt;
      let rejected = false;
      try {
        await importComponent.methods.parseFile.call(context, corrupt);
      } catch {
        rejected = true;
      }
      return { success, progress, rejected, status: context.status, parsingRes: context.parsingRes, messages };
    },
    Array.from(zip(files()))
  );
  assert.deepEqual(result.success, { success: true, message: '', data: expectedSimple });
  assert.equal(result.progress, 100);
  assert.equal(result.rejected, true);
  assert.equal(result.status, 'parsing');
  assert.equal(result.parsingRes, 'error');
  assert.equal(result.messages[0].message, '解析文件失败');
});

test('文件读取完成前清除选择，不再返回旧文件的数据', async () => {
  const result = await page.evaluate(
    async bytes => {
      const file = new File([Uint8Array.from(bytes)], 'template.xlsx');
      const context = {
        file,
        status: 'uploading',
        $t: value => value,
        $bkMessage: () => {
          throw new Error('stale error');
        },
      };
      const promise = importComponent.methods.parseFile.call(context, file);
      context.file = {};
      return await promise;
    },
    Array.from(zip(files()))
  );
  assert.deepEqual(result.data, []);
});

test('解析结果继续通过原有字段映射、校验与 task_list 导入流程', async () => {
  const result = await page.evaluate(
    async bytes => {
      const context = { file: {}, taskList: [], rulesMap: new Map(), $t: value => value, $bkMessage: () => {} };
      for (const [name, method] of Object.entries(importComponent.methods)) context[name] = method.bind(context);
      context.validateFile = async () => {};
      context.getRules = async () => ({
        success: true,
        data: [
          { cnkey: '任务名称（必填）', enkey: 'name', required: true },
          { cnkey: '协议（必填）', enkey: 'protocol', required: true },
        ],
      });
      const submitted = [];
      context.importTask = async data => {
        submitted.push(structuredClone(data));
        return { success: { total: 1 } };
      };
      await context.handleFile([new File([Uint8Array.from(bytes)], 'template.xlsx')]);
      return { submitted, taskList: context.taskList, parsingRes: context.parsingRes };
    },
    Array.from(zip(files()))
  );
  assert.deepEqual(result.submitted, [[{ name: '测试任务', protocol: 'TCP', status: 'pending' }]]);
  assert.deepEqual(result.taskList, [{ name: '测试任务', protocol: 'TCP', status: 'success' }]);
  assert.equal(result.parsingRes, 'finish');
});

test('解析过程中清除文件，旧解析结果不会获取规则或创建任务', async () => {
  const result = await page.evaluate(async () => {
    let finish;
    let calls = 0;
    const context = {
      file: {},
      getFileInfo: file => file,
      validateFile: async () => {},
      parseFile: () =>
        new Promise(resolve => {
          finish = resolve;
        }),
      getRules: async () => {
        calls++;
      },
    };
    const promise = importComponent.methods.handleFile.call(context, [new File([''], 'template.xlsx')]);
    await Promise.resolve();
    context.file = {};
    finish({ data: [{ '协议（必填）': 'TCP' }] });
    await promise;
    return calls;
  });
  assert.equal(result, 0);
});

test('真实 Vue 组件上传 ICMP 模板后显示预览并允许完成', async () => {
  const buffer = fs.readFileSync(path.join(root, '../static/example/uptime_check/bk_monitor_icmp_template.xlsx'));
  const result = await page.evaluate(async bytes => {
    const vm = createImportVm();
    try {
      await vm.handleFile([new File([Uint8Array.from(bytes)], 'bk_monitor_icmp_template.xlsx', { type: vm.accept })]);
      await vm.$nextTick();
      return { count: vm.taskList.length, state: vm.parsingRes, visible: getComputedStyle(vm.$el.querySelector('.data-preview')).display !== 'none', disabled: vm.$el.querySelector('.button-complete').disabled };
    } finally { vm.$destroy(); vm.$el.remove(); }
  }, Array.from(buffer));
  assert.deepEqual(result, { count: 1, state: 'finish', visible: true, disabled: false });
});

test('真实 Vue 组件上传只有表头的 Excel 时给出提示，不能静默停留在文件卡片', async () => {
  const buffer = zip(files(sheet(`<row r="1">${inline('A1', '任务名称（必填）')}${inline('B1', '协议（必填）')}</row>`, 'A1:B1')));
  const result = await page.evaluate(async bytes => {
    const vm = createImportVm();
    try {
      await vm.handleFile([new File([Uint8Array.from(bytes)], 'empty.xlsx', { type: vm.accept })]);
      await vm.$nextTick();
      return { count: vm.taskList.length, state: vm.parsingRes, messages: vm.testMessages, visible: getComputedStyle(vm.$el.querySelector('.data-preview')).display !== 'none', disabled: vm.$el.querySelector('.button-complete').disabled, hintVisible: getComputedStyle(vm.$el.querySelector('.parsing-result')).display !== 'none', hint: vm.$el.querySelector('.error-text').textContent.trim() };
    } finally { vm.$destroy(); vm.$el.remove(); }
  }, Array.from(buffer));
  assert.ok(result.messages.length > 0, JSON.stringify(result));
  assert.equal(result.state, 'empty');
  assert.equal(result.hintVisible, true);
  assert.equal(result.hint, '导入数据为空');
  assert.equal(result.disabled, true);
});
