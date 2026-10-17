from __future__ import annotations

from datetime import datetime, timezone

from supabase import Client, create_client

from .config import Settings


def service_client(settings: Settings | None = None) -> Client:
    settings = settings or Settings()
    settings.validate_supabase(service=True)
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def anon_client(settings: Settings | None = None) -> Client:
    settings = settings or Settings()
    settings.validate_supabase(service=False)
    return create_client(settings.supabase_url, settings.supabase_anon_key)


class HistoryStore:
    def __init__(self, client: Client):
        self.client = client

    def list_conversations(self) -> list[dict]:
        return (
            self.client.table("conversations")
            .select("*")
            .order("updated_at", desc=True)
            .execute()
            .data
            or []
        )

    def create_conversation(self, title: str, user_id: str) -> dict:
        return (
            self.client.table("conversations")
            .insert({"title": title[:120], "user_id": user_id})
            .execute()
            .data[0]
        )

    def messages(self, conversation_id: str) -> list[dict]:
        rows = (
            self.client.table("messages")
            .select(
                "id,conversation_id,user_id,role,content,action,confidence,metadata,created_at,"
                "message_sources(rank,score,document_id,documents(id,title,section,source_path,source_url,content))"
            )
            .eq("conversation_id", conversation_id)
            .order("created_at")
            .execute()
            .data
            or []
        )

        for row in rows:
            sources: list[dict] = []
            links = sorted(
                row.get("message_sources") or [],
                key=lambda item: item.get("rank") or 999,
            )

            for link in links:
                document = link.get("documents") or {}
                if not document:
                    continue

                sources.append(
                    {
                        "source_id": str(
                            document.get("id") or link.get("document_id") or ""
                        ),
                        "title": document.get("title") or "Source",
                        "section": document.get("section") or "",
                        "source_path": document.get("source_path") or "",
                        "url": document.get("source_url") or "",
                        "text": document.get("content") or "",
                        "score": float(link.get("score") or 0.0),
                    }
                )

            row["sources"] = sources

        return rows


    def delete_conversation(self, conversation_id: str) -> None:
        self.client.table("conversations").delete().eq("id", conversation_id).execute()

    def save_message(
        self,
        conversation_id: str,
        user_id: str,
        role: str,
        content: str,
        action: str | None = None,
        confidence: float | None = None,
        metadata: dict | None = None,
    ) -> dict:
        row = {
            "conversation_id": conversation_id,
            "user_id": user_id,
            "role": role,
            "content": content,
            "action": action,
            "confidence": confidence,
            "metadata": metadata or {},
        }

        message = self.client.table("messages").insert(row).execute().data[0]

        self.client.table("conversations").update(
            {"updated_at": datetime.now(timezone.utc).isoformat()}
        ).eq("id", conversation_id).execute()

        return message

    def save_sources(self, message_id: str, sources: list[dict]) -> None:
        if not sources:
            return

        rows = [
            {
                "message_id": message_id,
                "document_id": source["source_id"],
                "rank": index,
                "score": source.get("score"),
            }
            for index, source in enumerate(sources, 1)
        ]

        self.client.table("message_sources").insert(rows).execute()
