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
	"flag"
	"log/slog"
	"path/filepath"
	"regexp"
	"strings"
)

type ProcessMatcher struct {
	matchPattern              string
	excludePattern            *regexp.Regexp
	extractDimensionsPattern  *regexp.Regexp
	extractProcessNamePattern *regexp.Regexp
}

type ProcessMatchResult struct {
	ProcessName string
	Dimensions  map[string]string
}

func NewProcessMatcher(matchPattern, excludePattern, extractDimensionsPattern, extractProcessNamePattern string) *ProcessMatcher {
	var excludeRegx, dimsRegx, nameRegx *regexp.Regexp
	if excludePattern != "" {
		excludeRegx = regexp.MustCompile(excludePattern)
	}
	if extractDimensionsPattern != "" {
		dimsRegx = regexp.MustCompile(extractDimensionsPattern)
	}
	if extractProcessNamePattern != "" {
		nameRegx = regexp.MustCompile(extractProcessNamePattern)
	}

	return &ProcessMatcher{
		matchPattern:              matchPattern,
		excludePattern:            excludeRegx,
		extractDimensionsPattern:  dimsRegx,
		extractProcessNamePattern: nameRegx,
	}
}

func (c *ProcessMatcher) Match(processStr string) []*ProcessMatchResult {
	var results []*ProcessMatchResult

	// split the process string into lines
	lines := strings.Split(processStr, "\n")

	// iterate over each line and check for matches
	for _, line := range lines {
		if c.match(line) {
			// extract dimensions and process name
			dims := c.ExtractDimensions(line)
			processName := c.ExtractProcessName(line)

			result := &ProcessMatchResult{
				ProcessName: processName,
				Dimensions:  dims,
			}
			results = append(results, result)
		}
	}

	return results
}

func (c *ProcessMatcher) match(name string) bool {
	// 如果匹配到了除外正则，则跳过该进程
	if c.excludePattern != nil && c.excludePattern.MatchString(name) {
		// 如果匹配到了除外正则，则跳过该进程
		slog.Debug("proccustom: exclude case matched.")
		return false
	}

	if c.matchPattern == "" {
		return false
	}

	// 否则如果进程名包含表达式，就算匹配成功
	return strings.Contains(name, c.matchPattern)
}

func (c *ProcessMatcher) ExtractDimensions(name string) map[string]string {
	ret := make(map[string]string)
	if c.extractDimensionsPattern == nil {
		return ret
	}

	names := c.extractDimensionsPattern.SubexpNames()
	slog.Debug("proccustom: dimension regex", "subnames", names)
	// 获取所有维度分组，并取最后匹配到的不为空的字符串作为实际上报的信息
	subMatches := c.extractDimensionsPattern.FindAllStringSubmatch(name, -1)
	for _, subMatch := range subMatches {
		for index, matchInstance := range subMatch {
			// 第一个匹配项略过
			if index == 0 {
				continue
			}
			// 根据维度名对应关系，填充额外维度信息
			if names[index] != "" {
				ret[names[index]] = matchInstance
			}
		}
	}
	return ret
}

func (c *ProcessMatcher) ExtractProcessName(name string) string {
	// 如果未配置 process_name 则获取基础二进制名上报
	if c.extractProcessNamePattern == nil {
		fields := strings.Fields(name)
		baseName := filepath.Base(fields[0])
		return baseName
	}

	// 如果没有传入分组，则将配置提供的字符串作为 process_name 维度上报
	if c.extractProcessNamePattern.NumSubexp() == 0 {
		return c.extractProcessNamePattern.String()
	}

	var last string
	// 获取所有维度分组，并取最后一个
	subMatches := c.extractProcessNamePattern.FindAllStringSubmatch(name, -1)
	for _, subMatch := range subMatches {
		for _, matchInstance := range subMatch {
			last = matchInstance
		}
	}
	return last
}

func main() {
	var matchPattern, excludePattern, extractDimensionsPattern, extractProcessNamePattern, processes string
	flag.StringVar(&matchPattern, "match", "", "match process name")
	flag.StringVar(&excludePattern, "exclude", "", "exclude process name")
	flag.StringVar(&extractDimensionsPattern, "dimensions", "", "dimensions")
	flag.StringVar(&extractProcessNamePattern, "process_name", "", "process name")
	flag.StringVar(&processes, "processes", "", "processes to match")

	flag.Parse()

	matcher := NewProcessMatcher(matchPattern, excludePattern, extractDimensionsPattern, extractProcessNamePattern)
	results := matcher.Match(processes)
	for _, result := range results {
		slog.Info("matched process", "name", result.ProcessName, "dimensions", result.Dimensions)
	}
}