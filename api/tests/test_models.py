import pytest
from sqlalchemy import select

from lensor.models import Chunk, Contract

pytestmark = pytest.mark.db


async def test_tables_roundtrip(session_factory) -> None:
    async with session_factory() as session:
        contract = Contract(
            title="Supply Agreement", source="upload", text="abc def", status="queued"
        )
        session.add(contract)
        await session.flush()
        session.add_all(
            [
                Chunk(contract_id=contract.id, start_char=0, end_char=3, text="abc"),
                Chunk(contract_id=contract.id, start_char=4, end_char=7, text="def"),
            ]
        )
        await session.commit()
        contract_id = contract.id

    async with session_factory() as session:
        loaded = await session.get(Contract, contract_id)
        assert loaded is not None
        assert loaded.title == "Supply Agreement"
        assert loaded.source == "upload"
        assert loaded.status == "queued"
        assert loaded.risk_score is None
        assert loaded.created_at is not None
        chunks = (
            await session.scalars(
                select(Chunk).where(Chunk.contract_id == contract_id).order_by(Chunk.start_char)
            )
        ).all()
        assert [(c.start_char, c.end_char, c.text) for c in chunks] == [
            (0, 3, "abc"),
            (4, 7, "def"),
        ]
