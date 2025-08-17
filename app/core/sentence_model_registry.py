from sentence_transformers import SentenceTransformer, CrossEncoder

_model_cache: dict[str, SentenceTransformer] = {}

def get_sentence_model(model_name: str) -> SentenceTransformer:
    """
    Loads and returns a cached SentenceTransformer model by name.
    Avoids reloading the same model multiple times in memory.
    """
    if model_name not in _model_cache:
        print(f"🔄 Loading model: {model_name}")
        _model_cache[model_name] = SentenceTransformer(model_name)
    return _model_cache[model_name]

def get_cross_encoder_model(model_name: str) -> SentenceTransformer:
    """
    Loads and returns a cached CrossEncoder model by name.
    Avoids reloading the same model multiple times in memory.
    """
    if model_name not in _model_cache:
        print(f"🔄 Loading model: {model_name}")
        _model_cache[model_name] = CrossEncoder(model_name)
    return _model_cache[model_name]