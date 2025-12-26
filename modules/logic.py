import pandas as pd
import streamlit as st

def get_unique_subjects(db_manager):
    """
    Fetches all unique subjects from the 'Students' sheet.
    Assumes 'parsed_subjects' column exists and is comma-separated string.
    """
    df = db_manager.load_dataframe("Students")
    if df.empty or 'parsed_subjects' not in df.columns:
        return []

    unique_subjects = set()
    for subjects_str in df['parsed_subjects']:
        if pd.notna(subjects_str) and str(subjects_str).strip() != "":
            # Split by comma (it was joined by comma in app.py before saving)
            subjects = str(subjects_str).split(',')
            for sub in subjects:
                unique_subjects.add(sub.strip())
    
    return sorted(list(unique_subjects))

def get_unique_classes(db_manager):
    """
    Fetches all unique classes (Grade-Class combo?) or just Class?
    User request: "Select Student's Class (Checkbox)".
    Usually we need Grade-Class e.g. "1-1", "1-2".
    Let's parse columns '학년', '반' from Students.
    """
    df = db_manager.load_dataframe("Students")
    if df.empty or '학년' not in df.columns or '반' not in df.columns:
        # Fallback if no students yet
        return [f"{i}반" for i in range(1, 11)]

    # Create set of "Grade-Class" or just "Class" if grade is implicitly mixed?
    # Usually these courses are grade-specific or mixed?
    # Prompt says: "Student's Class(Class)".
    # Let's use "Grade-Class" format for uniqueness, e.g. "1-1", "2-1".
    # Or if the user just wants '1, 2, 3' (indicating Class 1, Class 2 regardless of grade?)
    # "teacher assigned to 'Students' Class' ... 'Example: Kim (Class 1, 2)'"
    # This implies Class Number. Let's assume Class Number for now, or Grade-Class if data varies.
    # Let's return "Grade-Class" to be safe.
    
    # Ensure encoded as string
    df['학년'] = df['학년'].astype(str)
    df['반'] = df['반'].astype(str)
    
    unique_classes = set()
    for _, row in df.iterrows():
        # clean leading zeros if needed?
        g = row['학년']
        c = row['반']
        class_str = f"{g}-{c}"
        unique_classes.add(class_str)
        
    return sorted(list(unique_classes))


def save_teacher_assignment(db_manager, subject, teacher_name, classes, room):
    """
    Saves or updates a teacher assignment.
    Structure of 'Teachers' sheet: [Subject, TeacherName, AssignedClasses, Room]
    AssignedClasses stored as comma-separated string.
    """
    df = db_manager.load_dataframe("Teachers")
    
    # If sheet is empty, create DataFrame with columns
    if df.empty:
        df = pd.DataFrame(columns=['Subject', 'TeacherName', 'AssignedClasses', 'Room'])

    # Check for existing assignment for this Teacher+Subject? 
    # Or can a teacher teach same subject to different classes in separate entries?
    # Logic: One row per (Subject, Teacher). Classes are aggregated? 
    # Or One row per (Subject, Teacher, Class)?
    # User said: "Checkboxes for classes".
    # Let's simple model: One row per Assignment.
    
    # To avoid complex updates, let's just append for now, or ID based?
    # Better: Subject + Teacher is unique? No, Subject is unique?
    # A subject (Kor_4) can have multiple teachers (Teacher A for Class 1, Teacher B for Class 2).
    # So (Subject, AssignedClasses) should not overlap? Complex.
    # Let's just Append and allow user to view/delete in UI.
    
    new_entry = {
         'Subject': subject,
         'TeacherName': teacher_name,
         'AssignedClasses': ','.join(map(str, classes)),
         'Room': room
    }
    
    # Simple append using concat
    new_df = pd.DataFrame([new_entry])
    df = pd.concat([df, new_df], ignore_index=True)
    
    return db_manager.save_dataframe("Teachers", df)

def get_teacher_assignments(db_manager):
    return db_manager.load_dataframe("Teachers")

def load_timetable(db_manager):
    return db_manager.load_dataframe("Timetable")

def add_timetable_slot(db_manager, week, date, day, period, subject):
    """
    Adds a subject to a specific Week, Day, Period.
    Structure: [Week, Date, Day, Period, Subject]
    """
    df = db_manager.load_dataframe("Timetable")
    if df.empty:
        df = pd.DataFrame(columns=['Week', 'Date', 'Day', 'Period', 'Subject'])
        
    # Ensure columns exist (migration)
    if 'Week' not in df.columns: df['Week'] = 1
    if 'Date' not in df.columns: df['Date'] = ""

    # Check if exactly same entry exists to prevent dupes
    # (Week, Day, Period, Subject) should be unique
    exclude = df[
        (df['Week'].astype(str) == str(week)) &
        (df['Day'] == day) & 
        (df['Period'] == period) & 
        (df['Subject'] == subject)
    ]
    if not exclude.empty:
        return False, "이미 해당 주차, 요일, 교시에 해당 과목이 배정되어 있습니다."

    new_row = pd.DataFrame([{'Week': week, 'Date': date, 'Day': day, 'Period': period, 'Subject': subject}])
    df = pd.concat([df, new_row], ignore_index=True)
    
    success = db_manager.save_dataframe("Timetable", df)
    return success, "저장 완료"

def delete_timetable_slot(db_manager, week, day, period, subject):
    df = db_manager.load_dataframe("Timetable")
    if df.empty:
        return
    
    # Ensure columns
    if 'Week' not in df.columns: 
        # If deleting from legacy data (no week), assume week 1?? 
        # Or just match Day/Period/Subject?
        # Let's matching stricter if week is provided.
        # But for safety, match Week if column exists.
        pass

    condition = (df['Day'] == day) & (df['Period'] == period) & (df['Subject'] == subject)
    if 'Week' in df.columns:
        condition = condition & (df['Week'].astype(str) == str(week))
        
    df = df[~condition]
    db_manager.save_dataframe("Timetable", df)

def check_conflicts(db_manager, week, day, period, new_subject):
    """
    Checks if 'new_subject' at (Week, Day, Period) conflicts with other subjects 
    already scheduled at that time for any student.
    Returns: List of student names/IDs who have overlapping subjects.
    """
    # 1. Get other subjects at this Week/Day/Period
    timetable_df = load_timetable(db_manager)
    if timetable_df.empty:
        return []
    
    # Ensure Week column
    if 'Week' not in timetable_df.columns:
        timetable_df['Week'] = 1 # Default legacy to Week 1

    others = timetable_df[
        (timetable_df['Week'].astype(str) == str(week)) &
        (timetable_df['Day'] == day) & 
        (timetable_df['Period'] == period) & 
        (timetable_df['Subject'] != new_subject)
    ]['Subject'].unique()
    
    if len(others) == 0:
        return []
        
    # 2. Find students who take 'new_subject' AND any of 'others'
    students_df = db_manager.load_dataframe("Students")
    if students_df.empty:
        return []

    conflicting_students = []
    
    # Iterate students
    for _, row in students_df.iterrows():
        # parsed_subjects is user string "Sub1, Sub2" or list?
        sub_str = str(row.get('parsed_subjects', ''))
        student_subs = [s.strip() for s in sub_str.split(',') if s.strip()]
        
        # Check if student takes new_subject
        if new_subject in student_subs:
            # Check if student takes any of 'others'
            for other in others:
                if other in student_subs:
                    conflicting_students.append(f"{row['이름']}({row['학번']}) - {other}와 겹침")
                    break
                    

    return conflicting_students


def generate_student_timetable(db_manager, student_id, week=None):
    """
    Generates personal timetable for a student.
    Returns DataFrame: [Week, Date, Day, Period, Subject, Teacher, Room]
    """
    # 1. Get Student Info
    students_df = db_manager.load_dataframe("Students")
    if students_df.empty:
        return None, "학생 데이터가 없습니다.", None
        
    student = students_df[students_df['학번'].astype(str) == str(student_id)]
    if student.empty:
        return None, "해당 학번의 학생을 찾을 수 없습니다.", None
        
    row = student.iloc[0]
    if row.get('is_exception'): 
        is_exc = row.get('is_exception')
        if is_exc == True or str(is_exc).upper() == 'TRUE':
             return None, "예외처리된 학생이므로 시간표가 없습니다.", None
    
    # Parse subjects
    sub_str = str(row.get('parsed_subjects', ''))
    failed_subjects = [s.strip() for s in sub_str.split(',') if s.strip()]
    
    if not failed_subjects:
        return None, "미도달 과목이 없습니다.", None
        
    # Student Class Info
    s_grade = str(row['학년'])
    s_class = str(row['반'])
    full_class = f"{s_grade}-{s_class}"
    
    # 2. Get Master Timetable
    timetable_df = load_timetable(db_manager)
    if timetable_df.empty:
         return pd.DataFrame(), "전체 시간표가 아직 편성되지 않았습니다.", None
         
    # Ensure Week/Date
    if 'Week' not in timetable_df.columns: timetable_df['Week'] = 1
    if 'Date' not in timetable_df.columns: timetable_df['Date'] = ""

    # Filter by Week if requested
    if week:
        timetable_df = timetable_df[timetable_df['Week'].astype(str) == str(week)]

    # 3. Get Teacher Assignments
    teachers_df = db_manager.load_dataframe("Teachers")
    
    personal_schedule = []
    
    for _, slot in timetable_df.iterrows():
        t_week = slot['Week']
        t_date = slot['Date']
        t_day = slot['Day']
        t_period = slot['Period']
        t_subject = slot['Subject']
        
        # Only relevant if student failed this subject
        if t_subject in failed_subjects:
            matched_teacher = "미배정"
            matched_room = ""
            
            if not teachers_df.empty:
                candidates = teachers_df[teachers_df['Subject'] == t_subject]
                for _, t_row in candidates.iterrows():
                    assigned_str = str(t_row['AssignedClasses'])
                    assigned_list = [c.strip() for c in assigned_str.split(',')]
                    
                    if full_class in assigned_list:
                        matched_teacher = t_row['TeacherName']
                        matched_room = t_row.get('Room', '')
                        break
            
            personal_schedule.append({
                '주차': t_week,
                '날짜': t_date,
                '요일': t_day,
                '교시': t_period,
                '과목': t_subject,
                '담당교사': matched_teacher,
                '장소': matched_room
            })
            
    if not personal_schedule:
        return pd.DataFrame(), "배정된 시간표가 없습니다.", None
        
    # Sort
    day_order = {'월': 1, '화': 2, '수': 3, '목': 4, '금': 5}
    
    schedule_df = pd.DataFrame(personal_schedule)
    schedule_df['DayKey'] = schedule_df['요일'].map(day_order)
    schedule_df['PeriodKey'] = schedule_df['교시'].astype(int)
    # Sort by Week -> Day -> Period
    # Assuming Week is int? or convert to int
    try:
        schedule_df['WeekKey'] = schedule_df['주차'].astype(int)
    except:
        schedule_df['WeekKey'] = 1 # Fallback

    schedule_df = schedule_df.sort_values(['WeekKey', 'DayKey', 'PeriodKey'])
    schedule_df = schedule_df[['주차', '날짜', '요일', '교시', '과목', '담당교사', '장소']]
    
    return schedule_df, "생성 완료", row.get('이름', '')


def get_teacher_schedule(db_manager, teacher_name):
    """
    Returns DataFrame of teacher's schedule.
    """
    teachers_df = db_manager.load_dataframe("Teachers")
    if teachers_df.empty:
        return pd.DataFrame()
        
    # Find subjects this teacher teaches
    my_assignments = teachers_df[teachers_df['TeacherName'] == teacher_name]
    if my_assignments.empty:
        return pd.DataFrame()
        
    my_subjects = my_assignments['Subject'].unique()
    
    # Filter Timetable
    timetable_df = load_timetable(db_manager)
    if timetable_df.empty:
         return pd.DataFrame()

    # Ensure columns
    if 'Week' not in timetable_df.columns: timetable_df['Week'] = 1
    if 'Date' not in timetable_df.columns: timetable_df['Date'] = ""
          
    teacher_schedule = timetable_df[timetable_df['Subject'].isin(my_subjects)].copy()
    
    # Add Room info?
    # Teacher room is in 'my_assignments'
    # Map subject -> Room
    sub_room_map = my_assignments.set_index('Subject')['Room'].to_dict()
    teacher_schedule['장소'] = teacher_schedule['Subject'].map(sub_room_map)
    
    # Sort
    day_order = {'월': 1, '화': 2, '수': 3, '목': 4, '금': 5}
    teacher_schedule['DayKey'] = teacher_schedule['Day'].map(day_order)
    teacher_schedule['PeriodKey'] = teacher_schedule['Period'].astype(int)
    try:
        teacher_schedule['WeekKey'] = teacher_schedule['Week'].astype(int)
    except:
        teacher_schedule['WeekKey'] = 1

    teacher_schedule = teacher_schedule.sort_values(['WeekKey', 'DayKey', 'PeriodKey'])
    
    return teacher_schedule[['Week', 'Date', 'Day', 'Period', 'Subject', '장소']]

def get_students_for_class_slot(db_manager, teacher_name, subject, day=None, period=None):
    """
    Returns list of students who should attend this class slot.
    Logic: 
    1. Find Teacher's Assigned Classes for this Subject.
    2. Find Students in those classes who failed this Subject.
    """
    # 1. Get Teacher's assigned classes
    teachers_df = db_manager.load_dataframe("Teachers")
    if teachers_df.empty:
        return pd.DataFrame()
    
    # Filter by Teacher and Subject
    assignment = teachers_df[
        (teachers_df['TeacherName'] == teacher_name) & 
        (teachers_df['Subject'] == subject)
    ]
    
    if assignment.empty:
        return pd.DataFrame()
        
    s_classes_str = str(assignment.iloc[0]['AssignedClasses'])
    target_classes = [c.strip() for c in s_classes_str.split(',')]
    
    # 2. Filter Students
    students_df = db_manager.load_dataframe("Students")
    if students_df.empty:
        return pd.DataFrame()
        
    matched_students = []
    for _, row in students_df.iterrows():
        # Check Exception
        is_exc = row.get('is_exception')
        if is_exc == True or str(is_exc).upper() == 'TRUE':
             continue
             
        # Check Class
        s_grade = str(row['학년'])
        s_class = str(row['반'])
        full_class = f"{s_grade}-{s_class}"
        
        if full_class in target_classes:
            # Check Subject Failure
            sub_str = str(row.get('parsed_subjects', ''))
            failed_subjects = [s.strip() for s in sub_str.split(',') if s.strip()]
            
            if subject in failed_subjects:
                matched_students.append({
                    '학번': row['학번'],
                    '이름': row['이름'],
                    '학년': s_grade,
                    '반': s_class,
                    '번호': row['번호']
                })
                
    return pd.DataFrame(matched_students)

def format_student_timetable_grid(schedule_df, student_info=None):
    """
    Transforms the list-based schedule DataFrame into an HTML grid (Timetable) format.
    student_info: dict {'id': '...', 'name': '...'}
    """
    if schedule_df.empty:
        return "<p>시간표 데이터가 없습니다.</p>"

    # Helper to format cell content
    def format_cell(row):
        # 1. Subject (Bold)
        txt = f"<b>{row['과목']}</b>"
        
        # 2. Date (if exists)
        if '날짜' in row and pd.notna(row['날짜']) and str(row['날짜']).strip() != "":
            txt += f"<br><span style='font-size:0.8em; color:#0066cc;'>({row['날짜']})</span>"
            
        # 3. Details (Smaller font)
        details = ""
        if row['담당교사'] and row['담당교사'] != "미배정":
            details += f"<br><span style='font-size:0.9em; color:#555;'>{row['담당교사']}</span>"
            
        if row['장소']:
            details += f"<br><span style='font-size:0.9em; color:#555;'>{str(row['장소'])}</span>"
        
        return txt + details

    schedule_df = schedule_df.copy()
    schedule_df['Cell'] = schedule_df.apply(format_cell, axis=1)
    
    # Ensure '교시' is int for correct reindexing
    schedule_df['교시'] = schedule_df['교시'].astype(int)
    
    # Identify Weeks
    week_col = '주차' if '주차' in schedule_df.columns else 'Week'
    
    if week_col in schedule_df.columns:
        unique_weeks = sorted(schedule_df[week_col].unique())
    else:
        unique_weeks = [1] # Default if no week info
        
    full_html = ""
    
    days = ["월", "화", "수", "목", "금"]
    periods = range(1, 8)

    sid = student_info.get('id', '') if student_info else ''
    name = student_info.get('name', '') if student_info else ''

    for week in unique_weeks:
        # Filter for current week
        if week_col in schedule_df.columns:
            week_df = schedule_df[schedule_df[week_col] == week]
        else:
            week_df = schedule_df
            
        if week_df.empty:
            continue
            
        week_label = f"({week}주차)"
        
        # Header HTML
        header_html = f"""
<div style="width: 100%; margin-bottom: 10px; font-family: 'Malgun Gothic', dotum, sans-serif; page-break-inside: avoid;">
<div style="text-align: center; margin-bottom: 10px;">
<h2 class="print-title" style="margin: 0; font-weight: bold; font-size: 24px;">최소 성취수준 보장지도 보충지도 시간표 {week_label}</h2>
</div>
<div style="text-align: right; font-weight: bold; font-size: 18px; border-bottom: 2px solid #333; padding-bottom: 5px;">
<span style="margin-right: 30px;">학번 : {sid}</span>
<span>이름 : {name}</span>
</div>
</div>
"""
        # Grid Generation
        # Pivot: Index=Periods, Columns=Days
        pivot_table = week_df.pivot_table(
            index='교시', columns='요일', values='Cell', 
            aggfunc=lambda x: '<br><hr style="margin:2px 0;">'.join(x)
        )
        
        # Generte HTML Table manually to ensure correct layout
        # IMPORTANT: Do not indent the HTML tags inside the string, or Streamlit will treat them as code blocks!
        table_html = """
<table style="width:100%; border-collapse: collapse; text-align: center; border: 1px solid #ddd; color: black; margin-bottom: 30px;">
<thead>
<tr style="background-color: #f2f2f2; border: 1px solid #ddd;">
<th style="padding: 10px; border: 1px solid #ddd; width: 10%;">교시</th>
<th style="padding: 10px; border: 1px solid #ddd; width: 18%;">월</th>
<th style="padding: 10px; border: 1px solid #ddd; width: 18%;">화</th>
<th style="padding: 10px; border: 1px solid #ddd; width: 18%;">수</th>
<th style="padding: 10px; border: 1px solid #ddd; width: 18%;">목</th>
<th style="padding: 10px; border: 1px solid #ddd; width: 18%;">금</th>
</tr>
</thead>
<tbody>
"""
        # Load period times (passed via student_info or use defaults)
        p_times = student_info.get('period_times', {}) if student_info else {}
        # Fill missing with standard defaults just in case
        defaults = {1:"08:40~09:30", 2:"09:40~10:30", 3:"10:40~11:30", 4:"11:40~12:30", 5:"13:30~14:20", 6:"14:30~15:20", 7:"15:30~16:20"}
        for k, v in defaults.items():
            if k not in p_times: p_times[k] = v

        for p in periods:
            # Format Period Label with Time
            time_range = p_times.get(p, "")
            p_label = f"{p}교시"
            if time_range:
                p_label += f"<br><span style='font-size:0.8em; font-weight:normal; color:#555;'>({time_range})</span>"
            
            table_html += f"<tr><td style='border: 1px solid #ddd; font-weight:bold; background-color:#fafafa;'>{p_label}</td>"
            for d in days:
                cell_content = ""
                try:
                    if p in pivot_table.index and d in pivot_table.columns:
                        val = pivot_table.loc[p, d]
                        if pd.notna(val):
                            cell_content = val
                except KeyError:
                    pass
                
                table_html += f"<td style='padding: 8px; border: 1px solid #ddd; vertical-align: middle; height: 80px;'>{cell_content}</td>"
            table_html += "</tr>"
            
        table_html += "</tbody></table>"
        
        full_html += f"""
<div class="week-block" style="margin-bottom: 40px; page-break-inside: avoid;">
    {header_html}
    {table_html}
</div>
"""

    return full_html


def get_students_in_class(db_manager, grade, class_num):
    """
    Fetches list of students in a specific Grade-Class who need timetables (not exceptioned, has failed items).
    Returns list of dicts: [{'학번': '...', '이름': '...'}, ...]
    """
    students_df = db_manager.load_dataframe("Students")
    if students_df.empty:
        return []
        
    targets = []
    # Ensure Types
    students_df['학년'] = students_df['학년'].astype(str)
    students_df['반'] = students_df['반'].astype(str)
    
    grade = str(grade)
    class_num = str(class_num)
    
    for _, row in students_df.iterrows():
        # Check Grade/Class
        if row['학년'] != grade or row['반'] != class_num:
            continue
            
        # Check Exception
        is_exc = row.get('is_exception')
        if is_exc == True or str(is_exc).upper() == 'TRUE':
             continue
             
        # Check parsed_subjects (if empty, no need for timetable)
        sub_str = str(row.get('parsed_subjects', ''))
        failed_subjects = [s.strip() for s in sub_str.split(',') if s.strip()]
        
        if not failed_subjects:
            continue
            
        targets.append({
            '학번': row['학번'],
            '이름': row['이름']
        })
        
    # Sort by Student ID
    targets.sort(key=lambda x: x['학번'])
    
    return targets

def load_period_times(db_manager):
    """
    Loads period times from 'Settings_PeriodTimes' sheet.
    Returns dict {period_int: time_str}
    """
    defaults = {
        1: "08:40~09:30",
        2: "09:40~10:30",
        3: "10:40~11:30",
        4: "11:40~12:30",
        5: "13:30~14:20",
        6: "14:30~15:20",
        7: "15:30~16:20"
    }
    
    try:
        df = db_manager.load_dataframe("Settings_PeriodTimes")
        if df.empty:
            return defaults
            
        times = {}
        # Expected cols: Period, TimeRange
        for _, row in df.iterrows():
            try:
                p = int(row['Period'])
                t = str(row['TimeRange'])
                times[p] = t
            except:
                continue
        
        # Merge with defaults to ensure all keys exist if partial data
        for k, v in defaults.items():
            if k not in times:
                times[k] = v
                
        return times
    except Exception:
        return defaults

def save_period_times(db_manager, times_dict):
    """
    Saves period times dict to 'Settings_PeriodTimes' sheet.
    """
    data = []
    for p in sorted(times_dict.keys()):
        data.append({'Period': p, 'TimeRange': times_dict[p]})
        
    df = pd.DataFrame(data)
    return db_manager.save_dataframe("Settings_PeriodTimes", df)

