"""
Java 相关 Grok 模式数据
对应 pygrok patterns/java 文件

注意：java 文件中存在重复定义的 JAVACLASS、JAVAFILE、JAVASTACKTRACEPART，
pygrok 会使用最后加载的版本，因此这里只保留最终有效的定义。
"""

PATTERNS = [
    {
        "name": "JAVACLASS",
        "pattern": r"(?:[a-zA-Z0-9-]+\.)+[A-Za-z0-9$]+",
        "sample": "com.example.service.UserService",
        "description": "匹配 Java 完全限定类名",
    },
    {
        "name": "JAVAFILE",
        "pattern": r"(?:[A-Za-z0-9_.-]+)",
        "sample": "UserService.java",
        "description": "匹配 Java 源文件名",
    },
    {
        "name": "JAVAMETHOD",
        "pattern": r"(?:(<init>)|[a-zA-Z$_][a-zA-Z$_0-9]*)",
        "sample": "getUserById",
        "description": "匹配 Java 方法名，支持特殊的 <init> 构造方法",
    },
    {
        "name": "JAVASTACKTRACEPART",
        "pattern": r"at %{JAVACLASS:class}\.%{WORD:method}\(%{JAVAFILE:file}:%{NUMBER:line}\)",
        "sample": "at com.example.service.UserService.getUserById(UserService.java:42)",
        "description": "匹配 Java 堆栈跟踪的单行内容",
    },
    {
        "name": "JAVATHREAD",
        "pattern": r"(?:[A-Z]{2}-Processor[\d]+)",
        "sample": "TP-Processor25",
        "description": "匹配 Java 线程名称（如 Tomcat 处理器线程）",
    },
    {
        "name": "JAVALOGMESSAGE",
        "pattern": r"(.*)",
        "sample": "User not found: id=12345",
        "description": "匹配 Java 日志消息的内容部分（任意文本）",
    },
    {
        "name": "CATALINA_DATESTAMP",
        "pattern": r"%{MONTH} %{MONTHDAY}, 20%{YEAR} %{HOUR}:?%{MINUTE}(?::?%{SECOND}) (?:AM|PM)",
        "sample": "Mar 15, 2024 2:30:59 PM",
        "description": "匹配 Apache Catalina（Tomcat）日志时间戳格式",
    },
    {
        "name": "TOMCAT_DATESTAMP",
        "pattern": r"20%{YEAR}-%{MONTHNUM}-%{MONTHDAY} %{HOUR}:?%{MINUTE}(?::?%{SECOND}) %{ISO8601_TIMEZONE}",
        "sample": "2024-03-15 14:30:59,527 +0800",
        "description": "匹配 Tomcat 日志时间戳格式（ISO 格式带时区）",
    },
    {
        "name": "CATALINALOG",
        "pattern": r"%{CATALINA_DATESTAMP:timestamp} %{JAVACLASS:class} %{JAVALOGMESSAGE:logmessage}",
        "sample": "Mar 15, 2024 2:30:59 PM com.example.service.UserService User not found: id=12345",
        "description": "匹配 Apache Catalina（Tomcat）日志行格式",
    },
    {
        "name": "TOMCATLOG",
        "pattern": r"%{TOMCAT_DATESTAMP:timestamp} \| %{LOGLEVEL:level} \| %{JAVACLASS:class} - %{JAVALOGMESSAGE:logmessage}",
        "sample": "2024-03-15 14:30:59,527 +0800 | ERROR | com.example.service.UserService - User not found: id=12345",
        "description": "匹配 Tomcat 自定义日志格式（时间戳 | 级别 | 类名 - 消息）",
    },
]
