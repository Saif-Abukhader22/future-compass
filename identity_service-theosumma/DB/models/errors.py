import uuid

from sqlalchemy import Column, String, DateTime, func, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from identity_service.DB.database import Base

class FrontEndError(Base):
    __tablename__="frontend_errors"
    error_id= Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    path = Column(String,nullable=False)
    time = Column(DateTime(timezone=True), default=func.now())
    exception = Column(Text ,nullable=False)
    traceback =Column(Text ,nullable=False)