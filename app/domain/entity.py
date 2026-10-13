"""Kimliği olan domain nesnelerinin ortak tabanı."""

from abc import ABC
from typing import Self


class Entity(ABC):
    """Tüm domain varlıklarının soyut tabanı (kalıtım + kapsülleme).

    Kimlik (`id`) dışarıdan yalnızca okunur. Yeni bir varlık henüz kaydedilmemişken
    kimliği yoktur (None); veritabanı kimliği verdiğinde repository `bind_id` ile
    bir kez bağlar. İki varlık, aynı türden ve aynı kimliğe sahipse eşittir.

    Alt sınıfların alanları `_` ile korunur ve `@property` ile okunur; durum
    yalnızca anlamlı iş metotlarıyla değişir (örn. `device.assign_to(user, ...)`).
    """

    def __init__(self, id: int | None = None) -> None:
        self._id = id

    @property
    def id(self) -> int | None:
        return self._id

    def bind_id(self, entity_id: int) -> Self:
        """Kalıcılık katmanı yeni kaydın kimliğini bir kez bağlar."""
        if self._id is not None and self._id != entity_id:
            raise ValueError(f"{type(self).__name__} zaten {self._id} kimliğine sahip.")
        self._id = entity_id
        return self

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Entity) or type(self) is not type(other):
            return NotImplemented
        if self._id is None or other._id is None:
            return self is other  # henüz kaydedilmemiş varlıklar yalnızca kendilerine eşittir
        return self._id == other._id

    def __hash__(self) -> int:
        return hash((type(self).__name__, self._id)) if self._id is not None else id(self)

    def __repr__(self) -> str:
        return f"{type(self).__name__}(id={self._id})"
