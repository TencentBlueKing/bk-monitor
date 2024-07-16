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
const https = require('node:https');
const path = require('node:path');
const fs = require('node:fs');
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
            } catch (e) {}
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
        },
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
        }),
      );
      text = '';
    }
  });
  Promise.all(list).then(() => {
    fs.writeFileSync(jsonUrl.replace(/-zh\.json$/, '-en.json'), JSON.stringify(jsonData));
  });
}

['content'].forEach(key => {
  translate(key);
});
