import * as SceneViewApi from 'monitor-api/modules/scene_view';

interface ICustomTsMetricGroups {
  common_dimensions: {
    alias: string;
    name: string;
  }[];
  metric_groups: {
    metrics: {
      alias: string;
      dimensions: {
        alias: string;
        name: string;
      }[];
      metric_name: string;
    }[];
    name: string;
  }[];
}

interface ICustomTsGraphConfig {
  groups: {
    name: string;
    panels: {
      sub_title: string;
      title: string;
      targets: {
        alias: string;
        expression: string;
        function: Record<string, any>;
        metric: {
          alias: string;
          name: string;
        };
        query_configs: {
          data_label: string;
          data_source_label: string;
          data_type_label: string;
          filter_dict: {
            common_filter: Record<string, any>;
            group_filter: Record<string, any>;
          };
          functions: {
            id: string;
            params: {
              id: string;
              value: number;
            }[];
          }[];
          group_by: any[];
          interval: string;
          metrics: {
            alias: string;
            field: string;
            method: string;
          }[];
          table: string;
        }[];
        unit: string;
      }[];
    }[];
  }[];
}

export const getCustomTsMetricGroups = SceneViewApi.getCustomTsMetricGroups<
  {
    time_series_group_id: number;
    bk_biz_id?: number;
  },
  ICustomTsMetricGroups
>;

export const getCustomTsDimensionValues = SceneViewApi.getCustomTsDimensionValues<
  {
    bk_biz_id: number;
    dimension: string;
    end_time: number;
    metrics: string[];
    start_time: number;
    time_series_group_id: number;
  },
  {
    alias: string;
    name: string;
  }[]
>;

export const getCustomTsGraphConfig = SceneViewApi.getCustomTsGraphConfig<
  {
    bk_biz_id: number;
    end_time: number;
    limit: {
      function: string;
      limit: number;
    };
    metrics: string[];
    start_time: number;
    time_series_group_id: number;
    view_column?: number;
  },
  ICustomTsGraphConfig
>;

export default {
  getCustomTsMetricGroups,
  getCustomTsDimensionValues,
  getCustomTsGraphConfig,
};
