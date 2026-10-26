"""Prompts for clause extraction. Change PROMPT_VERSION in extractor.py when you change them."""

from lensor.clauses import CLAUSE_TYPES

# From category_descriptions.csv in github.com/TheAtticusProject/cuad (CC BY 4.0).
CLAUSE_DESCRIPTIONS: dict[str, str] = {
    "Expiration Date": "On what date will the contract's initial term expire?",
    "Renewal Term": (
        "What is the renewal term after the initial term expires? This includes automatic "
        "extensions and unilateral extensions with prior notice."
    ),
    "Notice Period to Terminate Renewal": "What is the notice period required to terminate renewal?",
    "Governing Law": "Which state/country's law governs the interpretation of the contract?",
    "Termination for Convenience": (
        "Can a party terminate this contract without cause (solely by giving a notice and "
        "allowing a waiting period to expire)?"
    ),
    "Change of Control": (
        "Does one party have the right to terminate or is consent or notice required of the "
        "counterparty if such party undergoes a change of control, such as a merger, stock sale, "
        "transfer of all or substantially all of its assets or business, or assignment by "
        "operation of law?"
    ),
    "Anti-Assignment": "Is consent or notice required of a party if the contract is assigned to a third party?",
    "Non-Compete": (
        "Is there a restriction on the ability of a party to compete with the counterparty or "
        "operate in a certain geography or business or technology sector?"
    ),
    "Cap on Liability": (
        "Does the contract include a cap on liability upon the breach of a party's obligation? "
        "This includes time limitation for the counterparty to bring claims or maximum amount "
        "for recovery."
    ),
    "Uncapped Liability": (
        "Is a party's liability uncapped upon the breach of its obligation in the contract? This "
        "also includes uncap liability for a particular type of breach such as IP infringement "
        "or breach of confidentiality obligation."
    ),
}

SYSTEM_PROMPT = """You review commercial contracts. Find these {count} clause types:

{types}

Rules:
- Return exactly one item for each clause type, with the clause_type name exactly as above.
- quotes: copy up to 3 passages word for word from the contract. Do not change, shorten, or \
join the words. Each quote is one sentence or one short passage.
- If the contract has no such clause, set found to false, quotes to [], and risk_level to null.
- summary: one plain sentence that a person who is not a lawyer understands.
- risk_level: high, medium, or low, for the party that reviews the contract.
- Do not give legal advice."""


def system_prompt() -> str:
    types = "\n".join(f"- {name}: {CLAUSE_DESCRIPTIONS[name]}" for name in CLAUSE_TYPES)
    return SYSTEM_PROMPT.format(count=len(CLAUSE_TYPES), types=types)


def full_text_messages(text: str) -> list[dict]:
    return [
        {"role": "system", "content": system_prompt()},
        {"role": "user", "content": f"Contract:\n<<<\n{text}\n>>>"},
    ]


def excerpt_messages(excerpts: list[str]) -> list[dict]:
    body = "\n\n---\n\n".join(excerpts)
    return [
        {"role": "system", "content": system_prompt()},
        {
            "role": "user",
            "content": (
                "These are excerpts of one contract, not the full text. If no excerpt has a "
                f"clause type, set found to false.\n\nExcerpts:\n<<<\n{body}\n>>>"
            ),
        },
    ]
