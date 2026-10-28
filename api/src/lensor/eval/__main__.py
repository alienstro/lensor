"""Evaluate the clause extraction against the CUAD labels.

Run: python -m lensor.eval --contracts 50 --model <id> --mode full|retrieval [--retrieval-check]
The CLI uses only the evaluation set, which the demo and the prompts never see.
"""

import argparse
import asyncio
import logging
from collections import Counter
from pathlib import Path
from typing import Literal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lensor.clauses import CLAUSE_TYPES
from lensor.config import get_settings
from lensor.db import get_session_factory
from lensor.eval.metrics import prf, recall_at_k, score_contract
from lensor.extract.extractor import PROMPT_VERSION, extract_clauses
from lensor.extract.prompts import CLAUSE_DESCRIPTIONS
from lensor.ingest.chunker import chunk_text
from lensor.ingest.cuad import CuadContract, load_cuad, split_demo_eval
from lensor.llm.client import LLMClient, LLMError, OpenRouterClient
from lensor.models import Chunk, Contract, EvalResult, EvalRun
from lensor.vectorstore.base import ChunkHit, ChunkRecord, VectorStore
from lensor.vectorstore.factory import get_vector_store

logger = logging.getLogger(__name__)

Mode = Literal["full", "retrieval"]
SessionFactory = async_sessionmaker[AsyncSession]
TOP_K = 5


async def _index(
    contract: CuadContract, session_factory: SessionFactory, llm: LLMClient, store: VectorStore
) -> int:
    """Store a temporary copy of an eval contract (source "eval") with its chunks and vectors."""
    async with session_factory() as session:
        row = Contract(title=contract.title, source="eval", text=contract.text, status="ready")
        session.add(row)
        await session.flush()
        chunks = [
            Chunk(contract_id=row.id, start_char=c.start_char, end_char=c.end_char, text=c.text)
            for c in chunk_text(contract.text)
        ]
        session.add_all(chunks)
        await session.commit()
        contract_id = row.id
    vectors = await llm.embed([c.text for c in chunks])
    await store.upsert(
        [
            ChunkRecord(c.id, contract_id, c.start_char, c.end_char, c.text, v)
            for c, v in zip(chunks, vectors, strict=True)
        ]
    )
    return contract_id


async def _remove(contract_id: int, session_factory: SessionFactory, store: VectorStore) -> None:
    await store.delete_contract(contract_id)
    async with session_factory() as session:
        await session.execute(delete(Contract).where(Contract.id == contract_id))
        await session.commit()


async def run_eval(
    contracts: list[CuadContract],
    llm: LLMClient,
    model: str,
    mode: Mode,
    session_factory: SessionFactory,
    store: VectorStore,
    retrieval_check: bool = False,
) -> int:
    """Run the extraction on each contract, score it, and save one EvalRun with 10 results."""
    async with session_factory() as session:
        run = EvalRun(
            model=model,
            mode=mode,
            prompt_version=PROMPT_VERSION,
            contract_count=len(contracts),
            cost_usd=0.0,
            status="running",
        )
        session.add(run)
        await session.commit()
        run_id = run.id

    counts: dict[str, Counter[str]] = {name: Counter() for name in CLAUSE_TYPES}
    recall_hits: dict[str, list[float]] = {name: [] for name in CLAUSE_TYPES}
    cost = 0.0
    failed = 0
    query_vectors: list[list[float]] | None = None

    for index, contract in enumerate(contracts, start=1):
        contract_id: int | None = None
        try:
            retrieve = None
            if mode == "retrieval" or retrieval_check:
                contract_id = await _index(contract, session_factory, llm, store)
                cid = contract_id

                async def retrieve(query: str, cid: int = cid) -> list[ChunkHit]:
                    vector = (await llm.embed([query]))[0]
                    return await store.search(vector, TOP_K, [cid])

            clauses, usage = await extract_clauses(
                contract.text, llm, model, mode=mode, retrieve=retrieve
            )
            cost += usage.cost_usd or 0.0
            for clause in clauses:
                counts[clause.clause_type].update(
                    score_contract(clause.spans, contract.labels.get(clause.clause_type, []))
                )
            if retrieval_check and contract_id is not None:
                if query_vectors is None:
                    query_vectors = await llm.embed(
                        [f"{n}: {CLAUSE_DESCRIPTIONS[n]}" for n in CLAUSE_TYPES]
                    )
                for name, vector in zip(CLAUSE_TYPES, query_vectors, strict=True):
                    labels = contract.labels.get(name, [])
                    if labels:
                        found = await store.search(vector, TOP_K, [contract_id])
                        recall_hits[name].append(recall_at_k(found, labels))
            print(f"[{index}/{len(contracts)}] ok: {contract.title}")
        except LLMError as exc:
            failed += 1
            print(f"[{index}/{len(contracts)}] failed: {contract.title}: {exc}")
        finally:
            if contract_id is not None:
                await _remove(contract_id, session_factory, store)

    async with session_factory() as session:
        for name in CLAUSE_TYPES:
            c = counts[name]
            precision, recall, f1 = prf(c["tp"], c["fp"], c["fn"])
            scores = recall_hits[name]
            session.add(
                EvalResult(
                    run_id=run_id,
                    clause_type=name,
                    precision=precision,
                    recall=recall,
                    f1=f1,
                    recall_at_5=sum(scores) / len(scores) if scores else None,
                )
            )
        run_row = await session.get(EvalRun, run_id)
        assert run_row is not None
        run_row.cost_usd = cost
        run_row.status = "partial" if failed else "done"
        await session.commit()
    return run_id


async def _print_results(session_factory: SessionFactory, run_id: int) -> None:
    async with session_factory() as session:
        run = await session.get(EvalRun, run_id)
        results = (
            await session.scalars(select(EvalResult).where(EvalResult.run_id == run_id))
        ).all()
    assert run is not None
    print(f"\nRun {run_id}: model {run.model}, mode {run.mode}, status {run.status}")
    print(f"Cost: ${run.cost_usd:.4f}\n")
    print(f"{'Clause type':<36}{'P':>6}{'R':>6}{'F1':>6}{'R@5':>6}")
    for r in sorted(results, key=lambda x: CLAUSE_TYPES.index(x.clause_type)):
        r5 = f"{r.recall_at_5:.2f}" if r.recall_at_5 is not None else "-"
        print(f"{r.clause_type:<36}{r.precision:6.2f}{r.recall:6.2f}{r.f1:6.2f}{r5:>6}")


async def main(args: argparse.Namespace) -> None:
    settings = get_settings()
    session_factory = get_session_factory()
    _, evaluation = split_demo_eval(load_cuad(args.json))
    run_id = await run_eval(
        evaluation[: args.contracts],
        OpenRouterClient(settings),
        args.model or settings.llm_model_extract,
        args.mode,
        session_factory,
        get_vector_store(settings, session_factory),
        retrieval_check=args.retrieval_check,
    )
    await _print_results(session_factory, run_id)


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    parser = argparse.ArgumentParser(description="Evaluate Lensor against the CUAD labels.")
    parser.add_argument("--contracts", type=int, default=50)
    parser.add_argument(
        "--model", default=None, help="OpenRouter model id. Default: LLM_MODEL_EXTRACT."
    )
    parser.add_argument("--mode", choices=["full", "retrieval"], default="full")
    parser.add_argument("--retrieval-check", action="store_true", help="Also measure recall@5.")
    parser.add_argument("--json", type=Path, default=Path("data/CUADv1.json"))
    asyncio.run(main(parser.parse_args()))
