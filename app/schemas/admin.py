from pydantic import BaseModel
from typing import Optional

class SystemSettingsSchema(BaseModel):
    access_token_expire_minutes: int
    max_upload_size: int

class SystemSettingsUpdateSchema(BaseModel):
    access_token_expire_minutes: Optional[int] = None
    max_upload_size: Optional[int] = None
