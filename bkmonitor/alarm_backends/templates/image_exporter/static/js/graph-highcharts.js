//Highcharts主题
Highcharts.theme_default = {
	colors: ["#f6bb42","#4a89dc", "#3bafda", "#fc695e","#967adc","#64c256"],
	chart: {
		//backgroundColor: null,
		style: {
			fontFamily: "SourceHanSerifSC-Regular"
		}
	},
	title :{
		text:""
	},
	credits:{
		enabled:false
	},
	xAxis: {
		gridLineColor: '#ebebeb',
		gridLineWidth: 0,
		tickWidth: 0,
		lineColor: '#ebebeb'
	},
	yAxis: {
		floor: "",
        ceiling: "",
		gridLineColor: '#ebebeb',

	},
	tooltip: {
		borderWidth: 0,
		backgroundColor: 'rgba(0,0,0,0.7)',
		shadow: false,
		style: {
			color: '#ffffff'
		}
        //positioner: function(boxWidth, boxHeight, point) {
        //    return {
        //        x: point.plotX,
        //        y: point.plotY-100
        //    };
        //}
	},
	plotOptions: {
		line: {
			marker: {
				symbol: 'circle',
				radius: 2,
			}
		}
	},
    series:{
        cropThreshold: 1500
    }
};

var Hchart = {
    make_graph: function (chart_data, selector) {
        var options = {};
        if (chart_data.color_list) {
            $.extend(true, options, {
                colors: chart_data.color_list,
            });
        } else {
            if (chart_data.series_name_list.length > 5) {
                $.extend(true, options, {
                    colors: [
                        //'#05420F', '#247101',
                        "#27C24C", '#94BC35', '#F7F30E', '#F9CB06', '#F96060', '#E56B22', '#FE0000', '#C3017C']
                });
            } else {
                $.extend(true, options, {
                    colors: ['#27C24C', '#CAE1FF', '#CDCDB4', '#FE0000', '#C3017C']
                });
            }
            if (chart_data.series_name_list.length <= 2) {
                $.extend(true, options, {
                    colors: ['#94BC35', '#F96060']
                });
            }
        }
        Highcharts.setOptions(options);
        // 处理后台数据并保存
        var series_info = {};
        for (var i = 0; i < chart_data.series.length; i++) {
            series_info[chart_data.series[i].name] = chart_data.series[i];
        }
        //Hchart._default(chart_data, selector, series_info);
        var func = $(this).attr(chart_data.chart_type);
        if (func){
            func(chart_data, selector, series_info);
        }else{
            Hchart._default(chart_data, selector, series_info);
        }

        Hchart.after_graphed(chart_data, selector);
    },

    after_graphed: function(chart_data, selector){
        var chart_obj = $(selector).highcharts();
    },

    // 所有图如果没有配置的话，尝试从这里开始
    _default: function (chart_data, selector, series_info){
        var chart = {
            line : function(selector){
                var defaultOptions = {
                    title:{
                        text:''
                    },
                    chart: {
                        type: chart_data.chart_type
                    },
                    legend:{
                        align: 'right',
                        verticalAlign:'middle',
                        width: 50,
                        itemWidth: 50,
                        y: 0,
                        title: {
                            style: {
                                fontStyle: 'italic'
                            }
                        }
                    },
                    //legend: {

                    //},
                    plotOptions: {
                        line:{
                        },
                        spline: {
                            marker: {
                                threshold: 0,
                                symbol: 'circle',
                                radius: 2,
                                enabled: false
                            }
                        },
                        pie: {
                            center: ['30%', '50%'],
                            allowPointSelect: true,
                            cursor: 'pointer',
                            dataLabels: {
                                enabled: true
                            },
                            showInLegend: false
                        }
                    },
                    xAxis: chart_data.x_axis,
                    yAxis: [{
                                allowDecimals: true,

                            }],
                    tooltip: {
                        xDateFormat: '%Y-%m-%d %H:%M:%S',
                        followPointer: true,
                        followTouchMove: true,
                        crosshairs: true,
                        shared: true,
                        useHTML: true,
                        headerFormat: '<small>{point.key}</small><table>',
                        pointFormat: '<tr><td style="color: {series.color}">{series.name}: </td>' +
                            '<td><b>{point.y}</b></td></tr>',
                        footerFormat: '</table>',
                        valueDecimals: 0
                    },
                    credits:{
                        enabled: true,
                        text: "",
                        href: "###"
                    },
                    series: chart_data.series
                };
                if (chart_data.show_percent){
                    // 百分比展示
                    if (chart_data.chart_type == "pie"){
                        defaultOptions.tooltip.pointFormatter = function(){
                            return this.series.name + ': <b>'+ this.y+'%</b><b>&nbsp;|&nbsp;'+this.count;
                        };
                        defaultOptions.legend.borderWidth = 1;
                        defaultOptions.legend = {
                            borderWidth: 1,
                            align: "right",
                            floating:true,
                            verticalAlign:"right",
                            layout:"vertical",
                            itemMarginTop:10,
                            labelFormatter: function () {
                                return this.name.slice(0, 20) +"  -  " +this.count +'<b> | </b>'+this.y+'%';
                            }
                        }
                    }else{
                        defaultOptions.tooltip.pointFormatter = function(){
                            return '<tr><td style="color: '+this.series.color+'">'+this.series.name+': </td>' +
                                '<td><b>'+this.y+'%</b></td><td><b>&nbsp;('+series_info[this.series.name].count[this.index]+
                                    ')</b></td></tr>';
                        };
                        defaultOptions.tooltip.valueDecimals = 2;
                    }
                }else{
                    if (chart_data.chart_type == "pie"){
                        defaultOptions.tooltip.pointFormatter = function(){
                            return this.series.name + ': <b>'+ this.count;
                        };
                        defaultOptions.legend.borderWidth = 1;
                        defaultOptions.legend = {
                            borderWidth: 1,
                            align: "right",
                            floating:true,
                            verticalAlign:"right",
                            layout:"vertical",
                            itemMarginTop:10,
                            labelFormatter: function () {
                                return this.name.slice(0, 20) +"  -  " +this.count;
                            }
                        }
                    }else{
                        defaultOptions.tooltip.pointFormatter = function(){
                            return '<tr><td style="color: '+this.series.color+'">'+this.series.name+': </td>' +
                                '<td><b>'+series_info[this.series.name].count[this.index]+
                                    '</b></td></tr>';
                        };
                        defaultOptions.tooltip.valueDecimals = 2;
                    }
                }
                if (chart_data.pointInterval){
                    //实时图
                    defaultOptions.plotOptions.pointInterval = chart_data.pointInterval;
                    defaultOptions.plotOptions.pointStart = chart_data.pointStart;
                }
                if (chart_data.plot_line_range && chart_data.chart_type == "column"){
                    var line_range = chart_data.plot_line_range.split("-");
                    var min = line_range[0] == ""?0:parseInt(line_range[0]);
                    var max = line_range[1] == ""?0:parseInt(line_range[1]);
                    if (!max){
                        defaultOptions.yAxis[0].max = min + min /10 > chart_data.max_y?min + min /10 : chart_data.max_y;
                        defaultOptions.yAxis[0].plotLines = [{
                                value: min,
                                color: 'red',
                                dashStyle: 'shortdash',
                                width: 2,
                                label: {
                                    text: min
                                }
                            }];
                    }else{
                       defaultOptions.yAxis[0].max = max + max /10 > chart_data.max_y?max + max /10 : chart_data.max_y;
                    defaultOptions.yAxis[0].plotLines = [{
                            value: min,
                            color: 'green',
                            dashStyle: 'shortdash',
                            width: 2,
                            label: {
                                text: min
                            }
                        }, {
                            value: max,
                            color: 'red',
                            dashStyle: 'shortdash',
                            width: 2,
                            label: {
                                text: max
                            }
                        }];
                    }
                }
                if (chart_data.yaxis_range && (chart_data.chart_type == "column" || chart_data.chart_type == "line"
                	|| chart_data.chart_type == "spline" || chart_data.chart_type == "stackbar")) {
                    //设置y轴数值范围
                	var yaxis_range = chart_data.yaxis_range.split(":");
                    var floor = isNaN(parseInt(yaxis_range[0]))?"":parseInt(yaxis_range[0]);
                    var ceiling = isNaN(parseInt(yaxis_range[1]))?"":parseInt(yaxis_range[1]);
                    defaultOptions.yAxis[0].floor = floor;
                    defaultOptions.yAxis[0].ceiling = ceiling;
                }
                $(selector).highcharts(defaultOptions);
            }
        };
        chart.line(selector);
    },

    line: function(chart_data, selector, series_info){
		var defaultOptions = {
            title:{},
			chart: {
                backgroundColor: 'rgba(0,0,0,0)',
				type: chart_data.chart_type,
                zoomType: "x"
			},
			plotOptions: {
                spline: {
                    animation: false,
                    marker: {
                        threshold: 0,
                        symbol: 'circle',
                        radius: 0,
                        enabled: true
                    }
                },
				line: {
					marker: {
						symbol: 'circle',
						radius: 1
					}
				},
                series : {

                }
			},
            credits:{
                enabled: true,
                text: "",
                href: "###"
            },
			xAxis: chart_data.x_axis,
            yAxis: [{
                title: {
                    enabled: false
                },
                min: 0,
                gridLineDashStyle: "LongDash",
                allowDecimals: true,
                plotLines: [],
                opposite: false
                }],
            tooltip: {
                xDateFormat: '%Y-%m-%d %H:%M:%S',
                followPointer: true,
                followTouchMove: true,
                crosshairs:  {
					width: 1,
					color: "#e2e2e2"
				},
                shared: true,
                useHTML: true,
                headerFormat: '<small>{point.key}</small><table>',
                pointFormat: '<tr><td style="color: {series.color}">{series.name}:&nbsp;&nbsp;</td>' +
                    '<td><b>{point.y}</b></td></tr>',
                footerFormat: '</table>'
                //valueDecimals: 2
            },
                series: chart_data.series
		};
        if (chart_data.show_percent){
            defaultOptions.tooltip.pointFormatter = function(){
                return '<tr><td style="color: '+this.series.color+'">'+this.series.name+': </td>' +
                    '<td><b>'+this.y+'%</b></td><td><b>&nbsp;('+series_info[this.series.name].count[this.index]+
                        ')</b></td></tr>';
            };
            //  百分比区间
            defaultOptions.yAxis[0].max = 100;
            defaultOptions.yAxis[0].min = 0;
        }
        if (chart_data.pointInterval) {
            //实时图
            defaultOptions.plotOptions.pointInterval = chart_data.pointInterval;
            defaultOptions.plotOptions.pointStart = chart_data.pointStart;
            if (chart_data.pointInterval == 3600000){
                defaultOptions.xAxis.labels = {
                            formatter: function() {
                                return Highcharts.dateFormat('%m/%d', this.value);
                            }
                        }
            }
            defaultOptions.rangeSelector = {
                buttons: [{
                    count: 1,
                    type: 'minute',
                    text: '1M'
                }, {
                    count: 5,
                    type: 'minute',
                    text: '5M'
                }, {
                    type: 'all',
                    text: 'All'
                }],
                inputEnabled: false,
                selected: 0
            };
        }
        if (chart_data.plot_line_range){
            var line_range = chart_data.plot_line_range.split("-");
            var min = line_range[0] == ""?0:parseInt(line_range[0]);
            var max = line_range[1] == ""?0:parseInt(line_range[1]);
            if (!max){
                defaultOptions.yAxis[0].max = min + min /10 > chart_data.max_y?min + min /10 : chart_data.max_y;
                defaultOptions.yAxis[0].plotLines = [{
                        value: min,
                        color: 'red',
                        dashStyle: 'shortdash',
                        width: 2,
                        label: {
                            text: min
                        }
                    }];
            }else{
               defaultOptions.yAxis[0].max = max + max /10 > chart_data.max_y?max + max /10 : chart_data.max_y;
            defaultOptions.yAxis[0].plotLines = [{
                    value: min,
                    color: 'green',
                    dashStyle: 'shortdash',
                    width: 2,
                    label: {
                        text: min
                    }
                }, {
                    value: max,
                    color: 'red',
                    dashStyle: 'shortdash',
                    width: 2,
                    label: {
                        text: max
                    }
                }];
            }
        }
        if (chart_data.yaxis_range) {
            //设置y轴数值范围
        	var yaxis_range = chart_data.yaxis_range.split(":");
            var floor = isNaN(parseInt(yaxis_range[0]))?"":parseInt(yaxis_range[0]);
            var ceiling = isNaN(parseInt(yaxis_range[1]))?"":parseInt(yaxis_range[1]);
            if (floor){
                defaultOptions.yAxis[0].min = floor;
            }
            if (ceiling){
                defaultOptions.yAxis[0].max = ceiling;
            }

        }
        if (chart_data.unit){
            defaultOptions.yAxis[0].labels = {
                 format: '{value}'+chart_data.unit
             };
            defaultOptions.tooltip.pointFormatter = function(){
                return '<tr><td style="color: '+this.series.color+'">'+this.series.name+': </td>' +
                    '<td><b>'+this.y+chart_data.unit+'</b></td></tr>';
            };
        }
		$(selector).highcharts(defaultOptions);
    },

    spline: function(chart_data, selector, series_info){
        Hchart.line(chart_data, selector, series_info);
    },

    pie: function(chart_data, selector, series_info){
		var defaultOptions = {
			chart: {
				plotBackgroundColor: null,
				plotBorderWidth: null,
				plotShadow: false,
				type: 'pie'
			},
            tooltip: {
                xDateFormat: '%Y-%m-%d %H:%M:%S',
                followPointer: true,
                followTouchMove: true,
                crosshairs: true,
                shared: true,
                useHTML: true,
                headerFormat: '<small>{point.key}</small><table>',
                pointFormat: '<tr><td style="color: {series.color}">{series.name}: </td>' +
                    '<td><b>{point.y}</b></td></tr>',
                footerFormat: '</table>',
                valueDecimals: 0
            },
			plotOptions: {
				pie: {
					allowPointSelect: true,
					cursor: 'pointer',
					dataLabels: {
						enabled: true,
						format: '<b>{point.name}</b>: {point.percentage:.2f}%',
						style: {
							fontSize:'14px',
							color: '#666666'
						}
					},
					size:'80%'
				},
                series : {
                    cursor: 'pointer',
                    events: {
                        click: function (event) {
                            var s = event.point.name;
                            var x = "";
                            var graph_id = chart_data.graph_id;
                            var graph_source = chart_data.graph_source;
                            open_sub_page(graph_id, graph_source, s, x);
                        }
                    }
                }
			},
            legend:{
                align: 'right',
                verticalAlign:'middle',
                width: 50,
                itemWidth: 50,
                y: 0,
                title: {
                    style: {
                        fontStyle: 'italic'
                    }
                }
            },
            credits:{
                enabled: true,
                text: "",
                href: "###"
            },
            series: chart_data.series
		};
        var row_index = $(selector).attr('data-row_index');
        if (row_index=='1' || row_index=='2'){
            defaultOptions.series[0].innerSize = '40%';
        }else{
			defaultOptions.plotOptions.pie.center = ['30%', '50%'];
        }
        if (chart_data.show_percent){
            defaultOptions.tooltip.pointFormatter = function(){
                return this.series.name + ': <b>'+ this.y+'%</b><b>&nbsp;|&nbsp;'+this.count;
            };
            defaultOptions.legend.borderWidth = 1;
            defaultOptions.legend = {
                borderWidth: 1,
                align: "right",
                floating:true,
                verticalAlign:"right",
                layout:"vertical",
                itemMarginTop:10,
                labelFormatter: function () {
                    return this.name.length>20?(this.name.slice(0, 20) +"...  -  " +this.count +'<b> | </b>'+this.y+'%'):(this.name +"  -  " +this.count +'<b> | </b>'+this.y+'%');
                }
            }
        }else{
            defaultOptions.tooltip.pointFormatter = function(){
                return this.series.name + ': <b>'+ this.count;
            };
            defaultOptions.legend.borderWidth = 1;
            defaultOptions.legend = {
                borderWidth: 1,
                align: "right",
                floating:true,
                verticalAlign:"right",
                layout:"vertical",
                itemMarginTop:10,
                labelFormatter: function () {
                    return this.name.slice(0, 20) +"  -  " +this.count;
                }
            }
        }
		$(selector).highcharts(defaultOptions);
    },

    funnel: function(chart_data, selector, series_info){
    	// 设置颜色
    	var series_data = chart_data.series[0].data;
    	var color_list  = chart_data.color_list;
    	
    	if(color_list.length != 0) {
    		for(key in series_data) {
    			series_data[key].color = color_list[key];
    		}
    	}
    	
        var funnel_max = chart_data.series[0].data[0].count;
        if(chart_data.show_percent) {
            var template = "#= category # : #= value #(#= dataItem.percent #%)";
        } else {
            var template = "#= category # : #= value # (#= kendo.format('{0:P}', value/"+funnel_max+") #)";
        }

        // percent 字段就是百分比
        var defaultOptions = {
            legend: {
               position: "bottom"
            },
            theme : 'bootstrap',
            seriesDefaults: {
                labels: {
                    template : template,
                    visible: true,             
                    align: "center",
                    color:"white"
                },
                dynamicSlope: true
            },
            series: [{
                type: "funnel",
                dynamicHeight: false,
                data: chart_data.series[0].data,
                labels: {
		        	visible: true,
		            color:"black",
		            align:"center",
		            position: "center",
		            format: "N0",
	                background: "transparent",
	                template: template,
	            }
            }],
            tooltip: {
                visible: false,
                template : template
            }
        };

        $(selector).kendoChart(defaultOptions);
        
        //增加超链接
		$("div[data-graph_id='"+chart_data.graph_id+"']").find("svg>g >g:last >g >g").each(function(k){
			$(this).css("cursor","hand");
			var x = "";
			var text = $(this).find("g text").text();
			var arr = text.split(' : ');
			var s = arr[0];
			$(this).delegate("","click", function(){
				open_sub_page(chart_data.graph_id, chart_data.graph_source, s, x);
			});
		});
    },

    column: function(chart_data, selector, series_info){
        var column_1d = function(chart_data, selector, series_info){
            var defaultOptions = {
                chart: {
                    type: 'column'
                },
                xAxis: chart_data.x_axis,
                yAxis: {
                	floor:"",
                	ceiling:"",
                    min: 0
                },
                legend: {
                    enabled: false
                },
                tooltip: {
                    pointFormat: ' <b>{point.y}</b>'
                },
                plotOptions: {
    				series: {
    	                cursor: 'pointer',
    	                point: {
    	                    events: {
    	                    	click: function (event) {
    	                            var s = event.point.category;
    	                            var x = '';
    	                            var graph_id = chart_data.graph_id;
    	                            var graph_source = chart_data.graph_source;
    	                            open_sub_page(graph_id, graph_source, s, x);
    	                        }
    	                    }
    	                }
    	            }
    			},
                credits:{
                    enabled: true,
                    text: "",
                    href: "###"
                },
                series: [{
                    data: chart_data.series.data,
                    dataLabels: {
                        enabled: true,   //false不在图标的柱状上显示数值
                        color: '#666666',
                        y: -2,
                        style: {
                            textShadow: 'none',
                            fontWeight: 'normal'
                        }
                    }
                }]
            };
            if (chart_data.plot_line_range){
	            var line_range = chart_data.plot_line_range.split("-");
	            var min = line_range[0] == ""?0:parseInt(line_range[0]);
	            var max = line_range[1] == ""?0:parseInt(line_range[1]);
	            if (!max){
	                defaultOptions.yAxis.max = min + min /10 > chart_data.max_y?min + min /10 : chart_data.max_y;
	                defaultOptions.yAxis.plotLines = [{
	                        value: min,
	                        color: 'red',
	                        dashStyle: 'shortdash',
	                        width: 2,
	                        label: {
	                            text: min
	                        }
	                    }];
	            }else{
	               defaultOptions.yAxis.max = max + max /10 > chart_data.max_y?max + max /10 : chart_data.max_y;
	            defaultOptions.yAxis.plotLines = [{
	                    value: min,
	                    color: 'green',
	                    dashStyle: 'shortdash',
	                    width: 2,
	                    label: {
	                        text: min
	                    }
	                }, {
	                    value: max,
	                    color: 'red',
	                    dashStyle: 'shortdash',
	                    width: 2,
	                    label: {
	                        text: max
	                    }
	                }];
	            }
            }
            if (chart_data.yaxis_range) {
                //设置y轴数值范围
            	var yaxis_range = chart_data.yaxis_range.split(":");
                var floor = isNaN(parseInt(yaxis_range[0]))?"":parseInt(yaxis_range[0]);
                var ceiling = isNaN(parseInt(yaxis_range[1]))?"":parseInt(yaxis_range[1]);
                defaultOptions.yAxis.floor = floor;
                defaultOptions.yAxis.ceiling = ceiling;
            }
            $(selector).highcharts(defaultOptions);
        };

        var column_2d = function(chart_data, selector, series_info){
            var defaultOptions = {
                title:{
                    text:''
                },
                chart: {
                    type: chart_data.chart_type
                },
                legend:{
                    align: 'right',
                    verticalAlign:'middle',
                    width: 50,
                    itemWidth: 50,
                    y: 0,
                    title: {
                        style: {
                            fontStyle: 'italic'
                        }
                    }
                },
                plotOptions: {
    				series: {
    	                cursor: 'pointer',
    	                point: {
    	                    events: {
    	                    	click: function (event) {
    	                            var s = event.point.category;
    	                            var x = event.point.series.name;
    	                            var graph_id = chart_data.graph_id;
    	                            var graph_source = chart_data.graph_source;
    	                            open_sub_page(graph_id, graph_source, s, x);
    	                        }
    	                    }
    	                }
    	            }
    			},
                xAxis: chart_data.x_axis,
                tooltip: {
                    xDateFormat: '%Y-%m-%d %H:%M:%S',
                    followPointer: true,
                    followTouchMove: true,
                    crosshairs: true,
                    shared: true,
                    useHTML: true,
                    headerFormat: '<small>{point.key}</small><table>',
                    pointFormat: '<tr><td style="color: {series.color}">{series.name}: </td>' +
                        '<td><b>{point.y}</b></td></tr>',
                    footerFormat: '</table>',
                    valueDecimals: 0
                },
                credits:{
                    enabled: true,
                    text: "",
                    href: "###"
                },
                series: chart_data.series
            };
            if (chart_data.show_percent){
                // 百分比展示
                defaultOptions.tooltip.pointFormatter = function(){
                    return '<tr><td style="color: '+this.series.color+'">'+this.series.name+': </td>' +
                        '<td><b>'+this.y+'%</b></td><td><b>&nbsp;('+series_info[this.series.name].count[this.index]+
                            ')</b></td></tr>';
                };
                defaultOptions.tooltip.valueDecimals = 2;
            }else{
                defaultOptions.tooltip.pointFormatter = function(){
                    return '<tr><td style="color: '+this.series.color+'">'+this.series.name+': </td>' +
                        '<td><b>'+series_info[this.series.name].count[this.index]+
                            '</b></td></tr>';
                };
                defaultOptions.tooltip.valueDecimals = 2;
            }
            if (chart_data.plot_line_range){
                var line_range = chart_data.plot_line_range.split("-");
                var min = line_range[0] == ""?0:parseInt(line_range[0]);
                var max = line_range[1] == ""?0:parseInt(line_range[1]);
                if (!max){
                    defaultOptions.yAxis[0].max = min + min /10 > chart_data.max_y?min + min /10 : chart_data.max_y;
                    defaultOptions.yAxis[0].plotLines = [{
                            value: min,
                            color: 'red',
                            dashStyle: 'shortdash',
                            width: 2,
                            label: {
                                text: min
                            }
                        }];
                }else{
                   defaultOptions.yAxis[0].max = max + max /10 > chart_data.max_y?max + max /10 : chart_data.max_y;
                defaultOptions.yAxis[0].plotLines = [{
                        value: min,
                        color: 'green',
                        dashStyle: 'shortdash',
                        width: 2,
                        label: {
                            text: min
                        }
                    }, {
                        value: max,
                        color: 'red',
                        dashStyle: 'shortdash',
                        width: 2,
                        label: {
                            text: max
                        }
                    }];
                }
            }
            if (chart_data.yaxis_range) {
                //设置y轴数值范围
                var yaxis_range = chart_data.yaxis_range.split(":");
                var floor = isNaN(parseInt(yaxis_range[0]))?"":parseInt(yaxis_range[0]);
                var ceiling = isNaN(parseInt(yaxis_range[1]))?"":parseInt(yaxis_range[1]);
                defaultOptions.yAxis[0].floor = floor;
                defaultOptions.yAxis[0].ceiling = ceiling;
            }
            $(selector).highcharts(defaultOptions);

        };
        chart_data.series.length?column_2d(chart_data, selector, series_info):column_1d(chart_data, selector, series_info)
    },

	stackbar : function(chart_data,selector,series_info){
		var defaultOptions = {
			chart: {
				type: 'column'
			},
			xAxis: chart_data.x_axis,
			yAxis: {
				floor:"",
				ceiling:"",
				min: 0,
				stackLabels: {
					enabled: true,
					style: {
						fontWeight: 'normal',
						color: '#666666'
					}
				}
			},
            credits:{
                enabled: true,
                text: "",
                href: "###"
            },
            tooltip: {
                xDateFormat: '%Y-%m-%d %H:%M:%S',
                followPointer: true,
                followTouchMove: true,
                crosshairs: true,
                shared: false,
                useHTML: true,
                headerFormat: '<small>{point.key}</small><table>',
                pointFormat: '<tr><td style="color: {series.color}">{series.name}: </td>' +
                    '<td><b>{point.y}</b></td></tr>',
                footerFormat: '</table>',
                valueDecimals: 0
            },
			plotOptions: {
				column: {
					stacking: 'normal',
					dataLabels: {
						enabled: false,
						color: '#ffffff'
					}
				},
				series: {
	                cursor: 'pointer',
	                point: {
	                    events: {
	                    	click: function (event) {
	                            var s = event.point.category;
	                            var x = '';
	                            var graph_id = chart_data.graph_id;
	                            var graph_source = chart_data.graph_source;
	                            open_sub_page(graph_id, graph_source, s, x);
	                        }
	                    }
	                }
	            }
			},
			series: chart_data.series
		};
        if (chart_data.show_percent){
            defaultOptions.tooltip.pointFormatter = function(){
                return '<tr><td style="color: '+this.series.color+'">'+this.series.name+': </td>' +
                    '<td><b>'+this.y+'%</b></td><td><b>&nbsp;('+series_info[this.series.name].count[this.index]+
                        ')</b></td></tr>';
            };
        }
        if (chart_data.yaxis_range) {
            //设置y轴数值范围
        	var yaxis_range = chart_data.yaxis_range.split(":");
            var floor = isNaN(parseInt(yaxis_range[0]))?"":parseInt(yaxis_range[0]);
            var ceiling = isNaN(parseInt(yaxis_range[1]))?"":parseInt(yaxis_range[1]);
            defaultOptions.yAxis.floor = floor;
            defaultOptions.yAxis.ceiling = ceiling;
        }
        $(selector).highcharts(defaultOptions);
    },
    
    map:function(chart_data, selector){
    	var cnFullName = {
    			'北京':'北京市', '天津':'天津市', '上海':'上海市', '重庆':'重庆市', '河南':'河南省', '河北':'河北省', 
    			'云南':'云南省', '辽宁':'辽宁省', '黑龙江':'黑龙江省', '湖南':'湖南省', '安徽':'安徽省', '山东':'山东省', 
    			'新疆':'新疆维吾尔自治区', '江苏':'江苏省', '浙江':'浙江省', '江西':'江西省', '湖北':'湖北省', '广西':'广西壮族自治区', 
    			'甘肃':'甘肃省', '山西':'山西省', '内蒙古':'内蒙古自治区', '陕西':'陕西省', '吉林':'吉林省', '福建':'福建省', 
    			'贵州':'贵州省', '广东':'广东省', '青海':'青海省', '西藏':'西藏自治区', '四川':'四川省', '宁夏':'宁夏回族自治区', 
    			'海南':'海南省', '台湾':'台湾省', '香港':'香港特别行政区', '澳门':'澳门特别行政区'
    	}
    	var minColor = '#2fe589';
    	var maxColor = '#f15501';
    	if(chart_data.color_list.length > 0){
    		minColor = chart_data.color_list[0].split(',')[0];
    		maxColor = chart_data.color_list[0].split(',')[1];
    	}
	   	var options = {
	   		chart: {},
	   		mapNavigation: {
	   			enabled: true
	   		},
	   		title: {
	   			text: ''
	   		},
	   		subtitle: {
	   			text: ''
	   		},
	   		mapNavigation: {
	               enabled: true,
	               buttonOptions: {
	                   verticalAlign: 'bottom'
	               }
	           },
	   		colorAxis: {
	                min: 0,
	                minColor: minColor,
		   			maxColor: maxColor
	           },
            credits:{
                enabled: true,
                text: "",
                href: "###"
            },
	   		series: [{
	   			mapData: Highcharts.maps['countries/cn/custom/cn-all-sar-taiwan'],
	   			joinBy:'hc-key',  //设置节点与地图关联模式
	   			name: '省份',
//	   			dataLabels: {   //地图上显示省份名称
//	                   enabled: true,
//	                   format: '{point.properties.cn-name}'
//	   			},
	   			states: {
	                   hover: {
	                       color: '#f6bb42'
	                   }
	               },
	   			data: chart_data.map_list,
		   		cursor: 'pointer',
	            events: {
	                 click: function (event) {
	                	 var skey = event.point.properties['cn-name']
	                     var s = cnFullName[skey];
	                     var x = "";
	                     var graph_id = chart_data.graph_id;
	                     var graph_source = chart_data.graph_source;
	                     open_sub_page(graph_id, graph_source, s, x);
	                 }
	             }
	   		}],
	   		plotOptions: {
	               series: {
	                   tooltip: {
	   					headerFormat: '',
	                       pointFormat: '{point.properties.cn-name} {point.value}({point.percentage})'
	                   }
	               }
	           }
	   		
	   	};
	   	
	   	$(selector).highcharts('Map',options);
    },

    // 仪表盘
    gauge : function(chart_data,selector){
        var min = chart_data.color_range[0][1];
        var middle = chart_data.color_range[1][1];
        var max = chart_data.color_range[2][1];
        var min_color = chart_data.color_range[0][0];
        var middle_color = chart_data.color_range[1][0];
        var max_color = chart_data.color_range[2][0];

		var defaultOptions = {
			chart: {
				type: 'gauge',
				plotBackgroundColor: null,
				plotBackgroundImage: null,
				plotBorderWidth: 0,
				plotShadow: false
			},
			pane: {
				startAngle: -90,
				endAngle: 90,
				center: ['50%', '85%'],
				size: '140%',
				background: [],

			},
            credits:{
                enabled: true,
                text: "",
                href: "###"
            },
			// the value axis
			yAxis: {
				min: 0,
				max: max,
				minorTickInterval: false,
				tickPixelInterval: 50,

				tickWidth: 0,
				labels: {
					step: 2,
					rotation: 'auto',
					style: {
						color: '#333333'
					}
				},
				plotBands: [{
					thickness: '35%',
					from: 0,
					to: min,
					color: min_color
				}, {
					thickness: '35%',
					from: min,
					to: middle,
					color: middle_color
				}, {
					thickness: '35%',
					from: middle,
					to: max,
					color: max_color
				}]
			},
			plotOptions: {
				gauge: {
					dataLabels: {
						y: -65,
						borderWidth: 0,
						useHTML: true,
						format: '<div style="text-align:center"><span style="font-size:25px;color:#666666">{y}</span</div>'
					}
				}
			},
			tooltip: {
				enabled: false
			},
			series: chart_data.series
		};
		$(selector).highcharts(defaultOptions);
	},

    // 雷达图
    chartpolar : function(chart_data, selector, series_info){
        var value_list = [];
        var max_value = 0;
        for(var i= 0;i<chart_data.series[0].data.length;i++){
            max_value = max_value > chart_data.series[0].data[i].count ? max_value : chart_data.series[0].data[i].count;
            value_list.push(chart_data.series[0].data[i].count)
        }
        max_value = max_value> 100? max_value: 100;
		var defaultOptions = {
			chart: {
				polar: true,
				type: 'line'
			},
			pane: {
				size: '68%'
			},
            credits:{
                enabled: true,
                text: "",
                href: "###"
            },
			xAxis: {
                categories: chart_data.series_name_list,
				tickmarkPlacement: 'on',
				lineWidth: 0,
				gridLineWidth: 1,
				tickWidth: 0
            },
			yAxis: {
				gridLineInterpolation: 'polygon',
				lineWidth: 0,
				min: 0,
                max: max_value
			},
			legend: {
				enabled: false
			},
			series: [{
				color: chart_data.color_list?chart_data.color_list[0]:'#64c256',
				name: '得分',
				type: 'area',
				data: value_list,
				pointPlacement: 'on',
				cursor: 'pointer',
                events: {
                     click: function (event) {
                         var s = event.point.category;
                         var x = event.point.x;
                         var graph_id = chart_data.graph_id;
                         var graph_source = chart_data.graph_source;
                         open_sub_page(graph_id, graph_source, s, x);
                     }
                 }
			}]

		};
        console.log(defaultOptions);
		$(selector).highcharts(defaultOptions);
	}
};