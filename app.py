import streamlit as st
from modules.db_manager import DBManager
import pandas as pd
import textwrap

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
        # Week / Date input
        col_w1, col_w2, col_w3 = st.columns(3)
        with col_w1:
            s_week = st.number_input("주차 (Week)", min_value=1, value=1, step=1)
        with col_w2:
            s_date_str = st.text_input("날짜 (예: 11/04)", help="선택사항. 인쇄 시 표시됩니다.")
        with col_w3:
            st.empty()

        col1, col2, col3 = st.columns(3)
        with col1:
            s_day = st.selectbox("요일", days)
        with col2:
            s_period = st.selectbox("교시", periods)
        with col3:
            s_subject = st.selectbox("과목", subjects, key="timetable_sub")
            
        if st.button("배정 추가"):
            # Check Conflicts
            conflicts = check_conflicts(st.session_state.db, s_week, s_day, s_period, s_subject)
            if conflicts:
                st.warning(f"⚠️ 충돌 경고 ({s_week}주차 {s_day} {s_period}교시)! 다음 학생들이 이 시간에 다른 과목 수업이 있습니다: {', '.join(conflicts)}")
                if st.checkbox("충돌 무시하고 저장하시겠습니까?"):
                    success, msg = add_timetable_slot(st.session_state.db, s_week, s_date_str, s_day, s_period, s_subject)
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
            else:
                success, msg = add_timetable_slot(st.session_state.db, s_week, s_date_str, s_day, s_period, s_subject)
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
        if 'Week' not in tt_df.columns: tt_df['Week'] = 1
        
        # Week Filter for Grid
        all_weeks = sorted(tt_df['Week'].astype(int).unique())
        st.subheader("시간표 요약 (Grid)")
        
        selected_view_week = st.selectbox("조회할 주차 선택", all_weeks, index=0)
        
        # Filter Grid Data
        grid_df = tt_df[tt_df['Week'].astype(int) == selected_view_week].copy()

        # Grid View (Pivot)
        # Create full grid
        # Create pivot-ready data. Since multiple subjects can be in one slot, pivot might aggregate.
        # We join them with newlines.
        pivot_data = grid_df.assign(Subject=grid_df['Subject']).pivot_table(
            index='Period', columns='Day', values='Subject', 
            aggfunc=lambda x: '\n'.join(x)
        )
        # Reorder columns and index
        pivot_data = pivot_data.reindex(index=periods, columns=days)
        st.dataframe(pivot_data, use_container_width=True)
        
        # List View for Deletion
        st.subheader("배정 목록 및 삭제")
        # Show all or filter? Let's show all but sort by Week
        tt_df = tt_df.sort_values(by=['Week', 'Day', 'Period'])
        
        for i, row in tt_df.iterrows():
            col_a, col_b = st.columns([4, 1])
            week_info = f"[{row['Week']}주차]"
            date_info = f"({row['Date']})" if pd.notna(row.get('Date')) and row.get('Date') else ""
            
            with col_a:
                st.text(f"{week_info} {row['Day']}요일 {row['Period']}교시 - {row['Subject']} {date_info}")
            with col_b:
                if st.button("삭제", key=f"del_{i}"):
                     delete_timetable_slot(st.session_state.db, row['Week'], row['Day'], row['Period'], row['Subject'])
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
    st.header("학생 시간표 조회 및 인쇄")
    
    from modules.logic import generate_student_timetable, format_student_timetable_grid, get_students_in_class, load_timetable
    
    # Check available weeks
    tt_df = load_timetable(st.session_state.db)
    available_weeks = [1]
    if not tt_df.empty and 'Week' in tt_df.columns:
        available_weeks = sorted(tt_df['Week'].astype(int).unique())
    
    # Mode Selection using Tabs
    tab1, tab2 = st.tabs(["👤 개인별 조회", "🏫 학급별 일괄 조회 (인쇄용)"])
    
    with tab1:
        col_s1, col_s2 = st.columns([3, 1])
        with col_s1:
            sid_input = st.text_input("학번을 입력하세요 (예: 10101)")
        with col_s2:
            # Week Selector
            week_opts = ["전체"] + [f"{w}주차" for w in available_weeks]
            ver_week = st.selectbox("주차 선택", week_opts)
            
        if st.button("조회"):
            if sid_input:
                target_week = None
                if ver_week != "전체":
                    target_week = int(ver_week.replace("주차", ""))
                    
                schedule_df, msg, s_name = generate_student_timetable(st.session_state.db, sid_input, week=target_week)
                
                if schedule_df is not None and not schedule_df.empty:
                    st.success(f"학번: {sid_input} 이름: {s_name} 시간표")
                    
                    # Transform to Grid (Now returns HTML string with Header)
                    timetable_html = format_student_timetable_grid(schedule_df, student_info={'id': sid_input, 'name': s_name})
                    
                    # Improved Print Button using Components
                    import streamlit.components.v1 as components
                    
                    # CSS for clean print
                    st.markdown("""
                    <style>
                    @media print {
                        #MainMenu, header, footer, [data-testid="stSidebar"], .stDeployButton {display: none !important;}
                        /* Hide Streamlit UI elements */
                        .stTextInput, .stButton, .stExpander, .stSelectbox, .stProgress, .stAlert {display: none !important;}
                        
                        /* Hide Tab Headers and Borders */
                        [data-baseweb="tab-list"], 
                        [data-baseweb="tab-highlight"], 
                        [data-baseweb="tab-border"] {
                            display: none !important; 
                            border: none !important;
                            height: 0 !important;
                        }
                        hr { display: none !important; }

                        /* Hide Header Decoration Line */
                        header, .stApp > header {
                            display: none !important;
                            opacity: 0 !important;
                            visibility: hidden !important;
                        }
                        header:before, header:after, .stApp > header:before, .stApp > header:after {
                            display: none !important;
                            content: none !important;
                        }
                        
                        /* Hide Print Button by hiding the iframe content */
                        iframe {
                            display: none !important;
                            height: 0 !important;
                            width: 0 !important;
                        }

                        /* Hide main titles BUT show our custom print title */
                        h1, h2, h3, h4, h5, h6 {display: none !important;}
                        h2.print-title {display: block !important;}

                        /* Page Setup */
                        @page {
                            size: A4;
                            margin: 5mm 15mm 5mm 15mm; /* Top Right Bottom Left */
                        }

                        table {
                            display: table !important;
                            width: 100% !important;
                            border-collapse: collapse !important;
                        }
                        th, td {
                            border: 1px solid #000 !important;
                            padding: 8px !important;
                            color: black !important;
                            -webkit-print-color-adjust: exact; 
                        }
                        
                        html, body, .stApp { 
                            background-color: white !important; 
                            height: auto !important;
                            margin: 0 !important;
                            padding: 0 !important;
                            overflow: visible !important;
                        }
                        
                        /* Layout fixes */
                        .block-container, 
                        [data-testid="stAppViewContainer"], 
                        .main, 
                        .stApp { 
                            padding: 0 !important; 
                            margin: 0 !important;
                            padding-top: 0 !important;
                            margin-top: 0 !important;
                            overflow: visible !important;
                        }
                        
                        /* Adjusted positioning for Centering */
                        #print-area {
                            /* Flexbox Alignment */
                            position: absolute;
                            top: 0;
                            left: 0;
                            display: flex !important;
                            flex-direction: column;
                            justify-content: flex-start; /* Align to Top */
                            align-items: center; /* Center horizontally */
                            height: 98vh; 
                            width: 100%;
                            z-index: 9999;
                            margin: 0;
                            padding: 0;
                        }
                    }
                    </style>
                    """, unsafe_allow_html=True)

                    # Display HTML Table wrapped in print-area
                    st.markdown(f'<div id="print-area">{timetable_html}</div>', unsafe_allow_html=True)

                    # Print Button
                    components.html("""
                    <div style="text-align: center;">
                        <button onclick="window.parent.print()" style="background-color: #4CAF50; border: none; color: white; padding: 15px 32px; text-align: center; font-size: 16px; margin: 4px 2px; cursor: pointer; border-radius: 8px; font-weight: bold;">🖨️ 시간표 인쇄하기</button>
                    </div>
                    """, height=100)
                    
                elif schedule_df is None: 
                    st.warning(msg)
                else: 
                    st.info(msg)
            else:
                st.error("학번을 입력해주세요.")

    with tab2:
        st.info("특정 학급의 배정 대상 학생들의 시간표를 한 번에 출력합니다. (학생 1명당 A4 1페이지)")
        
        # Select Grade/Class
        col_g, col_c, col_w = st.columns(3)
        with col_g:
            grade_input = st.selectbox("학년", ["1", "2", "3"])
        with col_c:
            class_input = st.selectbox("반", [str(i) for i in range(1, 16)]) # 1~15 class
        with col_w:
            week_opts_batch = ["전체"] + [f"{w}주차" for w in available_weeks]
            batch_week_sel = st.selectbox("출력할 주차", week_opts_batch)
            
        if st.button("일괄 조회 및 인쇄 미리보기"):
            targets = get_students_in_class(st.session_state.db, grade_input, class_input)
            
            # Filter Week
            target_week_val = None
            if batch_week_sel != "전체":
                target_week_val = int(batch_week_sel.replace("주차", ""))
            
            if not targets:
                st.warning(f"{grade_input}학년 {class_input}반에 최소 성취수준 보장지도 대상 학생이 없습니다.")
            else:
                st.success(f"총 {len(targets)}명의 학생 시간표를 생성합니다.")
                
                full_html = ""
                
                # Progress bar
                prog_bar = st.progress(0)
                
                for idx, student in enumerate(targets):
                    sid = student['학번']
                    name = student['이름']
                    
                    sch_df, _, _ = generate_student_timetable(st.session_state.db, sid, week=target_week_val)
                    
                    # Generate HTML Grid with Header
                    if sch_df is not None and not sch_df.empty:
                        t_html = format_student_timetable_grid(sch_df, student_info={'id': sid, 'name': name})
                    else:
                        t_html = f"<div style='text-align:center; padding: 20px;'><h3>{name} ({sid})</h3>배정된 시간표 없음</div>"
                        
                    # Wrap with Page Break
                    full_html += f"""
<div class="print-page" style="page-break-after: always; box-sizing: border-box;">
{t_html}
</div>
<div class="no-print" style="height: 30px; border-bottom: 1px dashed #ccc; margin-bottom: 30px;"></div>
"""
                    prog_bar.progress((idx + 1) / len(targets))
                    
                # CSS for Batch Print
                st.markdown("""
                <style>
                @media print {
                    #MainMenu, header, footer, [data-testid="stSidebar"], .stDeployButton {display: none !important;}
                    .stTextInput, .stButton, .stExpander, .stSelectbox, .stProgress, .stAlert {display: none !important;}
                    iframe {display: none !important;} 
                    .no-print {display: none !important;}
                    
                    /* Hide Tab Headers and Borders */
                    [data-baseweb="tab-list"], 
                    [data-baseweb="tab-highlight"], 
                    [data-baseweb="tab-border"] {
                        display: none !important; 
                        border: none !important;
                        height: 0 !important;
                    }
                    hr { display: none !important; }

                    /* Hide Header Decoration Line */
                    header, .stApp > header {
                        display: none !important;
                        opacity: 0 !important;
                        visibility: hidden !important;
                    }
                    header:before, header:after, .stApp > header:before, .stApp > header:after {
                        display: none !important;
                        content: none !important;
                    }
                    
                    /* Hide Print Button by hiding the iframe content */
                    iframe {
                        display: none !important;
                        height: 0 !important;
                        width: 0 !important;
                    }

                    /* Hide main titles unless it is our custom print title */
                    h1, h2, h3, h4, h5, h6 {display: none !important;}
                    h2.print-title {display: block !important;}
                    
                    /* Page Setup */
                    @page {
                        size: A4;
                        margin: 5mm 15mm 5mm 15mm; /* Top Right Bottom Left */
                    }
                    
                    table {
                        display: table !important;
                        width: 100% !important;
                        border-collapse: collapse !important;
                    }
                    th, td {
                        border: 1px solid #000 !important;
                        padding: 8px !important;
                        color: black !important;
                        -webkit-print-color-adjust: exact; 
                    }
                    html, body, .stApp { 
                        background-color: white !important; 
                        height: auto !important;
                        margin: 0 !important;
                        padding: 0 !important;
                        overflow: visible !important;
                    }
                    
                    /* Aggressively remove Streamlit container padding */
                    .block-container, 
                    [data-testid="stAppViewContainer"], 
                    [data-testid="stHeader"], 
                    [data-testid="stToolbar"],
                    .main,
                    .stApp {
                        padding: 0 !important;
                        margin: 0 !important;
                        padding-top: 0 !important;
                        margin-top: 0 !important;
                        max-width: none !important;
                    }

                    /* Page Break Control & Alignment */
                    .print-page {
                        page-break-after: always;
                        break-after: page;
                        page-break-inside: avoid;
                        display: block; /* Back to block for natural flow */
                        padding-top: 0px; 
                        margin-top: 0px;
                        box-sizing: border-box;
                    }

                    /* Formatting for print area */
                    #print-area {
                        position: absolute;
                        top: 0;
                        left: 0;
                        display: block;
                        width: 100%;
                        z-index: 9999;
                        margin: 0;
                        padding: 0;
                    }
                }
                </style>
                """, unsafe_allow_html=True)
                
                # Display Full HTML (Timetables) -> Wrapped in #print-area
                st.markdown(f'<div id="print-area">{full_html}</div>', unsafe_allow_html=True)

                # Print Button (Placed at BOTTOM)
                import streamlit.components.v1 as components
                components.html(f"""
                <div style="text-align: center;">
                    <button onclick="window.parent.print()" style="background-color: #2196F3; border: none; color: white; padding: 15px 32px; text-align: center; font-size: 16px; margin: 4px 2px; cursor: pointer; border-radius: 8px; font-weight: bold;">🏫 일괄 인쇄하기 ({len(targets)}명)</button>
                </div>
                """, height=100)

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
