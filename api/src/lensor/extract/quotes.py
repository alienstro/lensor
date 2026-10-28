"""Find an LLM quote in the contract text, so that each saved clause points at real text."""

_QUOTE_MAP = str.maketrans(
    {
        "‘": "'",
        "’": "'",
        "‚": "'",
        "‛": "'",
        "“": '"',
        "”": '"',
        "„": '"',
        "‟": '"',
        " ": " ",
    }
)


def _normalize(text: str) -> tuple[str, list[int]]:
    """Lowercase, straight quotes, and one space for each whitespace run.

    Also return the index in `text` of each character of the result.
    """
    out: list[str] = []
    index: list[int] = []
    in_space = False
    for i, char in enumerate(text.translate(_QUOTE_MAP)):
        if char.isspace():
            if not in_space:
                out.append(" ")
                index.append(i)
            in_space = True
            continue
        in_space = False
        out.append(char.lower())
        index.append(i)
    return "".join(out), index


def locate_quote(text: str, quote: str) -> tuple[int, int] | None:
    """Return the (start, end) span of `quote` in `text`, or None when the text does not have it."""
    quote = quote.strip()
    if not quote:
        return None
    start = text.find(quote)
    if start >= 0:
        return start, start + len(quote)
    norm_text, index = _normalize(text)
    norm_quote, _ = _normalize(quote)
    found = norm_text.find(norm_quote)
    if found < 0:
        return None
    return index[found], index[found + len(norm_quote) - 1] + 1
