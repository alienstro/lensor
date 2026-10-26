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

_TITLE_RE = re.compile(r"^(?P<company>[^_]+)_\d{1,2}_\d{1,2}_(?P<year>\d{4})-EX-[^-]+-(?P<doc>.+)$")


def display_title(cuad_title: str) -> str:
    """Make a CUAD file title readable, for example "Distributor Agreement, Acme (1999)"."""
    match = _TITLE_RE.match(cuad_title.strip())
    if match is None:
        return cuad_title.strip()
    doc = match["doc"].strip().title()
    company = match["company"].strip().title()
    return f"{doc}, {company} ({match['year']})"


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
