import pytest
import sqlparse
from sqlparse.exceptions import SQLParseError
from sqlparse.lexer import tokenize


@pytest.mark.parametrize("left,inner,right", [("(", "1", ")"), ("[", "", "]")])
def test_grouping_depth_limit(left, inner, right):
    at_limit = "SELECT " + left * 100 + inner + right * 100
    above_limit = "SELECT " + left * 101 + inner + right * 101
    assert str(sqlparse.parse(at_limit)[0]) == at_limit
    with pytest.raises(SQLParseError, match="Maximum grouping depth"):
        sqlparse.parse(above_limit)


def test_grouping_depth_counts_mixed_groups():
    def query(parentheses):
        return "BEGIN " * 50 + "SELECT " + "(" * parentheses + "1" + ")" * parentheses + " END" * 50

    at_limit = query(50)
    assert str(sqlparse.parse(at_limit)[0]) == at_limit
    with pytest.raises(SQLParseError, match="Maximum grouping depth"):
        sqlparse.parse(query(51))


def test_grouping_token_limit_preserves_large_query_at_limit():
    query = "SELECT value FROM sample WHERE tag IN (" + ",".join(["'host'"] * 4992) + ")"
    at_limit = query + ";"
    above_limit = query + " ;"
    assert len(list(tokenize(at_limit))) == 10000
    assert len(list(tokenize(above_limit))) == 10001
    assert str(sqlparse.parse(at_limit)[0]) == at_limit
    with pytest.raises(SQLParseError, match="Maximum number of tokens"):
        sqlparse.parse(above_limit)
