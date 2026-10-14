"""Bildirim göndericileri: Strategy deseninin somut sınıfları.

Kurum e-posta / SMS entegrasyonu kapsam dışıdır: e-posta ve SMS göndericileri
benzetimdir, gerçek gönderim yerine ne gönderileceğini loglar. Bildirim her
kanalda zaten veritabanına kaydedilmiştir; kullanıcı onu zil menüsünde kanal
etiketiyle görür. Gerçek SMTP'ye geçiş: `SmtpEmailSender(NotificationSender)`
yazıp kompozisyon kökünde (core/dependencies.py) benzetimin yerine vermek.
"""

import logging

from app.application.interfaces.notification_sender import NotificationSender
from app.domain.notifications import NotificationChannel, UserNotification
from app.domain.user import User

logger = logging.getLogger(__name__)


class InAppSender(NotificationSender):
    """Strategy deseni — Concrete Strategy: uygulama içi bildirim.

    Teslim, bildirimin kaydedilmesidir: zil menüsü onu veritabanından okur
    (yoklama ile). Bu yüzden ek bir iş yapmaz, yalnızca iz bırakır.
    """

    channel = NotificationChannel.IN_APP

    def deliver(self, recipient: User, notification: UserNotification) -> None:
        logger.debug("Uygulama içi bildirim → %s: %s", recipient.full_name, notification.message)


class SimulatedEmailSender(NotificationSender):
    """Strategy deseni — Concrete Strategy: e-posta (benzetim; gerçek gönderim yok)."""

    channel = NotificationChannel.EMAIL

    def deliver(self, recipient: User, notification: UserNotification) -> None:
        logger.info("[E-posta benzetimi] Kime: %s | %s", recipient.email, notification.message)


class SimulatedSmsSender(NotificationSender):
    """Strategy deseni — Concrete Strategy: SMS (benzetim; gerçek gönderim yok)."""

    channel = NotificationChannel.SMS

    def deliver(self, recipient: User, notification: UserNotification) -> None:
        # Kullanıcı modelinde telefon yok: alıcı adıyla loglanır
        logger.info("[SMS benzetimi] Kime: %s | %s", recipient.full_name, notification.message)
