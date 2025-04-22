const fs = require('node:fs');
const https = require('node:https');
const path = require('node:path');
async function fetchTranslate(tempUrl, text) {
  const writeStream = fs.createWriteStream(tempUrl);
  return new Promise(resolve => {
    https
      .get(
        `https://translate.googleapis.com/translate_a/single?client=gtx&sl=zh-CN&tl=en&dt=t&q=${encodeURI(text)}`,
        response => {
          response.on('data', chunk => {
            writeStream.write(chunk);
          });
          // response.on('end', () => {
          //   writeStream.end();
          // });
          writeStream.on('end', () => {
            let data = [];
            try {
              data = JSON.parse(fs.readFileSync(tempUrl));
            } catch {}
            if (!data?.length) {
              resolve({});
              return;
            }
            const jsonData = data[0].reduce((total, [en, zh]) => {
              total[zh.replace(/\n$/gim, '')] = en.replace(/\n$/gim, '');
              return total;
            }, {});
            // fs.writeFileSync(jsonUrl.replace(/-zh\.json$/, '-en.json'), JSON.stringify(jsonData));
            resolve(jsonData);
            // writeStream.destroy();
          });

          writeStream.on('error', e => {
            console.info(e);
            resolve({});
          });
        }
      )
      .on('error', e => {
        console.info(e, '+++++++++++');
      });
  });
}
function translate(key) {
  const jsonUrl = path.resolve(__dirname, `../src/monitor-pc/lang/${key}-zh.json`);
  const data = JSON.parse(fs.readFileSync(jsonUrl));
  const list = [];
  let text = '';
  let jsonData = {};
  Object.keys(data).forEach((name, index, all) => {
    text += `${name}\n`;
    if ((index > 0 && text.length > 1024) || index === all.length - 1) {
      const tempUrl = path.resolve(__dirname, `./temp-${key}-${index}.txt`);
      list.push(
        fetchTranslate(tempUrl, text).then(tempData => {
          jsonData = { ...jsonData, ...tempData };
          // fs.unlink(tempUrl)
        })
      );
      text = '';
    }
  });
  Promise.all(list).then(() => {
    fs.writeFileSync(jsonUrl.replace(/-zh\.json$/, '-en.json'), JSON.stringify(jsonData));
  });
}
translate('content');
