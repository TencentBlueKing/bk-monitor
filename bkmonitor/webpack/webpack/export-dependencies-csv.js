const file = require('node:fs');
const path = require('node:path');
const paths = [
  './package.json',
  './src/apm/package.json',
  './src/fta-solutions/package.json',
  './src/monitor-api/package.json',
  './src/monitor-common/package.json',
  './src/monitor-mobile/package.json',
  './src/monitor-pc/package.json',
  './src/monitor-static/package.json',
  './src/monitor-ui/package.json',
  // './src/trace/package.json'
];
const tracePath = './src/trace/package.json';
let setData = {};
for (const p of paths) {
  const json = file.readFileSync(path.resolve(__dirname, p));
  const data = JSON.parse(json);
  setData = { ...setData, ...data.devDependencies, ...data.dependencies };
}
const list = Object.keys(setData).map(name => {
  const value = setData[name].replace(/[\^~]/, '');
  let path = name;
  if (path.includes('@')) {
    path = name.replace(/^@[^/]*\//gim, '');
  }
  return {
    name,
    value,
    link: value.includes('http') ? value : `https://registry.npmjs.org/${name}/-/${path}-${value}.tgz`,
  };
});

const json = file.readFileSync(path.resolve(__dirname, tracePath));
const data = JSON.parse(json);
const traceData = { ...data.devDependencies, ...data.dependencies };
for (const [name, val] of Object.entries(traceData)) {
  const value = val.replace(/[\^~]/, '');
  const item = list.find(set => set.name === name && set.value === value);
  if (!item) {
    let path = name;
    console.info(name);
    if (path.includes('@')) {
      path = name.replace(/^@[^/]*\//gim, '');
    }
    list.push({
      name,
      value,
      link: value.includes('http') ? value : `https://registry.npmjs.org/${name}/-/${path}-${value}.tgz`,
    });
  }
}
const jsonToExcel = (data, head = 'name,value,link', name = './前端依赖.csv') => {
  let str = head ? `${head}\n` : '';
  for (const item of data) {
    // biome-ignore lint/complexity/noForEach: <explanation>
    Object.keys(item).forEach(key => {
      str = `${`${str + item[key]}\t`},`;
    });
    str += '\n';
  }
  file.writeFileSync(name, str);
};
jsonToExcel(list);
