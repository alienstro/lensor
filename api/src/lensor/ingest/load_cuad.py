"""Load the CUAD demo set into the database.

Run: python -m lensor.ingest.load_cuad --set demo
"""

import argparse
import asyncio
import logging
import re
from pathlib import Path

from sqlalchemy import select

from lensor.config import get_settings
from lensor.db import get_session_factory
from lensor.ingest.cuad import load_cuad, split_demo_eval
from lensor.ingest.pipeline import ingest_contract
from lensor.llm.client import OpenRouterClient
from lensor.models import Contract
from lensor.vectorstore.factory import get_vector_store

DEFAULT_JSON = Path("data/CUADv1.json")

# Two CUAD title formats:
#   A: COMPANY_MM_DD_YYYY-EX-<exhibit>-DOC TYPE[_suffix]
#   B: CompanyName_YYYYMMDD_<form>_EX-<exhibit>_<id>_EX-<exhibit>_Doc Type
_FORMAT_A = re.compile(r"^(?P<company>.+?)_\d{2}_\d{2}_(?P<year>\d{4})-EX-[^-]+-(?P<doc>.+)$")
_FORMAT_B = re.compile(r"^(?P<company>[^_]+)_(?P<year>\d{4})\d{4}_.*_EX-[^_]+_(?P<doc>[^_].*)$")
_COMPANY_SUFFIX = re.compile(r",?\s*(INC|LLC|LTD|CORP|PLC|LP)\.?$", re.IGNORECASE)
_CAMEL = re.compile(r"(?<=[a-z])(?=[A-Z])")


def _clean_company(raw: str, camel: bool) -> str:
    name = _COMPANY_SUFFIX.sub("", raw.strip())
    if camel:
        name = _CAMEL.sub(" ", name)
    return name.title() if name.isupper() else name


def display_title(cuad_title: str) -> str:
    """Make a CUAD file title readable, for example "Distributor Agreement, Acme (1999)"."""
    title = cuad_title.strip()
    for pattern, camel in ((_FORMAT_A, False), (_FORMAT_B, True)):
        match = pattern.match(title)
        if match is None:
            continue
        doc = re.sub(r"\d+$", "", match["doc"].strip())
        if pattern is _FORMAT_A:
            doc = " ".join(part.strip().title() for part in doc.split("_") if part.strip())
        else:
            doc = ", ".join(part.strip() for part in doc.split("_") if part.strip())
        company = _clean_company(match["company"], camel)
        return f"{doc}, {company} ({match['year']})"
    return title


async def main(contract_set: str, json_path: Path, limit: int | None) -> None:
    settings = get_settings()
    session_factory = get_session_factory()
    llm = OpenRouterClient(settings)
    store = get_vector_store(settings, session_factory)

    demo, evaluation = split_demo_eval(load_cuad(json_path))
    chosen = demo if contract_set == "demo" else evaluation
    if limit is not None:
        chosen = chosen[:limit]

    for index, item in enumerate(chosen, start=1):
        title = display_title(item.title)
        async with session_factory() as session:
            existing = await session.scalar(
                select(Contract).where(Contract.title == title, Contract.source == "cuad")
            )
            if existing is not None and existing.status == "ready":
                print(f"[{index}/{len(chosen)}] skip (ready): {title}")
                continue
            if existing is None:
                existing = Contract(title=title, source="cuad", text=item.text, status="queued")
                session.add(existing)
                await session.commit()
            contract_id = existing.id
        await ingest_contract(contract_id, session_factory, llm, store, settings)
        async with session_factory() as session:
            loaded = await session.get(Contract, contract_id)
            status = loaded.status if loaded else "missing"
        print(f"[{index}/{len(chosen)}] {status}: {title}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    parser = argparse.ArgumentParser(description="Load CUAD contracts into Lensor.")
    parser.add_argument("--set", dest="contract_set", choices=["demo"], default="demo")
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    asyncio.run(main(args.contract_set, args.json, args.limit))
