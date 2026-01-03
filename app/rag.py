import os
import json
from time import time
import numpy as np

import ingest 

from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
from google import genai


# Load .env file
load_dotenv()

# Now the API key is in the environment variable
#client = genai.Client()

_client = None

def get_client():
    global _client
    if _client is None:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is not set!")
        _client = genai.Client(api_key=api_key)
    return _client

collection = ingest.load_index()

# Load the model used for embeddings
model = SentenceTransformer("all-MiniLM-L6-v2")

#Prompt Templates
prompt_template = """
You are a helpful assistant for Fahrschule Galaxy, a driving school in Hamburg. Answer the QUESTION based on the CONTEXT from the FAQ database. 
Use only the facts from the CONTEXT when answering the QUESTION. If the answer is not in the FAQs, politely say you don't have that information.
Always be friendly and helpful.

QUESTION: {question}

CONTEXT: 
{context}
""".strip()            

evaluation_prompt_template = """
You are an expert evaluator for a RAG system.
Your task is to analyze the relevance of the generated answer to the given question.
Based on the relevance of the generated answer, you will classify it
as "NON_RELEVANT", "PARTLY_RELEVANT", or "RELEVANT".
Here is the data for evaluation:
Question: {question}
Generated Answer: {answer}
Please analyze the content and context of the generated answer in relation to the question
and provide your evaluation in parsable JSON without using code blocks:
{{
  "Relevance": "NON_RELEVANT" | "PARTLY_RELEVANT" | "RELEVANT",
  "Explanation": "[Provide a brief explanation for your evaluation]"
}}
""".strip()

#rag functions
def search_faq(query, collection, top_k=3):
    """
    Search the Fahrschule Galaxy FAQ collection
    
    Args:
        query: Search query string
        collection: Chroma db collection
        top_k: Number of results to return
    
    Returns top_k most relevant FAQ documents for a query.
    """
    # Generate query embedding
    query_emb = model.encode([query], convert_to_numpy=True)
    
    # Query Chroma collection
    results = collection.query(
        query_embeddings=query_emb.tolist(),
        n_results=top_k
    )
    # Extract context text
    contexts = []
    for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
        contexts.append(
            f"Category: {meta['category']}\n{doc}"
        )
    return contexts 

def build_prompt(query, search_results):
    context = " ".join(search_results)
    
    prompt = prompt_template.format(question=query, context=context).strip()
    return prompt

def llm(prompt, model):
# generate content
    client = get_client()
    response = client.models.generate_content(
        model="gemini-2.5-flash", contents=prompt
    )
    return response.text

def evaluate_rag_response(question, answer, model="chat-bison-001'"):
    """
    Evaluate the relevance of the generated answer using LLM.
    Returns: evaluation_dict
    """
    prompt = evaluation_prompt_template.format(question=question, answer=answer)
    evaluation = llm(prompt, model=model)
    if "```json" in evaluation:
        json_str = evaluation.split("```json")[1].split("```")[0].strip()
    elif "```" in evaluation:
        json_str = evaluation.split("```")[1].split("```")[0].strip()
    else:
        json_str = evaluation.strip()
        evaluation = json.loads(json_str)
    return evaluation

def rag_with_evaluation(query, collection, model="chat-bison-001'"):
    """
    Complete RAG pipeline with evaluation
    Returns: answer_data dictionary with answer, relevance, and evaluation
    """
    t0 = time()
    
    # Search for relevant documents
    search_results = search_faq(query, collection, top_k=3)
    
    # Build prompt with context
    prompt = build_prompt(query, search_results)
    
    # Generate answer
    answer = llm(prompt, model=model)
    
    # Evaluate relevance
    relevance = evaluate_rag_response(query, answer, model=model)
    
    t1 = time()
    took = t1 - t0
        
    # Prepare answer data
    answer_data = {
        "answer": answer,
        "model_used": model,
        "response_time": took,
        "relevance": relevance.get("Relevance", "UNKNOWN"),
        "relevance_explanation": relevance.get("Explanation", "Failed to parse evaluation"),
    }
    
    # Save to database with all metrics
    return answer_data   

if __name__ == "__main__":
    # Example usage
    question = "How much does a driving license cost?"
    answer = rag_with_evaluation(question, collection)
    print(answer)