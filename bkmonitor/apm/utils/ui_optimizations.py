import bisect
import math


class HistogramNiceNumberGenerator:
    """使用 nice number 重新构建分桶大小和数量"""

    # fmt: off
    # 有序的桶大小列表
    _HISTOGRAM_BUCKET_SIZES = [
        1,     2,              4,     5,
        1e+1,  2e+1,  2.5e+1,  4e+1,  5e+1,
        1e+2,  2e+2,  2.5e+2,  4e+2,  5e+2,
        1e+3,  2e+3,  2.5e+3,  4e+3,  5e+3,
        1e+4,  2e+4,  2.5e+4,  4e+4,  5e+4,
        1e+5,  2e+5,  2.5e+5,  4e+5,  5e+5,
        1e+6,  2e+6,  2.5e+6,  4e+6,  5e+6,
        1e+7,  2e+7,  2.5e+7,  4e+7,  5e+7,
        1e+8,  2e+8,  2.5e+8,  4e+8,  5e+8,
        1e+9,  2e+9,  2.5e+9,  4e+9,  5e+9,
        1e+10,  2e+10,  2.5e+10,  4e+10,  5e+10,
        1e+11,  2e+11,  2.5e+11,  4e+11,  5e+11,
        1e+12,  2e+12,  2.5e+12,  4e+12,  5e+12,
        1e+13,  2e+13,  2.5e+13,  4e+13,  5e+13,
        1e+14,  2e+14,  2.5e+14,  4e+14,  5e+14,
        1e+15,  2e+15,  2.5e+15,  4e+15,  5e+15,
    ]
    # fmt: on

    @classmethod
    def align_histogram_bounds(
        cls,
        min_value: int,
        max_value: int,
        num_buckets: int,
        min_bucket_size: int = 1,
    ) -> tuple[int, int, int, int]:
        """重新计算左边界，右边界，桶大小和桶数量"""

        if min_value == max_value:
            return min_value, max_value + min_bucket_size, min_bucket_size, 1

        target_size = (max_value - min_value) / num_buckets
        bucket_size_index = bisect.bisect_left(cls._HISTOGRAM_BUCKET_SIZES, target_size)
        bucket_size_index = bucket_size_index if bucket_size_index != len(cls._HISTOGRAM_BUCKET_SIZES) else -1
        histogram_bucket_size = cls._HISTOGRAM_BUCKET_SIZES[bucket_size_index]

        bucket_size = int(max(histogram_bucket_size, min_bucket_size))
        left_x = math.floor(min_value / bucket_size) * bucket_size
        right_x = math.ceil(max_value / bucket_size) * bucket_size
        if right_x == max_value:
            right_x += bucket_size
        num_buckets = int((right_x - left_x) // bucket_size)

        return left_x, right_x, bucket_size, num_buckets
