"""Destek seviyeleri ve eskalasyon zinciri: Chain of Responsibility deseni.

Bir talep sırayla üç seviyeden geçebilir:

    AI (L0)  →  Teknisyen (L1)  →  Kıdemli teknisyen (L2)

Eskalasyon isteği zincirin başından gönderilir; her halka "bu talebi ben
üstlenebilir miyim?" diye bakar, üstlenemiyorsa isteği bir sonrakine iletir.
Talebin seviyesi, isteği üstlenen halkanın seviyesi olur. Zincirin sonuna
gelinip kimse üstlenmezse talep zaten en üst seviyededir (hata).

Neden State'in içine gömülmedi? State "bu durumda eskalasyon yapılabilir mi?"
sorusunu cevaplar (OPEN, AI_ANSWERED, ASSIGNED, IN_PROGRESS'te evet); zincir ise
"eskale edilen talebi kim üstlenir?" sorusunu. İkisi bağımsız değişir: yeni bir
seviye (örn. dış servis) eklemek durum diyagramına dokunmadan zincire yeni bir
halka sınıfı eklemek demektir (Açık/Kapalı ilkesi).

Halkalar ayrıca o seviyedeki talebe kimin atanabileceğini de bilir
(iş kuralı 12: L2 talep yalnızca kıdemli teknisyene atanabilir).
"""

from abc import ABC, abstractmethod

from app.domain.enums import SupportLevel
from app.domain.errors import HighestSupportLevelError
from app.domain.user import User

SUPPORT_LEVEL_LABELS = {
    SupportLevel.AI: "AI asistan",
    SupportLevel.TIER_1: "Teknisyen",
    SupportLevel.TIER_2: "Kıdemli teknisyen",
}


class SupportTier(ABC):
    """Chain of Responsibility deseni — Handler: bir destek seviyesi.

    `take_over` zincirin ortak akışıdır (üstlen ya da ilet); alt sınıflar
    yalnızca kendi kararlarını (`accepts`, `can_be_handled_by`) tanımlar.
    """

    level: SupportLevel

    def __init__(self, successor: "SupportTier | None" = None) -> None:
        self._successor = successor

    def take_over(self, current_level: SupportLevel) -> SupportLevel:
        """`current_level` seviyesinden eskale edilen talebi üstlenecek seviyeyi döndürür."""
        if self.accepts(current_level):
            return self.level
        if self._successor is None:
            raise HighestSupportLevelError()
        return self._successor.take_over(current_level)

    @abstractmethod
    def accepts(self, current_level: SupportLevel) -> bool:
        """Bu seviyeden eskale edilen talebi bu halka üstlenir mi?"""

    @abstractmethod
    def can_be_handled_by(self, technician: User) -> bool:
        """Bu seviyedeki talep bu teknisyene atanabilir mi?"""


# --- Somut halkalar (Chain of Responsibility deseni — Concrete Handler) ---


class AiTier(SupportTier):
    """Chain of Responsibility deseni — Concrete Handler: L0, AI asistan.

    Her talep bu seviyede açılır ve AI yanıtı (UC-14) burada denenir. Eskalasyon
    her zaman AI'dan uzaklaştığı için eskale edilen talebi asla üstlenmez;
    zincirin başında durması seviyelerin sırasını tek yerde tanımlar.
    """

    level = SupportLevel.AI

    def accepts(self, current_level: SupportLevel) -> bool:
        return False

    def can_be_handled_by(self, technician: User) -> bool:
        return False  # AI seviyesindeki talep teknisyene atanmaz (önce eskale edilir)


class TechnicianTier(SupportTier):
    """Chain of Responsibility deseni — Concrete Handler: L1, teknisyen.

    AI'ın çözemediği talebi üstlenir; her teknisyen bu seviyede çalışabilir.
    """

    level = SupportLevel.TIER_1

    def accepts(self, current_level: SupportLevel) -> bool:
        return current_level == SupportLevel.AI

    def can_be_handled_by(self, technician: User) -> bool:
        return technician.is_technician


class SeniorTechnicianTier(SupportTier):
    """Chain of Responsibility deseni — Concrete Handler: L2, kıdemli teknisyen.

    Teknisyenin üst seviyeye eskale ettiği talebi (UC-07) üstlenir.
    Yalnızca kıdemli (TIER_2) teknisyene atanabilir.
    """

    level = SupportLevel.TIER_2

    def accepts(self, current_level: SupportLevel) -> bool:
        return current_level == SupportLevel.TIER_1

    def can_be_handled_by(self, technician: User) -> bool:
        return technician.is_technician and technician.support_level == SupportLevel.TIER_2


class SupportChain:
    """Chain of Responsibility deseni — Client: zinciri kurar ve isteği başından gönderir.

    Halkaların sırası yalnızca burada tanımlıdır. Halkalar veri tutmadığı için
    (State nesneleri gibi) tek bir zincir yeterlidir.
    """

    def __init__(self) -> None:
        senior = SeniorTechnicianTier()
        technician = TechnicianTier(successor=senior)
        self._head = AiTier(successor=technician)
        self._tiers: dict[SupportLevel, SupportTier] = {
            tier.level: tier for tier in (self._head, technician, senior)
        }

    def escalate_from(self, current_level: SupportLevel) -> SupportLevel:
        return self._head.take_over(current_level)

    def tier(self, level: SupportLevel) -> SupportTier:
        return self._tiers[level]


SUPPORT_CHAIN = SupportChain()
