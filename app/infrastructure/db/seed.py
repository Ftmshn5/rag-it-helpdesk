"""Geliştirme için başlangıç verisi (seed data).

LDAP entegrasyonu kapsam dışı olduğu için kullanıcılar buradan gelir.
Çalıştırma (migration'lardan sonra):

    python -m app.infrastructure.db.seed

Script tekrar çalıştırılabilir (idempotent): veritabanında kullanıcı varsa
hiçbir şey eklemeden çıkar, böylece veriler ikinci kez eklenmez.

Veriler iş kurallarıyla tutarlıdır: zimmetli cihazın durumu ASSIGNED ve tek
aktif zimmeti var; bakımdaki cihaz IN_REPAIR ve tek açık bakım kaydı var.
Ticket eklenmez; ticket'lar uygulama akışıyla (AI yanıtı vb.) oluşmalıdır.
"""

from collections.abc import Callable
from datetime import UTC, date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.enums import DeviceStatus, MaintenanceType, SupportLevel, UserRole
from app.infrastructure.db.models import AssignmentModel, DeviceModel, MaintenanceRecordModel, UserModel
from app.infrastructure.db.projections import ReadModelRebuilder
from app.infrastructure.db.session import Database


class DemoDataSeeder:
    """Boş veritabanına örnek kullanıcı, cihaz, zimmet ve bakım kayıtlarını ekler."""

    EMAIL_DOMAIN = "ornekfakulte.edu.tr"

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def run(self) -> bool:
        """Veritabanı boşsa örnek verileri ekler ve read model'leri kurar. Ekleme yaptıysa True döner."""
        with self._session_factory() as session:
            seeded = self.seed(session)
        # Seed doğrudan tablolara yazar, olay üretmez; read model'ler elle kurulur
        ReadModelRebuilder(self._session_factory).rebuild_all()
        return seeded

    def seed(self, session: Session) -> bool:
        if session.scalar(select(func.count()).select_from(UserModel)):
            return False

        users = self._build_users()
        devices = self._build_devices()
        session.add_all([*users.values(), *devices.values()])
        # flush: kayıtları veritabanına gönderir, id'leri alırız; commit en sonda tek seferde
        session.flush()

        admin = users["bt.yonetici"]
        technician = users["ali.celik"]

        session.add_all(
            [
                # Aktif zimmetler (returned_at boş) — ilgili cihazlar ASSIGNED durumda
                AssignmentModel(device_id=devices["PC-0001"].id, user_id=users["ayse.yilmaz"].id, assigned_by=admin.id),
                AssignmentModel(device_id=devices["LT-0001"].id, user_id=users["dekan"].id, assigned_by=admin.id),
                # Geçmiş zimmet: PC-0002 önce Mehmet'teydi, iade edildi (şu an depoda)
                AssignmentModel(
                    device_id=devices["PC-0002"].id,
                    user_id=users["mehmet.kaya"].id,
                    assigned_by=admin.id,
                    assigned_at=datetime(2024, 10, 1, tzinfo=UTC),
                    returned_at=datetime(2025, 6, 30, tzinfo=UTC),
                ),
                # Açık bakım: yazıcı tamirde; bitince önceki durumu olan IN_STOCK'a dönecek
                MaintenanceRecordModel(
                    device_id=devices["PR-0001"].id,
                    technician_id=technician.id,
                    type=MaintenanceType.REPAIR,
                    description="Kağıt besleme ünitesi arızalı, yedek parça bekleniyor.",
                    previous_device_status=DeviceStatus.IN_STOCK,
                ),
                # Tamamlanmış bakım (bakım geçmişi ekranında görünecek)
                MaintenanceRecordModel(
                    device_id=devices["PC-0001"].id,
                    technician_id=users["elif.sahin"].id,
                    type=MaintenanceType.PART_REPLACEMENT,
                    description="RAM 8 GB'tan 16 GB'a yükseltildi.",
                    previous_device_status=DeviceStatus.ASSIGNED,
                    performed_at=datetime(2025, 3, 10, 9, 0, tzinfo=UTC),
                    completed_at=datetime(2025, 3, 10, 11, 30, tzinfo=UTC),
                ),
            ]
        )
        session.commit()
        return True

    def _user(
        self,
        key: str,
        full_name: str,
        role: UserRole,
        department: str,
        is_vip: bool = False,
        support_level: SupportLevel | None = None,
    ) -> UserModel:
        # Domain kuralıyla aynı: teknisyenin seviyesi belirtilmezse L1, diğer rollerde boş
        if role == UserRole.TECHNICIAN and support_level is None:
            support_level = SupportLevel.TIER_1
        return UserModel(
            full_name=full_name,
            email=f"{key}@{self.EMAIL_DOMAIN}",
            role=role,
            department=department,
            is_vip=is_vip,
            support_level=support_level,
        )

    def _build_users(self) -> dict[str, UserModel]:
        return {
            "ayse.yilmaz": self._user("ayse.yilmaz", "Ayşe Yılmaz", UserRole.USER, "Bilgisayar Mühendisliği"),
            "mehmet.kaya": self._user("mehmet.kaya", "Mehmet Kaya", UserRole.USER, "Elektrik-Elektronik Müh."),
            # VIP: ticket'ları otomatik olarak VipTicket decorator'ı ile sarılacak
            "dekan": self._user("dekan", "Prof. Dr. Zeynep Demir", UserRole.USER, "Dekanlık", is_vip=True),
            "ali.celik": self._user("ali.celik", "Ali Çelik", UserRole.TECHNICIAN, "Bilgi İşlem"),
            # Kıdemli teknisyen (L2): üst seviyeye eskale edilen talepler yalnızca ona atanabilir
            "elif.sahin": self._user(
                "elif.sahin", "Elif Şahin", UserRole.TECHNICIAN, "Bilgi İşlem", support_level=SupportLevel.TIER_2
            ),
            "bt.yonetici": self._user("bt.yonetici", "Can Arslan", UserRole.ADMIN, "Bilgi İşlem"),
        }

    @staticmethod
    def _build_devices() -> dict[str, DeviceModel]:
        rows = [
            ("PC-0001", "Masaüstü", "Dell", "OptiPlex 7010", "DL7010-A1B2", DeviceStatus.ASSIGNED, "B Blok 204", date(2023, 9, 1)),
            ("LT-0001", "Dizüstü", "Lenovo", "ThinkPad T14", "LNT14-C3D4", DeviceStatus.ASSIGNED, "Dekanlık", date(2024, 2, 15)),
            ("PR-0001", "Yazıcı", "HP", "LaserJet M404", "HPM404-E5F6", DeviceStatus.IN_REPAIR, "A Blok Koridor", date(2021, 5, 10)),
            ("PC-0002", "Masaüstü", "HP", "ProDesk 400", "HP400-G7H8", DeviceStatus.IN_STOCK, "BT Depo", date(2024, 9, 20)),
            ("PJ-0001", "Projeksiyon", "Epson", "EB-X51", "EPX51-I9J0", DeviceStatus.IN_STOCK, "BT Depo", date(2022, 3, 3)),
            ("PC-0003", "Masaüstü", "Dell", "OptiPlex 3020", "DL3020-K1L2", DeviceStatus.RETIRED, "Hurda Deposu", date(2015, 1, 12)),
        ]
        return {
            asset_tag: DeviceModel(
                asset_tag=asset_tag,
                type=type_,
                brand=brand,
                model=model,
                serial_number=serial,
                status=status,
                location=location,
                purchase_date=purchased,
            )
            for asset_tag, type_, brand, model, serial, status, location, purchased in rows
        }


def main() -> None:
    # Komut satırı giriş noktası: bağımlılıklar burada kurulur
    from app.core.config import get_settings

    seeded = DemoDataSeeder(Database(get_settings().database_url).session_factory).run()
    print("Örnek veriler eklendi." if seeded else "Veritabanında zaten kullanıcı var; seed atlandı.")


if __name__ == "__main__":
    main()
