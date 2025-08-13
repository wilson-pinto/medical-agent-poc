# test_reranker.py
import logging
import os
import sys

# Add the 'app/core/rerankers' directory to the system path
# This allows the script to find and import the cross_encoder module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'app', 'core', 'rerankers')))

# Set up basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Import the function from our main module
try:
    from cross_encoder import rerank_documents
except ImportError as e:
    logging.error(f"Failed to import rerank_documents. Ensure cross_encoder.py is in the correct path. Error: {e}")
    sys.exit(1)

def run_test_for_model(model_name: str):
    """
    Runs a test with a specific reranker model.
    """
    logging.info(f"--- Running a direct test with model: {model_name} ---")

    # Define a sample query and a list of documents
    # The new query and documents are designed to be more nuanced to better test the rerankers.
    query = "takst for kirurgisk inngrep" # The fee for a surgical procedure
    documents = [
        "Takst for kirurgisk inngrep er definert i takstgruppe A.", # Most relevant document
        "Regelverk for takstgruppe C beskriver takster for kirurgiske inngrep.", # Highly relevant, but potentially less specific
        "Takst for radiologiske undersøkelser er definert i takstgruppe R.", # Irrelevant but similar medical context
        "Takst for fysioterapi er definert i takstgruppe F.", # Irrelevant topic
        "Kirurgisk assistanse er et annet takstområde." # Mentions "surgical" but is a different concept
    ]

    # Call the reranking function
    try:
        reranked_results = rerank_documents(query, documents, model_name=model_name)

        # Print the results
        if reranked_results:
            logging.info("Reranking successful. Results (sorted by relevance):")
            for doc, score in reranked_results:
                print(f"Score: {score:.4f} | Document: '{doc}'")
        else:
            logging.warning("Reranking returned an empty list. Please check the logs for errors.")

    except Exception as e:
        logging.error(f"An error occurred during the test run with model {model_name}: {e}")

if __name__ == "__main__":
    # Ensure the script can find the 'app' directory if it's not in the path
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    # Run the test for the first model
    run_test_for_model("cross-encoder/mmarco-mMiniLMv2-L12-H384-v1")
    print("\n" + "="*50 + "\n") # Separator for clarity
    # Run the test for the second model
    run_test_for_model("BAAI/bge-reranker-base")
