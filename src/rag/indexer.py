import os
from dotenv import load_dotenv
from llama_index.core import VectorStoreIndex, Document, StorageContext, Settings
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.groq import Groq
import chromadb

load_dotenv()

# Initialize embedding model
embed_model = HuggingFaceEmbedding(model_name="all-MiniLM-L6-v2")

# Initialize ChromaDB
chroma_client = chromadb.PersistentClient(path="data/chroma")

# Configure LlamaIndex to use Groq
Settings.llm = Groq(
    model="llama-3.3-70b-versatile",
    api_key=os.getenv("GROQ_API_KEY")
)
Settings.embed_model = embed_model


def build_filing_index(ticker: str, filing_data: dict) -> dict:
    """
    Builds a ChromaDB vector index from filing sections.
    If index already exists for ticker, loads it instead of rebuilding.

    Input:
        ticker (str) — e.g. "AAPL"
        filing_data (dict) — output from edgar.get_filing()
    Output: dict with keys:
        - index: VectorStoreIndex object
        - retriever: retriever object ready for querying
        - status: dict
    """

    result = {
        "index": None,
        "retriever": None,
        "status": {}
    }

    try:
        existing_collections = [
            c.name for c in chroma_client.list_collections()
        ]
        collection_name = f"filing_{ticker.lower()}"

        if collection_name in existing_collections:
            print(f"Loading existing index for {ticker}...")
            collection    = chroma_client.get_collection(collection_name)
            vector_store  = ChromaVectorStore(chroma_collection=collection)
            index = VectorStoreIndex.from_vector_store(
                vector_store,
                embed_model=embed_model
            )
            result["status"]["index_source"] = "loaded_existing"

        else:
            print(f"Building new index for {ticker}...")

            documents = []

            if filing_data.get("mda"):
                documents.append(Document(
                    text=filing_data["mda"],
                    metadata={"section": "mda", "ticker": ticker}
                ))

            if filing_data.get("risk_factors"):
                documents.append(Document(
                    text=filing_data["risk_factors"],
                    metadata={"section": "risk_factors", "ticker": ticker}
                ))

            if filing_data.get("full_text"):
                documents.append(Document(
                    text=filing_data["full_text"],
                    metadata={"section": "full_text", "ticker": ticker}
                ))

            if not documents:
                result["status"]["success"] = False
                result["status"]["error"] = (
                    "No filing sections available to index"
                )
                return result

            collection   = chroma_client.get_or_create_collection(collection_name)
            vector_store = ChromaVectorStore(chroma_collection=collection)
            storage_context = StorageContext.from_defaults(
                vector_store=vector_store
            )

            index = VectorStoreIndex.from_documents(
                documents,
                storage_context=storage_context,
                embed_model=embed_model,
                show_progress=False
            )

            result["status"]["index_source"]      = "built_new"
            result["status"]["documents_indexed"] = len(documents)

        result["index"]     = index
        result["retriever"] = index.as_retriever(similarity_top_k=3)
        result["status"]["success"] = True

    except Exception as e:
        result["status"]["success"] = False
        result["status"]["error"]   = str(e)

    return result


def query_filing(retriever, query: str) -> str:
    """
    Queries the filing index and returns relevant text chunks.

    Input:
        retriever — retriever object from build_filing_index()
        query (str) — natural language question
    Output: str — concatenated relevant chunks
    """
    try:
        nodes  = retriever.retrieve(query)
        chunks = [node.text for node in nodes]
        return "\n\n---\n\n".join(chunks)
    except Exception as e:
        return f"Query failed: {str(e)}"