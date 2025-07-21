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

import {
  toHex,
  sci,
  toHex0x,
  toPercent,
  toPercentUnit,
} from './arithmetic-formatters';
import {
  dateTimeAsIso,
  dateTimeAsUS,
  dateTimeFromNow,
  toClockMilliseconds,
  toClockSeconds,
  toDays,
  toDurationInHoursMinutesSeconds,
  toDurationInMilliseconds,
  toDurationInSeconds,
  toHours,
  toMicroSeconds,
  toMilliSeconds,
  toMinutes,
  toNanoSeconds,
  toSeconds,
  toTimeTicks,
} from './date-time-formatters';
import { binarySIPrefix, currency, decimalSIPrefix } from './symbol-formatters';
import {
  locale,
  scaledUnits,
  simpleCountUnit,
  toFixedUnit,
  ValueFormatCategory,
} from './value-formats';

export default (): ValueFormatCategory[] => [
  {
    formats: [
      { fn: toFixedUnit(''), id: 'none', name: 'none' },
      {
        fn: scaledUnits(1000, [
          '',
          ' K',
          ' Mil',
          ' Bil',
          ' Tri',
          ' Quadr',
          ' Quint',
          ' Sext',
          ' Sept',
        ]),
        id: 'short',
        name: 'short',
      },
      { fn: toPercent, id: 'percent', name: 'percent (0-100)' },
      { fn: toPercentUnit, id: 'percentunit', name: 'percent (0.0-1.0)' },
      { fn: toFixedUnit('%H'), id: 'humidity', name: 'Humidity (%H)' },
      { fn: toFixedUnit('dB'), id: 'dB', name: 'decibel' },
      { fn: toHex0x, id: 'hex0x', name: 'hexadecimal (0x)' },
      { fn: toHex, id: 'hex', name: 'hexadecimal' },
      { fn: sci, id: 'sci', name: 'scientific notation' },
      { fn: locale, id: 'locale', name: 'locale format' },
      { fn: toFixedUnit('px'), id: 'pixel', name: 'Pixels' },
    ],
    name: 'Misc',
  },
  {
    formats: [
      { fn: toFixedUnit('m/sec²'), id: 'accMS2', name: 'Meters/sec²' },
      { fn: toFixedUnit('f/sec²'), id: 'accFS2', name: 'Feet/sec²' },
      { fn: toFixedUnit('g'), id: 'accG', name: 'G unit' },
    ],
    name: 'Acceleration',
  },
  {
    formats: [
      { fn: toFixedUnit('°'), id: 'degree', name: 'Degrees (°)' },
      { fn: toFixedUnit('rad'), id: 'radian', name: 'Radians' },
      { fn: toFixedUnit('grad'), id: 'grad', name: 'Gradian' },
      { fn: toFixedUnit('arcmin'), id: 'arcmin', name: 'Arc Minutes' },
      { fn: toFixedUnit('arcsec'), id: 'arcsec', name: 'Arc Seconds' },
    ],
    name: 'Angle',
  },
  {
    formats: [
      { fn: toFixedUnit('m²'), id: 'areaM2', name: 'Square Meters (m²)' },
      { fn: toFixedUnit('ft²'), id: 'areaF2', name: 'Square Feet (ft²)' },
      { fn: toFixedUnit('mi²'), id: 'areaMI2', name: 'Square Miles (mi²)' },
    ],
    name: 'Area',
  },
  {
    formats: [
      { fn: decimalSIPrefix('FLOP/s'), id: 'flops', name: 'FLOP/s' },
      { fn: decimalSIPrefix('FLOP/s', 2), id: 'mflops', name: 'MFLOP/s' },
      { fn: decimalSIPrefix('FLOP/s', 3), id: 'gflops', name: 'GFLOP/s' },
      { fn: decimalSIPrefix('FLOP/s', 4), id: 'tflops', name: 'TFLOP/s' },
      { fn: decimalSIPrefix('FLOP/s', 5), id: 'pflops', name: 'PFLOP/s' },
      { fn: decimalSIPrefix('FLOP/s', 6), id: 'eflops', name: 'EFLOP/s' },
      { fn: decimalSIPrefix('FLOP/s', 7), id: 'zflops', name: 'ZFLOP/s' },
      { fn: decimalSIPrefix('FLOP/s', 8), id: 'yflops', name: 'YFLOP/s' },
    ],
    name: 'Computation',
  },
  {
    formats: [
      { fn: toFixedUnit('ppm'), id: 'ppm', name: 'parts-per-million (ppm)' },
      { fn: toFixedUnit('ppb'), id: 'conppb', name: 'parts-per-billion (ppb)' },
      {
        fn: toFixedUnit('ng/m³'),
        id: 'conngm3',
        name: 'nanogram per cubic meter (ng/m³)',
      },
      {
        fn: toFixedUnit('ng/Nm³'),
        id: 'conngNm3',
        name: 'nanogram per normal cubic meter (ng/Nm³)',
      },
      {
        fn: toFixedUnit('μg/m³'),
        id: 'conμgm3',
        name: 'microgram per cubic meter (μg/m³)',
      },
      {
        fn: toFixedUnit('μg/Nm³'),
        id: 'conμgNm3',
        name: 'microgram per normal cubic meter (μg/Nm³)',
      },
      {
        fn: toFixedUnit('mg/m³'),
        id: 'conmgm3',
        name: 'milligram per cubic meter (mg/m³)',
      },
      {
        fn: toFixedUnit('mg/Nm³'),
        id: 'conmgNm3',
        name: 'milligram per normal cubic meter (mg/Nm³)',
      },
      {
        fn: toFixedUnit('g/m³'),
        id: 'congm3',
        name: 'gram per cubic meter (g/m³)',
      },
      {
        fn: toFixedUnit('g/Nm³'),
        id: 'congNm3',
        name: 'gram per normal cubic meter (g/Nm³)',
      },
      {
        fn: toFixedUnit('mg/dL'),
        id: 'conmgdL',
        name: 'milligrams per decilitre (mg/dL)',
      },
      {
        fn: toFixedUnit('mmol/L'),
        id: 'conmmolL',
        name: 'millimoles per litre (mmol/L)',
      },
    ],
    name: 'Concentration',
  },
  {
    formats: [
      { fn: currency('$'), id: 'currencyUSD', name: 'Dollars ($)' },
      { fn: currency('£'), id: 'currencyGBP', name: 'Pounds (£)' },
      { fn: currency('€'), id: 'currencyEUR', name: 'Euro (€)' },
      { fn: currency('¥'), id: 'currencyJPY', name: 'Yen (¥)' },
      { fn: currency('₽'), id: 'currencyRUB', name: 'Rubles (₽)' },
      { fn: currency('₴'), id: 'currencyUAH', name: 'Hryvnias (₴)' },
      { fn: currency('R$'), id: 'currencyBRL', name: 'Real (R$)' },
      {
        fn: currency('kr', true),
        id: 'currencyDKK',
        name: 'Danish Krone (kr)',
      },
      {
        fn: currency('kr', true),
        id: 'currencyISK',
        name: 'Icelandic Króna (kr)',
      },
      {
        fn: currency('kr', true),
        id: 'currencyNOK',
        name: 'Norwegian Krone (kr)',
      },
      {
        fn: currency('kr', true),
        id: 'currencySEK',
        name: 'Swedish Krona (kr)',
      },
      { fn: currency('czk'), id: 'currencyCZK', name: 'Czech koruna (czk)' },
      { fn: currency('CHF'), id: 'currencyCHF', name: 'Swiss franc (CHF)' },
      { fn: currency('PLN'), id: 'currencyPLN', name: 'Polish Złoty (PLN)' },
      { fn: currency('฿'), id: 'currencyBTC', name: 'Bitcoin (฿)' },
      { fn: currency('R'), id: 'currencyZAR', name: 'South African Rand (R)' },
      { fn: currency('₹'), id: 'currencyINR', name: 'Indian Rupee (₹)' },
      { fn: currency('₩'), id: 'currencyKRW', name: 'South Korean Won (₩)' },
    ],
    name: 'Currency',
  },
  {
    formats: [
      { fn: binarySIPrefix('b'), id: 'bits', name: 'bits' },
      { fn: binarySIPrefix('B'), id: 'bytes', name: 'bytes' },
      { fn: binarySIPrefix('B', 1), id: 'kbytes', name: 'kibibytes' },
      { fn: binarySIPrefix('B', 2), id: 'mbytes', name: 'mebibytes' },
      { fn: binarySIPrefix('B', 3), id: 'gbytes', name: 'gibibytes' },
      { fn: binarySIPrefix('B', 4), id: 'tbytes', name: 'tebibytes' },
      { fn: binarySIPrefix('B', 5), id: 'pbytes', name: 'pebibytes' },
    ],
    name: 'Data (IEC)',
  },
  {
    formats: [
      { fn: decimalSIPrefix('b'), id: 'decbits', name: 'bits' },
      { fn: decimalSIPrefix('B'), id: 'decbytes', name: 'bytes' },
      { fn: decimalSIPrefix('B', 1), id: 'deckbytes', name: 'kilobytes' },
      { fn: decimalSIPrefix('B', 2), id: 'decmbytes', name: 'megabytes' },
      { fn: decimalSIPrefix('B', 3), id: 'decgbytes', name: 'gigabytes' },
      { fn: decimalSIPrefix('B', 4), id: 'dectbytes', name: 'terabytes' },
      { fn: decimalSIPrefix('B', 5), id: 'decpbytes', name: 'petabytes' },
    ],
    name: 'Data (Metric)',
  },
  {
    formats: [
      { fn: decimalSIPrefix('pps'), id: 'pps', name: 'packets/sec' },
      { fn: decimalSIPrefix('bps'), id: 'bps', name: 'bits/sec' },
      { fn: decimalSIPrefix('Bs'), id: 'Bps', name: 'bytes/sec' },
      { fn: decimalSIPrefix('Bs', 1), id: 'KBs', name: 'kilobytes/sec' },
      { fn: decimalSIPrefix('bps', 1), id: 'Kbits', name: 'kilobits/sec' },
      { fn: decimalSIPrefix('Bs', 2), id: 'MBs', name: 'megabytes/sec' },
      { fn: decimalSIPrefix('bps', 2), id: 'Mbits', name: 'megabits/sec' },
      { fn: decimalSIPrefix('Bs', 3), id: 'GBs', name: 'gigabytes/sec' },
      { fn: decimalSIPrefix('bps', 3), id: 'Gbits', name: 'gigabits/sec' },
      { fn: decimalSIPrefix('Bs', 4), id: 'TBs', name: 'terabytes/sec' },
      { fn: decimalSIPrefix('bps', 4), id: 'Tbits', name: 'terabits/sec' },
      { fn: decimalSIPrefix('Bs', 5), id: 'PBs', name: 'petabytes/sec' },
      { fn: decimalSIPrefix('bps', 5), id: 'Pbits', name: 'petabits/sec' },
    ],
    name: 'Data Rate',
  },
  {
    formats: [
      { fn: dateTimeAsIso, id: 'dateTimeAsIso', name: 'YYYY-MM-DD HH:mm:ss' },
      { fn: dateTimeAsUS, id: 'dateTimeAsUS', name: 'MM/DD/YYYY h:mm:ss a' },
      { fn: dateTimeFromNow, id: 'dateTimeFromNow', name: 'From Now' },
    ],
    name: 'Date & Time',
  },
  {
    formats: [
      { fn: decimalSIPrefix('W'), id: 'watt', name: 'Watt (W)' },
      { fn: decimalSIPrefix('W', 1), id: 'kwatt', name: 'Kilowatt (kW)' },
      { fn: decimalSIPrefix('W', 2), id: 'megwatt', name: 'Megawatt (MW)' },
      { fn: decimalSIPrefix('W', 3), id: 'gwatt', name: 'Gigawatt (GW)' },
      { fn: decimalSIPrefix('W', -1), id: 'mwatt', name: 'Milliwatt (mW)' },
      {
        fn: toFixedUnit('W/m²'),
        id: 'Wm2',
        name: 'Watt per square meter (W/m²)',
      },
      { fn: decimalSIPrefix('VA'), id: 'voltamp', name: 'Volt-ampere (VA)' },
      {
        fn: decimalSIPrefix('VA', 1),
        id: 'kvoltamp',
        name: 'Kilovolt-ampere (kVA)',
      },
      {
        fn: decimalSIPrefix('var'),
        id: 'voltampreact',
        name: 'Volt-ampere reactive (var)',
      },
      {
        fn: decimalSIPrefix('var', 1),
        id: 'kvoltampreact',
        name: 'Kilovolt-ampere reactive (kvar)',
      },
      { fn: decimalSIPrefix('Wh'), id: 'watth', name: 'Watt-hour (Wh)' },
      {
        fn: decimalSIPrefix('Wh/kg'),
        id: 'watthperkg',
        name: 'Watt-hour per Kilogram (Wh/kg)',
      },
      {
        fn: decimalSIPrefix('Wh', 1),
        id: 'kwatth',
        name: 'Kilowatt-hour (kWh)',
      },
      {
        fn: decimalSIPrefix('W-Min', 1),
        id: 'kwattm',
        name: 'Kilowatt-min (kWm)',
      },
      { fn: decimalSIPrefix('Ah'), id: 'amph', name: 'Ampere-hour (Ah)' },
      {
        fn: decimalSIPrefix('Ah', 1),
        id: 'kamph',
        name: 'Kiloampere-hour (kAh)',
      },
      {
        fn: decimalSIPrefix('Ah', -1),
        id: 'mamph',
        name: 'Milliampere-hour (mAh)',
      },
      { fn: decimalSIPrefix('J'), id: 'joule', name: 'Joule (J)' },
      { fn: decimalSIPrefix('eV'), id: 'ev', name: 'Electron volt (eV)' },
      { fn: decimalSIPrefix('A'), id: 'amp', name: 'Ampere (A)' },
      { fn: decimalSIPrefix('A', 1), id: 'kamp', name: 'Kiloampere (kA)' },
      { fn: decimalSIPrefix('A', -1), id: 'mamp', name: 'Milliampere (mA)' },
      { fn: decimalSIPrefix('V'), id: 'volt', name: 'Volt (V)' },
      { fn: decimalSIPrefix('V', 1), id: 'kvolt', name: 'Kilovolt (kV)' },
      { fn: decimalSIPrefix('V', -1), id: 'mvolt', name: 'Millivolt (mV)' },
      {
        fn: decimalSIPrefix('dBm'),
        id: 'dBm',
        name: 'Decibel-milliwatt (dBm)',
      },
      { fn: decimalSIPrefix('Ω'), id: 'ohm', name: 'Ohm (Ω)' },
      { fn: decimalSIPrefix('Ω', 1), id: 'kohm', name: 'Kiloohm (kΩ)' },
      { fn: decimalSIPrefix('Ω', 2), id: 'Mohm', name: 'Megaohm (MΩ)' },
      { fn: decimalSIPrefix('F'), id: 'farad', name: 'Farad (F)' },
      { fn: decimalSIPrefix('F', -2), id: 'µfarad', name: 'Microfarad (µF)' },
      { fn: decimalSIPrefix('F', -3), id: 'nfarad', name: 'Nanofarad (nF)' },
      { fn: decimalSIPrefix('F', -4), id: 'pfarad', name: 'Picofarad (pF)' },
      { fn: decimalSIPrefix('F', -5), id: 'ffarad', name: 'Femtofarad (fF)' },
      { fn: decimalSIPrefix('H'), id: 'henry', name: 'Henry (H)' },
      { fn: decimalSIPrefix('H', -1), id: 'mhenry', name: 'Millihenry (mH)' },
      { fn: decimalSIPrefix('H', -2), id: 'µhenry', name: 'Microhenry (µH)' },
      { fn: decimalSIPrefix('Lm'), id: 'lumens', name: 'Lumens (Lm)' },
    ],
    name: 'Energy',
  },
  {
    formats: [
      { fn: toFixedUnit('gpm'), id: 'flowgpm', name: 'Gallons/min (gpm)' },
      { fn: toFixedUnit('cms'), id: 'flowcms', name: 'Cubic meters/sec (cms)' },
      { fn: toFixedUnit('cfs'), id: 'flowcfs', name: 'Cubic feet/sec (cfs)' },
      { fn: toFixedUnit('cfm'), id: 'flowcfm', name: 'Cubic feet/min (cfm)' },
      { fn: toFixedUnit('L/h'), id: 'litreh', name: 'Litre/hour' },
      { fn: toFixedUnit('L/min'), id: 'flowlpm', name: 'Litre/min (L/min)' },
      {
        fn: toFixedUnit('mL/min'),
        id: 'flowmlpm',
        name: 'milliLitre/min (mL/min)',
      },
      { fn: toFixedUnit('lux'), id: 'lux', name: 'Lux (lx)' },
    ],
    name: 'Flow',
  },
  {
    formats: [
      { fn: decimalSIPrefix('Nm'), id: 'forceNm', name: 'Newton-meters (Nm)' },
      {
        fn: decimalSIPrefix('Nm', 1),
        id: 'forcekNm',
        name: 'Kilonewton-meters (kNm)',
      },
      { fn: decimalSIPrefix('N'), id: 'forceN', name: 'Newtons (N)' },
      { fn: decimalSIPrefix('N', 1), id: 'forcekN', name: 'Kilonewtons (kN)' },
    ],
    name: 'Force',
  },
  {
    formats: [
      { fn: decimalSIPrefix('H/s'), id: 'Hs', name: 'hashes/sec' },
      { fn: decimalSIPrefix('H/s', 1), id: 'KHs', name: 'kilohashes/sec' },
      { fn: decimalSIPrefix('H/s', 2), id: 'MHs', name: 'megahashes/sec' },
      { fn: decimalSIPrefix('H/s', 3), id: 'GHs', name: 'gigahashes/sec' },
      { fn: decimalSIPrefix('H/s', 4), id: 'THs', name: 'terahashes/sec' },
      { fn: decimalSIPrefix('H/s', 5), id: 'PHs', name: 'petahashes/sec' },
      { fn: decimalSIPrefix('H/s', 6), id: 'EHs', name: 'exahashes/sec' },
    ],
    name: 'Hash Rate',
  },
  {
    formats: [
      { fn: decimalSIPrefix('g', -1), id: 'massmg', name: 'milligram (mg)' },
      { fn: decimalSIPrefix('g'), id: 'massg', name: 'gram (g)' },
      { fn: decimalSIPrefix('g', 1), id: 'masskg', name: 'kilogram (kg)' },
      { fn: toFixedUnit('t'), id: 'masst', name: 'metric ton (t)' },
    ],
    name: 'Mass',
  },
  {
    formats: [
      { fn: decimalSIPrefix('m', -1), id: 'lengthmm', name: 'millimeter (mm)' },
      { fn: toFixedUnit('ft'), id: 'lengthft', name: 'feet (ft)' },
      { fn: decimalSIPrefix('m'), id: 'lengthm', name: 'meter (m)' },
      { fn: decimalSIPrefix('m', 1), id: 'lengthkm', name: 'kilometer (km)' },
      { fn: toFixedUnit('mi'), id: 'lengthmi', name: 'mile (mi)' },
    ],
    name: 'length',
  },
  {
    formats: [
      { fn: decimalSIPrefix('bar', -1), id: 'pressurembar', name: 'Millibars' },
      { fn: decimalSIPrefix('bar'), id: 'pressurebar', name: 'Bars' },
      { fn: decimalSIPrefix('bar', 1), id: 'pressurekbar', name: 'Kilobars' },
      { fn: toFixedUnit('hPa'), id: 'pressurehpa', name: 'Hectopascals' },
      { fn: toFixedUnit('kPa'), id: 'pressurekpa', name: 'Kilopascals' },
      { fn: toFixedUnit('"Hg'), id: 'pressurehg', name: 'Inches of mercury' },
      {
        fn: scaledUnits(1000, ['psi', 'ksi', 'Mpsi']),
        id: 'pressurepsi',
        name: 'PSI',
      },
    ],
    name: 'Pressure',
  },
  {
    formats: [
      { fn: decimalSIPrefix('Bq'), id: 'radbq', name: 'Becquerel (Bq)' },
      { fn: decimalSIPrefix('Ci'), id: 'radci', name: 'curie (Ci)' },
      { fn: decimalSIPrefix('Gy'), id: 'radgy', name: 'Gray (Gy)' },
      { fn: decimalSIPrefix('rad'), id: 'radrad', name: 'rad' },
      { fn: decimalSIPrefix('Sv'), id: 'radsv', name: 'Sievert (Sv)' },
      {
        fn: decimalSIPrefix('mSv', -1),
        id: 'radmsv',
        name: 'milliSievert (mSv)',
      },
      {
        fn: decimalSIPrefix('µSv', -2),
        id: 'radusv',
        name: 'microSievert (µSv)',
      },
      { fn: decimalSIPrefix('rem'), id: 'radrem', name: 'rem' },
      { fn: decimalSIPrefix('C/kg'), id: 'radexpckg', name: 'Exposure (C/kg)' },
      { fn: decimalSIPrefix('R'), id: 'radr', name: 'roentgen (R)' },
      {
        fn: decimalSIPrefix('Sv/h'),
        id: 'radsvh',
        name: 'Sievert/hour (Sv/h)',
      },
      {
        fn: decimalSIPrefix('Sv/h', -1),
        id: 'radmsvh',
        name: 'milliSievert/hour (mSv/h)',
      },
      {
        fn: decimalSIPrefix('Sv/h', -2),
        id: 'radusvh',
        name: 'microSievert/hour (µSv/h)',
      },
    ],
    name: 'Radiation',
  },
  {
    formats: [
      { fn: toFixedUnit('°C'), id: 'celsius', name: 'Celsius (°C)' },
      { fn: toFixedUnit('°F'), id: 'fahrenheit', name: 'Fahrenheit (°F)' },
      { fn: toFixedUnit('K'), id: 'kelvin', name: 'Kelvin (K)' },
    ],
    name: 'Temperature',
  },
  {
    formats: [
      { fn: decimalSIPrefix('Hz'), id: 'hertz', name: 'Hertz (1/s)' },
      { fn: toNanoSeconds, id: 'ns', name: 'nanoseconds (ns)' },
      { fn: toMicroSeconds, id: 'µs', name: 'microseconds (µs)' },
      { fn: toMilliSeconds, id: 'ms', name: 'milliseconds (ms)' },
      { fn: toSeconds, id: 's', name: 'seconds (s)' },
      { fn: toMinutes, id: 'm', name: 'minutes (m)' },
      { fn: toHours, id: 'h', name: 'hours (h)' },
      { fn: toDays, id: 'd', name: 'days (d)' },
      {
        fn: toDurationInMilliseconds,
        id: 'dtdurationms',
        name: 'duration (ms)',
      },
      { fn: toDurationInSeconds, id: 'dtdurations', name: 'duration (s)' },
      {
        fn: toDurationInHoursMinutesSeconds,
        id: 'dthms',
        name: 'duration (hh:mm:ss)',
      },
      { fn: toTimeTicks, id: 'timeticks', name: 'Timeticks (s/100)' },
      { fn: toClockMilliseconds, id: 'clockms', name: 'clock (ms)' },
      { fn: toClockSeconds, id: 'clocks', name: 'clock (s)' },
    ],
    name: 'Time',
  },
  {
    formats: [
      { fn: simpleCountUnit('cps'), id: 'cps', name: 'counts/sec (cps)' },
      { fn: simpleCountUnit('ops'), id: 'ops', name: 'ops/sec (ops)' },
      { fn: simpleCountUnit('reqps'), id: 'reqps', name: 'requests/sec (rps)' },
      { fn: simpleCountUnit('rps'), id: 'rps', name: 'reads/sec (rps)' },
      { fn: simpleCountUnit('wps'), id: 'wps', name: 'writes/sec (wps)' },
      { fn: simpleCountUnit('iops'), id: 'iops', name: 'I/O ops/sec (iops)' },
      { fn: simpleCountUnit('cpm'), id: 'cpm', name: 'counts/min (cpm)' },
      { fn: simpleCountUnit('opm'), id: 'opm', name: 'ops/min (opm)' },
      { fn: simpleCountUnit('rpm'), id: 'rpm', name: 'reads/min (rpm)' },
      { fn: simpleCountUnit('wpm'), id: 'wpm', name: 'writes/min (wpm)' },
    ],
    name: 'Throughput',
  },
  {
    formats: [
      { fn: toFixedUnit('m/s'), id: 'velocityms', name: 'meters/second (m/s)' },
      {
        fn: toFixedUnit('km/h'),
        id: 'velocitykmh',
        name: 'kilometers/hour (km/h)',
      },
      { fn: toFixedUnit('mph'), id: 'velocitymph', name: 'miles/hour (mph)' },
      { fn: toFixedUnit('kn'), id: 'velocityknot', name: 'knot (kn)' },
    ],
    name: 'Velocity',
  },
  {
    formats: [
      { fn: decimalSIPrefix('L', -1), id: 'mlitre', name: 'millilitre (mL)' },
      { fn: decimalSIPrefix('L'), id: 'litre', name: 'litre (L)' },
      { fn: toFixedUnit('m³'), id: 'm3', name: 'cubic meter' },
      { fn: toFixedUnit('Nm³'), id: 'Nm3', name: 'Normal cubic meter' },
      { fn: toFixedUnit('dm³'), id: 'dm3', name: 'cubic decimeter' },
      { fn: toFixedUnit('gal'), id: 'gallons', name: 'gallons' },
    ],
    name: 'Volume',
  },
];
