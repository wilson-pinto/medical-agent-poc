# # app/agents/helfo_agent.py
# import os
# import json
# import yaml
# from typing import List, Dict, Any, TypedDict
# from dotenv import load_dotenv
#
# from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer
# from presidio_analyzer.nlp_engine import SpacyNlpEngine
# from presidio_anonymizer import AnonymizerEngine
# from presidio_anonymizer.entities import OperatorConfig
#
# # FAISS search
# from app.core.search_service_codes import search_service_codes
# from app.core.search_diagnosis import search_diagnosis_with_explanation
#
# # Load environment variables
# load_dotenv()
# print("[DEBUG] Using helfo_agent.py version")  # in helfo_agent.py
#
#
# # ------------------- HELFO Rules -------------------
# with open("data/takst_rules.yaml", "r", encoding="utf-8") as f:
#     TAKST_RULES = yaml.safe_load(f)
#
# # ------------------- Gemini Setup -------------------
# try:
#     import google.generativeai as genai
#     GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
#     if GEMINI_API_KEY:
#         genai.configure(api_key=GEMINI_API_KEY)
#         GEMINI_MODEL = genai.GenerativeModel("gemini-1.5-flash")
#         print("Gemini Model configured successfully.")
#     else:
#         GEMINI_MODEL = None
#         print("GEMINI_API_KEY not found. Gemini node will be skipped.")
# except ImportError:
#     GEMINI_MODEL = None
#     print("google.generativeai not installed. Gemini node will be skipped.")
#
# # ------------------- Presidio Setup -------------------
# nlp_engine = SpacyNlpEngine()
# try:
#     nlp_engine.load({"en": "en_core_web_sm"})
# except Exception as e:
#     print(f"Error loading English SpaCy model: {e}")
#
# analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["en"])
# anonymizer = AnonymizerEngine()
#
# # ------------------- Custom Recognizers -------------------
# class FNRRecognizer(PatternRecognizer):
#     def __init__(self):
#         patterns = [Pattern(name="FNR", regex=r"\b\d{11}\b", score=0.9)]
#         super().__init__(supported_entity="FNR", patterns=patterns, context=["national id", "ssn"], supported_language="en")
#
# class PhoneNumberRecognizer(PatternRecognizer):
#     def __init__(self):
#         patterns = [Pattern(name="PHONE_NUMBER", regex=r"\b\d{10}\b", score=0.8)]
#         super().__init__(supported_entity="PHONE_NUMBER", patterns=patterns, context=["phone", "mobile"], supported_language="en")
#
# class PersonRecognizer(PatternRecognizer):
#     def __init__(self):
#         patterns = [Pattern(name="PERSON", regex=r"\b[A-Z][a-z]+ [A-Z][a-z]+\b", score=0.7)]
#         super().__init__(supported_entity="PERSON", patterns=patterns, context=["patient", "name", "doctor"], supported_language="en")
#
# class DateRecognizer(PatternRecognizer):
#     def __init__(self):
#         patterns = [
#             Pattern(name="DATE_TIME", regex=r"\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b", score=0.9),
#             Pattern(name="DATE_TIME", regex=r"\b\d{4}-\d{2}-\d{2}\b", score=0.9)
#         ]
#         super().__init__(supported_entity="DATE_TIME", patterns=patterns, context=["date", "birthdate", "time"], supported_language="en")
#
# # Register all recognizers
# for rec in [FNRRecognizer(), PhoneNumberRecognizer(), PersonRecognizer(), DateRecognizer()]:
#     analyzer.registry.add_recognizer(rec)
#
# # ------------------- LangGraph -------------------
# from langgraph.graph import StateGraph, END
#
# class AgentState(TypedDict):
#     soap_note: str
#     anonymized_note: str
#     diagnoses: List[Dict]
#     service_codes: List[Dict]
#     validation_results: Dict
#     pending_questions: List[Dict]
#
# # ------------------- HelfoAgent -------------------
# class HelfoAgent:
#     def __init__(self, user_id: str):
#         self.user_id = user_id
#         self.app = self._build_graph()
#         self.current_state: AgentState = {}
#
#     # ---------------- Helper Methods ----------------
#     def _anonymize_soap(self, text: str) -> str:
#         results = analyzer.analyze(text=text, language="en")
#         if results:
#             operators = {
#                 "PERSON": OperatorConfig("replace", {"new_value": "[NAME]"}),
#                 "PHONE_NUMBER": OperatorConfig("replace", {"new_value": "[PHONE]"}),
#                 "FNR": OperatorConfig("replace", {"new_value": "[FNR]"}),
#                 "DATE_TIME": OperatorConfig("replace", {"new_value": "[DATE]"}),
#             }
#             return anonymizer.anonymize(text=text, analyzer_results=results, operators=operators).text
#         return text
#
#     def _extract_concepts(self, text: str) -> List[str]:
#         return [s.strip() for s in text.split(".") if s.strip()]
#
#     def _validate_against_rules(self, note: str, codes: List[str]) -> Dict:
#         results = []
#         for code in codes:
#             rule = TAKST_RULES.get(code, {})
#             missing_terms = [term for term in rule.get("required_terms", []) if term.lower() not in note.lower()]
#             severity = "pass" if not missing_terms else rule.get("severity", "fail")
#             results.append({
#                 "code": code,
#                 "valid": severity == "pass",
#                 "missing_terms": missing_terms,
#                 "severity": severity
#             })
#         return {"results": results}
#
#     def _plan_questions(self, validation_results: Dict) -> List[Dict]:
#         missing_terms = {term for r in validation_results.get("results", []) for term in r.get("missing_terms", [])}
#         return [{"id": f"q_{term}", "text": f"Can you provide {term}?"} for term in missing_terms]
#
#     # ---------------- Nodes ----------------
#     def extract_diagnoses_node(self, state: AgentState) -> Dict[str, Any]:
#         anon_note = self._anonymize_soap(state.get("soap_note", ""))
#         concepts = self._extract_concepts(anon_note)
#         diagnoses = search_diagnosis_with_explanation(concepts, top_k=3)
#         return {"anonymized_note": anon_note, "diagnoses": diagnoses}
#
#     def predict_service_codes_node(self, state: AgentState) -> Dict[str, Any]:
#         candidates_raw = search_service_codes(state.get("anonymized_note", ""), top_k=5)
#         # Ensure all candidates are dicts with "code"
#         candidates = [{"code": c} if isinstance(c, str) else c for c in candidates_raw]
#         return {"service_codes": candidates}
#
#     def gemini_reasoning_node(self, state: AgentState) -> Dict[str, Any]:
#         if not GEMINI_MODEL or not state.get("service_codes"):
#             return {}
#         refined = []
#         generation_config = {"response_mime_type": "application/json"}
#         for candidate in state.get("service_codes", []):
#             code_val = candidate.get("code", "")
#             prompt = f"""
# You are a medical billing AI.
# SOAP note: "{state.get('anonymized_note', '')}"
# Candidate service code: "{code_val}"
#
# Return JSON: {{"code": "{code_val}", "reasoning": "<text>", "recommended_action": "<text>"}}
# """
#             try:
#                 response = GEMINI_MODEL.generate_content(prompt, generation_config=generation_config).text
#                 gem_resp = json.loads(response)
#                 candidate["gemini_reasoning"] = gem_resp.get("reasoning")
#                 candidate["recommended_action"] = gem_resp.get("recommended_action")
#                 refined.append(candidate)
#             except Exception as e:
#                 print(f"Gemini failed: {e}. Skipping reasoning for {code_val}.")
#                 refined.append(candidate)
#         return {"service_codes": refined}
#
#     def validate_service_codes_node(self, state: AgentState) -> Dict[str, Any]:
#         codes = [c.get("code", "") for c in state.get("service_codes", [])]
#         results = self._validate_against_rules(state.get("anonymized_note", ""), codes)
#         questions = self._plan_questions(results)
#         return {"validation_results": results, "pending_questions": questions}
#
#     # ---------------- Graph ----------------
#     def _build_graph(self) -> StateGraph:
#         graph = StateGraph(AgentState)
#         graph.add_node("extract_diagnoses", self.extract_diagnoses_node)
#         graph.add_node("predict_service_codes", self.predict_service_codes_node)
#         graph.add_node("gemini_reasoning", self.gemini_reasoning_node)
#         graph.add_node("validate_service_codes", self.validate_service_codes_node)
#
#         graph.set_entry_point("extract_diagnoses")
#         graph.add_edge("extract_diagnoses", "predict_service_codes")
#         graph.add_edge("predict_service_codes", "gemini_reasoning")
#         graph.add_edge("gemini_reasoning", "validate_service_codes")
#         graph.add_edge("validate_service_codes", END)
#         return graph.compile()
#
#     # ---------------- Run & Human-in-loop ----------------
#     def run(self, soap_note: str) -> Dict:
#         initial_state: AgentState = {
#             "soap_note": soap_note,
#             "anonymized_note": "",
#             "diagnoses": [],
#             "service_codes": [],
#             "validation_results": {},
#             "pending_questions": []
#         }
#         final_state = self.app.invoke(initial_state)
#         self.current_state = final_state
#         return final_state
#
#     def get_pending_questions(self) -> List[Dict]:
#         return self.current_state.get("pending_questions", [])
#
#     def answer_question(self, q_id: str, answer: str):
#         if not self.current_state:
#             print("Error: Must run agent before answering questions.")
#             return
#         self.current_state["soap_note"] += f"\n[User Answer for {q_id}]: {answer}"
#         self.current_state["anonymized_note"] = self._anonymize_soap(self.current_state["soap_note"])
#         updated = self.validate_service_codes_node(self.current_state)
#         self.current_state.update(updated)
# app/agents/helfo_agent.py
import os
import json
import yaml
from typing import List, Dict, Any, TypedDict
from dotenv import load_dotenv

from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer
from presidio_analyzer.nlp_engine import SpacyNlpEngine
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

# FAISS search
from app.core.search_service_codes import search_service_codes
from app.core.search_diagnosis import search_diagnosis_with_explanation

# Load environment variables
load_dotenv()
print("[DEBUG] Using helfo_agent.py version")  # in helfo_agent.py


# ------------------- HELFO Rules -------------------
with open("data/takst_rules.yaml", "r", encoding="utf-8") as f:
    TAKST_RULES = yaml.safe_load(f)

# ------------------- Gemini Setup -------------------
try:
    import google.generativeai as genai
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    if GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
        GEMINI_MODEL = genai.GenerativeModel("gemini-1.5-flash")
        print("Gemini Model configured successfully.")
    else:
        GEMINI_MODEL = None
        print("GEMINI_API_KEY not found. Gemini node will be skipped.")
except ImportError:
    GEMINI_MODEL = None
    print("google.generativeai not installed. Gemini node will be skipped.")

# ------------------- Presidio Setup -------------------
nlp_engine = SpacyNlpEngine()
try:
    nlp_engine.load({"en": "en_core_web_sm"})
except Exception as e:
    print(f"Error loading English SpaCy model: {e}")

analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["en"])
anonymizer = AnonymizerEngine()

# ------------------- Custom Recognizers -------------------
class FNRRecognizer(PatternRecognizer):
    def __init__(self):
        patterns = [Pattern(name="FNR", regex=r"\b\d{11}\b", score=0.9)]
        super().__init__(supported_entity="FNR", patterns=patterns, context=["national id", "ssn"], supported_language="en")

class PhoneNumberRecognizer(PatternRecognizer):
    def __init__(self):
        patterns = [Pattern(name="PHONE_NUMBER", regex=r"\b\d{10}\b", score=0.8)]
        super().__init__(supported_entity="PHONE_NUMBER", patterns=patterns, context=["phone", "mobile"], supported_language="en")

class PersonRecognizer(PatternRecognizer):
    def __init__(self):
        patterns = [Pattern(name="PERSON", regex=r"\b[A-Z][a-z]+ [A-Z][a-z]+\b", score=0.7)]
        super().__init__(supported_entity="PERSON", patterns=patterns, context=["patient", "name", "doctor"], supported_language="en")

class DateRecognizer(PatternRecognizer):
    def __init__(self):
        patterns = [
            Pattern(name="DATE_TIME", regex=r"\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b", score=0.9),
            Pattern(name="DATE_TIME", regex=r"\b\d{4}-\d{2}-\d{2}\b", score=0.9)
        ]
        super().__init__(supported_entity="DATE_TIME", patterns=patterns, context=["date", "birthdate", "time"], supported_language="en")

# Register all recognizers
for rec in [FNRRecognizer(), PhoneNumberRecognizer(), PersonRecognizer(), DateRecognizer()]:
    analyzer.registry.add_recognizer(rec)

# ------------------- LangGraph -------------------
from langgraph.graph import StateGraph, END

class AgentState(TypedDict):
    soap_note: str
    anonymized_note: str
    diagnoses: List[Dict]
    service_codes: List[Dict]
    validation_results: Dict
    pending_questions: List[Dict]
    user_input: str  # New field to hold the user's response

# ------------------- HelfoAgent -------------------
class HelfoAgent:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.app = self._build_graph()
        self.current_state: AgentState = {}

    # ---------------- Helper Methods ----------------
    def _anonymize_soap(self, text: str) -> str:
        results = analyzer.analyze(text=text, language="en")
        if results:
            operators = {
                "PERSON": OperatorConfig("replace", {"new_value": "[NAME]"}),
                "PHONE_NUMBER": OperatorConfig("replace", {"new_value": "[PHONE]"}),
                "FNR": OperatorConfig("replace", {"new_value": "[FNR]"}),
                "DATE_TIME": OperatorConfig("replace", {"new_value": "[DATE]"}),
            }
            return anonymizer.anonymize(text=text, analyzer_results=results, operators=operators).text
        return text

    def _extract_concepts(self, text: str) -> List[str]:
        return [s.strip() for s in text.split(".") if s.strip()]

    def _validate_against_rules(self, note: str, codes: List[str]) -> Dict:
        results = []
        for code in codes:
            rule = TAKST_RULES.get(code, {})
            missing_terms = [term for term in rule.get("required_terms", []) if term.lower() not in note.lower()]
            severity = "pass" if not missing_terms else rule.get("severity", "fail")
            results.append({
                "code": code,
                "valid": severity == "pass",
                "missing_terms": missing_terms,
                "severity": severity
            })
        return {"results": results}

    def _plan_questions(self, validation_results: Dict) -> List[Dict]:
        missing_terms = {term for r in validation_results.get("results", []) for term in r.get("missing_terms", [])}
        return [{"id": f"q_{term}", "text": f"Can you provide {term}?"} for term in missing_terms]

    # ---------------- Nodes ----------------
    def extract_diagnoses_node(self, state: AgentState) -> Dict[str, Any]:
        print("[DEBUG] Running extract_diagnoses_node")
        anon_note = self._anonymize_soap(state.get("soap_note", ""))
        concepts = self._extract_concepts(anon_note)
        diagnoses = search_diagnosis_with_explanation(concepts, top_k=3)
        return {"anonymized_note": anon_note, "diagnoses": diagnoses}

    def predict_service_codes_node(self, state: AgentState) -> Dict[str, Any]:
        print("[DEBUG] Running predict_service_codes_node")
        candidates_raw = search_service_codes(state.get("anonymized_note", ""), top_k=5)
        candidates = [{"code": c} if isinstance(c, str) else c for c in candidates_raw]
        return {"service_codes": candidates}

    def gemini_reasoning_node(self, state: AgentState) -> Dict[str, Any]:
        print("[DEBUG] Running gemini_reasoning_node")
        if not GEMINI_MODEL or not state.get("service_codes"):
            return {}
        refined = []
        generation_config = {"response_mime_type": "application/json"}
        for candidate in state.get("service_codes", []):
            code_val = candidate.get("code", "")
            prompt = f"""
You are a medical billing AI.
SOAP note: "{state.get('anonymized_note', '')}"
Candidate service code: "{code_val}"

Return JSON: {{"code": "{code_val}", "reasoning": "<text>", "recommended_action": "<text>"}}
"""
            try:
                response = GEMINI_MODEL.generate_content(prompt, generation_config=generation_config).text
                gem_resp = json.loads(response)
                candidate["gemini_reasoning"] = gem_resp.get("reasoning")
                candidate["recommended_action"] = gem_resp.get("recommended_action")
                refined.append(candidate)
            except Exception as e:
                print(f"Gemini failed: {e}. Skipping reasoning for {code_val}.")
                refined.append(candidate)
        return {"service_codes": refined}

    def validate_service_codes_node(self, state: AgentState) -> Dict[str, Any]:
        print("[DEBUG] Running validate_service_codes_node")
        # If user input exists, add it to the SOAP note before validation
        if state.get("user_input"):
            state["soap_note"] += f"\n[User Answer]: {state['user_input']}"
            state["anonymized_note"] = self._anonymize_soap(state["soap_note"])
            state["user_input"] = ""  # Clear the input after use

        codes = [c.get("code", "") for c in state.get("service_codes", [])]
        results = self._validate_against_rules(state.get("anonymized_note", ""), codes)
        questions = self._plan_questions(results)
        return {"validation_results": results, "pending_questions": questions}

    def human_in_loop_node(self, state: AgentState) -> str:
        print("[DEBUG] Running human_in_loop_node")
        if state.get("pending_questions"):
            return "ask_user"
        return "end_workflow"

    # ---------------- Graph ----------------
    def _build_graph(self) -> StateGraph:
        graph = StateGraph(AgentState)
        graph.add_node("extract_diagnoses", self.extract_diagnoses_node)
        graph.add_node("predict_service_codes", self.predict_service_codes_node)
        graph.add_node("gemini_reasoning", self.gemini_reasoning_node)
        graph.add_node("validate_service_codes", self.validate_service_codes_node)
        graph.add_node("human_in_loop", self.human_in_loop_node)

        # Build the conditional edges
        graph.set_entry_point("extract_diagnoses")
        graph.add_edge("extract_diagnoses", "predict_service_codes")
        graph.add_edge("predict_service_codes", "gemini_reasoning")
        graph.add_edge("gemini_reasoning", "validate_service_codes")

        # This is the crucial conditional edge that fixes the problem
        graph.add_conditional_edges(
            "validate_service_codes",
            self.human_in_loop_node,
            {
                "ask_user": "validate_service_codes",  # Loop back if questions are pending
                "end_workflow": END,
            }
        )

        return graph.compile()

    # ---------------- Run & Human-in-loop ----------------
    def run(self, soap_note: str) -> Dict:
        initial_state: AgentState = {
            "soap_note": soap_note,
            "anonymized_note": "",
            "diagnoses": [],
            "service_codes": [],
            "validation_results": {},
            "pending_questions": [],
            "user_input": ""  # Initialize new field
        }
        final_state = self.app.invoke(initial_state)
        self.current_state = final_state
        return final_state

    # This method is now simplified to work with the new graph logic
    def answer_question(self, user_response: str) -> Dict:
        if not self.current_state:
            print("Error: Must run agent before answering questions.")
            return {}

        # Update the state with the user's input and re-invoke the graph
        self.current_state["user_input"] = user_response
        final_state = self.app.invoke(self.current_state)
        self.current_state = final_state
        return final_state
