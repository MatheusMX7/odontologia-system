from sqlalchemy.orm import Session

from ..models import ClinicSettings


def get_clinic_settings(db: Session) -> ClinicSettings:
    cs = db.get(ClinicSettings, 1)
    if cs is None:
        cs = ClinicSettings(id=1)
        db.add(cs)
        db.commit()
    return cs


def working_days(cs: ClinicSettings) -> set[int]:
    return {int(x) for x in (cs.working_days or "").split(",") if x != ""}
