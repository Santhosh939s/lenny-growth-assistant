import pytest
from app.services.ingestion_service import chunk_text, generate_content_hash
from app.services.retrieval_service import RetrievalService
from app.models.document import DocumentChunk

def test_generate_content_hash():
    text1 = "hello world"
    text2 = "hello world"
    text3 = "hello there"
    assert generate_content_hash(text1) == generate_content_hash(text2)
    assert generate_content_hash(text1) != generate_content_hash(text3)

def test_chunk_text():
    text = "word " * 100
    chunks = chunk_text(text, chunk_size=20, overlap=5)
    
    assert len(chunks) > 1
    # Check if first chunk has 20 words
    assert len(chunks[0].split()) == 20
    # Check overlap (last 5 words of chunk 0 should be first 5 words of chunk 1)
    # Since all words are "word", this is trivial, let's test a distinct sequence
    
    seq_text = " ".join([str(i) for i in range(100)])
    seq_chunks = chunk_text(seq_text, chunk_size=20, overlap=5)
    
    chunk_0_words = seq_chunks[0].split()
    chunk_1_words = seq_chunks[1].split()
    
    assert chunk_0_words[-5:] == chunk_1_words[:5]

def test_cosine_similarity(mocker):
    # Mock DB session
    mock_db = mocker.MagicMock()
    service = RetrievalService(mock_db)
    
    vec1 = [1.0, 0.0, 0.0]
    vec2 = [1.0, 0.0, 0.0]
    vec3 = [0.0, 1.0, 0.0]
    
    assert service._cosine_similarity(vec1, vec2) == 1.0
    assert service._cosine_similarity(vec1, vec3) == 0.0

def test_retrieval(mocker):
    # Mock DB and Ollama
    mock_db = mocker.MagicMock()
    service = RetrievalService(mock_db)
    
    mocker.patch.object(service, "_get_query_embedding", return_value=[1.0, 0.0, 0.0])
    
    chunk1 = DocumentChunk(
        id="c1", chunk_index=0, text="A", embedding=[1.0, 0.0, 0.0], 
        metadata_={"guest": "Bob"}
    )
    chunk2 = DocumentChunk(
        id="c2", chunk_index=1, text="B", embedding=[0.0, 1.0, 0.0], 
        metadata_={"guest": "Alice"}
    )
    
    # Setup mock to return chunks
    mock_scalars = mocker.MagicMock()
    mock_scalars.all.return_value = [chunk1, chunk2]
    mock_execute = mocker.MagicMock()
    mock_execute.scalars.return_value = mock_scalars
    mock_db.execute.return_value = mock_execute
    
    results = service.retrieve("test query", top_k=2)
    
    assert len(results) == 2
    assert results[0]["guest"] == "Bob"
    assert results[0]["similarity"] == 1.0
    assert results[1]["guest"] == "Alice"
    assert results[1]["similarity"] == 0.0
