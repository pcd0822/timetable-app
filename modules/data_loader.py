import pandas as pd
import re

def parse_excel(file):
    """
    Parses the uploaded Excel file.
    Expected Columns: [학번, 이름, 특기사항, 미도달내역, 미도달과목, 보충지도(추가학습) 내역, 예외처리]
    """
    try:
        df = pd.read_excel(file)
    except Exception as e:
        return None, f"Error reading Excel file: {e}"

    # Normalize columns (strip whitespace)
    df.columns = df.columns.astype(str).str.strip()
    
    required_cols = ['학번', '이름', '미도달과목', '예외처리']
    # Check if critical columns exist
    missing_cols = [col for col in required_cols if col not in df.columns]
    
    if missing_cols:
        return None, f"엑셀 파일 양식이 맞지 않습니다.\n누락된 열: {missing_cols}\n현재 파일의 열: {list(df.columns)}"

    # 1. Student ID Parsing
    # Ensure '학번' is treated as string
    df['학번'] = df['학번'].astype(str)
    
    def parse_student_id(sid):
        if len(sid) != 5:
            return None, None, None
        return sid[0], sid[1:3], sid[3:5]

    df[['학년', '반', '번호']] = df['학번'].apply(
        lambda x: pd.Series(parse_student_id(x))
    )

    # 2. Exception Handling
    df['is_exception'] = df['예외처리'].notna() & (df['예외처리'].str.strip() != '')

    # 3. Subject Parsing
    # Input: "국어(4학점), 영어(3학점)"
    # Output: List of Subject IDs e.g., ["국어_4", "영어_3"]
    
    def parse_subjects(sub_str):
        if pd.isna(sub_str):
            return []
        
        # Split by comma
        items = str(sub_str).split(',')
        parsed_list = []
        for item in items:
            item = item.strip()
            # Regex to capture Name and Credit
            # Matches "SubjectName(NCredit)" or similar
            match = re.match(r'(.+)\((\d+)학점\)', item)
            if match:
                name = match.group(1).strip()
                credit = match.group(2).strip()
                subject_id = f"{name}_{credit}"
                parsed_list.append(subject_id)
            else:
                # Fallback if format is slightly different or just text
                parsed_list.append(item)
        return parsed_list

    df['parsed_subjects'] = df['미도달과목'].apply(parse_subjects)

    return df, None
