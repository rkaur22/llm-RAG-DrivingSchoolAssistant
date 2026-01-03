import json
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions

from pathlib import Path

# Path relative to this script
BASE_DIR = Path(__file__).resolve().parent.parent  # go up from app/ to root
DATA_PATH = BASE_DIR / "data" / "faq.json"

#DATA_PATH = os.getenv("DATA_PATH", "../data/faq.json")

def load_index(data_path=DATA_PATH):
    """
    Load Fahrschule Galaxy FAQ data from JSON and create a Chroma collection
    """    
    try:
        # Initialize ChromaDB client with persistence
        client = chromadb.PersistentClient(path="../chroma_db")

        # Configure sentence transformer embeddings
        sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
        )
        
        # Create or get existing collection
        collection = client.get_or_create_collection(
        name="fahrschule_faq",
        embedding_function=sentence_transformer_ef
    )

        # Load JSON data
        with open(data_path, 'r', encoding='utf-8') as f:
            faq_data = json.load(f)
        
        print(f"✓ Loaded {len(faq_data)} items from JSON")
        
        # Prepare data for Chroma
        documents = []
        metadatas = []
        ids = []

        for faq in faq_data:
            text = f"Question: {faq['question']}\nAnswer: {faq['answer']}"
    
            documents.append(text)
            metadatas.append({
                "category": faq["category"],
                "question": faq["question"]
            })
            ids.append(faq["id"])
        
        # Add documents to collection (Chroma will auto-generate embeddings)
        # Add documents to Chroma collection
        collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )

        print(f"✓ Successfully ingested {len(documents)} documents into ChromaDB")
        return collection
        
    except FileNotFoundError:
        print(f"❌ ERROR: File not found at {data_path}")
        print("   Please check the file path and try again.")
        return None
    except json.JSONDecodeError as e:
        print(f"❌ ERROR: Invalid JSON format - {e}")
        return None
    except Exception as e:
        print(f"❌ ERROR: {type(e).__name__}: {e}")
        return None

 
if __name__ == "__main__":
    load_index()