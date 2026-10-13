"""İş yürütücü arayüzü: bir işi hemen ya da arka planda çalıştırır.

Yavaş işler (gerçek LLM ile AI yanıtı, saniyeler sürer) kullanıcının isteğini
bekletmemelidir. Application katmanı işi bu arayüze verir; işin hemen mi (testler)
yoksa arka planda mı (uygulama) çalışacağına kompozisyon kökü karar verir.
Implementasyonlar: infrastructure/events/task_runner.py.
"""

from abc import ABC, abstractmethod
from collections.abc import Callable


class TaskRunner(ABC):
    @abstractmethod
    def submit(self, task: Callable[[], None], description: str) -> None:
        """İşi çalıştırır veya sıraya koyar; description loglarda kullanılır."""

    def shutdown(self) -> None:
        """Uygulama kapanırken çağrılır (varsayılan: yapılacak bir şey yok)."""
