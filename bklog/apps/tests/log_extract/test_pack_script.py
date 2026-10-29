"""Exercise the deployed shell filter without Django, JOB or remote hosts."""

import os
import shlex
import subprocess
import tempfile
from pathlib import Path
from unittest import TestCase


class TestPackScriptMatchWord(TestCase):
    modes = ("keyword_or", "keyword_and", "keyword_not")

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        script = Path(__file__).resolve().parents[2] / "log_extract/scripts/pack.sh"
        # Source the real function definitions, stopping before JOB/packing side effects.
        cls.functions, separator, _ = script.read_text(encoding="utf-8").partition("\njob_start\n")
        if not separator:
            raise AssertionError("Cannot isolate pack.sh function definitions")

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.logfile = self.directory / "input with spaces.log"
        self.target = self.directory / "filtered with spaces.log"

    def match(self, pattern, mode, logs, *, check=True):
        self.logfile.write_text(logs, encoding="utf-8")
        # Use the same shell quoting as FileServer.get_script_info. Inputs deliberately
        # bypass the HTTP serializer, as persisted/recreated tasks can do.
        params = " ".join(shlex.quote(str(arg)) for arg in (self.logfile, self.target, mode, pattern))
        result = subprocess.run(
            ["bash", "-c", self.functions + "\nmatch_word " + params],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=self.directory,
            env={**os.environ, "LC_ALL": "C", "LANG": "C"},
        )
        if check:
            self.assertEqual(result.returncode, 0, result.stderr)
        return result, self.target.read_bytes().decode("utf-8")

    def assert_matches(self, pattern, logs, matching):
        nonmatching = "".join(line for line in logs.splitlines(keepends=True) if line not in matching.splitlines(True))
        for mode in self.modes:
            with self.subTest(pattern=pattern, mode=mode):
                _, actual = self.match(pattern, mode, logs)
                self.assertEqual(actual, nonmatching if mode == "keyword_not" else matching)

    def test_normal_keyword_and_chinese(self):
        self.assert_matches("error", "error\nother\nerror details\n", "error\nerror details\n")
        self.assert_matches("错误", "错误详情\n正常\n", "错误详情\n")

    def test_dash_n_is_matched_as_keyword(self):
        self.assert_matches("-n", "normal log\nstartup -n 10\n-n\nstartup -N 10\n", "startup -n 10\n-n\n")

    def test_regular_expression_semantics(self):
        self.assert_matches("^(foo|bar)[0-9]+$", "foo1\nbar23\nfoo\nother\n", "foo1\nbar23\n")
        self.assert_matches("foo|bar", "foo\nbar\nfoobar\nother\n", "foo\nbar\nfoobar\n")

    def test_backslashes_are_not_decoded_by_variable_assignment(self):
        self.assert_matches(r"foo\.log", "foo.log\nfooXlog\n", "foo.log\n")
        self.assert_matches(r"foo\\bar", "foo\\bar\nfoobar\n", "foo\\bar\n")
        self.assert_matches(r"foo\tbar", "foo\tbar\nfootbar\n", "foo\tbar\n")
        self.assert_matches(r"foo\057bar", "foo/bar\nfooXbar\n", "foo/bar\n")

    def test_slashes_quotes_and_awk_syntax_are_pattern_data(self):
        self.assert_matches("/var/log/app.log", "/var/log/app.log\nother\n", "/var/log/app.log\n")
        self.assert_matches(r"foo\/bar", "foo/bar\nfoobar\n", "foo/bar\n")
        self.assert_matches("a'b\"c;{d}", "a'b\"c;{d}\nother\n", "a'b\"c;{d}\n")

    def test_comma_separated_input_keeps_existing_semantics(self):
        self.assert_matches("foo,bar", "foo\nbar\nfoo,bar\nother\n", "foo,bar\n")

    def test_historical_and_not_space_transformations_are_preserved(self):
        logs = "foo\nbar\nfoo bar\nfoo && bar\nother\n"
        expected = {
            "keyword_and": "foo && bar\n",
            "keyword_not": "other\n",
        }
        # The OR transformation produces adjacent empty alternatives, whose
        # handling is not portable between awk implementations.
        for mode in expected:
            with self.subTest(mode=mode):
                _, actual = self.match("foo bar", mode, logs)
                self.assertEqual(actual, expected[mode])

    def test_awk_program_injection_is_not_executed(self):
        marker = "AWK_INJECTION_MARKER"
        patterns = (
            'foo/;BEGIN{print"' + marker + '"};/foo',
            'foo/;END{print"' + marker + '"};/foo',
            'foo/;BEGIN{system("printf${IFS}' + marker + '")};/foo',
            'foo/\nBEGIN{print"' + marker + '"}\n/foo',
        )
        for pattern in patterns:
            for mode in self.modes:
                with self.subTest(pattern=pattern, mode=mode):
                    result, actual = self.match(pattern, mode, "unrelated log line\n")
                    self.assertNotIn(marker, result.stdout + result.stderr + actual)
                    self.assertEqual(actual, "unrelated log line\n" if mode == "keyword_not" else "")

    def test_shell_substitutions_are_not_executed(self):
        marker_file = self.directory / "command-executed"
        for pattern in (f"$(touch${{IFS}}{marker_file})", f"`touch${{IFS}}{marker_file}`"):
            for mode in self.modes:
                with self.subTest(pattern=pattern, mode=mode):
                    self.match(pattern, mode, "unrelated log line\n")
                    self.assertFalse(marker_file.exists())

    def test_control_characters_and_length_boundaries(self):
        for pattern in ("foo\tbar", "foo\rbar", "foo\x01bar", "x" * 64, "x" * 65, "x" * 4096):
            with self.subTest(pattern=repr(pattern)):
                self.assert_matches(pattern, pattern + "\nother\n", pattern + "\n")

    def test_invalid_regex_fails_without_executing_code(self):
        for pattern in ("[", "("):
            for mode in self.modes:
                with self.subTest(pattern=pattern, mode=mode):
                    result, actual = self.match(pattern, mode, "unrelated log line\n", check=False)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(actual, "")
