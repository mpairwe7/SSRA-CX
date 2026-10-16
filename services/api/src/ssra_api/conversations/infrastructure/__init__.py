"""Infrastructure repository for conversations bounded context (with RLS office_code filtering)."""

from __future__ import annotations

from ssra_api.conversations.domain import ConversationEntity


class InMemoryConversationRepository:
    def __init__(self) -> None:
        self._store: dict[str, ConversationEntity] = {}

    def save(self, entity: ConversationEntity) -> None:
        self._store[entity.id] = entity

    def get(self, conv_id: str) -> ConversationEntity | None:
        return self._store.get(conv_id)

    def list_by_office(self, office_code: str) -> list[ConversationEntity]:
        return [c for c in self._store.values() if c.office_code == office_code]
