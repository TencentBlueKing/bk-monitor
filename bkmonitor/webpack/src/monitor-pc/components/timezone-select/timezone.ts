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
/*
const list = [];
const names = moment.tz.names();
names.forEach(name => {
  list.push({
    name,
    z: moment.tz(name).format('z'),
    Z: moment.tz(name).format('Z')
  })
})
console.log(list);
*/
// 时区列表(数据来源于moment)
export default [
  {
    name: 'Africa/Abidjan',
    z: 'GMT',
    Z: '+00:00',
  },
  {
    name: 'Africa/Accra',
    z: 'GMT',
    Z: '+00:00',
  },
  {
    name: 'Africa/Addis_Ababa',
    z: 'EAT',
    Z: '+03:00',
  },
  {
    name: 'Africa/Algiers',
    z: 'CET',
    Z: '+01:00',
  },
  {
    name: 'Africa/Asmara',
    z: 'EAT',
    Z: '+03:00',
  },
  {
    name: 'Africa/Asmera',
    z: 'EAT',
    Z: '+03:00',
  },
  {
    name: 'Africa/Bamako',
    z: 'GMT',
    Z: '+00:00',
  },
  {
    name: 'Africa/Bangui',
    z: 'WAT',
    Z: '+01:00',
  },
  {
    name: 'Africa/Banjul',
    z: 'GMT',
    Z: '+00:00',
  },
  {
    name: 'Africa/Bissau',
    z: 'GMT',
    Z: '+00:00',
  },
  {
    name: 'Africa/Blantyre',
    z: 'CAT',
    Z: '+02:00',
  },
  {
    name: 'Africa/Brazzaville',
    z: 'WAT',
    Z: '+01:00',
  },
  {
    name: 'Africa/Bujumbura',
    z: 'CAT',
    Z: '+02:00',
  },
  {
    name: 'Africa/Cairo',
    z: 'EEST',
    Z: '+03:00',
  },
  {
    name: 'Africa/Casablanca',
    z: '+01',
    Z: '+01:00',
  },
  {
    name: 'Africa/Ceuta',
    z: 'CEST',
    Z: '+02:00',
  },
  {
    name: 'Africa/Conakry',
    z: 'GMT',
    Z: '+00:00',
  },
  {
    name: 'Africa/Dakar',
    z: 'GMT',
    Z: '+00:00',
  },
  {
    name: 'Africa/Dar_es_Salaam',
    z: 'EAT',
    Z: '+03:00',
  },
  {
    name: 'Africa/Djibouti',
    z: 'EAT',
    Z: '+03:00',
  },
  {
    name: 'Africa/Douala',
    z: 'WAT',
    Z: '+01:00',
  },
  {
    name: 'Africa/El_Aaiun',
    z: '+01',
    Z: '+01:00',
  },
  {
    name: 'Africa/Freetown',
    z: 'GMT',
    Z: '+00:00',
  },
  {
    name: 'Africa/Gaborone',
    z: 'CAT',
    Z: '+02:00',
  },
  {
    name: 'Africa/Harare',
    z: 'CAT',
    Z: '+02:00',
  },
  {
    name: 'Africa/Johannesburg',
    z: 'SAST',
    Z: '+02:00',
  },
  {
    name: 'Africa/Juba',
    z: 'CAT',
    Z: '+02:00',
  },
  {
    name: 'Africa/Kampala',
    z: 'EAT',
    Z: '+03:00',
  },
  {
    name: 'Africa/Khartoum',
    z: 'CAT',
    Z: '+02:00',
  },
  {
    name: 'Africa/Kigali',
    z: 'CAT',
    Z: '+02:00',
  },
  {
    name: 'Africa/Kinshasa',
    z: 'WAT',
    Z: '+01:00',
  },
  {
    name: 'Africa/Lagos',
    z: 'WAT',
    Z: '+01:00',
  },
  {
    name: 'Africa/Libreville',
    z: 'WAT',
    Z: '+01:00',
  },
  {
    name: 'Africa/Lome',
    z: 'GMT',
    Z: '+00:00',
  },
  {
    name: 'Africa/Luanda',
    z: 'WAT',
    Z: '+01:00',
  },
  {
    name: 'Africa/Lubumbashi',
    z: 'CAT',
    Z: '+02:00',
  },
  {
    name: 'Africa/Lusaka',
    z: 'CAT',
    Z: '+02:00',
  },
  {
    name: 'Africa/Malabo',
    z: 'WAT',
    Z: '+01:00',
  },
  {
    name: 'Africa/Maputo',
    z: 'CAT',
    Z: '+02:00',
  },
  {
    name: 'Africa/Maseru',
    z: 'SAST',
    Z: '+02:00',
  },
  {
    name: 'Africa/Mbabane',
    z: 'SAST',
    Z: '+02:00',
  },
  {
    name: 'Africa/Mogadishu',
    z: 'EAT',
    Z: '+03:00',
  },
  {
    name: 'Africa/Monrovia',
    z: 'GMT',
    Z: '+00:00',
  },
  {
    name: 'Africa/Nairobi',
    z: 'EAT',
    Z: '+03:00',
  },
  {
    name: 'Africa/Ndjamena',
    z: 'WAT',
    Z: '+01:00',
  },
  {
    name: 'Africa/Niamey',
    z: 'WAT',
    Z: '+01:00',
  },
  {
    name: 'Africa/Nouakchott',
    z: 'GMT',
    Z: '+00:00',
  },
  {
    name: 'Africa/Ouagadougou',
    z: 'GMT',
    Z: '+00:00',
  },
  {
    name: 'Africa/Porto-Novo',
    z: 'WAT',
    Z: '+01:00',
  },
  {
    name: 'Africa/Sao_Tome',
    z: 'GMT',
    Z: '+00:00',
  },
  {
    name: 'Africa/Timbuktu',
    z: 'GMT',
    Z: '+00:00',
  },
  {
    name: 'Africa/Tripoli',
    z: 'EET',
    Z: '+02:00',
  },
  {
    name: 'Africa/Tunis',
    z: 'CET',
    Z: '+01:00',
  },
  {
    name: 'Africa/Windhoek',
    z: 'CAT',
    Z: '+02:00',
  },
  {
    name: 'America/Adak',
    z: 'HDT',
    Z: '-09:00',
  },
  {
    name: 'America/Anchorage',
    z: 'AKDT',
    Z: '-08:00',
  },
  {
    name: 'America/Anguilla',
    z: 'AST',
    Z: '-04:00',
  },
  {
    name: 'America/Antigua',
    z: 'AST',
    Z: '-04:00',
  },
  {
    name: 'America/Araguaina',
    z: '-03',
    Z: '-03:00',
  },
  {
    name: 'America/Argentina/Buenos_Aires',
    z: '-03',
    Z: '-03:00',
  },
  {
    name: 'America/Argentina/Catamarca',
    z: '-03',
    Z: '-03:00',
  },
  {
    name: 'America/Argentina/ComodRivadavia',
    z: '-03',
    Z: '-03:00',
  },
  {
    name: 'America/Argentina/Cordoba',
    z: '-03',
    Z: '-03:00',
  },
  {
    name: 'America/Argentina/Jujuy',
    z: '-03',
    Z: '-03:00',
  },
  {
    name: 'America/Argentina/La_Rioja',
    z: '-03',
    Z: '-03:00',
  },
  {
    name: 'America/Argentina/Mendoza',
    z: '-03',
    Z: '-03:00',
  },
  {
    name: 'America/Argentina/Rio_Gallegos',
    z: '-03',
    Z: '-03:00',
  },
  {
    name: 'America/Argentina/Salta',
    z: '-03',
    Z: '-03:00',
  },
  {
    name: 'America/Argentina/San_Juan',
    z: '-03',
    Z: '-03:00',
  },
  {
    name: 'America/Argentina/San_Luis',
    z: '-03',
    Z: '-03:00',
  },
  {
    name: 'America/Argentina/Tucuman',
    z: '-03',
    Z: '-03:00',
  },
  {
    name: 'America/Argentina/Ushuaia',
    z: '-03',
    Z: '-03:00',
  },
  {
    name: 'America/Aruba',
    z: 'AST',
    Z: '-04:00',
  },
  {
    name: 'America/Asuncion',
    z: '-03',
    Z: '-03:00',
  },
  {
    name: 'America/Atikokan',
    z: 'EST',
    Z: '-05:00',
  },
  {
    name: 'America/Atka',
    z: 'HDT',
    Z: '-09:00',
  },
  {
    name: 'America/Bahia',
    z: '-03',
    Z: '-03:00',
  },
  {
    name: 'America/Bahia_Banderas',
    z: 'CST',
    Z: '-06:00',
  },
  {
    name: 'America/Barbados',
    z: 'AST',
    Z: '-04:00',
  },
  {
    name: 'America/Belem',
    z: '-03',
    Z: '-03:00',
  },
  {
    name: 'America/Belize',
    z: 'CST',
    Z: '-06:00',
  },
  {
    name: 'America/Blanc-Sablon',
    z: 'AST',
    Z: '-04:00',
  },
  {
    name: 'America/Boa_Vista',
    z: '-04',
    Z: '-04:00',
  },
  {
    name: 'America/Bogota',
    z: '-05',
    Z: '-05:00',
  },
  {
    name: 'America/Boise',
    z: 'MDT',
    Z: '-06:00',
  },
  {
    name: 'America/Buenos_Aires',
    z: '-03',
    Z: '-03:00',
  },
  {
    name: 'America/Cambridge_Bay',
    z: 'MDT',
    Z: '-06:00',
  },
  {
    name: 'America/Campo_Grande',
    z: '-04',
    Z: '-04:00',
  },
  {
    name: 'America/Cancun',
    z: 'EST',
    Z: '-05:00',
  },
  {
    name: 'America/Caracas',
    z: '-04',
    Z: '-04:00',
  },
  {
    name: 'America/Catamarca',
    z: '-03',
    Z: '-03:00',
  },
  {
    name: 'America/Cayenne',
    z: '-03',
    Z: '-03:00',
  },
  {
    name: 'America/Cayman',
    z: 'EST',
    Z: '-05:00',
  },
  {
    name: 'America/Chicago',
    z: 'CDT',
    Z: '-05:00',
  },
  {
    name: 'America/Chihuahua',
    z: 'CST',
    Z: '-06:00',
  },
  {
    name: 'America/Ciudad_Juarez',
    z: 'MDT',
    Z: '-06:00',
  },
  {
    name: 'America/Coral_Harbour',
    z: 'EST',
    Z: '-05:00',
  },
  {
    name: 'America/Cordoba',
    z: '-03',
    Z: '-03:00',
  },
  {
    name: 'America/Costa_Rica',
    z: 'CST',
    Z: '-06:00',
  },
  {
    name: 'America/Creston',
    z: 'MST',
    Z: '-07:00',
  },
  {
    name: 'America/Cuiaba',
    z: '-04',
    Z: '-04:00',
  },
  {
    name: 'America/Curacao',
    z: 'AST',
    Z: '-04:00',
  },
  {
    name: 'America/Danmarkshavn',
    z: 'GMT',
    Z: '+00:00',
  },
  {
    name: 'America/Dawson',
    z: 'MST',
    Z: '-07:00',
  },
  {
    name: 'America/Dawson_Creek',
    z: 'MST',
    Z: '-07:00',
  },
  {
    name: 'America/Denver',
    z: 'MDT',
    Z: '-06:00',
  },
  {
    name: 'America/Detroit',
    z: 'EDT',
    Z: '-04:00',
  },
  {
    name: 'America/Dominica',
    z: 'AST',
    Z: '-04:00',
  },
  {
    name: 'America/Edmonton',
    z: 'MDT',
    Z: '-06:00',
  },
  {
    name: 'America/Eirunepe',
    z: '-05',
    Z: '-05:00',
  },
  {
    name: 'America/El_Salvador',
    z: 'CST',
    Z: '-06:00',
  },
  {
    name: 'America/Ensenada',
    z: 'PDT',
    Z: '-07:00',
  },
  {
    name: 'America/Fort_Nelson',
    z: 'MST',
    Z: '-07:00',
  },
  {
    name: 'America/Fort_Wayne',
    z: 'EDT',
    Z: '-04:00',
  },
  {
    name: 'America/Fortaleza',
    z: '-03',
    Z: '-03:00',
  },
  {
    name: 'America/Glace_Bay',
    z: 'ADT',
    Z: '-03:00',
  },
  {
    name: 'America/Godthab',
    z: '-02',
    Z: '-02:00',
  },
  {
    name: 'America/Goose_Bay',
    z: 'ADT',
    Z: '-03:00',
  },
  {
    name: 'America/Grand_Turk',
    z: 'EDT',
    Z: '-04:00',
  },
  {
    name: 'America/Grenada',
    z: 'AST',
    Z: '-04:00',
  },
  {
    name: 'America/Guadeloupe',
    z: 'AST',
    Z: '-04:00',
  },
  {
    name: 'America/Guatemala',
    z: 'CST',
    Z: '-06:00',
  },
  {
    name: 'America/Guayaquil',
    z: '-05',
    Z: '-05:00',
  },
  {
    name: 'America/Guyana',
    z: '-04',
    Z: '-04:00',
  },
  {
    name: 'America/Halifax',
    z: 'ADT',
    Z: '-03:00',
  },
  {
    name: 'America/Havana',
    z: 'CDT',
    Z: '-04:00',
  },
  {
    name: 'America/Hermosillo',
    z: 'MST',
    Z: '-07:00',
  },
  {
    name: 'America/Indiana/Indianapolis',
    z: 'EDT',
    Z: '-04:00',
  },
  {
    name: 'America/Indiana/Knox',
    z: 'CDT',
    Z: '-05:00',
  },
  {
    name: 'America/Indiana/Marengo',
    z: 'EDT',
    Z: '-04:00',
  },
  {
    name: 'America/Indiana/Petersburg',
    z: 'EDT',
    Z: '-04:00',
  },
  {
    name: 'America/Indiana/Tell_City',
    z: 'CDT',
    Z: '-05:00',
  },
  {
    name: 'America/Indiana/Vevay',
    z: 'EDT',
    Z: '-04:00',
  },
  {
    name: 'America/Indiana/Vincennes',
    z: 'EDT',
    Z: '-04:00',
  },
  {
    name: 'America/Indiana/Winamac',
    z: 'EDT',
    Z: '-04:00',
  },
  {
    name: 'America/Indianapolis',
    z: 'EDT',
    Z: '-04:00',
  },
  {
    name: 'America/Inuvik',
    z: 'MDT',
    Z: '-06:00',
  },
  {
    name: 'America/Iqaluit',
    z: 'EDT',
    Z: '-04:00',
  },
  {
    name: 'America/Jamaica',
    z: 'EST',
    Z: '-05:00',
  },
  {
    name: 'America/Jujuy',
    z: '-03',
    Z: '-03:00',
  },
  {
    name: 'America/Juneau',
    z: 'AKDT',
    Z: '-08:00',
  },
  {
    name: 'America/Kentucky/Louisville',
    z: 'EDT',
    Z: '-04:00',
  },
  {
    name: 'America/Kentucky/Monticello',
    z: 'EDT',
    Z: '-04:00',
  },
  {
    name: 'America/Knox_IN',
    z: 'CDT',
    Z: '-05:00',
  },
  {
    name: 'America/Kralendijk',
    z: 'AST',
    Z: '-04:00',
  },
  {
    name: 'America/La_Paz',
    z: '-04',
    Z: '-04:00',
  },
  {
    name: 'America/Lima',
    z: '-05',
    Z: '-05:00',
  },
  {
    name: 'America/Los_Angeles',
    z: 'PDT',
    Z: '-07:00',
  },
  {
    name: 'America/Louisville',
    z: 'EDT',
    Z: '-04:00',
  },
  {
    name: 'America/Lower_Princes',
    z: 'AST',
    Z: '-04:00',
  },
  {
    name: 'America/Maceio',
    z: '-03',
    Z: '-03:00',
  },
  {
    name: 'America/Managua',
    z: 'CST',
    Z: '-06:00',
  },
  {
    name: 'America/Manaus',
    z: '-04',
    Z: '-04:00',
  },
  {
    name: 'America/Marigot',
    z: 'AST',
    Z: '-04:00',
  },
  {
    name: 'America/Martinique',
    z: 'AST',
    Z: '-04:00',
  },
  {
    name: 'America/Matamoros',
    z: 'CDT',
    Z: '-05:00',
  },
  {
    name: 'America/Mazatlan',
    z: 'MST',
    Z: '-07:00',
  },
  {
    name: 'America/Mendoza',
    z: '-03',
    Z: '-03:00',
  },
  {
    name: 'America/Menominee',
    z: 'CDT',
    Z: '-05:00',
  },
  {
    name: 'America/Merida',
    z: 'CST',
    Z: '-06:00',
  },
  {
    name: 'America/Metlakatla',
    z: 'AKDT',
    Z: '-08:00',
  },
  {
    name: 'America/Mexico_City',
    z: 'CST',
    Z: '-06:00',
  },
  {
    name: 'America/Miquelon',
    z: '-02',
    Z: '-02:00',
  },
  {
    name: 'America/Moncton',
    z: 'ADT',
    Z: '-03:00',
  },
  {
    name: 'America/Monterrey',
    z: 'CST',
    Z: '-06:00',
  },
  {
    name: 'America/Montevideo',
    z: '-03',
    Z: '-03:00',
  },
  {
    name: 'America/Montreal',
    z: 'EDT',
    Z: '-04:00',
  },
  {
    name: 'America/Montserrat',
    z: 'AST',
    Z: '-04:00',
  },
  {
    name: 'America/Nassau',
    z: 'EDT',
    Z: '-04:00',
  },
  {
    name: 'America/New_York',
    z: 'EDT',
    Z: '-04:00',
  },
  {
    name: 'America/Nipigon',
    z: 'EDT',
    Z: '-04:00',
  },
  {
    name: 'America/Nome',
    z: 'AKDT',
    Z: '-08:00',
  },
  {
    name: 'America/Noronha',
    z: '-02',
    Z: '-02:00',
  },
  {
    name: 'America/North_Dakota/Beulah',
    z: 'CDT',
    Z: '-05:00',
  },
  {
    name: 'America/North_Dakota/Center',
    z: 'CDT',
    Z: '-05:00',
  },
  {
    name: 'America/North_Dakota/New_Salem',
    z: 'CDT',
    Z: '-05:00',
  },
  {
    name: 'America/Nuuk',
    z: '-02',
    Z: '-02:00',
  },
  {
    name: 'America/Ojinaga',
    z: 'CDT',
    Z: '-05:00',
  },
  {
    name: 'America/Panama',
    z: 'EST',
    Z: '-05:00',
  },
  {
    name: 'America/Pangnirtung',
    z: 'EDT',
    Z: '-04:00',
  },
  {
    name: 'America/Paramaribo',
    z: '-03',
    Z: '-03:00',
  },
  {
    name: 'America/Phoenix',
    z: 'MST',
    Z: '-07:00',
  },
  {
    name: 'America/Port-au-Prince',
    z: 'EDT',
    Z: '-04:00',
  },
  {
    name: 'America/Port_of_Spain',
    z: 'AST',
    Z: '-04:00',
  },
  {
    name: 'America/Porto_Acre',
    z: '-05',
    Z: '-05:00',
  },
  {
    name: 'America/Porto_Velho',
    z: '-04',
    Z: '-04:00',
  },
  {
    name: 'America/Puerto_Rico',
    z: 'AST',
    Z: '-04:00',
  },
  {
    name: 'America/Punta_Arenas',
    z: '-03',
    Z: '-03:00',
  },
  {
    name: 'America/Rainy_River',
    z: 'CDT',
    Z: '-05:00',
  },
  {
    name: 'America/Rankin_Inlet',
    z: 'CDT',
    Z: '-05:00',
  },
  {
    name: 'America/Recife',
    z: '-03',
    Z: '-03:00',
  },
  {
    name: 'America/Regina',
    z: 'CST',
    Z: '-06:00',
  },
  {
    name: 'America/Resolute',
    z: 'CDT',
    Z: '-05:00',
  },
  {
    name: 'America/Rio_Branco',
    z: '-05',
    Z: '-05:00',
  },
  {
    name: 'America/Rosario',
    z: '-03',
    Z: '-03:00',
  },
  {
    name: 'America/Santa_Isabel',
    z: 'PDT',
    Z: '-07:00',
  },
  {
    name: 'America/Santarem',
    z: '-03',
    Z: '-03:00',
  },
  {
    name: 'America/Santiago',
    z: '-03',
    Z: '-03:00',
  },
  {
    name: 'America/Santo_Domingo',
    z: 'AST',
    Z: '-04:00',
  },
  {
    name: 'America/Sao_Paulo',
    z: '-03',
    Z: '-03:00',
  },
  {
    name: 'America/Scoresbysund',
    z: '+00',
    Z: '+00:00',
  },
  {
    name: 'America/Shiprock',
    z: 'MDT',
    Z: '-06:00',
  },
  {
    name: 'America/Sitka',
    z: 'AKDT',
    Z: '-08:00',
  },
  {
    name: 'America/St_Barthelemy',
    z: 'AST',
    Z: '-04:00',
  },
  {
    name: 'America/St_Johns',
    z: 'NDT',
    Z: '-02:30',
  },
  {
    name: 'America/St_Kitts',
    z: 'AST',
    Z: '-04:00',
  },
  {
    name: 'America/St_Lucia',
    z: 'AST',
    Z: '-04:00',
  },
  {
    name: 'America/St_Thomas',
    z: 'AST',
    Z: '-04:00',
  },
  {
    name: 'America/St_Vincent',
    z: 'AST',
    Z: '-04:00',
  },
  {
    name: 'America/Swift_Current',
    z: 'CST',
    Z: '-06:00',
  },
  {
    name: 'America/Tegucigalpa',
    z: 'CST',
    Z: '-06:00',
  },
  {
    name: 'America/Thule',
    z: 'ADT',
    Z: '-03:00',
  },
  {
    name: 'America/Thunder_Bay',
    z: 'EDT',
    Z: '-04:00',
  },
  {
    name: 'America/Tijuana',
    z: 'PDT',
    Z: '-07:00',
  },
  {
    name: 'America/Toronto',
    z: 'EDT',
    Z: '-04:00',
  },
  {
    name: 'America/Tortola',
    z: 'AST',
    Z: '-04:00',
  },
  {
    name: 'America/Vancouver',
    z: 'PDT',
    Z: '-07:00',
  },
  {
    name: 'America/Virgin',
    z: 'AST',
    Z: '-04:00',
  },
  {
    name: 'America/Whitehorse',
    z: 'MST',
    Z: '-07:00',
  },
  {
    name: 'America/Winnipeg',
    z: 'CDT',
    Z: '-05:00',
  },
  {
    name: 'America/Yakutat',
    z: 'AKDT',
    Z: '-08:00',
  },
  {
    name: 'America/Yellowknife',
    z: 'MDT',
    Z: '-06:00',
  },
  {
    name: 'Antarctica/Casey',
    z: '+11',
    Z: '+11:00',
  },
  {
    name: 'Antarctica/Davis',
    z: '+07',
    Z: '+07:00',
  },
  {
    name: 'Antarctica/DumontDUrville',
    z: '+10',
    Z: '+10:00',
  },
  {
    name: 'Antarctica/Macquarie',
    z: 'AEDT',
    Z: '+11:00',
  },
  {
    name: 'Antarctica/Mawson',
    z: '+05',
    Z: '+05:00',
  },
  {
    name: 'Antarctica/McMurdo',
    z: 'NZDT',
    Z: '+13:00',
  },
  {
    name: 'Antarctica/Palmer',
    z: '-03',
    Z: '-03:00',
  },
  {
    name: 'Antarctica/Rothera',
    z: '-03',
    Z: '-03:00',
  },
  {
    name: 'Antarctica/South_Pole',
    z: 'NZDT',
    Z: '+13:00',
  },
  {
    name: 'Antarctica/Syowa',
    z: '+03',
    Z: '+03:00',
  },
  {
    name: 'Antarctica/Troll',
    z: '+02',
    Z: '+02:00',
  },
  {
    name: 'Antarctica/Vostok',
    z: '+06',
    Z: '+06:00',
  },
  {
    name: 'Arctic/Longyearbyen',
    z: 'CEST',
    Z: '+02:00',
  },
  {
    name: 'Asia/Aden',
    z: '+03',
    Z: '+03:00',
  },
  {
    name: 'Asia/Almaty',
    z: '+06',
    Z: '+06:00',
  },
  {
    name: 'Asia/Amman',
    z: '+03',
    Z: '+03:00',
  },
  {
    name: 'Asia/Anadyr',
    z: '+12',
    Z: '+12:00',
  },
  {
    name: 'Asia/Aqtau',
    z: '+05',
    Z: '+05:00',
  },
  {
    name: 'Asia/Aqtobe',
    z: '+05',
    Z: '+05:00',
  },
  {
    name: 'Asia/Ashgabat',
    z: '+05',
    Z: '+05:00',
  },
  {
    name: 'Asia/Ashkhabad',
    z: '+05',
    Z: '+05:00',
  },
  {
    name: 'Asia/Atyrau',
    z: '+05',
    Z: '+05:00',
  },
  {
    name: 'Asia/Baghdad',
    z: '+03',
    Z: '+03:00',
  },
  {
    name: 'Asia/Bahrain',
    z: '+03',
    Z: '+03:00',
  },
  {
    name: 'Asia/Baku',
    z: '+04',
    Z: '+04:00',
  },
  {
    name: 'Asia/Bangkok',
    z: '+07',
    Z: '+07:00',
  },
  {
    name: 'Asia/Barnaul',
    z: '+07',
    Z: '+07:00',
  },
  {
    name: 'Asia/Beirut',
    z: 'EEST',
    Z: '+03:00',
  },
  {
    name: 'Asia/Bishkek',
    z: '+06',
    Z: '+06:00',
  },
  {
    name: 'Asia/Brunei',
    z: '+08',
    Z: '+08:00',
  },
  {
    name: 'Asia/Calcutta',
    z: 'IST',
    Z: '+05:30',
  },
  {
    name: 'Asia/Chita',
    z: '+09',
    Z: '+09:00',
  },
  {
    name: 'Asia/Choibalsan',
    z: '+08',
    Z: '+08:00',
  },
  {
    name: 'Asia/Chongqing',
    z: 'CST',
    Z: '+08:00',
  },
  {
    name: 'Asia/Chungking',
    z: 'CST',
    Z: '+08:00',
  },
  {
    name: 'Asia/Colombo',
    z: '+0530',
    Z: '+05:30',
  },
  {
    name: 'Asia/Dacca',
    z: '+06',
    Z: '+06:00',
  },
  {
    name: 'Asia/Damascus',
    z: '+03',
    Z: '+03:00',
  },
  {
    name: 'Asia/Dhaka',
    z: '+06',
    Z: '+06:00',
  },
  {
    name: 'Asia/Dili',
    z: '+09',
    Z: '+09:00',
  },
  {
    name: 'Asia/Dubai',
    z: '+04',
    Z: '+04:00',
  },
  {
    name: 'Asia/Dushanbe',
    z: '+05',
    Z: '+05:00',
  },
  {
    name: 'Asia/Famagusta',
    z: 'EEST',
    Z: '+03:00',
  },
  {
    name: 'Asia/Gaza',
    z: 'EEST',
    Z: '+03:00',
  },
  {
    name: 'Asia/Harbin',
    z: 'CST',
    Z: '+08:00',
  },
  {
    name: 'Asia/Hebron',
    z: 'EEST',
    Z: '+03:00',
  },
  {
    name: 'Asia/Ho_Chi_Minh',
    z: '+07',
    Z: '+07:00',
  },
  {
    name: 'Asia/Hong_Kong',
    z: 'HKT',
    Z: '+08:00',
  },
  {
    name: 'Asia/Hovd',
    z: '+07',
    Z: '+07:00',
  },
  {
    name: 'Asia/Irkutsk',
    z: '+08',
    Z: '+08:00',
  },
  {
    name: 'Asia/Istanbul',
    z: '+03',
    Z: '+03:00',
  },
  {
    name: 'Asia/Jakarta',
    z: 'WIB',
    Z: '+07:00',
  },
  {
    name: 'Asia/Jayapura',
    z: 'WIT',
    Z: '+09:00',
  },
  {
    name: 'Asia/Jerusalem',
    z: 'IDT',
    Z: '+03:00',
  },
  {
    name: 'Asia/Kabul',
    z: '+0430',
    Z: '+04:30',
  },
  {
    name: 'Asia/Kamchatka',
    z: '+12',
    Z: '+12:00',
  },
  {
    name: 'Asia/Karachi',
    z: 'PKT',
    Z: '+05:00',
  },
  {
    name: 'Asia/Kashgar',
    z: '+06',
    Z: '+06:00',
  },
  {
    name: 'Asia/Kathmandu',
    z: '+0545',
    Z: '+05:45',
  },
  {
    name: 'Asia/Katmandu',
    z: '+0545',
    Z: '+05:45',
  },
  {
    name: 'Asia/Khandyga',
    z: '+09',
    Z: '+09:00',
  },
  {
    name: 'Asia/Kolkata',
    z: 'IST',
    Z: '+05:30',
  },
  {
    name: 'Asia/Krasnoyarsk',
    z: '+07',
    Z: '+07:00',
  },
  {
    name: 'Asia/Kuala_Lumpur',
    z: '+08',
    Z: '+08:00',
  },
  {
    name: 'Asia/Kuching',
    z: '+08',
    Z: '+08:00',
  },
  {
    name: 'Asia/Kuwait',
    z: '+03',
    Z: '+03:00',
  },
  {
    name: 'Asia/Macao',
    z: 'CST',
    Z: '+08:00',
  },
  {
    name: 'Asia/Macau',
    z: 'CST',
    Z: '+08:00',
  },
  {
    name: 'Asia/Magadan',
    z: '+11',
    Z: '+11:00',
  },
  {
    name: 'Asia/Makassar',
    z: 'WITA',
    Z: '+08:00',
  },
  {
    name: 'Asia/Manila',
    z: 'PST',
    Z: '+08:00',
  },
  {
    name: 'Asia/Muscat',
    z: '+04',
    Z: '+04:00',
  },
  {
    name: 'Asia/Nicosia',
    z: 'EEST',
    Z: '+03:00',
  },
  {
    name: 'Asia/Novokuznetsk',
    z: '+07',
    Z: '+07:00',
  },
  {
    name: 'Asia/Novosibirsk',
    z: '+07',
    Z: '+07:00',
  },
  {
    name: 'Asia/Omsk',
    z: '+06',
    Z: '+06:00',
  },
  {
    name: 'Asia/Oral',
    z: '+05',
    Z: '+05:00',
  },
  {
    name: 'Asia/Phnom_Penh',
    z: '+07',
    Z: '+07:00',
  },
  {
    name: 'Asia/Pontianak',
    z: 'WIB',
    Z: '+07:00',
  },
  {
    name: 'Asia/Pyongyang',
    z: 'KST',
    Z: '+09:00',
  },
  {
    name: 'Asia/Qatar',
    z: '+03',
    Z: '+03:00',
  },
  {
    name: 'Asia/Qostanay',
    z: '+06',
    Z: '+06:00',
  },
  {
    name: 'Asia/Qyzylorda',
    z: '+05',
    Z: '+05:00',
  },
  {
    name: 'Asia/Rangoon',
    z: '+0630',
    Z: '+06:30',
  },
  {
    name: 'Asia/Riyadh',
    z: '+03',
    Z: '+03:00',
  },
  {
    name: 'Asia/Saigon',
    z: '+07',
    Z: '+07:00',
  },
  {
    name: 'Asia/Sakhalin',
    z: '+11',
    Z: '+11:00',
  },
  {
    name: 'Asia/Samarkand',
    z: '+05',
    Z: '+05:00',
  },
  {
    name: 'Asia/Seoul',
    z: 'KST',
    Z: '+09:00',
  },
  {
    name: 'Asia/Shanghai',
    z: 'CST',
    Z: '+08:00',
  },
  {
    name: 'Asia/Singapore',
    z: '+08',
    Z: '+08:00',
  },
  {
    name: 'Asia/Srednekolymsk',
    z: '+11',
    Z: '+11:00',
  },
  {
    name: 'Asia/Taipei',
    z: 'CST',
    Z: '+08:00',
  },
  {
    name: 'Asia/Tashkent',
    z: '+05',
    Z: '+05:00',
  },
  {
    name: 'Asia/Tbilisi',
    z: '+04',
    Z: '+04:00',
  },
  {
    name: 'Asia/Tehran',
    z: '+0330',
    Z: '+03:30',
  },
  {
    name: 'Asia/Tel_Aviv',
    z: 'IDT',
    Z: '+03:00',
  },
  {
    name: 'Asia/Thimbu',
    z: '+06',
    Z: '+06:00',
  },
  {
    name: 'Asia/Thimphu',
    z: '+06',
    Z: '+06:00',
  },
  {
    name: 'Asia/Tokyo',
    z: 'JST',
    Z: '+09:00',
  },
  {
    name: 'Asia/Tomsk',
    z: '+07',
    Z: '+07:00',
  },
  {
    name: 'Asia/Ujung_Pandang',
    z: 'WITA',
    Z: '+08:00',
  },
  {
    name: 'Asia/Ulaanbaatar',
    z: '+08',
    Z: '+08:00',
  },
  {
    name: 'Asia/Ulan_Bator',
    z: '+08',
    Z: '+08:00',
  },
  {
    name: 'Asia/Urumqi',
    z: '+06',
    Z: '+06:00',
  },
  {
    name: 'Asia/Ust-Nera',
    z: '+10',
    Z: '+10:00',
  },
  {
    name: 'Asia/Vientiane',
    z: '+07',
    Z: '+07:00',
  },
  {
    name: 'Asia/Vladivostok',
    z: '+10',
    Z: '+10:00',
  },
  {
    name: 'Asia/Yakutsk',
    z: '+09',
    Z: '+09:00',
  },
  {
    name: 'Asia/Yangon',
    z: '+0630',
    Z: '+06:30',
  },
  {
    name: 'Asia/Yekaterinburg',
    z: '+05',
    Z: '+05:00',
  },
  {
    name: 'Asia/Yerevan',
    z: '+04',
    Z: '+04:00',
  },
  {
    name: 'Atlantic/Azores',
    z: '+00',
    Z: '+00:00',
  },
  {
    name: 'Atlantic/Bermuda',
    z: 'ADT',
    Z: '-03:00',
  },
  {
    name: 'Atlantic/Canary',
    z: 'WEST',
    Z: '+01:00',
  },
  {
    name: 'Atlantic/Cape_Verde',
    z: '-01',
    Z: '-01:00',
  },
  {
    name: 'Atlantic/Faeroe',
    z: 'WEST',
    Z: '+01:00',
  },
  {
    name: 'Atlantic/Faroe',
    z: 'WEST',
    Z: '+01:00',
  },
  {
    name: 'Atlantic/Jan_Mayen',
    z: 'CEST',
    Z: '+02:00',
  },
  {
    name: 'Atlantic/Madeira',
    z: 'WEST',
    Z: '+01:00',
  },
  {
    name: 'Atlantic/Reykjavik',
    z: 'GMT',
    Z: '+00:00',
  },
  {
    name: 'Atlantic/South_Georgia',
    z: '-02',
    Z: '-02:00',
  },
  {
    name: 'Atlantic/St_Helena',
    z: 'GMT',
    Z: '+00:00',
  },
  {
    name: 'Atlantic/Stanley',
    z: '-03',
    Z: '-03:00',
  },
  {
    name: 'Australia/ACT',
    z: 'AEDT',
    Z: '+11:00',
  },
  {
    name: 'Australia/Adelaide',
    z: 'ACDT',
    Z: '+10:30',
  },
  {
    name: 'Australia/Brisbane',
    z: 'AEST',
    Z: '+10:00',
  },
  {
    name: 'Australia/Broken_Hill',
    z: 'ACDT',
    Z: '+10:30',
  },
  {
    name: 'Australia/Canberra',
    z: 'AEDT',
    Z: '+11:00',
  },
  {
    name: 'Australia/Currie',
    z: 'AEDT',
    Z: '+11:00',
  },
  {
    name: 'Australia/Darwin',
    z: 'ACST',
    Z: '+09:30',
  },
  {
    name: 'Australia/Eucla',
    z: '+0845',
    Z: '+08:45',
  },
  {
    name: 'Australia/Hobart',
    z: 'AEDT',
    Z: '+11:00',
  },
  {
    name: 'Australia/LHI',
    z: '+11',
    Z: '+11:00',
  },
  {
    name: 'Australia/Lindeman',
    z: 'AEST',
    Z: '+10:00',
  },
  {
    name: 'Australia/Lord_Howe',
    z: '+11',
    Z: '+11:00',
  },
  {
    name: 'Australia/Melbourne',
    z: 'AEDT',
    Z: '+11:00',
  },
  {
    name: 'Australia/NSW',
    z: 'AEDT',
    Z: '+11:00',
  },
  {
    name: 'Australia/North',
    z: 'ACST',
    Z: '+09:30',
  },
  {
    name: 'Australia/Perth',
    z: 'AWST',
    Z: '+08:00',
  },
  {
    name: 'Australia/Queensland',
    z: 'AEST',
    Z: '+10:00',
  },
  {
    name: 'Australia/South',
    z: 'ACDT',
    Z: '+10:30',
  },
  {
    name: 'Australia/Sydney',
    z: 'AEDT',
    Z: '+11:00',
  },
  {
    name: 'Australia/Tasmania',
    z: 'AEDT',
    Z: '+11:00',
  },
  {
    name: 'Australia/Victoria',
    z: 'AEDT',
    Z: '+11:00',
  },
  {
    name: 'Australia/West',
    z: 'AWST',
    Z: '+08:00',
  },
  {
    name: 'Australia/Yancowinna',
    z: 'ACDT',
    Z: '+10:30',
  },
  {
    name: 'Brazil/Acre',
    z: '-05',
    Z: '-05:00',
  },
  {
    name: 'Brazil/DeNoronha',
    z: '-02',
    Z: '-02:00',
  },
  {
    name: 'Brazil/East',
    z: '-03',
    Z: '-03:00',
  },
  {
    name: 'Brazil/West',
    z: '-04',
    Z: '-04:00',
  },
  {
    name: 'CET',
    z: 'CEST',
    Z: '+02:00',
  },
  {
    name: 'CST6CDT',
    z: 'CDT',
    Z: '-05:00',
  },
  {
    name: 'Canada/Atlantic',
    z: 'ADT',
    Z: '-03:00',
  },
  {
    name: 'Canada/Central',
    z: 'CDT',
    Z: '-05:00',
  },
  {
    name: 'Canada/Eastern',
    z: 'EDT',
    Z: '-04:00',
  },
  {
    name: 'Canada/Mountain',
    z: 'MDT',
    Z: '-06:00',
  },
  {
    name: 'Canada/Newfoundland',
    z: 'NDT',
    Z: '-02:30',
  },
  {
    name: 'Canada/Pacific',
    z: 'PDT',
    Z: '-07:00',
  },
  {
    name: 'Canada/Saskatchewan',
    z: 'CST',
    Z: '-06:00',
  },
  {
    name: 'Canada/Yukon',
    z: 'MST',
    Z: '-07:00',
  },
  {
    name: 'Chile/Continental',
    z: '-03',
    Z: '-03:00',
  },
  {
    name: 'Chile/EasterIsland',
    z: '-05',
    Z: '-05:00',
  },
  {
    name: 'Cuba',
    z: 'CDT',
    Z: '-04:00',
  },
  {
    name: 'EET',
    z: 'EEST',
    Z: '+03:00',
  },
  {
    name: 'EST',
    z: 'EST',
    Z: '-05:00',
  },
  {
    name: 'EST5EDT',
    z: 'EDT',
    Z: '-04:00',
  },
  {
    name: 'Egypt',
    z: 'EEST',
    Z: '+03:00',
  },
  {
    name: 'Eire',
    z: 'IST',
    Z: '+01:00',
  },
  {
    name: 'Etc/GMT',
    z: 'GMT',
    Z: '+00:00',
  },
  {
    name: 'Etc/GMT+0',
    z: 'GMT',
    Z: '+00:00',
  },
  {
    name: 'Etc/GMT+1',
    z: '-01',
    Z: '-01:00',
  },
  {
    name: 'Etc/GMT+10',
    z: '-10',
    Z: '-10:00',
  },
  {
    name: 'Etc/GMT+11',
    z: '-11',
    Z: '-11:00',
  },
  {
    name: 'Etc/GMT+12',
    z: '-12',
    Z: '-12:00',
  },
  {
    name: 'Etc/GMT+2',
    z: '-02',
    Z: '-02:00',
  },
  {
    name: 'Etc/GMT+3',
    z: '-03',
    Z: '-03:00',
  },
  {
    name: 'Etc/GMT+4',
    z: '-04',
    Z: '-04:00',
  },
  {
    name: 'Etc/GMT+5',
    z: '-05',
    Z: '-05:00',
  },
  {
    name: 'Etc/GMT+6',
    z: '-06',
    Z: '-06:00',
  },
  {
    name: 'Etc/GMT+7',
    z: '-07',
    Z: '-07:00',
  },
  {
    name: 'Etc/GMT+8',
    z: '-08',
    Z: '-08:00',
  },
  {
    name: 'Etc/GMT+9',
    z: '-09',
    Z: '-09:00',
  },
  {
    name: 'Etc/GMT-0',
    z: 'GMT',
    Z: '+00:00',
  },
  {
    name: 'Etc/GMT-1',
    z: '+01',
    Z: '+01:00',
  },
  {
    name: 'Etc/GMT-10',
    z: '+10',
    Z: '+10:00',
  },
  {
    name: 'Etc/GMT-11',
    z: '+11',
    Z: '+11:00',
  },
  {
    name: 'Etc/GMT-12',
    z: '+12',
    Z: '+12:00',
  },
  {
    name: 'Etc/GMT-13',
    z: '+13',
    Z: '+13:00',
  },
  {
    name: 'Etc/GMT-14',
    z: '+14',
    Z: '+14:00',
  },
  {
    name: 'Etc/GMT-2',
    z: '+02',
    Z: '+02:00',
  },
  {
    name: 'Etc/GMT-3',
    z: '+03',
    Z: '+03:00',
  },
  {
    name: 'Etc/GMT-4',
    z: '+04',
    Z: '+04:00',
  },
  {
    name: 'Etc/GMT-5',
    z: '+05',
    Z: '+05:00',
  },
  {
    name: 'Etc/GMT-6',
    z: '+06',
    Z: '+06:00',
  },
  {
    name: 'Etc/GMT-7',
    z: '+07',
    Z: '+07:00',
  },
  {
    name: 'Etc/GMT-8',
    z: '+08',
    Z: '+08:00',
  },
  {
    name: 'Etc/GMT-9',
    z: '+09',
    Z: '+09:00',
  },
  {
    name: 'Etc/GMT0',
    z: 'GMT',
    Z: '+00:00',
  },
  {
    name: 'Etc/Greenwich',
    z: 'GMT',
    Z: '+00:00',
  },
  {
    name: 'Etc/UCT',
    z: 'UTC',
    Z: '+00:00',
  },
  {
    name: 'Etc/UTC',
    z: 'UTC',
    Z: '+00:00',
  },
  {
    name: 'Etc/Universal',
    z: 'UTC',
    Z: '+00:00',
  },
  {
    name: 'Etc/Zulu',
    z: 'UTC',
    Z: '+00:00',
  },
  {
    name: 'Europe/Amsterdam',
    z: 'CEST',
    Z: '+02:00',
  },
  {
    name: 'Europe/Andorra',
    z: 'CEST',
    Z: '+02:00',
  },
  {
    name: 'Europe/Astrakhan',
    z: '+04',
    Z: '+04:00',
  },
  {
    name: 'Europe/Athens',
    z: 'EEST',
    Z: '+03:00',
  },
  {
    name: 'Europe/Belfast',
    z: 'BST',
    Z: '+01:00',
  },
  {
    name: 'Europe/Belgrade',
    z: 'CEST',
    Z: '+02:00',
  },
  {
    name: 'Europe/Berlin',
    z: 'CEST',
    Z: '+02:00',
  },
  {
    name: 'Europe/Bratislava',
    z: 'CEST',
    Z: '+02:00',
  },
  {
    name: 'Europe/Brussels',
    z: 'CEST',
    Z: '+02:00',
  },
  {
    name: 'Europe/Bucharest',
    z: 'EEST',
    Z: '+03:00',
  },
  {
    name: 'Europe/Budapest',
    z: 'CEST',
    Z: '+02:00',
  },
  {
    name: 'Europe/Busingen',
    z: 'CEST',
    Z: '+02:00',
  },
  {
    name: 'Europe/Chisinau',
    z: 'EEST',
    Z: '+03:00',
  },
  {
    name: 'Europe/Copenhagen',
    z: 'CEST',
    Z: '+02:00',
  },
  {
    name: 'Europe/Dublin',
    z: 'IST',
    Z: '+01:00',
  },
  {
    name: 'Europe/Gibraltar',
    z: 'CEST',
    Z: '+02:00',
  },
  {
    name: 'Europe/Guernsey',
    z: 'BST',
    Z: '+01:00',
  },
  {
    name: 'Europe/Helsinki',
    z: 'EEST',
    Z: '+03:00',
  },
  {
    name: 'Europe/Isle_of_Man',
    z: 'BST',
    Z: '+01:00',
  },
  {
    name: 'Europe/Istanbul',
    z: '+03',
    Z: '+03:00',
  },
  {
    name: 'Europe/Jersey',
    z: 'BST',
    Z: '+01:00',
  },
  {
    name: 'Europe/Kaliningrad',
    z: 'EET',
    Z: '+02:00',
  },
  {
    name: 'Europe/Kiev',
    z: 'EEST',
    Z: '+03:00',
  },
  {
    name: 'Europe/Kirov',
    z: 'MSK',
    Z: '+03:00',
  },
  {
    name: 'Europe/Kyiv',
    z: 'EEST',
    Z: '+03:00',
  },
  {
    name: 'Europe/Lisbon',
    z: 'WEST',
    Z: '+01:00',
  },
  {
    name: 'Europe/Ljubljana',
    z: 'CEST',
    Z: '+02:00',
  },
  {
    name: 'Europe/London',
    z: 'BST',
    Z: '+01:00',
  },
  {
    name: 'Europe/Luxembourg',
    z: 'CEST',
    Z: '+02:00',
  },
  {
    name: 'Europe/Madrid',
    z: 'CEST',
    Z: '+02:00',
  },
  {
    name: 'Europe/Malta',
    z: 'CEST',
    Z: '+02:00',
  },
  {
    name: 'Europe/Mariehamn',
    z: 'EEST',
    Z: '+03:00',
  },
  {
    name: 'Europe/Minsk',
    z: '+03',
    Z: '+03:00',
  },
  {
    name: 'Europe/Monaco',
    z: 'CEST',
    Z: '+02:00',
  },
  {
    name: 'Europe/Moscow',
    z: 'MSK',
    Z: '+03:00',
  },
  {
    name: 'Europe/Nicosia',
    z: 'EEST',
    Z: '+03:00',
  },
  {
    name: 'Europe/Oslo',
    z: 'CEST',
    Z: '+02:00',
  },
  {
    name: 'Europe/Paris',
    z: 'CEST',
    Z: '+02:00',
  },
  {
    name: 'Europe/Podgorica',
    z: 'CEST',
    Z: '+02:00',
  },
  {
    name: 'Europe/Prague',
    z: 'CEST',
    Z: '+02:00',
  },
  {
    name: 'Europe/Riga',
    z: 'EEST',
    Z: '+03:00',
  },
  {
    name: 'Europe/Rome',
    z: 'CEST',
    Z: '+02:00',
  },
  {
    name: 'Europe/Samara',
    z: '+04',
    Z: '+04:00',
  },
  {
    name: 'Europe/San_Marino',
    z: 'CEST',
    Z: '+02:00',
  },
  {
    name: 'Europe/Sarajevo',
    z: 'CEST',
    Z: '+02:00',
  },
  {
    name: 'Europe/Saratov',
    z: '+04',
    Z: '+04:00',
  },
  {
    name: 'Europe/Simferopol',
    z: 'MSK',
    Z: '+03:00',
  },
  {
    name: 'Europe/Skopje',
    z: 'CEST',
    Z: '+02:00',
  },
  {
    name: 'Europe/Sofia',
    z: 'EEST',
    Z: '+03:00',
  },
  {
    name: 'Europe/Stockholm',
    z: 'CEST',
    Z: '+02:00',
  },
  {
    name: 'Europe/Tallinn',
    z: 'EEST',
    Z: '+03:00',
  },
  {
    name: 'Europe/Tirane',
    z: 'CEST',
    Z: '+02:00',
  },
  {
    name: 'Europe/Tiraspol',
    z: 'EEST',
    Z: '+03:00',
  },
  {
    name: 'Europe/Ulyanovsk',
    z: '+04',
    Z: '+04:00',
  },
  {
    name: 'Europe/Uzhgorod',
    z: 'EEST',
    Z: '+03:00',
  },
  {
    name: 'Europe/Vaduz',
    z: 'CEST',
    Z: '+02:00',
  },
  {
    name: 'Europe/Vatican',
    z: 'CEST',
    Z: '+02:00',
  },
  {
    name: 'Europe/Vienna',
    z: 'CEST',
    Z: '+02:00',
  },
  {
    name: 'Europe/Vilnius',
    z: 'EEST',
    Z: '+03:00',
  },
  {
    name: 'Europe/Volgograd',
    z: 'MSK',
    Z: '+03:00',
  },
  {
    name: 'Europe/Warsaw',
    z: 'CEST',
    Z: '+02:00',
  },
  {
    name: 'Europe/Zagreb',
    z: 'CEST',
    Z: '+02:00',
  },
  {
    name: 'Europe/Zaporozhye',
    z: 'EEST',
    Z: '+03:00',
  },
  {
    name: 'Europe/Zurich',
    z: 'CEST',
    Z: '+02:00',
  },
  {
    name: 'GB',
    z: 'BST',
    Z: '+01:00',
  },
  {
    name: 'GB-Eire',
    z: 'BST',
    Z: '+01:00',
  },
  {
    name: 'GMT',
    z: 'GMT',
    Z: '+00:00',
  },
  {
    name: 'GMT+0',
    z: 'GMT',
    Z: '+00:00',
  },
  {
    name: 'GMT-0',
    z: 'GMT',
    Z: '+00:00',
  },
  {
    name: 'GMT0',
    z: 'GMT',
    Z: '+00:00',
  },
  {
    name: 'Greenwich',
    z: 'GMT',
    Z: '+00:00',
  },
  {
    name: 'HST',
    z: 'HST',
    Z: '-10:00',
  },
  {
    name: 'Hongkong',
    z: 'HKT',
    Z: '+08:00',
  },
  {
    name: 'Iceland',
    z: 'GMT',
    Z: '+00:00',
  },
  {
    name: 'Indian/Antananarivo',
    z: 'EAT',
    Z: '+03:00',
  },
  {
    name: 'Indian/Chagos',
    z: '+06',
    Z: '+06:00',
  },
  {
    name: 'Indian/Christmas',
    z: '+07',
    Z: '+07:00',
  },
  {
    name: 'Indian/Cocos',
    z: '+0630',
    Z: '+06:30',
  },
  {
    name: 'Indian/Comoro',
    z: 'EAT',
    Z: '+03:00',
  },
  {
    name: 'Indian/Kerguelen',
    z: '+05',
    Z: '+05:00',
  },
  {
    name: 'Indian/Mahe',
    z: '+04',
    Z: '+04:00',
  },
  {
    name: 'Indian/Maldives',
    z: '+05',
    Z: '+05:00',
  },
  {
    name: 'Indian/Mauritius',
    z: '+04',
    Z: '+04:00',
  },
  {
    name: 'Indian/Mayotte',
    z: 'EAT',
    Z: '+03:00',
  },
  {
    name: 'Indian/Reunion',
    z: '+04',
    Z: '+04:00',
  },
  {
    name: 'Iran',
    z: '+0330',
    Z: '+03:30',
  },
  {
    name: 'Israel',
    z: 'IDT',
    Z: '+03:00',
  },
  {
    name: 'Jamaica',
    z: 'EST',
    Z: '-05:00',
  },
  {
    name: 'Japan',
    z: 'JST',
    Z: '+09:00',
  },
  {
    name: 'Kwajalein',
    z: '+12',
    Z: '+12:00',
  },
  {
    name: 'Libya',
    z: 'EET',
    Z: '+02:00',
  },
  {
    name: 'MET',
    z: 'MEST',
    Z: '+02:00',
  },
  {
    name: 'MST',
    z: 'MST',
    Z: '-07:00',
  },
  {
    name: 'MST7MDT',
    z: 'MDT',
    Z: '-06:00',
  },
  {
    name: 'Mexico/BajaNorte',
    z: 'PDT',
    Z: '-07:00',
  },
  {
    name: 'Mexico/BajaSur',
    z: 'MST',
    Z: '-07:00',
  },
  {
    name: 'Mexico/General',
    z: 'CST',
    Z: '-06:00',
  },
  {
    name: 'NZ',
    z: 'NZDT',
    Z: '+13:00',
  },
  {
    name: 'NZ-CHAT',
    z: '+1345',
    Z: '+13:45',
  },
  {
    name: 'Navajo',
    z: 'MDT',
    Z: '-06:00',
  },
  {
    name: 'PRC',
    z: 'CST',
    Z: '+08:00',
  },
  {
    name: 'PST8PDT',
    z: 'PDT',
    Z: '-07:00',
  },
  {
    name: 'Pacific/Apia',
    z: '+13',
    Z: '+13:00',
  },
  {
    name: 'Pacific/Auckland',
    z: 'NZDT',
    Z: '+13:00',
  },
  {
    name: 'Pacific/Bougainville',
    z: '+11',
    Z: '+11:00',
  },
  {
    name: 'Pacific/Chatham',
    z: '+1345',
    Z: '+13:45',
  },
  {
    name: 'Pacific/Chuuk',
    z: '+10',
    Z: '+10:00',
  },
  {
    name: 'Pacific/Easter',
    z: '-05',
    Z: '-05:00',
  },
  {
    name: 'Pacific/Efate',
    z: '+11',
    Z: '+11:00',
  },
  {
    name: 'Pacific/Enderbury',
    z: '+13',
    Z: '+13:00',
  },
  {
    name: 'Pacific/Fakaofo',
    z: '+13',
    Z: '+13:00',
  },
  {
    name: 'Pacific/Fiji',
    z: '+12',
    Z: '+12:00',
  },
  {
    name: 'Pacific/Funafuti',
    z: '+12',
    Z: '+12:00',
  },
  {
    name: 'Pacific/Galapagos',
    z: '-06',
    Z: '-06:00',
  },
  {
    name: 'Pacific/Gambier',
    z: '-09',
    Z: '-09:00',
  },
  {
    name: 'Pacific/Guadalcanal',
    z: '+11',
    Z: '+11:00',
  },
  {
    name: 'Pacific/Guam',
    z: 'ChST',
    Z: '+10:00',
  },
  {
    name: 'Pacific/Honolulu',
    z: 'HST',
    Z: '-10:00',
  },
  {
    name: 'Pacific/Johnston',
    z: 'HST',
    Z: '-10:00',
  },
  {
    name: 'Pacific/Kanton',
    z: '+13',
    Z: '+13:00',
  },
  {
    name: 'Pacific/Kiritimati',
    z: '+14',
    Z: '+14:00',
  },
  {
    name: 'Pacific/Kosrae',
    z: '+11',
    Z: '+11:00',
  },
  {
    name: 'Pacific/Kwajalein',
    z: '+12',
    Z: '+12:00',
  },
  {
    name: 'Pacific/Majuro',
    z: '+12',
    Z: '+12:00',
  },
  {
    name: 'Pacific/Marquesas',
    z: '-0930',
    Z: '-09:30',
  },
  {
    name: 'Pacific/Midway',
    z: 'SST',
    Z: '-11:00',
  },
  {
    name: 'Pacific/Nauru',
    z: '+12',
    Z: '+12:00',
  },
  {
    name: 'Pacific/Niue',
    z: '-11',
    Z: '-11:00',
  },
  {
    name: 'Pacific/Norfolk',
    z: '+12',
    Z: '+12:00',
  },
  {
    name: 'Pacific/Noumea',
    z: '+11',
    Z: '+11:00',
  },
  {
    name: 'Pacific/Pago_Pago',
    z: 'SST',
    Z: '-11:00',
  },
  {
    name: 'Pacific/Palau',
    z: '+09',
    Z: '+09:00',
  },
  {
    name: 'Pacific/Pitcairn',
    z: '-08',
    Z: '-08:00',
  },
  {
    name: 'Pacific/Pohnpei',
    z: '+11',
    Z: '+11:00',
  },
  {
    name: 'Pacific/Ponape',
    z: '+11',
    Z: '+11:00',
  },
  {
    name: 'Pacific/Port_Moresby',
    z: '+10',
    Z: '+10:00',
  },
  {
    name: 'Pacific/Rarotonga',
    z: '-10',
    Z: '-10:00',
  },
  {
    name: 'Pacific/Saipan',
    z: 'ChST',
    Z: '+10:00',
  },
  {
    name: 'Pacific/Samoa',
    z: 'SST',
    Z: '-11:00',
  },
  {
    name: 'Pacific/Tahiti',
    z: '-10',
    Z: '-10:00',
  },
  {
    name: 'Pacific/Tarawa',
    z: '+12',
    Z: '+12:00',
  },
  {
    name: 'Pacific/Tongatapu',
    z: '+13',
    Z: '+13:00',
  },
  {
    name: 'Pacific/Truk',
    z: '+10',
    Z: '+10:00',
  },
  {
    name: 'Pacific/Wake',
    z: '+12',
    Z: '+12:00',
  },
  {
    name: 'Pacific/Wallis',
    z: '+12',
    Z: '+12:00',
  },
  {
    name: 'Pacific/Yap',
    z: '+10',
    Z: '+10:00',
  },
  {
    name: 'Poland',
    z: 'CEST',
    Z: '+02:00',
  },
  {
    name: 'Portugal',
    z: 'WEST',
    Z: '+01:00',
  },
  {
    name: 'ROC',
    z: 'CST',
    Z: '+08:00',
  },
  {
    name: 'ROK',
    z: 'KST',
    Z: '+09:00',
  },
  {
    name: 'Singapore',
    z: '+08',
    Z: '+08:00',
  },
  {
    name: 'Turkey',
    z: '+03',
    Z: '+03:00',
  },
  {
    name: 'UCT',
    z: 'UTC',
    Z: '+00:00',
  },
  {
    name: 'US/Alaska',
    z: 'AKDT',
    Z: '-08:00',
  },
  {
    name: 'US/Aleutian',
    z: 'HDT',
    Z: '-09:00',
  },
  {
    name: 'US/Arizona',
    z: 'MST',
    Z: '-07:00',
  },
  {
    name: 'US/Central',
    z: 'CDT',
    Z: '-05:00',
  },
  {
    name: 'US/East-Indiana',
    z: 'EDT',
    Z: '-04:00',
  },
  {
    name: 'US/Eastern',
    z: 'EDT',
    Z: '-04:00',
  },
  {
    name: 'US/Hawaii',
    z: 'HST',
    Z: '-10:00',
  },
  {
    name: 'US/Indiana-Starke',
    z: 'CDT',
    Z: '-05:00',
  },
  {
    name: 'US/Michigan',
    z: 'EDT',
    Z: '-04:00',
  },
  {
    name: 'US/Mountain',
    z: 'MDT',
    Z: '-06:00',
  },
  {
    name: 'US/Pacific',
    z: 'PDT',
    Z: '-07:00',
  },
  {
    name: 'US/Samoa',
    z: 'SST',
    Z: '-11:00',
  },
  {
    name: 'UTC',
    z: 'UTC',
    Z: '+00:00',
  },
  {
    name: 'Universal',
    z: 'UTC',
    Z: '+00:00',
  },
  {
    name: 'W-SU',
    z: 'MSK',
    Z: '+03:00',
  },
  {
    name: 'WET',
    z: 'WEST',
    Z: '+01:00',
  },
  {
    name: 'Zulu',
    z: 'UTC',
    Z: '+00:00',
  },
];
