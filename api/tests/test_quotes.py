from lensor.extract.quotes import locate_quote
from lensor.extract.schema import ExtractionResult


def test_locate_quote_exact() -> None:
    assert locate_quote("abc def", "def") == (4, 7)


def test_locate_quote_missing_returns_none() -> None:
    assert locate_quote("abc def", "xyz") is None
    assert locate_quote("abc def", "   ") is None


def test_locate_quote_whitespace_and_quotes() -> None:
    text = "Intro. The Licensee shall  not\nassign the “Licensed Rights”. End."
    quote = 'shall not assign the "licensed rights"'

    span = locate_quote(text, quote)

    assert span is not None
    start, end = span
    assert text[start:end] == "shall  not\nassign the “Licensed Rights”"


def test_locate_quote_trims_quote_whitespace() -> None:
    text = "Term: five (5) years."
    assert locate_quote(text, "  five (5) years \n") == (6, 20)


def test_extraction_schema_limits_quotes() -> None:
    result = ExtractionResult.model_validate(
        {
            "clauses": [
                {
                    "clause_type": "Renewal Term",
                    "found": True,
                    "quotes": ["a", "b", "c", "d"],
                    "summary": "s",
                    "risk_level": "high",
                }
            ]
        }
    )
    assert result.clauses[0].quotes == ["a", "b", "c"]
