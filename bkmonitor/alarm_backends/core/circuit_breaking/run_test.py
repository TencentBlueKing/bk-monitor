#!/usr/bin/env python3
"""
快速运行 AccessDataCircuitBreakingManager 自测脚本
[uv run] python alarm_backends/core/circuit_breaking/run_test.py
"""

import os
import sys
import django

django.setup()

# 添加项目路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_dir))))
sys.path.insert(0, project_root)

if __name__ == "__main__":
    from test_access_data_manager import main

    main()
