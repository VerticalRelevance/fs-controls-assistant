import os
import uuid

from bedrock_agentcore.memory.integrations.strands.config import AgentCoreMemoryConfig, RetrievalConfig
from bedrock_agentcore.memory.integrations.strands.session_manager import AgentCoreMemorySessionManager

MEMORY_ID = os.getenv("MEMORY_CONTROLSAGENTMEMORY_ID")
REGION = os.getenv("AWS_REGION")


def get_memory_session_manager(session_id, actor_id):
    """Short-term: this session's turns. Long-term: this actor's preferences only."""
    if not MEMORY_ID:
        return None
    session_id = session_id or uuid.uuid4().hex
    retrieval_config = {
        f"/users/{actor_id}/preferences": RetrievalConfig(top_k=3, relevance_score=0.3),
    }
    return AgentCoreMemorySessionManager(
        AgentCoreMemoryConfig(memory_id=MEMORY_ID, session_id=session_id, actor_id=actor_id,
                              retrieval_config=retrieval_config),
        REGION,
    )
