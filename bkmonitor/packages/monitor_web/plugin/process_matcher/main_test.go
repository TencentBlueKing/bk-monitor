// MIT License

// Copyright (c) 2021~2025 腾讯蓝鲸

// Permission is hereby granted, free of charge, to any person obtaining a copy
// of this software and associated documentation files (the "Software"), to deal
// in the Software without restriction, including without limitation the rights
// to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
// copies of the Software, and to permit persons to whom the Software is
// furnished to do so, subject to the following conditions:

// The above copyright notice and this permission notice shall be included in all
// copies or substantial portions of the Software.

// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
// IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
// FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
// AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
// LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
// OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
// SOFTWARE.

package main

import (
	"testing"
)

func TestProcessMatcher_Match(t *testing.T) {
	tests := []struct {
		name                      string
		matchPattern              string
		excludePattern            string
		extractDimensionsPattern  string
		extractProcessNamePattern string
		processStr                string
		want                      []*ProcessMatchResult
	}{
		{
			name:                      "基本匹配测试",
			matchPattern:              "nginx",
			excludePattern:            "",
			extractDimensionsPattern:  "",
			extractProcessNamePattern: "",
			processStr:                "/usr/sbin/nginx -g daemon off;\n/usr/bin/python3 app.py",
			want: []*ProcessMatchResult{
				{
					ProcessName: "nginx",
					Dimensions:  map[string]string{},
				},
			},
		},
		{
			name:                      "排除模式测试",
			matchPattern:              "python",
			excludePattern:            "test",
			extractDimensionsPattern:  "",
			extractProcessNamePattern: "",
			processStr:                "/usr/bin/python3 app.py\n/usr/bin/python3 test.py",
			want: []*ProcessMatchResult{
				{
					ProcessName: "python3",
					Dimensions:  map[string]string{},
				},
			},
		},
		{
			name:                      "维度提取测试",
			matchPattern:              "python",
			excludePattern:            "",
			extractDimensionsPattern:  `port=(?P<port>\d+)`,
			extractProcessNamePattern: "",
			processStr:                "/usr/bin/python3 app.py --port=8080",
			want: []*ProcessMatchResult{
				{
					ProcessName: "python3",
					Dimensions: map[string]string{
						"port": "8080",
					},
				},
			},
		},
		{
			name:                      "默认进程名",
			matchPattern:              "python",
			excludePattern:            "",
			extractDimensionsPattern:  "",
			extractProcessNamePattern: "app.py",
			processStr:                "/usr/bin/python3 app.py",
			want: []*ProcessMatchResult{
				{
					ProcessName: "app.py",
					Dimensions:  map[string]string{},
				},
			},
		},
		{
			name:                      "进程名提取测试",
			matchPattern:              "python",
			excludePattern:            "",
			extractDimensionsPattern:  "",
			extractProcessNamePattern: `(python\d*)`,
			processStr:                "/usr/bin/python3 app.py",
			want: []*ProcessMatchResult{
				{
					ProcessName: "python3",
					Dimensions:  map[string]string{},
				},
			},
		},

	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			matcher := NewProcessMatcher(
				tt.matchPattern,
				tt.excludePattern,
				tt.extractDimensionsPattern,
				tt.extractProcessNamePattern,
			)
			got := matcher.Match(tt.processStr)

			if len(got) != len(tt.want) {
				t.Errorf("Match() got %d results, want %d", len(got), len(tt.want))
				return
			}

			for i, result := range got {
				if result.ProcessName != tt.want[i].ProcessName {
					t.Errorf("ProcessName = %v, want %v", result.ProcessName, tt.want[i].ProcessName)
				}

				for k, v := range tt.want[i].Dimensions {
					if result.Dimensions[k] != v {
						t.Errorf("Dimensions[%s] = %v, want %v", k, result.Dimensions[k], v)
					}
				}
			}
		})
	}
}
