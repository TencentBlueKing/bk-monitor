/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */
import type { SyntaxNode } from '@lezer/common';
import type { LRParser } from '@lezer/lr';

export const ErrorId = 0;

interface ParseError {
  node: SyntaxNode;
  text: string;
}

interface ParserErrorBoundary {
  endColumn: number;
  endLineNumber: number;
  error: string;
  startColumn: number;
  startLineNumber: number;
}

export function validateQuery(
  query: string,
  interpolatedQuery: string,
  queryLines: string[],
  parser: LRParser
): false | ParserErrorBoundary[] {
  if (!query) {
    return false;
  }

  const interpolatedErrors: ParseError[] = parseQuery(interpolatedQuery, parser);
  if (!interpolatedErrors.length) {
    return false;
  }

  let parseErrors: ParseError[] = interpolatedErrors;
  if (query !== interpolatedQuery) {
    const queryErrors: ParseError[] = parseQuery(query, parser);
    parseErrors = interpolatedErrors.flatMap(
      interpolatedError =>
        queryErrors.filter(queryError => interpolatedError.text === queryError.text) || interpolatedError
    );
  }

  return parseErrors.map(parseError => findErrorBoundary(query, queryLines, parseError)).filter(isErrorBoundary);
}

function findErrorBoundary(query: string, queryLines: string[], parseError: ParseError): null | ParserErrorBoundary {
  if (queryLines.length === 1) {
    const isEmptyString = parseError.node.from === parseError.node.to;
    const errorNode = isEmptyString && parseError.node.parent ? parseError.node.parent : parseError.node;
    const error = isEmptyString ? query.substring(errorNode.from, errorNode.to) : parseError.text;
    return {
      startLineNumber: 1,
      startColumn: errorNode.from + 1,
      endLineNumber: 1,
      endColumn: errorNode.to + 1,
      error,
    };
  }

  let startPos = 0;
  let endPos = 0;
  for (let line = 0; line < queryLines.length; line++) {
    endPos = startPos + queryLines[line].length;

    if (parseError.node.from > endPos) {
      startPos += queryLines[line].length + 1;
      continue;
    }

    return {
      startLineNumber: line + 1,
      startColumn: parseError.node.from - startPos + 1,
      endLineNumber: line + 1,
      endColumn: parseError.node.to - startPos + 1,
      error: parseError.text,
    };
  }

  return null;
}

function isErrorBoundary(boundary: null | ParserErrorBoundary): boundary is ParserErrorBoundary {
  return boundary !== null;
}

function parseQuery(query: string, parser: LRParser) {
  const parseErrors: ParseError[] = [];
  const tree = parser.parse(query);
  tree.iterate({
    enter: (nodeRef): false | void => {
      if (nodeRef.type.id === ErrorId) {
        const { node } = nodeRef;
        parseErrors.push({
          node,
          text: query.substring(node.from, node.to),
        });
      }
    },
  });
  return parseErrors;
}

export const placeHolderScopedVars = {
  __interval: { text: '1s', value: '1s' },
  __rate_interval: { text: '1s', value: '1s' },
  __auto: { text: '1s', value: '1s' },
  __interval_ms: { text: '1000', value: 1000 },
  __range_ms: { text: '1000', value: 1000 },
  __range_s: { text: '1', value: 1 },
  __range: { text: '1s', value: '1s' },
};
