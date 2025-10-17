import google.generativeai as genai
import numpy as np
import os
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

async def generate_embedding(text: str, task_type: str = "RETRIEVAL_DOCUMENT", output_dimensionality: int = 1536):
    """Generates a normalized embedding for the given text."""
    try:
        result = genai.embed_content(
            model="models/embedding-001",
            content=text,
            task_type=task_type,
            output_dimensionality=output_dimensionality
        )
        embedding = np.array(result['embedding'])
        # Normalize the embedding
        normalized_embedding = embedding / np.linalg.norm(embedding)
        return normalized_embedding.tolist()
    except Exception as e:
        print(f"Error generating embedding: {e}")
        # Depending on error handling strategy, might raise, log, or return empty
        raise # Re-raise for upstream handling

async def search_sources(db: AsyncSession, query: str, top_k: int = 5):
    """Searches academic sources using vector similarity."""
    query_embedding = await generate_embedding(query, task_type="RETRIEVAL_QUERY")
    
    # Convert list of floats to string representation that pgvector understands
    query_embedding_str = "[" + ",".join(map(str, query_embedding)) + "]"

    # Use pgvector for cosine similarity search
    # ORDER BY embedding <=> :query_embedding::vector calculates cosine distance.
    # We want the smallest distance for the most similar.
    stmt = text(f"""
        SELECT id, title, authors, publication_year, abstract, source_type
        FROM academic_sources
        ORDER BY embedding <=> '{query_embedding_str}'::vector
        LIMIT :top_k
    """)
    # Note: Using f-string for query_embedding_str to directly embed the vector
    # as pgvector's <=> operator needs the vector literal.
    # While typically not ideal for security, for numeric vector literals, this is common.
    # For user-provided strings, always use parameterized queries.
    
    result = await db.execute(stmt, {"top_k": top_k}) # Only top_k is passed as a parameter
    return result.fetchall()