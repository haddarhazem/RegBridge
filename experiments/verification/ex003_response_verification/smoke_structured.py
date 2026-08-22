"""Developer-only synthetic EX-003 V2 structured-output smoke test."""

from __future__ import annotations

import asyncio

from .contracts import VerificationInput, VerificationOutput
from .input_projection import forbidden_fields
from .run_ex003 import v2


async def main() -> None:
    item = VerificationInput(
        question="Question synthétique de conformité",
        answer="La réponse synthétique indique une obligation.",
        public_sources=["Synthetic Authority"],
        cited_evidence_ids=["E1"],
        claims=[{"claim_id": "C1", "text": "Une obligation est indiquée.", "material": True}],
        evidence=[{
            "evidence_id": "E1",
            "organization": "Synthetic Authority",
            "source_domain": "synthetic.local",
            "url": "https://synthetic.local/evidence",
            "content": "Evidence synthétique bornée.",
        }],
    )
    assert not (set(item.model_dump()) & forbidden_fields())
    output, usage, error = await v2(item)
    if error or output is None:
        print("Structured V2 smoke: FAIL")
        print(f"Error: {error or 'no structured output'}")
        return
    assert isinstance(output, VerificationOutput)
    print("Structured V2 smoke: PASS")
    print("Schema: VerificationOutput")
    print(f"Claims: {len(output.claims)}")
    print(f"Usage keys: {sorted(usage)}")
    print("Benchmark fields supplied: NO")
    print("Private data supplied: NO")


if __name__ == "__main__":
    asyncio.run(main())
