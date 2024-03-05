import com.google.gson.Gson;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.annotations.SerializedName;
import com.tencent.bk.base.dataflow.common.api.AbstractFlinkBasicTransform;

import org.apache.flink.api.common.state.MapState;
import org.apache.flink.api.common.state.MapStateDescriptor;
import org.apache.flink.api.common.state.StateTtlConfig;
import org.apache.flink.api.common.state.StateTtlConfig.StateVisibility;
import org.apache.flink.api.common.state.StateTtlConfig.UpdateType;
import org.apache.flink.api.common.state.ValueState;
import org.apache.flink.api.common.state.ValueStateDescriptor;
import org.apache.flink.api.common.time.Time;
import org.apache.flink.api.java.functions.KeySelector;
import org.apache.flink.configuration.Configuration;
import org.apache.flink.streaming.api.datastream.DataStream;
import org.apache.flink.streaming.api.functions.KeyedProcessFunction;
import org.apache.flink.types.Row;

import java.io.Serializable;
import java.math.BigInteger;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Pattern;
import java.util.stream.Collectors;
import java.util.stream.IntStream;

import org.apache.flink.api.common.typeinfo.BasicTypeInfo;
import org.apache.flink.api.common.typeinfo.TypeInformation;
import org.apache.flink.api.java.typeutils.RowTypeInfo;
import org.apache.flink.util.Collector;

/**
 * 请注意以下几点，以防开发的 Code 节点不可用
 * 1.jdk 版本为 1.8
 * 2.Flink 版本 为 1.17.1
 * 2.请不要修改数据处理类名 CodeTransform
 *
 * 数据处理，示例为将一个数据的所有字段选择，并输出
 *
 */
public class CodeTransform extends AbstractFlinkBasicTransform {

    @Override
    public Map<String, DataStream<Row>> transform(Map<String, DataStream<Row>> input) {

        Gson gson = new Gson();
        GsonCondition condition = gson.fromJson(args.get(0), GsonCondition.class);

        // 数据输入
        DataStream<Row> inputDataStream0 = input.get(condition.getInputTableID());

        // 数据处理
        // 输出表字段名配置
        String[] fieldNames = new String[] {
                "time",
                "span_name",
                "span_id",
                "kind",
                "events",
                "parent_span_id",
                "end_time",
                "links",
                "trace_id",
                "elapsed_time",
                "status",
                "attributes",
                "start_time",
                "trace_state",
                "resource",
                "datatime"
        };

        // 输出表字段类型配置
        TypeInformation<?>[] rowType = new TypeInformation<?>[]{
                BasicTypeInfo.STRING_TYPE_INFO,
                BasicTypeInfo.STRING_TYPE_INFO,
                BasicTypeInfo.STRING_TYPE_INFO,
                BasicTypeInfo.INT_TYPE_INFO,
                BasicTypeInfo.STRING_TYPE_INFO,
                BasicTypeInfo.STRING_TYPE_INFO,
                BasicTypeInfo.LONG_TYPE_INFO,
                BasicTypeInfo.STRING_TYPE_INFO,
                BasicTypeInfo.STRING_TYPE_INFO,
                BasicTypeInfo.LONG_TYPE_INFO,
                BasicTypeInfo.STRING_TYPE_INFO,
                BasicTypeInfo.STRING_TYPE_INFO,
                BasicTypeInfo.LONG_TYPE_INFO,
                BasicTypeInfo.STRING_TYPE_INFO,
                BasicTypeInfo.STRING_TYPE_INFO,
                BasicTypeInfo.LONG_TYPE_INFO,
        };

        // 获取数据源字段的index
        int spanInfoIndex = this.getFieldIndexByName(inputDataStream0, "span_info");
        int traceIDIndex = this.getFieldIndexByName(inputDataStream0, "trace_id");
        int datetimeIndex = this.getFieldIndexByName(inputDataStream0, "dtEventTimeStamp");
        int spanIDIndex = this.getFieldIndexByName(inputDataStream0, "span_id");


        DataStream<Row> newOutput = inputDataStream0.keyBy(new KeySelector<Row, String>() {
                    @Override
                    public String getKey(Row row) throws Exception {
                        return String.valueOf(row.getField(traceIDIndex));
                    }
                }).process(new TraceFunction(traceIDIndex, spanInfoIndex, datetimeIndex, spanIDIndex, condition))
                .returns(new RowTypeInfo(rowType, fieldNames));

        // 数据输出
        Map<String, DataStream<Row>> output = new HashMap<>();
        output.put(condition.getOutputTableID(), newOutput);
        return output;
    }

    public class GsonCondition implements Serializable {

        private static final long serialVersionUID = 1L;

        @SerializedName(value = "input_table_id")
        private String inputTableID;
        @SerializedName(value = "output_table_id")
        private String outputTableID;

        @SerializedName(value = "trace_session_gap_min")
        private int traceSessionGapMin;
        @SerializedName(value = "trace_mark_timeout_min")
        private int traceMarkTimeoutMin;
        @SerializedName(value = "sampling_conditions")
        private List<SamplingConditions> samplingConditions;
        @SerializedName(value = "random_sampling_ratio") // 0 - 100
        private int randomSamplingRatio;
        @SerializedName(value = "max_span_count") // 单个trace最大缓存/输出span的条数
        private long maxSpanCount;

        public GsonCondition(String inputTableID, String outputTableID,
                int traceSessionGapMin, int traceMarkTimeoutMin,
                List<SamplingConditions> samplingConditions,
                int randomSamplingRatio,
                long maxSpanCount) {
            this.inputTableID = inputTableID;
            this.outputTableID = outputTableID;
            this.traceSessionGapMin = traceSessionGapMin;
            this.traceMarkTimeoutMin = traceMarkTimeoutMin;
            this.samplingConditions = samplingConditions;
            this.randomSamplingRatio = randomSamplingRatio;
            this.maxSpanCount = maxSpanCount;
        }

        public String getInputTableID() {
            return inputTableID;
        }

        public String getOutputTableID() {
            return outputTableID;
        }

        public int getTraceSessionGapMin() {
            return traceSessionGapMin;
        }

        public List<SamplingConditions> getSamplingConditions() {
            return samplingConditions;
        }

        public int getTraceMarkTimeoutMin() {
            return traceMarkTimeoutMin;
        }

        public int getRandomSamplingRatio() {
            return randomSamplingRatio;
        }

        public long getMaxSpanCount() {
            return maxSpanCount;
        }

        public void setInputTableID(String inputTableID) {
            this.inputTableID = inputTableID;
        }

        public void setOutputTableID(String outputTableID) {
            this.outputTableID = outputTableID;
        }

        public void setTraceSessionGapMin(int traceSessionGapMin) {
            this.traceSessionGapMin = traceSessionGapMin;
        }

        public void setTraceMarkTimeoutMin(int traceMarkTimeoutMin) {
            this.traceMarkTimeoutMin = traceMarkTimeoutMin;
        }

        public void setSamplingConditions(
                List<SamplingConditions> samplingConditions) {
            this.samplingConditions = samplingConditions;
        }

        public void setRandomSamplingRatio(int randomSamplingRatio) {
            this.randomSamplingRatio = randomSamplingRatio;
        }

        public void setMaxSpanCount(long maxSpanCount) {
            this.maxSpanCount = maxSpanCount;
        }

        @Override
        public String toString() {
            return "SamplingConditions [trace_session_gap_min=" + traceSessionGapMin
                    + ", samplingConditions=" + samplingConditions + "]";
        }
    }

    public class SamplingConditions implements Serializable {
        private static final long serialVersionUID = 1L;
        private String condition = null;
        private String key;
        private List<String> value;
        private String method;

        public SamplingConditions(String key, List<String> value, String method) {
            this.key = key;
            this.value = value;
            this.method = method;
        }

        public SamplingConditions(String condition, String key, List<String> value, String method) {
            this.condition = condition;
            this.key = key;
            this.value = value;
            this.method = method;
        }

        public String getCondition() {
            return condition;
        }

        public void setCondition(String condition) {
            this.condition = condition;
        }

        public String getKey() {
            return key;
        }

        public void setKey(String key) {
            this.key = key;
        }

        public List<String> getValue() {
            return value;
        }

        public void setValue(List<String> value) {
            this.value = value;
        }

        public String getMethod() {
            return method;
        }

        public void setMethod(String method) {
            this.method = method;
        }

        @Override
        public String toString() {
            return "SamplingConditions [key=" + key + ", value=" + value
                    + ", condition=" + condition + ", method=" + method + "]";
        }
    }

    public class ErrorTraceTag {
        public boolean isError = false;
        public long beginMinuteTime = System.currentTimeMillis() / 1000 / 60;
        public int spanCount = 0;
    }

    public class TraceFunction extends KeyedProcessFunction<String, Row, Row> {
        private final int traceIDIndex;
        private final int spanInfoIndex;
        private final int datetimeIndex;
        private final int spanIDIndex;
        private ValueState<ErrorTraceTag> traceTagState;
        private MapState<String, String> traceState;
        private final GsonCondition condition;
        private int ttlSize;
        private int errorTagTtlSize;
        private List<List<SamplingConditions>> structConditions = new ArrayList<>();

        public TraceFunction(int traceIDIndex, int spanInfoIndex, int datetimeIndex,
                int spanIDIndex, GsonCondition condition) {
            this.traceIDIndex = traceIDIndex;
            this.spanInfoIndex = spanInfoIndex;
            this.datetimeIndex = datetimeIndex;
            this.spanIDIndex = spanIDIndex;
            this.condition = condition;
        }

        @Override
        public void open(Configuration parameters) throws Exception {
            parseConditions();

            StateTtlConfig errorTagTtlConfig = StateTtlConfig.newBuilder(Time.minutes(errorTagTtlSize))
                    .setUpdateType(UpdateType.OnCreateAndWrite)
                    .setStateVisibility(StateVisibility.ReturnExpiredIfNotCleanedUp)
                    .cleanupInRocksdbCompactFilter(100000)
                    .build();
            ValueStateDescriptor<ErrorTraceTag> errorTraceTag =
                    new ValueStateDescriptor<>("errorTraceTag", ErrorTraceTag.class);
            errorTraceTag.enableTimeToLive(errorTagTtlConfig);
            traceTagState = getRuntimeContext().getState(errorTraceTag);

            StateTtlConfig ttlConfig = StateTtlConfig.newBuilder(Time.minutes(ttlSize))
                    .setUpdateType(UpdateType.OnCreateAndWrite)
                    .setStateVisibility(StateVisibility.ReturnExpiredIfNotCleanedUp)
                    .cleanupInRocksdbCompactFilter(100000)
                    .build();
            MapStateDescriptor<String, String> traceState = new MapStateDescriptor<>("traceState", String.class,
                    String.class);
            traceState.enableTimeToLive(ttlConfig);
            this.traceState =  getRuntimeContext().getMapState(traceState);
        }

        private void parseConditions() {
            ttlSize = condition.getTraceSessionGapMin();
            errorTagTtlSize = condition.getTraceMarkTimeoutMin();
            List<SamplingConditions> samplingConditions = condition.getSamplingConditions();

            IntStream.range(0, samplingConditions.size()).forEach(i -> {
                if (i == 0) {
                    List<SamplingConditions> tmp = new ArrayList<>();
                    tmp.add(samplingConditions.get(i));
                    structConditions.add(tmp);
                } else if (i > 0 && samplingConditions.get(i).getCondition().equalsIgnoreCase("OR")) {
                    List<SamplingConditions> tmp = new ArrayList<>();
                    structConditions.add(tmp);
                } else if (i > 0 && samplingConditions.get(i).getCondition().equalsIgnoreCase("AND")) {
                    structConditions.get(structConditions.size() - 1).add(samplingConditions.get(i));
                } else {
                    throw new IllegalArgumentException("Not support condition "
                            + samplingConditions.get(i).getCondition());
                }
            });
        }

        private boolean isSampling(String data) {
            try {
                List<Boolean> orConditions = new ArrayList<>();

                for (List<SamplingConditions> andCondition : structConditions) {
                    boolean tag = true;
                    for (SamplingConditions samplingConditions : andCondition) {
                        if (! isChildSample(data, samplingConditions)) {
                            tag = false;
                            break;
                        }
                    }
                    orConditions.add(tag);
                }

                boolean tag1 = false;
                for (Boolean orCondition : orConditions) {
                    if (orCondition) {
                        tag1 = true;
                        break;
                    }
                }
                return tag1;
            } catch (Exception e) {
                throw new RuntimeException("data is " + data + "  conditions is " + structConditions, e);
            }

        }

        /**
         * 支持匹配规则符号 "gt", "gte", "lt", "lte", "eq", "neq", "reg", "nreg"
         *
         * @param data
         * @param samplingConditions
         * @return
         */
        private boolean isChildSample(String data, SamplingConditions samplingConditions) {
            String method = samplingConditions.getMethod();
            String key = samplingConditions.getKey();
            List<String> value = samplingConditions.getValue();
            String valueType = "Number";
            // 当匹配方式为 等于/不等于/是否正则匹配时，字段需转为string类型，其他比较逻辑为double
            if (("eq").equalsIgnoreCase(method) || ("neq").equalsIgnoreCase(method)
                    || ("reg").equalsIgnoreCase(method) || ("nreg").equalsIgnoreCase(method)) {
                valueType = "String";
            }
            String[] split = key.split("\\.", 2);
            List<String> keys = new ArrayList<>(split.length);
            Collections.addAll(keys, split);
            boolean compare;
            if (keys.size() == 1) {
                Gson gson = new Gson();
                JsonElement ssObject = gson.fromJson(data, JsonObject.class).get(keys.get(0));
                if (null == ssObject) {
                    return false;
                }
                if (("String").equals(valueType)) {
                    String stringValue = ssObject.getAsString();
                    compare = compare(stringValue, value, method);
                } else {
                    double doubleValue = ssObject.getAsDouble();
                    compare = numberCompare(doubleValue, value, method);
                }
            } else {
                Gson gson = new Gson();
                JsonElement oneElement = gson.fromJson(data, JsonObject.class).get(keys.get(0));
                if (null == oneElement) {
                    return false;
                }
                JsonElement jsonElement = oneElement.getAsJsonObject().get(keys.get(1));
                if (null == jsonElement) {
                    return false;
                }
                if (("String").equals(valueType)) {
                    String stringValue = jsonElement.getAsString();
                    compare = compare(stringValue, value, method);
                } else {
                    double doubleValue = jsonElement.getAsDouble();
                    compare = numberCompare(doubleValue, value, method);
                }
            }
            return compare;
        }

        private boolean compare(String data, List<String> value, String method) {
            switch (method) {
                case "eq":
                    for (String s : value) {
                        if (data.equals(s)) {
                            return true;
                        }
                    }
                    return false;
                case "neq":
                    for (String s : value) {
                        if (data.equals(s)) {
                            return false;
                        }
                    }
                    return true;
                case "reg":
                    for (String pattern : value) {
                        if (Pattern.matches(pattern, data)) {
                            return true;
                        }
                    }
                    return false;
                case "nreg":
                    for (String pattern : value) {
                        if (Pattern.matches(pattern, data)) {
                            return false;
                        }
                    }
                    return true;
                default:
                    throw new RuntimeException("Not support method " + method);
            }
        }

        private boolean numberCompare(Double data, List<String> value, String method) {
            List<Double> collect = value.stream().map(Double::valueOf).collect(Collectors.toList());
            switch (method) {
                case "gt":
                    return data > Collections.max(collect);
                case "gte":
                    return data >= Collections.max(collect);
                case "lt":
                    return data < Collections.min(collect);
                case "lte":
                    return data <= Collections.min(collect);
                default:
                    throw new RuntimeException("Not support method " + method);
            }
        }

        /**
         * 对 trace id 的md5值取mod，判断是否在随机采样分桶中
         * @param traceID trace id
         * @return 是否随机采样分桶中, 结果为true代表在随机采样分桶中
         */
        private boolean isBucket(String traceID, int randomSamplingRatio) {
            try {
                MessageDigest md5 = MessageDigest.getInstance("MD5");
                byte[] digest  = md5.digest(traceID.getBytes(StandardCharsets.UTF_8));
                BigInteger bigInteger = new BigInteger(1, digest);
                BigInteger bucket = new BigInteger("100");
                return Integer.parseInt(String.valueOf(bigInteger.mod(bucket))) < randomSamplingRatio;
            } catch (Exception e) {
                throw new RuntimeException("sample trace failed.", e);
            }
        }

        @Override
        public void processElement(Row input, Context ctx, Collector<Row> output) throws Exception {
            String traceID = String.valueOf(input.getField(traceIDIndex));
            Long datetime = Long.parseLong(String.valueOf(input.getField(datetimeIndex)));
            String spanID = String.valueOf(input.getField(spanIDIndex));

            // tag state
            ErrorTraceTag errorTraceTag = traceTagState.value();
            if (errorTraceTag == null) {
                errorTraceTag = new ErrorTraceTag();
            }

            // trace_mark_timeout_min 时间后，清理当前trace tag state
            if (System.currentTimeMillis() / 1000 / 60 - errorTraceTag.beginMinuteTime
                    > condition.getTraceMarkTimeoutMin()) {
                traceTagState.clear();
                return;
            }

            // 按照比率随机采样, 符合随机采样标准，并且数据没有达到 max_span_count 条时，输出
            if (isBucket(traceID, condition.getRandomSamplingRatio())
                    && errorTraceTag.spanCount < condition.getMaxSpanCount()) {
                String spanInfo = String.valueOf(input.getField(spanInfoIndex));
                output.collect(buildOutput(spanInfo, datetime, spanID, traceID));
                errorTraceTag.spanCount++;
            } else {
                // 尾部采样
                // 保存错误trace id
                if (isErrorTrace(errorTraceTag)) {
                    // 如果数据到达了 max_span_count，不输出
                    if (errorTraceTag.spanCount >= condition.getMaxSpanCount()) {
                        return;
                    }
                    String spanInfo = String.valueOf(input.getField(spanInfoIndex));
                    output.collect(buildOutput(spanInfo, datetime, spanID, traceID));
                    errorTraceTag.spanCount++;
                } else if (isSampling(String.valueOf(input.getField(spanInfoIndex)))) {
                    errorTraceTag.isError = true;
                    String spanInfo = String.valueOf(input.getField(spanInfoIndex));
                    output.collect(buildOutput(spanInfo, datetime, spanID, traceID));
                    errorTraceTag.spanCount++;

                    // 从状态中取数据
                    for (Map.Entry<String, String> entry : traceState.entries()) {
                        // 如果数据到达了 max_span_count，不输出
                        if (errorTraceTag.spanCount >= condition.getMaxSpanCount()) {
                            traceState.clear();
                            return;
                        }
                        String tmpSpanInfo = entry.getValue();
                        String tmpSpanId = entry.getKey();
                        output.collect(buildOutput(tmpSpanInfo, datetime, tmpSpanId, traceID));
                        errorTraceTag.spanCount++;
                    }
                    traceState.clear();
                } else {
                    // 当缓存数据达到 max_span_count 时，重新缓存
                    if (errorTraceTag.spanCount >= condition.getMaxSpanCount()) {
                        traceState.clear();
                        errorTraceTag.spanCount = 1;
                    }
                    // 存入状态数据
                    traceState.put(spanID, String.valueOf(input.getField(spanInfoIndex)));
                }
            }

            traceTagState.update(errorTraceTag);
        }

        private Row buildOutput(String spanInfo, Long datetime, String spanID, String traceID) {
            JsonObject spanInfoJson = new Gson().fromJson(spanInfo, JsonObject.class);
            Row out = new Row(16);
            out.setField(0, String.valueOf(datetime));
            out.setField(1, spanInfoJson.get("span_name").getAsString());
            out.setField(2, spanID);
            out.setField(3, Integer.valueOf(String.valueOf(spanInfoJson.get("kind"))));
            out.setField(4, String.valueOf(spanInfoJson.get("events")));
            out.setField(5, spanInfoJson.get("parent_span_id").getAsString());
            out.setField(6, Long.valueOf(String.valueOf(spanInfoJson.get("end_time"))));
            out.setField(7, String.valueOf(spanInfoJson.get("links")));
            out.setField(8, traceID);
            out.setField(9, Long.valueOf(String.valueOf(spanInfoJson.get("elapsed_time"))));
            out.setField(10, String.valueOf(spanInfoJson.get("status")));
            out.setField(11, String.valueOf(spanInfoJson.get("attributes")));
            out.setField(12, Long.valueOf(String.valueOf(spanInfoJson.get("start_time"))));
            out.setField(13, spanInfoJson.get("trace_state").getAsString());
            out.setField(14, String.valueOf(spanInfoJson.get("resource")));
            out.setField(15, datetime);
            return out;
        }

        private boolean isErrorTrace(ErrorTraceTag errorTraceTag) throws Exception {
            return errorTraceTag.isError;
        }
    }
}