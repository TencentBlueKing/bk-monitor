"""
内置 Grok 模式数据包

将 pygrok 内置 18 个 pattern 文件中的所有 Grok 模式数据
（含 name、pattern、sample、description）按文件拆分为独立的 Python 数据模块。
"""

from apps.log_databus.grok_patterns_data.aws import PATTERNS as AWS_PATTERNS
from apps.log_databus.grok_patterns_data.bacula import PATTERNS as BACULA_PATTERNS
from apps.log_databus.grok_patterns_data.bro import PATTERNS as BRO_PATTERNS
from apps.log_databus.grok_patterns_data.exim import PATTERNS as EXIM_PATTERNS
from apps.log_databus.grok_patterns_data.firewalls import PATTERNS as FIREWALLS_PATTERNS
from apps.log_databus.grok_patterns_data.grok_patterns import PATTERNS as GROK_PATTERNS
from apps.log_databus.grok_patterns_data.haproxy import PATTERNS as HAPROXY_PATTERNS
from apps.log_databus.grok_patterns_data.java import PATTERNS as JAVA_PATTERNS
from apps.log_databus.grok_patterns_data.junos import PATTERNS as JUNOS_PATTERNS
from apps.log_databus.grok_patterns_data.linux_syslog import PATTERNS as LINUX_SYSLOG_PATTERNS
from apps.log_databus.grok_patterns_data.mcollective import PATTERNS as MCOLLECTIVE_PATTERNS
from apps.log_databus.grok_patterns_data.mcollective_patterns import (
    PATTERNS as MCOLLECTIVE_PATTERNS_PATTERNS,
)
from apps.log_databus.grok_patterns_data.mongodb import PATTERNS as MONGODB_PATTERNS
from apps.log_databus.grok_patterns_data.nagios import PATTERNS as NAGIOS_PATTERNS
from apps.log_databus.grok_patterns_data.postgresql import PATTERNS as POSTGRESQL_PATTERNS
from apps.log_databus.grok_patterns_data.rails import PATTERNS as RAILS_PATTERNS
from apps.log_databus.grok_patterns_data.redis import PATTERNS as REDIS_PATTERNS
from apps.log_databus.grok_patterns_data.ruby import PATTERNS as RUBY_PATTERNS

ALL_PATTERNS = (
    GROK_PATTERNS
    + AWS_PATTERNS
    + BACULA_PATTERNS
    + BRO_PATTERNS
    + EXIM_PATTERNS
    + FIREWALLS_PATTERNS
    + HAPROXY_PATTERNS
    + JAVA_PATTERNS
    + JUNOS_PATTERNS
    + LINUX_SYSLOG_PATTERNS
    + MCOLLECTIVE_PATTERNS
    + MCOLLECTIVE_PATTERNS_PATTERNS
    + MONGODB_PATTERNS
    + NAGIOS_PATTERNS
    + POSTGRESQL_PATTERNS
    + RAILS_PATTERNS
    + REDIS_PATTERNS
    + RUBY_PATTERNS
)
