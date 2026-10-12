"""Birden fazla router'ın kullandığı ortak yanıt şemaları."""

from pydantic import BaseModel


class CreatedResponse(BaseModel):
    """Oluşturma command'larının yanıtı: CQRS gereği yalnızca yeni kaydın id'si."""

    id: int
