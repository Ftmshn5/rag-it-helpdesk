"""Olay dinleyicilerinin işini hemen ya da arka planda çalıştıran yürütücüler.

Event bus senkrondur: read model'ler aynı istekte güncellenir (CQRS kararı).
Ama yavaş işler (gerçek LLM ile AI yanıtı, saniyeler sürer) kullanıcının
isteğini bekletmemeli. Bu yüzden dinleyici, işini doğrudan değil bir
TaskRunner (application/interfaces) üzerinden çalıştırır; hangi yürütücünün kullanılacağına kompozisyon
kökü karar verir:

- InlineTaskRunner: hemen, aynı thread'de (testler; deterministik).
- BackgroundTaskRunner: tek işçili thread havuzunda, istek yanıtlandıktan sonra.

Neden FastAPI BackgroundTasks değil: o, bir HTTP isteğine bağlıdır. AI ise bir
olay dinleyicisinden tetiklenir ve talep açma kodu AI'dan habersiz kalmalıdır.
Neden tek işçi: CPU'da çalışan yerel LLM aynı anda tek isteği verimli işler;
işler sıraya girer, birbirini yavaşlatmaz.

Sınır: kuyruk bellektedir. Uygulama kapanırsa bekleyen işler kaybolur; bu yüzden
açılışta yanıt bekleyen (OPEN) talepler yeniden kuyruğa alınır (bkz. main.py).
"""

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

from app.application.interfaces.task_runner import TaskRunner

logger = logging.getLogger(__name__)


class InlineTaskRunner(TaskRunner):
    """İşi hemen, aynı thread'de çalıştırır (testler; deterministik)."""

    def submit(self, task: Callable[[], None], description: str) -> None:
        task()


class BackgroundTaskRunner(TaskRunner):
    """İşi tek işçili thread havuzunda, istek yanıtlandıktan sonra çalıştırır."""

    def __init__(self, max_workers: int = 1, thread_name_prefix: str = "background") -> None:
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix=thread_name_prefix)

    def submit(self, task: Callable[[], None], description: str) -> None:
        self._executor.submit(self._run_logged, task, description)

    def shutdown(self) -> None:
        # Kuyrukta bekleyenler iptal edilir (açılışta yeniden kuyruğa alınırlar);
        # çalışan iş bitmeden beklenmez, kapanma takılmasın
        self._executor.shutdown(wait=False, cancel_futures=True)

    @staticmethod
    def _run_logged(task: Callable[[], None], description: str) -> None:
        # Arka plandaki hata kimseye dönmez; en azından loglanmalı
        try:
            task()
        except Exception:
            logger.exception("Arka plan işi başarısız: %s", description)
