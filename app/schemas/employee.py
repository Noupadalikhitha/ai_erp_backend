from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date

class EmployeeCreate(BaseModel):
    employee_id: str
    first_name: str
    last_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    position: str
    department: str
    hire_date: date
    salary: Optional[float] = None

class EmployeeUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    position: Optional[str] = None
    department: Optional[str] = None
    salary: Optional[float] = None
    is_active: Optional[bool] = None

class EmployeeResponse(BaseModel):
    id: int
    employee_id: str
    first_name: str
    last_name: str
    email: Optional[str]
    phone: Optional[str]
    position: str
    department: str
    hire_date: date
    salary: Optional[float]
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class AttendanceCreate(BaseModel):
    employee_id: int
    date: date
    status: str
    check_in: Optional[datetime] = None
    check_out: Optional[datetime] = None
    hours_worked: Optional[float] = None
    notes: Optional[str] = None

class AttendanceResponse(BaseModel):
    id: int
    employee_id: int
    employee_name: Optional[str] = None
    date: date
    status: str
    check_in: Optional[datetime]
    check_out: Optional[datetime]
    hours_worked: Optional[float]
    notes: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

class MonthlySalaryCreate(BaseModel):
    employee_id: int
    year: int
    month: int
    base_salary: float
    bonuses: float = 0.0
    deductions: float = 0.0
    notes: Optional[str] = None

class MonthlySalaryResponse(BaseModel):
    id: int
    employee_id: int
    employee_name: Optional[str] = None
    year: int
    month: int
    base_salary: float
    bonuses: float
    deductions: float
    net_salary: float
    notes: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

class MonthlyPerformanceCreate(BaseModel):
    employee_id: int
    year: int
    month: int
    performance_score: float  # 0-100
    goals_achieved: int
    goals_total: int
    comments: Optional[str] = None

class MonthlyPerformanceResponse(BaseModel):
    id: int
    employee_id: int
    employee_name: Optional[str] = None
    year: int
    month: int
    performance_score: float
    goals_achieved: int
    goals_total: int
    comments: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

class TimesheetResponse(BaseModel):
    employee_id: int
    employee_name: str
    year: int
    month: int
    total_days: int
    present_days: int
    absent_days: int
    late_days: int
    leave_days: int
    total_hours_worked: float
    attendance_records: List[AttendanceResponse]
    
    class Config:
        from_attributes = True


