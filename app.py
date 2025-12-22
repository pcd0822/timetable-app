import streamlit as st
from modules.db_manager import DBManager
import pandas as pd

# Page Config
st.set_page_config(page_title="시간표 배정 프로그램", layout="wide")

# Initialize Session State
if 'db' not in st.session_state:
    st.session_state.db = DBManager()

# Sidebar
st.sidebar.title("Navigation")
menu = st.sidebar.radio("Go to", 
    ["Data Upload", "Teacher Assignment", "Timetable Setup", "Room Assignment", "Student View", "Teacher View"])

st.sidebar.divider()
if st.sidebar.button("🔄 데이터 새로고침 (Refresh)"):
    # Clear internal cache if exists
    if hasattr(st.session_state.db, 'cache'):
        st.session_state.db.cache = {}
    st.cache_data.clear()
    st.rerun()

# --- DB Status Indicator ---
try:
    # Quick fetch of counts (using cached load for speed)
    st_count = len(st.session_state.db.load_dataframe("Students"))
    tc_count = len(st.session_state.db.load_dataframe("Teachers"))
    st.sidebar.info(f"📊 **DB 상태**\n\n- 학생: {st_count}명\n- 교사 배정: {tc_count}건")
except Exception:
    st.sidebar.warning("DB 연결 대기 중...")

# Main Content Placeholder
st.title("최소 성취수준 보장지도 시간표 관리")

if menu == "Data Upload":
    st.header("엑셀 데이터 업로드")
    from modules.data_loader import parse_excel
    
    # 1. Show Current DB Status
    st.subheader("📂 현재 저장된 데이터")
    current_df = st.session_state.db.load_dataframe("Students")
    if not current_df.empty:
        st.info(f"현재 데이터베이스에 **{len(current_df)}명**의 학생 정보가 저장되어 있습니다.")
        with st.expander("현재 저장된 데이터 보기"):
             st.dataframe(current_df)
    else:
        st.warning("현재 저장된 학생 데이터가 없습니다.")

    st.divider()

    # 2. Upload New File
    st.subheader("새 파일 업로드")
    st.caption("⚠️ 새로운 파일을 업로드하고 저장하면 **기존 데이터가 덮어씌워집니다.**")
    
    uploaded_file = st.file_uploader("학생 명단 엑셀 파일 업로드", type=['xlsx'])
    if uploaded_file:
        df, error = parse_excel(uploaded_file)
        if error:
            st.error(error)
        else:
            st.success(f"파일 파싱 성공! 총 {len(df)}명의 학생 데이터가 로드되었습니다.")
            
            with st.expander("데이터 미리보기 (전체 데이터 확인)", expanded=True):
                st.dataframe(df) # Show full dataframe (Streamlit handles pagination)
            
            if st.button("DB에 저장하기"):
                # Save to Google Sheets
                # Flatten the list of subjects for display compatibility if needed, 
                # but allow DBManager to handle it. 
                # For basic JSON serialization in Sheets, lists are tricky. 
                # We save the raw strings for now or convert 'parsed_subjects' to string.
                
                # Convert list to string for storage
                save_df = df.copy()
                save_df['parsed_subjects'] = save_df['parsed_subjects'].apply(lambda x: ','.join(x))
                
                success = st.session_state.db.save_dataframe("Students", save_df)
                if success:
                    st.success("데이터베이스(Google Sheets - Students)에 저장되었습니다.")
                else:
                    # Generic error fallback only if db_manager didn't already show a detailed error
                    # (In our case, db_manager handles the details, but a generic "Please check above" is helpful)
                    st.error("저장 실패. 위의 오류 메시지를 확인하세요.")

elif menu == "Teacher Assignment":
    st.header("교사 및 과목 배정")
    
    from modules.logic import get_unique_subjects, get_unique_classes, save_teacher_assignment, get_teacher_assignments

    # 1. Fetch Options
    subjects = get_unique_subjects(st.session_state.db)
    classes_options = get_unique_classes(st.session_state.db)

    if not subjects:
        st.warning("등록된 학생 데이터가 없거나 미도달 과목이 파싱되지 않았습니다. 먼저 'Data Upload'를 진행하세요.")
    else:
        with st.form("teacher_assign_form"):
            st.subheader("새 배정 추가")
            col1, col2 = st.columns(2)
            with col1:
                t_name = st.text_input("교사 성명")
                sub_select = st.selectbox("담당 과목", subjects)
            with col2:
                # Room input here or separate? 
                # "Room Assignment" is a separate menu item in plan, but User Req 2.3 says:
                # "When assigning teacher... input room". Actually 2.3 says "Time table... Room Assignment UI".
                # But Point 1 Teacher Assignment says "Assign Teacher to Subject... Checkbox Class".
                # Let's keep Room separate or add here?
                # User Prompt: "3. Room Assignment: When subject assigned to timetable... input room".
                # Okay, Room is later. But maybe convenient here? 
                # Let's strictly follow plan: Room later.
                # But wait, logic.save_teacher_assignment has 'Room' param. 
                # I'll enable it here for convenience, or default empty.
                room_input = st.text_input("강의실 (선택)", help="나중에 '강의실 배정' 메뉴에서도 수정 가능합니다.")
            
            # Class Selection
            selected_classes = st.multiselect("담당 학급 (학년-반)", classes_options)
            
            submitted = st.form_submit_button("저장")
            
            if submitted:
                if t_name and sub_select and selected_classes:
                    success = save_teacher_assignment(st.session_state.db, sub_select, t_name, selected_classes, room_input)
                    if success:
                        st.success(f"{t_name} 교사 배정 완료!")
                        st.rerun() # Refresh to show in table
                else:
                    st.error("교사 성명, 과목, 담당 학급은 필수입니다.")

    # 2. View Current Assignments
    st.divider()
    st.subheader("현재 배정 현황")
    assignments_df = get_teacher_assignments(st.session_state.db)
    if not assignments_df.empty:
        st.dataframe(assignments_df)
    else:
        st.info("아직 배정된 내역이 없습니다.")


elif menu == "Timetable Setup":
    st.header("전체 시간표 편성")
    
    from modules.logic import get_unique_subjects, add_timetable_slot, load_timetable, check_conflicts, delete_timetable_slot

    subjects = get_unique_subjects(st.session_state.db)
    days = ["월", "화", "수", "목", "금"]
    periods = range(1, 8) # 1~7교시

    # 1. Add Slot Form
    with st.expander("시간표 배정 추가", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            s_day = st.selectbox("요일", days)
        with col2:
            s_period = st.selectbox("교시", periods)
        with col3:
            s_subject = st.selectbox("과목", subjects, key="timetable_sub")
            
        if st.button("배정 추가"):
            # Check Conflicts
            conflicts = check_conflicts(st.session_state.db, s_day, s_period, s_subject)
            if conflicts:
                st.warning(f"⚠️ 충돌 경고! 다음 학생들이 이 시간에 다른 과목 수업이 있습니다: {', '.join(conflicts)}")
                if st.checkbox("충돌 무시하고 저장하시겠습니까?"):
                    success, msg = add_timetable_slot(st.session_state.db, s_day, s_period, s_subject)
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
            else:
                success, msg = add_timetable_slot(st.session_state.db, s_day, s_period, s_subject)
                if success:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

    # 2. View Timetable (List & Grid)
    st.divider()
    tt_df = load_timetable(st.session_state.db)
    
    if not tt_df.empty:
        # Sort for display
        tt_df['Period'] = tt_df['Period'].astype(int)
        
        # Grid View (Pivot)
        # Create full grid
        st.subheader("시간표 요약 (Grid)")
        
        # Create pivot-ready data. Since multiple subjects can be in one slot, pivot might aggregate.
        # We join them with newlines.
        pivot_data = tt_df.assign(Subject=tt_df['Subject']).pivot_table(
            index='Period', columns='Day', values='Subject', 
            aggfunc=lambda x: '\n'.join(x)
        )
        # Reorder columns and index
        pivot_data = pivot_data.reindex(index=periods, columns=days)
        st.dataframe(pivot_data, use_container_width=True)
        
        # List View for Deletion
        st.subheader("배정 목록 및 삭제")
        for i, row in tt_df.iterrows():
            col_a, col_b = st.columns([4, 1])
            with col_a:
                st.text(f"{row['Day']}요일 {row['Period']}교시 - {row['Subject']}")
            with col_b:
                if st.button("삭제", key=f"del_{i}"):
                     delete_timetable_slot(st.session_state.db, row['Day'], row['Period'], row['Subject'])
                     st.rerun()
    else:
        st.info("편성된 시간표가 없습니다.")


elif menu == "Room Assignment":
    st.header("강의실 배정 (관리)")
    st.info("교사-과목 배정 내역에서 강의실 정보를 수정합니다.")
    
    from modules.logic import get_teacher_assignments
    
    df = get_teacher_assignments(st.session_state.db)
    if not df.empty:
        # Use data editor to allow inline editing of 'Room'
        edited_df = st.data_editor(df, num_rows="dynamic", key="room_editor")
        
        if st.button("변경사항 저장"):
            # Save back to DB
            success = st.session_state.db.save_dataframe("Teachers", edited_df)
            if success:
                st.success("강의실 배정 정보가 업데이트되었습니다.")
                st.rerun()
            else:
                st.error("저장 실패")
    else:
        st.warning("교사 배정 데이터가 없습니다. 'Teacher Assignment'를 먼저 진행하세요.")

elif menu == "Student View":
    st.header("학생 개인 시간표 조회")
    
    from modules.logic import generate_student_timetable
    
    sid_input = st.text_input("학번을 입력하세요 (예: 10101)")
    
    if st.button("조회"):
        if sid_input:
            schedule_df, msg = generate_student_timetable(st.session_state.db, sid_input)
            
            if schedule_df is not None and not schedule_df.empty:
                st.success(f"학번: {sid_input} 시간표")
                
                # Transform to Grid
                from modules.logic import format_student_timetable_grid
                grid_df = format_student_timetable_grid(schedule_df)
                
                # Display Grid using HTML table for better print control (st.table is deprecated-ish but good for static)
                # st.table is fine.
                st.table(grid_df) 
                
                # Improved Print Button & CSS
                # Using a styled HTML button and explicit @media print rules
                st.markdown("""
                <br>
                <div style="text-align: center;">
                    <button onclick="window.print()" style="
                        background-color: #4CAF50; 
                        border: none;
                        color: white;
                        padding: 15px 32px;
                        text-align: center;
                        text-decoration: none;
                        display: inline-block;
                        font-size: 16px;
                        margin: 4px 2px;
                        cursor: pointer;
                        border-radius: 8px;">
                        🖨️ 시간표 인쇄하기
                    </button>
                    <p style="color: gray; font-size: 0.8em; margin-top: 5px;">(인쇄 설정에서 '배경 그래픽'을 체크하면 더 잘 보입니다)</p>
                </div>

                <style>
                @media print {
                    /* Hide Streamlit UI elements */
                    #MainMenu {display: none !important;}
                    header {display: none !important;}
                    footer {display: none !important;}
                    [data-testid="stSidebar"] {display: none !important;}
                    .stApp > header {display: none !important;}
                    .stDeployButton {display: none !important;}
                    
                    /* Hide inputs and buttons in main area */
                    .stTextInput, .stButton, .stExpander {display: none !important;}
                    button {display: none !important;} 
                    
                    /* Ensure Table is visible and centered */
                    .stTable {
                        display: block !important;
                        width: 100% !important;
                    }
                    
                    /* Force white background */
                    body, .stApp {
                        background-color: white !important;
                    }
                    
                    /* Add a title for print */
                    .stApp:before {
                        content: '학번: """ + sid_input + """ 시간표';
                        font-size: 24px;
                        font-weight: bold;
                        display: block;
                        text-align: center;
                        margin-bottom: 20px;
                    }
                }
                </style>
                """, unsafe_allow_html=True)
                
            elif schedule_df is None: # Error case (e.g. exception or not found)
                st.warning(msg)
            else: # Empty DF but success (e.g. no subjects scheduled yet)
                st.info(msg)
        else:
            st.error("학번을 입력해주세요.")

elif menu == "Teacher View":
    st.header("교사별 시간표 조회")
    
    from modules.logic import get_teacher_assignments, get_teacher_schedule
    
    teachers_df = get_teacher_assignments(st.session_state.db)
    if not teachers_df.empty:
        teacher_list = teachers_df['TeacherName'].unique()
        selected_teacher = st.selectbox("교사 선택", teacher_list)
        
        if selected_teacher:
            st.subheader(f"{selected_teacher} 선생님 시간표")
            t_schedule = get_teacher_schedule(st.session_state.db, selected_teacher)
            if not t_schedule.empty:
                st.table(t_schedule)
                
                # Student List for a specific slot?
                # User request: "Bottom: Student list table for that class time"
                # Need to select a slot first? Or show all?
                # "Teacher timetable... Bottom: Student List"
                # Maybe show list for ALL slots? Or interactively click?
                # Interactive click in Streamlit table is hard.
                # Let's add a selector "Select Slot to View Students".
                
                slot_options = t_schedule.apply(lambda x: f"{x['Day']} {x['Period']}교시 ({x['Subject']})", axis=1)
                selected_slot_str = st.selectbox("수강생 명단 조회할 수업 선택", slot_options)
                
                # Parse back
                if selected_slot_str:
                    # Format: "월 5교시 (Subject)"
                    try:
                        # Simple regex or split
                        parts = selected_slot_str.split(' ')
                        # parts[0] = Day, parts[1] = "5교시", parts[2] = "(Subject)"
                        sel_day = parts[0]
                        sel_period = parts[1].replace("교시", "")
                        sel_subject = selected_slot_str.split('(')[1].replace(')', '')
                        
                        from modules.logic import get_students_for_class_slot
                        stud_df = get_students_for_class_slot(st.session_state.db, selected_teacher, sel_subject)
                        
                        st.write(f"**[{sel_subject}] 수강 대상 학생 명단**")
                        if not stud_df.empty:
                            st.dataframe(stud_df)
                            st.caption(f"총 {len(stud_df)}명")
                        else:
                            st.info("해당 수업을 듣는 학생이 없습니다.")
                    except Exception as e:
                        st.error(f"명단 조회 중 오류 발생: {e}")
            else:
                st.info("배정된 시간표가 없습니다.")
    else:
        st.warning("교사 데이터가 없습니다.")


