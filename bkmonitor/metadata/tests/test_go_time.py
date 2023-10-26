from metadata.utils import go_time

# import pdb
#
# pdb.set_trace()


class TestUtilsGoTime(object):
    def test_parse_duration(self):
        value_list = [
            ("mhs", 0),
            (".m", 0),
            ("1zhw", 0),
            ("1wh", 0),
            ("1w0h", 7 * 24 * 60 * 60),
            ("5m", 5 * 60),
            ("-2.5h", -2.5 * 60 * 60),
            ("1d1h1m1s", 24 * 60 * 60 + 60 * 60 + 60 + 1),
        ]

        for v in value_list:
            assert go_time.parse_duration(v[0]) == v[1]

    def test_duration(self):
        value_list = [
            (0, "0s"),
            (60, "1m"),
            (2 * 60 + 5, "125s"),
            (-(24 * 60 * 60 + 120), "-1442m"),
        ]

        for v in value_list:
            assert go_time.duration_string(v[0]) == v[1]
