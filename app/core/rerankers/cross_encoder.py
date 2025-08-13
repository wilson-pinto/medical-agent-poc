import logging
from typing import List, Tuple
from sentence_transformers import CrossEncoder

# Try to import CrossEncoder, handle the case where the library is not installed.
try:
    from sentence_transformers import CrossEncoder
except ImportError:
    # If the library is missing, we'll log an error and define a dummy class
    # to prevent a hard crash on import. The actual functions will fail.
    logging.error("The 'sentence-transformers' library is not installed. Please install it with 'pip install sentence-transformers'.")
    class CrossEncoder:
        def __init__(self, *args, **kwargs):
            raise ImportError("sentence-transformers is not installed.")

logger = logging.getLogger(__name__)

# Cache for the loaded cross-encoder model
_CROSS_ENCODER_MODEL = None
_CURRENT_MODEL_NAME = None # Tracks the name of the currently loaded model

# The reranker model we selected based on our test.
RERANKER_MODEL_NAME = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"

def get_reranker_model(model_name: str = RERANKER_MODEL_NAME) -> CrossEncoder:
    """
    Loads and caches the cross-encoder model for reranking.
    This function checks if the requested model is already in the cache.
    """
    global _CROSS_ENCODER_MODEL
    global _CURRENT_MODEL_NAME

    if _CROSS_ENCODER_MODEL is not None and _CURRENT_MODEL_NAME == model_name:
        logger.info(f"Using cached model: {_CURRENT_MODEL_NAME}")
        return _CROSS_ENCODER_MODEL

    # If the requested model is different, or the cache is empty, load the new one.
    try:
        logger.info(f"Loading cross-encoder reranker model: {model_name}")
        _CROSS_ENCODER_MODEL = CrossEncoder(model_name)
        _CURRENT_MODEL_NAME = model_name
    except Exception as e:
        logger.error(f"Failed to load reranker model '{model_name}': {e}")
        # Clear the cache to ensure we try to load again next time
        _CROSS_ENCODER_MODEL = None
        _CURRENT_MODEL_NAME = None
        raise

    return _CROSS_ENCODER_MODEL

def rerank_documents(query: str, documents: List[str], model_name: str = RERANKER_MODEL_NAME) -> List[Tuple[str, float]]:
    """
    Reranks a list of documents based on their relevance to a query
    using a cross-encoder model.

    Args:
        query (str): The search query.
        documents (List[str]): A list of documents retrieved by a bi-encoder.
        model_name (str): The name of the cross-encoder model to use.

    Returns:
        List[Tuple[str, float]]: A list of tuples, where each tuple contains
        the document text and its reranked relevance score. The list is sorted
        in descending order by score.
    """
    try:
        model = get_reranker_model(model_name)
    except ImportError:
        logger.error("Skipping reranking due to missing 'sentence-transformers' library.")
        return []
    except Exception as e:
        logger.error(f"Failed to get reranker model: {e}")
        return []

    # Prepare the input pairs for the cross-encoder
    sentence_pairs = [[query, doc] for doc in documents]

    if not sentence_pairs:
        logger.warning("No documents to rerank. Returning an empty list.")
        return []

    logger.info("Reranking documents...")
    try:
        # Get the relevance scores for each pair
        scores = model.predict(sentence_pairs)

        # Combine documents with their scores and sort by score
        reranked_results = sorted(zip(documents, scores), key=lambda x: x[1], reverse=True)

        logger.info("Reranking complete.")
        return reranked_results
    except Exception as e:
        logger.error(f"Failed to rerank documents: {e}")
        return []
