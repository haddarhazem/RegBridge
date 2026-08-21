"""Explicit local BGE-M3 query encoder used only by the research helper."""

from __future__ import annotations

import torch
from transformers import AutoModel, AutoTokenizer


class BGEQueryEncoder:
    """Mean-pool and normalize BGE-M3 query embeddings.

    The historical ingestion implementation was not found. BGE-M3's
    multilingual query path is therefore explicit and documented as a
    compatibility limitation, not claimed historical reproduction.
    """

    def __init__(self, model_name: str = "BAAI/bge-m3", device: str = "cpu") -> None:
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name).to(device).eval()
        self.device = device

    def encode(self, question: str) -> list[float]:
        batch = self.tokenizer([question], padding=True, truncation=True, return_tensors="pt").to(self.device)
        with torch.inference_mode():
            output = self.model(**batch).last_hidden_state
        mask = batch["attention_mask"].unsqueeze(-1).expand(output.size()).float()
        vector = (output * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1e-9)
        vector = torch.nn.functional.normalize(vector, p=2, dim=1)[0].cpu().tolist()
        if len(vector) != 1024:
            raise ValueError(f"BGE-M3 query vector must have 1024 dimensions, got {len(vector)}")
        return vector

