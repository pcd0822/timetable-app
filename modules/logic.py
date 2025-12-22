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


    return db_manager.save_dataframe("Teachers", df)

def get_teacher_assignments(db_manager):
    return db_manager.load_dataframe("Teachers")

def load_timetable(db_manager):
    return db_manager.load_dataframe("Timetable")

def add_timetable_slot(db_manager, day, period, subject):
    """
    Adds a subject to a specific Day/Period.
    Structure: [Day, Period, Subject]
    """
    df = db_manager.load_dataframe("Timetable")
    if df.empty:
        df = pd.DataFrame(columns=['Day', 'Period', 'Subject'])
        
    # Check if exactly same entry exists to prevent dupes
    # (Day, Period, Subject) should be unique
    exclude = df[
        (df['Day'] == day) & 
        (df['Period'] == period) & 
        (df['Subject'] == subject)
    ]
    if not exclude.empty:
        return False, "이미 해당 시간에 해당 과목이 배정되어 있습니다."

    new_row = pd.DataFrame([{'Day': day, 'Period': period, 'Subject': subject}])
    df = pd.concat([df, new_row], ignore_index=True)
    
    success = db_manager.save_dataframe("Timetable", df)
    return success, "저장 완료"

def delete_timetable_slot(db_manager, day, period, subject):
    df = db_manager.load_dataframe("Timetable")
    if df.empty:
        return
    
    condition = (df['Day'] == day) & (df['Period'] == period) & (df['Subject'] == subject)
    df = df[~condition]
    db_manager.save_dataframe("Timetable", df)

def check_conflicts(db_manager, day, period, new_subject):
    """
    Checks if 'new_subject' at (Day, Period) conflicts with other subjects 
    already scheduled at that time for any student.
    Returns: List of student names/IDs who have overlapping subjects.
    """
    # 1. Get other subjects at this Day/Period
    timetable_df = load_timetable(db_manager)
    if timetable_df.empty:
        return []
        
    others = timetable_df[
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
        # In Load Logic, we saved it as comma-joined string.
        # We need to re-parse or use 'in'.
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


def generate_student_timetable(db_manager, student_id):
    """
    Generates personal timetable for a student.
    Returns DataFrame: [Day, Period, Subject, Teacher, Room]
    """
    # 1. Get Student Info
    students_df = db_manager.load_dataframe("Students")
    if students_df.empty:
        return None, "학생 데이터가 없습니다."
        
    student = students_df[students_df['학번'].astype(str) == str(student_id)]
    if student.empty:
        return None, "해당 학번의 학생을 찾을 수 없습니다."
        
    row = student.iloc[0]
    if row.get('is_exception'): # Boolean check or check string 'TRUE'?
        # Based on data_loader, it's boolean. But loading from Sheets makes it int/bool?
        # Sheets might return TRUE/FALSE string or 1/0.
        is_exc = row.get('is_exception')
        if is_exc == True or str(is_exc).upper() == 'TRUE':
             return None, "예외처리된 학생이므로 시간표가 없습니다."
    
    # Parse subjects
    sub_str = str(row.get('parsed_subjects', ''))
    failed_subjects = [s.strip() for s in sub_str.split(',') if s.strip()]
    
    if not failed_subjects:
        return None, "미도달 과목이 없습니다."
        
    # Student Class Info
    s_grade = str(row['학년'])
    s_class = str(row['반'])
    full_class = f"{s_grade}-{s_class}" # Matches Teacher Assignment format "1-1"
    
    # 2. Get Master Timetable
    timetable_df = load_timetable(db_manager)
    if timetable_df.empty:
         return pd.DataFrame(), "전체 시간표가 아직 편성되지 않았습니다."
         
    # 3. Get Teacher Assignments
    teachers_df = db_manager.load_dataframe("Teachers")
    
    personal_schedule = []
    
    for _, slot in timetable_df.iterrows():
        t_day = slot['Day']
        t_period = slot['Period']
        t_subject = slot['Subject']
        
        # Only relevant if student failed this subject
        if t_subject in failed_subjects:
            # Find Teacher for this Subject AND Student's Class
            # teachers_df columns: Subject, TeacherName, AssignedClasses, Room
            matched_teacher = "미배정"
            matched_room = ""
            
            if not teachers_df.empty:
                candidates = teachers_df[teachers_df['Subject'] == t_subject]
                for _, t_row in candidates.iterrows():
                    # assigned_classes is "['1-1', '1-2']" string formatting from list str?
                    # Or "1-1,1-2" string? In 'save_teacher_assignment' we did: ','.join(map(str, classes))
                    assigned_str = str(t_row['AssignedClasses'])
                    assigned_list = [c.strip() for c in assigned_str.split(',')]
                    
                    if full_class in assigned_list:
                        matched_teacher = t_row['TeacherName']
                        matched_room = t_row.get('Room', '')
                        break
            
            personal_schedule.append({
                '요일': t_day,
                '교시': t_period,
                '과목': t_subject,
                '담당교사': matched_teacher,
                '장소': matched_room
            })
            
    if not personal_schedule:
        return pd.DataFrame(), "배정된 시간표가 없습니다. (전체 시간표에 해당 과목이 없거나 교사 배정이 누락됨)"
        
    # Sort by Day/Period
    # Custom Sort Order for Days
    day_order = {'월': 1, '화': 2, '수': 3, '목': 4, '금': 5}
    
    schedule_df = pd.DataFrame(personal_schedule)
    schedule_df['DayKey'] = schedule_df['요일'].map(day_order)
    schedule_df['PeriodKey'] = schedule_df['교시'].astype(int)
    
    schedule_df = schedule_df.sort_values(['DayKey', 'PeriodKey'])
    schedule_df = schedule_df[['요일', '교시', '과목', '담당교사', '장소']]
    
    return schedule_df, "Success"

def get_teacher_schedule(db_manager, teacher_name):
    """
    Generates schedule for a specific teacher.
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
    teacher_schedule = teacher_schedule.sort_values(['DayKey', 'PeriodKey'])
    
    return teacher_schedule[['Day', 'Period', 'Subject', '장소']]

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
                
    if not matched_students:
        return pd.DataFrame()
        
    return pd.DataFrame(matched_students)




    return pd.DataFrame(matched_students)

def format_student_timetable_grid(schedule_df):
    """
    Transforms the list-based schedule DataFrame into a grid (Timetable) format.
    Rows: Periods (1~7)
    Columns: Days (Mon~Fri)
    Cell: Subject\n(Teacher / Room)
    """
    if schedule_df.empty:
        return pd.DataFrame()

    # Create a composite text for the cell
    # Use HTML breaks <br>
    def format_cell(row):
        # 1. Subject (Bold)
        txt = f"<b>{row['과목']}</b>"
        
        # 2. Details (Smaller font)
        details = ""
        if row['담당교사'] and row['담당교사'] != "미배정":
            details += f"<br><span style='font-size:0.9em; color:#555;'>담당선생님: {row['담당교사']}</span>"
            
        if row['장소']:
            details += f"<br><span style='font-size:0.9em; color:#555;'>교실: {str(row['장소'])}</span>"
        
        return txt + details

    schedule_df['Cell'] = schedule_df.apply(format_cell, axis=1)

    # Pivot
    # Ensure '교시' is int for correct reindexing
    schedule_df['교시'] = schedule_df['교시'].astype(int)
    
    pivot_df = schedule_df.pivot_table(
        index='교시', 
        columns='요일', 
        values='Cell', 
        aggfunc=lambda x: '<br><hr style="margin:2px 0;"><br>'.join(x) # Separator for conflicts
    )
    
    # Reindex
    days = ["월", "화", "수", "목", "금"]
    periods = range(1, 8)
    
    pivot_df = pivot_df.reindex(index=periods, columns=days)
    pivot_df = pivot_df.fillna("") 
    
    # Generate HTML Table
    html = """
    <table style="width:100%; border-collapse: collapse; text-align: center; border: 1px solid #ddd; color: black;">
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
    
    for p in periods:
        html += f"<tr><td style='border: 1px solid #ddd; font-weight:bold; background-color:#fafafa;'>{p}교시</td>"
        for d in days:
            try:
                cell_content = pivot_df.loc[p, d]
                if pd.isna(cell_content): cell_content = ""
            except KeyError:
                cell_content = ""
            
            # Make cell look clickable/interactive or just nice
            html += f"<td style='padding: 8px; border: 1px solid #ddd; vertical-align: middle; height: 80px;'>{cell_content}</td>"
        html += "</tr>"
        
    html += "</tbody></table>"
    
    return html


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
