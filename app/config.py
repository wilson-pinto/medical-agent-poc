# import os
# from dotenv import load_dotenv
#
# load_dotenv()
#
# # ---------------------------
# # API Keys
# # ---------------------------
# GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # Optional, keep for future use
#
# # ---------------------------
# # LLM Selection
# # ---------------------------
# # If True, use Gemini cloud LLM. If False, use local LLM.
# USE_GEMINI = os.getenv("USE_GEMINI", "false").lower() == "true"
# USE_GEMINI_FOR_PATIENT_SUMMARY = os.getenv("USE_GEMINI_FOR_PATIENT_SUMMARY", "false").lower() == "true"
# GEMINI_PATIENT_SUMMARY_API_KEY = os.getenv("GEMINI_PATIENT_SUMMARY_API_KEY")
#
#
# # ---------------------------
# # Local LLM Configuration
# # ---------------------------
# # Path to the local LLM model (choose one model only)
# # LOCAL_LLM_PATH = os.path.join(
# #     os.path.dirname(os.path.abspath(__file__)),
# #     "models",
# #     "mistral-7b",
# #     "mistral-7b-instruct-v0.2.Q4_K_M.gguf"
# # )
# # For llama-cpp-python, point to the GGUF or DLL:
# LOCAL_LLM_PATH = os.path.join(
#     os.path.dirname(os.path.abspath(__file__)),
#     "..",  # go up to project root
#     "models",
#     "llama-b6018-bin-win-cpu-x64",
#     "ggml-base.dll"  # main model file
# )
#
# # Optional: you can define the backend if needed (e.g., llama-cpp-python)
# LOCAL_LLM_BACKEND = os.getenv("LOCAL_LLM_BACKEND", "llama_cpp")  # default to llama-cpp-python
import os
from dotenv import load_dotenv

load_dotenv()

# ---------------------------
# API Keys
# ---------------------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # Optional, keep for future use

# ---------------------------
# LLM Selection
# ---------------------------
# If True, use Gemini cloud LLM. If False, use local LLM.
USE_GEMINI = os.getenv("USE_GEMINI", "false").lower() == "true"
USE_GEMINI_FOR_PATIENT_SUMMARY = os.getenv("USE_GEMINI_FOR_PATIENT_SUMMARY", "false").lower() == "true"
GEMINI_PATIENT_SUMMARY_API_KEY = os.getenv("GEMINI_PATIENT_SUMMARY_API_KEY")


# ---------------------------
# Local LLM Configuration
# ---------------------------
# Path to the local LLM model (choose one model only)
LOCAL_LLM_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..",  # go up to project root
    "models",
    "mistral-7b",
    "mistral-7b-instruct-v0.2.Q4_K_M.gguf"
)
# For llama-cpp-python, point to the GGUF or DLL:
# LOCAL_LLM_PATH = os.path.join(
#     os.path.dirname(os.path.abspath(__file__)),
#     "..",  # go up to project root
#     "models",
#     "llama-b6018-bin-win-cpu-x64",
#     "ggml-base.dll"  # main model file
# )

# Optional: you can define the backend if needed (e.g., llama-cpp-python)
LOCAL_LLM_BACKEND = os.getenv("LOCAL_LLM_BACKEND", "llama_cpp")  # default to llama-cpp-python