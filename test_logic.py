import sys
import os
sys.path.append(os.getcwd())

import pandas as pd
try:
    from modules.logic import add_timetable_slot, generate_student_timetable, check_conflicts
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)

class MockDB:
    def __init__(self):
        self.data = {
            "Timetable": pd.DataFrame(columns=['Week', 'Date', 'Day', 'Period', 'Subject']),
            "Students": pd.DataFrame([
                {'학번': '10101', '이름': 'TestStudent', '학년': '1', '반': '1', '번호': '1', 'parsed_subjects': 'Math', 'is_exception': False}
            ]),
            "Teachers": pd.DataFrame([
                {'Subject': 'Math', 'TeacherName': 'Mr. Kim', 'AssignedClasses': '1-1', 'Room': '101'}
            ])
        }
        
    def load_dataframe(self, name, force_update=False):
        return self.data.get(name, pd.DataFrame())
        
    def save_dataframe(self, name, df):
        self.data[name] = df
        return True

def test():
    try:
        db = MockDB()
        
        # 1. Add Slot Week 1
        success, msg = add_timetable_slot(db, 1, "11/04", "월", 1, "Math")
        print(f"Add Week 1: {success} - {msg}")
        
        # 2. Add Slot Week 2 (Same time, different week)
        success, msg = add_timetable_slot(db, 2, "11/11", "월", 1, "Math")
        print(f"Add Week 2: {success} - {msg}")
        
        # 3. Add Slot Week 1 Duplicate
        success, msg = add_timetable_slot(db, 1, "11/04", "월", 1, "Math")
        print(f"Add Duplicate: {success} - {msg}")
        
        # 4. Generate Student Timetable Week 1
        print("\n--- Student Timetable Week 1 ---")
        sch, msg, name = generate_student_timetable(db, '10101', week=1)
        if sch is not None and not sch.empty:
            print(sch)
        else:
            print(msg)
            
        # 5. Generate Student Timetable Week 2
        print("\n--- Student Timetable Week 2 ---")
        sch, msg, name = generate_student_timetable(db, '10101', week=2)
        if sch is not None and not sch.empty:
            print(sch)
        else:
            print(msg)
    except Exception as e:
        print(f"Runtime Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test()
