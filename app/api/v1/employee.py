from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, desc
from typing import List, Optional
from datetime import datetime, date, timedelta
from app.core.database import get_db
from app.models.employee import Employee, Attendance, Performance, Payroll, AttendanceStatus
from app.schemas.employee import (
    EmployeeCreate, EmployeeResponse, EmployeeUpdate,
    AttendanceCreate, AttendanceResponse,
    MonthlySalaryCreate, MonthlySalaryResponse,
    MonthlyPerformanceCreate, MonthlyPerformanceResponse,
    TimesheetResponse
)
from app.api.v1.dependencies import get_current_user, get_current_manager_or_admin
from app.models.user import User

router = APIRouter()

# Employees
@router.get("/employees", response_model=List[EmployeeResponse])
def get_employees(
    skip: int = 0,
    limit: int = 100,
    department: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Employee)
    if department:
        query = query.filter(Employee.department == department)
    if is_active is not None:
        query = query.filter(Employee.is_active == is_active)
    employees = query.offset(skip).limit(limit).all()
    return employees

@router.get("/employees/{employee_id}", response_model=EmployeeResponse)
def get_employee(
    employee_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    return employee

@router.post("/employees", response_model=EmployeeResponse)
def create_employee(
    employee: EmployeeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager_or_admin)
):
    if db.query(Employee).filter(Employee.employee_id == employee.employee_id).first():
        raise HTTPException(status_code=400, detail="Employee ID already exists")
    if employee.email and db.query(Employee).filter(Employee.email == employee.email).first():
        raise HTTPException(status_code=400, detail="Email already exists")
    
    db_employee = Employee(**employee.dict())
    db.add(db_employee)
    db.commit()
    db.refresh(db_employee)
    return db_employee

@router.put("/employees/{employee_id}", response_model=EmployeeResponse)
def update_employee(
    employee_id: int,
    employee_update: EmployeeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager_or_admin)
):
    """Update employee - Manager or Admin only"""
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    update_data = employee_update.dict(exclude_unset=True)
    
    # Check email uniqueness if being updated
    if "email" in update_data and update_data["email"]:
        existing = db.query(Employee).filter(
            Employee.email == update_data["email"],
            Employee.id != employee_id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already exists")
    
    for field, value in update_data.items():
        setattr(employee, field, value)
    
    employee.updated_at = datetime.now()
    db.commit()
    db.refresh(employee)
    return employee

@router.delete("/employees/{employee_id}")
def delete_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager_or_admin)
):
    """Delete employee - Manager or Admin only (soft delete)"""
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    # Soft delete - set is_active to False
    employee.is_active = False
    employee.updated_at = datetime.now()
    db.commit()
    return {"message": "Employee deactivated successfully", "employee_id": employee_id}

# Attendance
@router.get("/attendance", response_model=List[AttendanceResponse])
def get_attendance(
    employee_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Attendance)
    if employee_id:
        query = query.filter(Attendance.employee_id == employee_id)
    if start_date:
        query = query.filter(Attendance.date >= start_date)
    if end_date:
        query = query.filter(Attendance.date <= end_date)
    
    records = query.options(joinedload(Attendance.employee)).order_by(desc(Attendance.date)).offset(skip).limit(limit).all()
    
    result = []
    for record in records:
        record_dict = AttendanceResponse.from_orm(record).dict()
        record_dict["employee_name"] = f"{record.employee.first_name} {record.employee.last_name}" if record.employee else None
        result.append(AttendanceResponse(**record_dict))
    return result

@router.post("/attendance", response_model=AttendanceResponse)
def create_attendance(
    attendance: AttendanceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create attendance record - automatically calculates hours if check_in/check_out provided"""
    # Check if attendance already exists for this employee and date
    existing = db.query(Attendance).filter(
        Attendance.employee_id == attendance.employee_id,
        Attendance.date == attendance.date
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Attendance record already exists for this date")
    
    attendance_data = attendance.dict()
    
    # Auto-calculate hours_worked if check_in and check_out are provided
    if attendance_data.get("check_in") and attendance_data.get("check_out"):
        try:
            # Handle string datetime inputs
            if isinstance(attendance_data["check_in"], str):
                check_in = datetime.fromisoformat(attendance_data["check_in"].replace("Z", "+00:00"))
            else:
                check_in = attendance_data["check_in"]
            
            if isinstance(attendance_data["check_out"], str):
                check_out = datetime.fromisoformat(attendance_data["check_out"].replace("Z", "+00:00"))
            else:
                check_out = attendance_data["check_out"]
            
            if check_in and check_out:
                time_diff = check_out - check_in
                hours_worked = time_diff.total_seconds() / 3600.0
                attendance_data["hours_worked"] = round(hours_worked, 2)
        except Exception as e:
            # If datetime parsing fails, don't calculate hours
            pass
    
    db_attendance = Attendance(**attendance_data)
    db.add(db_attendance)
    db.commit()
    db.refresh(db_attendance)
    
    record_dict = AttendanceResponse.from_orm(db_attendance).dict()
    record_dict["employee_name"] = f"{db_attendance.employee.first_name} {db_attendance.employee.last_name}" if db_attendance.employee else None
    return AttendanceResponse(**record_dict)

@router.put("/attendance/{attendance_id}", response_model=AttendanceResponse)
def update_attendance(
    attendance_id: int,
    attendance_update: AttendanceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager_or_admin)
):
    """Update attendance record - Manager or Admin only"""
    attendance = db.query(Attendance).filter(Attendance.id == attendance_id).first()
    if not attendance:
        raise HTTPException(status_code=404, detail="Attendance record not found")
    
    update_data = attendance_update.dict(exclude_unset=True)
    
    # Auto-calculate hours_worked if check_in and check_out are provided
    if update_data.get("check_in") and update_data.get("check_out"):
        check_in = update_data["check_in"]
        check_out = update_data["check_out"]
        if isinstance(check_in, str):
            check_in = datetime.fromisoformat(check_in.replace("Z", "+00:00"))
        if isinstance(check_out, str):
            check_out = datetime.fromisoformat(check_out.replace("Z", "+00:00"))
        if check_in and check_out:
            time_diff = check_out - check_in
            hours_worked = time_diff.total_seconds() / 3600.0
            update_data["hours_worked"] = round(hours_worked, 2)
    
    for field, value in update_data.items():
        setattr(attendance, field, value)
    
    db.commit()
    db.refresh(attendance)
    
    record_dict = AttendanceResponse.from_orm(attendance).dict()
    record_dict["employee_name"] = f"{attendance.employee.first_name} {attendance.employee.last_name}" if attendance.employee else None
    return AttendanceResponse(**record_dict)

@router.delete("/attendance/{attendance_id}")
def delete_attendance(
    attendance_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager_or_admin)
):
    """Delete attendance record - Manager or Admin only"""
    attendance = db.query(Attendance).filter(Attendance.id == attendance_id).first()
    if not attendance:
        raise HTTPException(status_code=404, detail="Attendance record not found")
    
    db.delete(attendance)
    db.commit()
    return {"message": "Attendance record deleted successfully"}

@router.get("/employees/{employee_id}/attendance/stats")
def get_employee_attendance_stats(
    employee_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not start_date:
        start_date = date.today() - timedelta(days=30)
    if not end_date:
        end_date = date.today()
    
    records = db.query(Attendance).filter(
        Attendance.employee_id == employee_id,
        Attendance.date >= start_date,
        Attendance.date <= end_date
    ).all()
    
    present_count = sum(1 for r in records if r.status == AttendanceStatus.PRESENT)
    absent_count = sum(1 for r in records if r.status == AttendanceStatus.ABSENT)
    late_count = sum(1 for r in records if r.status == AttendanceStatus.LATE)
    total_hours = sum(r.hours_worked or 0 for r in records)
    
    return {
        "employee_id": employee_id,
        "period_start": start_date,
        "period_end": end_date,
        "present_days": present_count,
        "absent_days": absent_count,
        "late_days": late_count,
        "total_hours_worked": total_hours
    }

# Payroll
@router.get("/payroll")
def get_payroll(
    employee_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Payroll)
    if employee_id:
        query = query.filter(Payroll.employee_id == employee_id)
    records = query.order_by(desc(Payroll.pay_period_start)).offset(skip).limit(limit).all()
    
    result = []
    for record in records:
        result.append({
            "id": record.id,
            "employee_id": record.employee_id,
            "employee_name": f"{record.employee.first_name} {record.employee.last_name}" if record.employee else None,
            "pay_period_start": record.pay_period_start,
            "pay_period_end": record.pay_period_end,
            "base_salary": record.base_salary,
            "bonuses": record.bonuses,
            "deductions": record.deductions,
            "net_salary": record.net_salary,
            "status": record.status
        })
    return result

@router.post("/payroll")
def create_payroll(
    payroll_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager_or_admin)
):
    employee = db.query(Employee).filter(Employee.id == payroll_data["employee_id"]).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    net_salary = payroll_data["base_salary"] + payroll_data.get("bonuses", 0) - payroll_data.get("deductions", 0)
    
    payroll = Payroll(
        employee_id=payroll_data["employee_id"],
        pay_period_start=payroll_data["pay_period_start"],
        pay_period_end=payroll_data["pay_period_end"],
        base_salary=payroll_data["base_salary"],
        bonuses=payroll_data.get("bonuses", 0),
        deductions=payroll_data.get("deductions", 0),
        net_salary=net_salary
    )
    db.add(payroll)
    db.commit()
    db.refresh(payroll)
    
    return {
        "id": payroll.id,
        "employee_id": payroll.employee_id,
        "net_salary": payroll.net_salary,
        "status": payroll.status
    }

# Monthly Salary Management
@router.post("/employees/monthly-salary", response_model=MonthlySalaryResponse)
def create_monthly_salary(
    salary_data: MonthlySalaryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager_or_admin)
):
    """Create monthly salary record - Manager or Admin only"""
    employee = db.query(Employee).filter(Employee.id == salary_data.employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    # Check if salary already exists for this month
    existing_payroll = db.query(Payroll).filter(
        Payroll.employee_id == salary_data.employee_id,
        func.extract('year', Payroll.pay_period_start) == salary_data.year,
        func.extract('month', Payroll.pay_period_start) == salary_data.month
    ).first()
    
    if existing_payroll:
        raise HTTPException(status_code=400, detail="Salary record already exists for this month")
    
    # Calculate pay period dates
    from datetime import date as date_type
    pay_period_start = date_type(salary_data.year, salary_data.month, 1)
    if salary_data.month == 12:
        pay_period_end = date_type(salary_data.year + 1, 1, 1) - timedelta(days=1)
    else:
        pay_period_end = date_type(salary_data.year, salary_data.month + 1, 1) - timedelta(days=1)
    
    net_salary = salary_data.base_salary + salary_data.bonuses - salary_data.deductions
    
    payroll = Payroll(
        employee_id=salary_data.employee_id,
        pay_period_start=pay_period_start,
        pay_period_end=pay_period_end,
        base_salary=salary_data.base_salary,
        bonuses=salary_data.bonuses,
        deductions=salary_data.deductions,
        net_salary=net_salary,
        status="pending"
    )
    db.add(payroll)
    db.commit()
    db.refresh(payroll)
    
    return {
        "id": payroll.id,
        "employee_id": payroll.employee_id,
        "employee_name": f"{employee.first_name} {employee.last_name}",
        "year": salary_data.year,
        "month": salary_data.month,
        "base_salary": payroll.base_salary,
        "bonuses": payroll.bonuses,
        "deductions": payroll.deductions,
        "net_salary": payroll.net_salary,
        "notes": salary_data.notes,
        "created_at": payroll.created_at
    }

@router.get("/employees/{employee_id}/monthly-salary")
def get_employee_monthly_salaries(
    employee_id: int,
    year: Optional[int] = None,
    month: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get monthly salary records for an employee"""
    query = db.query(Payroll).filter(Payroll.employee_id == employee_id)
    
    if year:
        query = query.filter(func.extract('year', Payroll.pay_period_start) == year)
    if month:
        query = query.filter(func.extract('month', Payroll.pay_period_start) == month)
    
    payrolls = query.order_by(desc(Payroll.pay_period_start)).all()
    
    result = []
    for payroll in payrolls:
        result.append({
            "id": payroll.id,
            "employee_id": payroll.employee_id,
            "employee_name": f"{payroll.employee.first_name} {payroll.employee.last_name}" if payroll.employee else None,
            "year": payroll.pay_period_start.year,
            "month": payroll.pay_period_start.month,
            "base_salary": payroll.base_salary,
            "bonuses": payroll.bonuses,
            "deductions": payroll.deductions,
            "net_salary": payroll.net_salary,
            "status": payroll.status,
            "created_at": payroll.created_at
        })
    return result

# Monthly Performance Management
@router.post("/employees/monthly-performance", response_model=MonthlyPerformanceResponse)
def create_monthly_performance(
    performance_data: MonthlyPerformanceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager_or_admin)
):
    """Create monthly performance record - Manager or Admin only"""
    employee = db.query(Employee).filter(Employee.id == performance_data.employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    # Check if performance already exists for this month
    from datetime import date as date_type
    review_date = date_type(performance_data.year, performance_data.month, 1)
    
    existing = db.query(Performance).filter(
        Performance.employee_id == performance_data.employee_id,
        func.extract('year', Performance.review_date) == performance_data.year,
        func.extract('month', Performance.review_date) == performance_data.month
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Performance record already exists for this month")
    
    # Convert performance_score (0-100) to rating (1-5)
    rating = max(1, min(5, int((performance_data.performance_score / 100) * 5)))
    
    performance = Performance(
        employee_id=performance_data.employee_id,
        review_date=review_date,
        rating=rating,
        goals_achieved=performance_data.goals_achieved,
        goals_total=performance_data.goals_total,
        comments=performance_data.comments
    )
    db.add(performance)
    db.commit()
    db.refresh(performance)
    
    return {
        "id": performance.id,
        "employee_id": performance.employee_id,
        "employee_name": f"{employee.first_name} {employee.last_name}",
        "year": performance_data.year,
        "month": performance_data.month,
        "performance_score": performance_data.performance_score,
        "goals_achieved": performance.goals_achieved,
        "goals_total": performance.goals_total,
        "comments": performance.comments,
        "created_at": performance.created_at
    }

@router.get("/employees/{employee_id}/monthly-performance")
def get_employee_monthly_performance(
    employee_id: int,
    year: Optional[int] = None,
    month: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get monthly performance records for an employee"""
    query = db.query(Performance).filter(Performance.employee_id == employee_id)
    
    if year:
        query = query.filter(func.extract('year', Performance.review_date) == year)
    if month:
        query = query.filter(func.extract('month', Performance.review_date) == month)
    
    performances = query.order_by(desc(Performance.review_date)).all()
    
    result = []
    for perf in performances:
        # Convert rating (1-5) back to performance_score (0-100)
        performance_score = (perf.rating / 5) * 100 if perf.rating else 0
        result.append({
            "id": perf.id,
            "employee_id": perf.employee_id,
            "employee_name": f"{perf.employee.first_name} {perf.employee.last_name}" if perf.employee else None,
            "year": perf.review_date.year,
            "month": perf.review_date.month,
            "performance_score": performance_score,
            "goals_achieved": perf.goals_achieved,
            "goals_total": perf.goals_total,
            "comments": perf.comments,
            "created_at": perf.created_at
        })
    return result

# Timesheet Generation
@router.get("/employees/{employee_id}/timesheet", response_model=TimesheetResponse)
def generate_timesheet(
    employee_id: int,
    year: int,
    month: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Auto-generate timesheet from attendance logs for a specific month"""
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    from datetime import date as date_type
    start_date = date_type(year, month, 1)
    if month == 12:
        end_date = date_type(year + 1, 1, 1) - timedelta(days=1)
    else:
        end_date = date_type(year, month + 1, 1) - timedelta(days=1)
    
    # Get all attendance records for the month
    attendance_records = db.query(Attendance).filter(
        Attendance.employee_id == employee_id,
        Attendance.date >= start_date,
        Attendance.date <= end_date
    ).order_by(Attendance.date).all()
    
    # Calculate statistics
    total_days = (end_date - start_date).days + 1
    present_days = sum(1 for r in attendance_records if r.status == AttendanceStatus.PRESENT)
    absent_days = sum(1 for r in attendance_records if r.status == AttendanceStatus.ABSENT)
    late_days = sum(1 for r in attendance_records if r.status == AttendanceStatus.LATE)
    leave_days = sum(1 for r in attendance_records if r.status == AttendanceStatus.LEAVE)
    total_hours_worked = sum(r.hours_worked or 0 for r in attendance_records)
    
    # Format attendance records
    formatted_records = []
    for record in attendance_records:
        record_dict = AttendanceResponse.from_orm(record).dict()
        record_dict["employee_name"] = f"{employee.first_name} {employee.last_name}"
        formatted_records.append(AttendanceResponse(**record_dict))
    
    return {
        "employee_id": employee_id,
        "employee_name": f"{employee.first_name} {employee.last_name}",
        "year": year,
        "month": month,
        "total_days": total_days,
        "present_days": present_days,
        "absent_days": absent_days,
        "late_days": late_days,
        "leave_days": leave_days,
        "total_hours_worked": round(total_hours_worked, 2),
        "attendance_records": formatted_records
    }


# AI HR FEATURES

@router.get("/ai/performance-anomalies")
def get_performance_anomalies(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager_or_admin)
):
    """
    AI detects performance anomalies and attendance irregularities.
    Identifies employees with unusual patterns that need attention.
    """
    from app.services.ai_service import call_groq_chat, GROQ_MODEL_CHAT
    
    try:
        # Get all active employees with their recent performance and attendance
        employees_data = db.query(Employee).filter(Employee.is_active == True).all()
        
        anomalies = []
        
        for emp in employees_data:
            # Get recent performance records (last 6 months)
            recent_perf = db.query(Performance).filter(
                Performance.employee_id == emp.id,
                Performance.review_date >= datetime.now() - timedelta(days=180)
            ).order_by(desc(Performance.review_date)).all()
            
            # Get recent attendance (last 30 days)
            recent_attend = db.query(Attendance).filter(
                Attendance.employee_id == emp.id,
                Attendance.date >= datetime.now().date() - timedelta(days=30)
            ).all()
            
            # Calculate performance metrics
            perf_ratings = [p.rating for p in recent_perf if p.rating]
            avg_rating = sum(perf_ratings) / len(perf_ratings) if perf_ratings else None
            rating_trend = "declining" if len(perf_ratings) >= 2 and perf_ratings[-1] < perf_ratings[-2] else "stable"
            
            # Calculate attendance metrics
            absent_count = len([a for a in recent_attend if a.status == AttendanceStatus.ABSENT])
            late_count = len([a for a in recent_attend if a.status == AttendanceStatus.LATE])
            present_count = len([a for a in recent_attend if a.status == AttendanceStatus.PRESENT])
            attendance_rate = (present_count / len(recent_attend) * 100) if recent_attend else 0
            
            # Detect anomalies
            is_anomaly = False
            reasons = []
            
            # Performance anomalies
            if avg_rating and avg_rating < 2.5:
                is_anomaly = True
                reasons.append(f"Low performance rating ({avg_rating:.1f}/5)")
            if rating_trend == "declining":
                is_anomaly = True
                reasons.append("Performance declining trend")
            
            # Attendance anomalies
            if absent_count >= 5:
                is_anomaly = True
                reasons.append(f"{absent_count} absences in last 30 days")
            if late_count >= 8:
                is_anomaly = True
                reasons.append(f"{late_count} late arrivals in last 30 days")
            if attendance_rate < 80:
                is_anomaly = True
                reasons.append(f"Low attendance rate ({attendance_rate:.0f}%)")
            
            if is_anomaly:
                anomalies.append({
                    "employee_id": emp.id,
                    "name": f"{emp.first_name} {emp.last_name}",
                    "position": emp.position,
                    "department": emp.department,
                    "hire_date": emp.hire_date.isoformat(),
                    "avg_performance_rating": round(avg_rating, 2) if avg_rating else None,
                    "performance_trend": rating_trend,
                    "recent_reviews": len(recent_perf),
                    "attendance_rate": round(attendance_rate, 2),
                    "absent_days": absent_count,
                    "late_days": late_count,
                    "anomaly_reasons": reasons,
                    "severity": "critical" if len(reasons) >= 3 else "warning"
                })
        
        # AI Analysis of anomalies
        anomaly_summary = {
            "total_employees": len(employees_data),
            "anomaly_count": len(anomalies),
            "anomaly_percentage": (len(anomalies) / max(len(employees_data), 1)) * 100,
            "critical_count": len([a for a in anomalies if a["severity"] == "critical"]),
            "anomalies": sorted(anomalies, key=lambda x: len(x["anomaly_reasons"]), reverse=True)
        }
        
        prompt = f"""
        Analyze the following employee performance and attendance anomalies data:
        
        Total Employees: {anomaly_summary['total_employees']}
        Employees with Anomalies: {anomaly_summary['anomaly_count']} ({anomaly_summary['anomaly_percentage']:.1f}%)
        Critical Cases: {anomaly_summary['critical_count']}
        
        Top Anomalies:
        {chr(10).join([f"- {a['name']} ({a['position']}): {', '.join(a['anomaly_reasons'])}" for a in anomaly_summary['anomalies'][:10]])}
        
        Provide:
        1. Summary of key issues and patterns
        2. Risk assessment for each anomaly type
        3. Root cause analysis (performance vs attendance)
        4. Immediate action recommendations
        5. Follow-up timeline and responsibilities
        
        Be professional and constructive.
        """
        
        try:
            ai_analysis = call_groq_chat(
                messages=[
                    {"role": "system", "content": "You are an HR analytics expert. Provide professional analysis of employee performance and attendance issues."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=700,
                model=GROQ_MODEL_CHAT
            )
        except Exception:
            critical_issues = ', '.join([a['name'] for a in anomaly_summary['anomalies'][:3]])
            ai_analysis = f"Flagged {anomaly_summary['anomaly_count']} employees with anomalies. Critical cases: {critical_issues}. Recommend immediate HR review."
        
        return {
            "summary": anomaly_summary,
            "ai_analysis": ai_analysis,
            "generated_at": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing performance anomalies: {str(e)}")


@router.post("/ai/hr-report")
def generate_hr_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager_or_admin)
):
    """
    AI generates natural-language HR reports.
    Creates professional reports on workforce metrics and trends.
    """
    from app.services.ai_service import call_groq_chat, GROQ_MODEL_CHAT
    
    try:
        # Gather comprehensive HR metrics
        total_employees = db.query(func.count(Employee.id)).filter(Employee.is_active == True).scalar()
        
        # Department breakdown
        by_dept = db.query(
            Employee.department,
            func.count(Employee.id).label("count"),
            func.avg(Employee.salary).label("avg_salary")
        ).filter(Employee.is_active == True).group_by(Employee.department).all()
        
        # Attendance metrics (last 30 days)
        date_threshold = datetime.now().date() - timedelta(days=30)
        attendance_stats = db.query(
            Attendance.status,
            func.count(Attendance.id).label("count")
        ).filter(Attendance.date >= date_threshold).group_by(Attendance.status).all()
        
        # Performance metrics (last 6 months)
        perf_threshold = datetime.now().date() - timedelta(days=180)
        performance_stats = db.query(
            func.avg(Performance.rating).label("avg_rating"),
            func.count(Performance.id).label("total_reviews")
        ).filter(Performance.review_date >= perf_threshold).first()
        
        # Turnover data (last year)
        year_ago = datetime.now().date() - timedelta(days=365)
        inactive_employees = db.query(func.count(Employee.id)).filter(
            Employee.is_active == False,
            Employee.updated_at >= year_ago
        ).scalar()
        
        # Compile metrics
        dept_list = [
            {
                "name": d.department or "Unassigned",
                "count": d.count,
                "avg_salary": round(d.avg_salary, 2) if d.avg_salary else 0
            }
            for d in by_dept
        ]
        
        attend_dict = {a.status.value: a.count for a in attendance_stats}
        
        hr_metrics = {
            "total_active_employees": total_employees,
            "total_payroll": round(
                db.query(func.sum(Employee.salary)).filter(Employee.is_active == True).scalar() or 0,
                2
            ),
            "departments": dept_list,
            "avg_department_size": round(total_employees / max(len(dept_list), 1), 1),
            "attendance_last_30_days": {
                "present": attend_dict.get("present", 0),
                "absent": attend_dict.get("absent", 0),
                "late": attend_dict.get("late", 0),
                "leave": attend_dict.get("leave", 0)
            },
            "avg_performance_rating": round(performance_stats.avg_rating, 2) if performance_stats.avg_rating else None,
            "recent_reviews": performance_stats.total_reviews if performance_stats else 0,
            "turnover_last_year": inactive_employees
        }
        
        # AI Report Generation
        prompt = f"""
        Generate a professional HR report based on the following workforce metrics:
        
        Workforce Overview:
        - Total Active Employees: {hr_metrics['total_active_employees']}
        - Total Payroll: ${hr_metrics['total_payroll']:,.2f}
        - Number of Departments: {len(hr_metrics['departments'])}
        
        Department Breakdown:
        {chr(10).join([f"- {d['name']}: {d['count']} employees (avg salary: ${d['avg_salary']:,.0f})" for d in hr_metrics['departments']])}
        
        Attendance (Last 30 Days):
        - Present: {hr_metrics['attendance_last_30_days']['present']}
        - Absent: {hr_metrics['attendance_last_30_days']['absent']}
        - Late: {hr_metrics['attendance_last_30_days']['late']}
        - Leave: {hr_metrics['attendance_last_30_days']['leave']}
        
        Performance:
        - Average Rating: {hr_metrics['avg_performance_rating']}/5
        - Reviews Conducted: {hr_metrics['recent_reviews']}
        
        Turnover:
        - Departures Last Year: {hr_metrics['turnover_last_year']}
        
        Create a comprehensive HR report including:
        1. Executive Summary of workforce health
        2. Department performance analysis
        3. Attendance and punctuality assessment
        4. Employee performance insights
        5. Recommendations for HR improvements
        
        Keep it professional, data-driven, and actionable.
        """
        
        try:
            report_content = call_groq_chat(
                messages=[
                    {"role": "system", "content": "You are a senior HR consultant. Write professional, comprehensive HR reports."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=800,
                model=GROQ_MODEL_CHAT
            )
        except Exception:
            report_content = f"**HR Report Summary**\n\nWorkforce comprises {hr_metrics['total_active_employees']} active employees across {len(hr_metrics['departments'])} departments. Average performance rating is {hr_metrics['avg_performance_rating']}/5 with {hr_metrics['recent_reviews']} recent reviews. Turnover has been {hr_metrics['turnover_last_year']} departures in the past year."
        
        return {
            "metrics": hr_metrics,
            "report_content": report_content,
            "generated_at": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating HR report: {str(e)}")


@router.post("/ai/training-recommendations")
def get_training_recommendations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager_or_admin)
):
    """
    AI suggests training/upskilling for low-performing staff.
    Provides personalized development recommendations based on performance data.
    """
    from app.services.ai_service import call_groq_chat, GROQ_MODEL_CHAT
    
    try:
        # Identify low-performing employees (rating < 3)
        low_performers = db.query(Employee).filter(Employee.is_active == True).all()
        
        training_candidates = []
        
        for emp in low_performers:
            # Get latest performance reviews
            recent_reviews = db.query(Performance).filter(
                Performance.employee_id == emp.id,
                Performance.review_date >= datetime.now().date() - timedelta(days=180)
            ).order_by(desc(Performance.review_date)).all()
            
            if recent_reviews:
                avg_rating = sum([r.rating for r in recent_reviews if r.rating]) / len([r.rating for r in recent_reviews if r.rating])
                
                # Low performer if rating < 3
                if avg_rating < 3.0:
                    # Analyze performance patterns
                    goals_achieved = sum([r.goals_achieved or 0 for r in recent_reviews])
                    goals_total = sum([r.goals_total or 0 for r in recent_reviews])
                    goals_completion_rate = (goals_achieved / goals_total * 100) if goals_total > 0 else 0
                    
                    # Get comments to understand weaknesses
                    comments = [r.comments for r in recent_reviews if r.comments]
                    
                    training_candidates.append({
                        "employee_id": emp.id,
                        "name": f"{emp.first_name} {emp.last_name}",
                        "position": emp.position,
                        "department": emp.department,
                        "salary": emp.salary,
                        "avg_rating": round(avg_rating, 2),
                        "goals_completion": round(goals_completion_rate, 2),
                        "review_count": len(recent_reviews),
                        "performance_comments": comments[:2],  # Last 2 comments
                        "improvement_potential": "high" if goals_completion_rate > 50 else "medium" if goals_completion_rate > 25 else "low"
                    })
        
        # Sort by average rating (most critical first)
        training_candidates.sort(key=lambda x: x['avg_rating'])
        
        summary = {
            "total_low_performers": len(training_candidates),
            "total_active_employees": db.query(func.count(Employee.id)).filter(Employee.is_active == True).scalar(),
            "low_performer_percentage": (len(training_candidates) / max(db.query(func.count(Employee.id)).filter(Employee.is_active == True).scalar(), 1)) * 100,
            "high_potential": len([c for c in training_candidates if c["improvement_potential"] == "high"]),
            "candidates": training_candidates[:15]  # Top 15 candidates
        }
        
        # AI Training Recommendation Generation
        prompt = f"""
        Generate personalized training and upskilling recommendations for the following low-performing employees:
        
        Overview:
        - Low Performers: {summary['total_low_performers']} out of {summary['total_active_employees']} employees ({summary['low_performer_percentage']:.1f}%)
        - High Improvement Potential: {summary['high_potential']}
        
        Detailed Analysis:
        {chr(10).join([f"- {c['name']} ({c['position']}): Rating {c['avg_rating']}/5, Goal Completion {c['goals_completion']}%" for c in summary['candidates'][:8]])}
        
        For each low performer, provide:
        1. Root cause analysis of underperformance
        2. Specific skill gaps to address
        3. Recommended training programs (soft skills, technical, leadership)
        4. Mentoring/coaching suggestions
        5. Expected outcomes and timeline
        6. Success metrics
        
        Prioritize by improvement potential and departmental impact.
        """
        
        try:
            recommendations = call_groq_chat(
                messages=[
                    {"role": "system", "content": "You are a talent development expert. Provide specific, actionable training recommendations for employee development."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=900,
                model=GROQ_MODEL_CHAT
            )
        except Exception:
            bottom_3 = ', '.join([c['name'] for c in training_candidates[:3]])
            recommendations = f"Identified {summary['total_low_performers']} employees needing development. Priority: {bottom_3}. Recommend communication, technical upskilling, and management support programs tailored per employee."
        
        return {
            "summary": summary,
            "recommendations": recommendations,
            "generated_at": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating training recommendations: {str(e)}")
