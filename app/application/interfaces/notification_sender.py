"""Bildirim teslimi arayüzü (Strategy deseni).

Her kanalın (uygulama içi, e-posta, SMS) teslim yöntemi ayrı bir sınıftır.
Bildirimi üreten handler hangi kanalın nasıl çalıştığını bilmez; kanala karşılık
gelen göndericiyi seçip `deliver` der. Gerçek bir SMTP sunucusuna geçmek,
benzetim sınıfının yerine yeni bir sınıf vermek demektir (Açık/Kapalı ilkesi).
"""

from abc import ABC, abstractmethod

from app.domain.notifications import NotificationChannel, UserNotification
from app.domain.user import User


class NotificationSender(ABC):
    """Strategy deseni — Strategy: bir kanaldan bildirim teslimi."""

    channel: NotificationChannel

    @abstractmethod
    def deliver(self, recipient: User, notification: UserNotification) -> None:
        """Kaydedilmiş bildirimi alıcıya bu kanaldan ulaştırır."""
