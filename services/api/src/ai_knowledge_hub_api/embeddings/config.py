from dataclasses import dataclass


@dataclass(frozen=True)
class EmbeddingConfig:
    """
    Local CPU embedding settings for intfloat/multilingual-e5-small.

    First use downloads model weights from Hugging Face (requires network once).
    Expect roughly hundreds of MB disk and ~1 GB RAM for CPU inference.
    """

    model_name: str = "intfloat/multilingual-e5-small"
    expected_dimensions: int = 384
    max_input_tokens: int = 512
    batch_size: int = 32
    passage_prefix: str = "passage: "
    query_prefix: str = "query: "
