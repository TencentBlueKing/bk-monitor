import * as StrategiesApi from 'monitor-api/modules/strategies';

/** 单位列表 */
export interface IUnitItem {
  formats: {
    id: string;
    name: string;
    suffix: string;
  }[];
  name: string;
}

/** 获取单位列表 rest/v2/strategies/get_unit_list/ */
export const getUnitList = StrategiesApi.getUnitList<undefined, IUnitItem[]>;
