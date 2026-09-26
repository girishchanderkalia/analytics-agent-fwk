"""SQLite metadata store that does not duplicate LangGraph graph state."""
from __future__ import annotations
import json, sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

@dataclass(frozen=True)
class ConversationMetadata:
    conversation_id: str
    agent_id: str
    agent_version: str
    definition_digest: str
    status: str
    public_result: Mapping[str, Any]
    pending_approval: Mapping[str, Any] | None
    version: int

class SQLiteConversationMetadataStore:
    def __init__(self,path: Path|str) -> None:
        self.path=Path(path).resolve(); self.path.parent.mkdir(parents=True,exist_ok=True); self._setup()
    def create(self, **v):
        now=datetime.now(timezone.utc).isoformat()
        with self._connect() as c:
            c.execute("INSERT INTO langgraph_conversations VALUES (?,?,?,?,?,?,?,?,?,?)",(v["conversation_id"],v["agent_id"],v["agent_version"],v["definition_digest"],v["status"],json.dumps(v["public_result"]),json.dumps(v["pending_approval"]) if v["pending_approval"] is not None else None,1,now,now))
        return self.get(v["conversation_id"])
    def get(self,conversation_id):
        with self._connect() as c: row=c.execute("SELECT * FROM langgraph_conversations WHERE conversation_id=?",(conversation_id,)).fetchone()
        if row is None: raise KeyError(conversation_id)
        return ConversationMetadata(row[0],row[1],row[2],row[3],row[4],json.loads(row[5]),json.loads(row[6]) if row[6] else None,row[7])
    def update(self, *, conversation_id, expected_version, status, public_result, pending_approval):
        now=datetime.now(timezone.utc).isoformat()
        with self._connect() as c:
            cursor=c.execute("UPDATE langgraph_conversations SET status=?,public_result_json=?,pending_approval_json=?,version=?,updated_at=? WHERE conversation_id=? AND version=?",(status,json.dumps(public_result),json.dumps(pending_approval) if pending_approval is not None else None,expected_version+1,now,conversation_id,expected_version))
            if cursor.rowcount != 1: raise RuntimeError("Conversation version conflict")
        return self.get(conversation_id)
    def _connect(self): return sqlite3.connect(self.path)
    def _setup(self):
        with self._connect() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS langgraph_conversations (conversation_id TEXT PRIMARY KEY,agent_id TEXT NOT NULL,agent_version TEXT NOT NULL,definition_digest TEXT NOT NULL,status TEXT NOT NULL,public_result_json TEXT NOT NULL,pending_approval_json TEXT,version INTEGER NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL)""")
