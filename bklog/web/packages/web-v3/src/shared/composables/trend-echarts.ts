/* Copyright (C) 2021 THL A29 Limited, a Tencent company, MIT License. */
import { use, init } from 'echarts/core';
import { BarChart, LineChart } from 'echarts/charts';
import {
  GridComponent,
  TitleComponent,
  TooltipComponent,
  LegendScrollComponent,
  ToolboxComponent,
  DataZoomComponent,
  MarkLineComponent,
  MarkAreaComponent,
} from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';

// Trend charts retain scroll legends, zoom/restore/export and mark overlays.
// Other routes may register additional chart types without making them a
// dependency of the retrieval trend renderer.
use([
  BarChart, LineChart, GridComponent, TitleComponent, TooltipComponent,
  LegendScrollComponent, ToolboxComponent, DataZoomComponent,
  MarkLineComponent, MarkAreaComponent, CanvasRenderer,
]);
export { init };
