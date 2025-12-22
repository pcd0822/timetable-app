import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import streamlit as st
import os
import json
import time

SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

class DBManager:
    def __init__(self, credentials_path="credentials.json"):
        self.credentials_path = credentials_path
        self.client = None
        self.spreadsheet = None
        # User provided specific URL to avoid Quota issues with new creations
        self.spreadsheet_url = "https://docs.google.com/spreadsheets/d/1VWAAy-5JJlX0kyRNQg4nXkTtkCeab-YLMISUnhCHkZQ/edit?usp=sharing"
        self.spreadsheet_name = "Timetable_System_DB" # Kept for reference
        self.is_local = False # Flag for local fallback
        self.cache = {} # In-memory cache for dataframes

    def _get_service_account_email(self):
        """Extracts client_email from credentials.json or secrets."""
        try:
            if "gcp_service_account" in st.secrets:
                return st.secrets["gcp_service_account"].get("client_email", "Unknown")
            
            if os.path.exists(self.credentials_path):
                with open(self.credentials_path, 'r', encoding='utf-8') as f:
                    creds = json.load(f)
                    return creds.get("client_email", "Unknown")
        except Exception:
            return "Unknown"
        return "Unknown"

    def connect(self):
        """Connects to Google Sheets API."""
        # 1. Try Streamlit Secrets First (for Cloud Deployment)
        if "gcp_service_account" in st.secrets:
            try:
                # Create credentials from secrets dict
                creds_dict = st.secrets["gcp_service_account"]
                creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
                self.client = gspread.authorize(creds)
                return True
            except Exception as e:
                st.error(f"Failed to connect using Streamlit Secrets: {e}")
                return False

        # 2. Fallback to Local File
        if not os.path.exists(self.credentials_path):
             st.error(f"Credentials not found. Expected 'secrets.toml' for cloud or '{self.credentials_path}' for local.")
             return False
        
        try:
            creds = ServiceAccountCredentials.from_json_keyfile_name(self.credentials_path, SCOPE)
            self.client = gspread.authorize(creds)
            return True
        except Exception as e:
            st.error(f"Failed to connect to Google Sheets: {e}")
            return False

    def get_spreadsheet(self):
        """Opens the spreadsheet using URL provided by user."""
        if self.is_local:
            return None

        if not self.client:
            if not self.connect():
                self.is_local = True
                return None
        
        if self.spreadsheet:
            return self.spreadsheet

        # Try opening by URL first (User Request)
        try:
            self.spreadsheet = self.client.open_by_url(self.spreadsheet_url)
            return self.spreadsheet
        except Exception as e:
            # Check for Permission (403) or generic errors
            err_msg = str(e)
            if "403" in err_msg or "permission" in err_msg.lower() or "quota" in err_msg.lower():
                sa_email = self._get_service_account_email()
                st.error(
                    f"""
                    ⚠️ **Google Sheets 접근 권한 오류**
                    
                    서비스 계정이 지정된 스프레드시트에 접근할 수 없거나 할당량(Quota) 문제가 발생했습니다.
                    
                    **[해결 방법]**
                    1. 아래 스프레드시트 링크로 이동하세요:
                    [스프레드시트 바로가기]({self.spreadsheet_url})
                    
                    2. 우측 상단 '공유' 버튼을 누르고 아래 이메일을 **편집자(Editor)**로 추가하세요:
                    
                    `{sa_email}`
                    
                    3. 공유 후 다시 '저장' 버튼을 눌러보세요.
                    """
                )
                with st.expander("상세 오류 메시지 (Debug Info)"):
                    st.write(err_msg)
                
                st.warning("⚠️ 권한 문제로 인해 **로컬 저장소 모드**로 전환합니다.")
                self.is_local = True
                return None
            
            # Other errors (e.g. Not Found)
            st.error(f"Failed to open spreadsheet by URL: {e}")
            self.is_local = True
            return None

    def save_dataframe(self, sheet_name, df):
        """Saves a pandas DataFrame to a specific worksheet or local CSV."""
        # Update Cache immediately so we don't need to re-fetch
        self.cache[sheet_name] = df.copy()

        # Check Local Mode first
        if self.is_local:
            return self._save_local(sheet_name, df)

        sh = self.get_spreadsheet()
        if self.is_local: # Check again in case get_spreadsheet caught an error
            return self._save_local(sheet_name, df)
            
        if not sh:
            return False

        try:
            worksheet = sh.worksheet(sheet_name)
            worksheet.clear()
        except gspread.WorksheetNotFound:
            try:
                worksheet = sh.add_worksheet(title=sheet_name, rows=100, cols=20)
            except Exception as e:
                # Local fallback for any creation error
                if "quota" in str(e).lower() or "403" in str(e):
                    st.warning("⚠️ Google Drive 용량 부족으로 인해 **로컬 저장소 모드**로 전환합니다.")
                    self.is_local = True
                    return self._save_local(sheet_name, df)
                st.error(f"Failed to add worksheet: {e}")
                return False
        except Exception as e:
             st.error(f"Worksheet error: {e}")
             return False
        
        # Retry logic for Writing
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Sanitize DataFrame: Replace NaN and Infinity with empty strings for JSON compatibility
                df_cleaned = df.fillna("").replace([float('inf'), float('-inf')], "")
                worksheet.update([df_cleaned.columns.values.tolist()] + df_cleaned.values.tolist())
                return True
            except Exception as e:
                if "quota" in str(e).lower() or "429" in str(e):
                    if attempt < max_retries - 1:
                        sleep_time = (2 ** attempt) + 1 # 2, 3, 5 seconds
                        time.sleep(sleep_time)
                        continue
                    else:
                        st.warning("⚠️ API 사용량 초과(429)가 지속되어 **로컬 저장소 모드**로 전환하여 저장합니다.")
                        self.is_local = True
                        return self._save_local(sheet_name, df)
                elif "403" in str(e):
                     st.warning("⚠️ 권한 오류로 인해 **로컬 저장소 모드**로 전환합니다.")
                     self.is_local = True
                     return self._save_local(sheet_name, df)
                
                st.error(f"Failed to save data to {sheet_name}: {e}")
                return False
        return False

    def load_dataframe(self, sheet_name, force_update=False):
        """Loads a worksheet into a pandas DataFrame."""
        # 1. Check Cache
        if not force_update and sheet_name in self.cache:
            return self.cache[sheet_name]

        if self.is_local:
            df = self._load_local(sheet_name)
            self.cache[sheet_name] = df
            return df

        sh = self.get_spreadsheet()
        if self.is_local:
             df = self._load_local(sheet_name)
             self.cache[sheet_name] = df
             return df
             
        if not sh:
            return pd.DataFrame() 

        # Retry logic for Reading
        max_retries = 3
        for attempt in range(max_retries):
            try:
                worksheet = sh.worksheet(sheet_name)
                data = worksheet.get_all_records()
                df = pd.DataFrame(data)
                self.cache[sheet_name] = df # Update Cache
                return df
            except gspread.WorksheetNotFound:
                # This is not an error, just empty
                return pd.DataFrame() 
            except Exception as e:
                if "quota" in str(e).lower() or "429" in str(e):
                    if attempt < max_retries - 1:
                        sleep_time = (2 ** attempt) + 1
                        time.sleep(sleep_time)
                        continue
                    else:
                        if not force_update:
                             # Last ditch: return cache if exists even if old
                             if sheet_name in self.cache:
                                 st.warning(f"⚠️ API 연결 불안정. 캐시된 데이터(이전 버전)를 불러옵니다. ({sheet_name})")
                                 return self.cache[sheet_name]
                        
                        st.warning(f"Error loading from Sheets ({e}). Trying local...")
                        return self._load_local(sheet_name)
                else:
                    # Other errors
                     st.warning(f"Error loading from Sheets ({e}). Trying local...")
                     return self._load_local(sheet_name)
        
        return pd.DataFrame()

    # --- Local Fallback Methods ---
    def _get_local_path(self, sheet_name):
        data_dir = "data"
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
        return os.path.join(data_dir, f"{sheet_name}.csv")

    def _save_local(self, sheet_name, df):
        try:
            path = self._get_local_path(sheet_name)
            df.to_csv(path, index=False)
            st.info(f"💾 로컬 파일(CSV)로 저장되었습니다: {path}")
            return True
        except Exception as e:
            st.error(f"Local save failed: {e}")
            return False

    def _load_local(self, sheet_name):
        try:
            path = self._get_local_path(sheet_name)
            if os.path.exists(path):
                return pd.read_csv(path)
            return pd.DataFrame()
        except Exception as e:
            # st.error(f"Local load failed: {e}") # Suppress unless needed
            return pd.DataFrame()
