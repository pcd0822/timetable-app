import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import streamlit as st
import os
import json

SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

class DBManager:
    def __init__(self, credentials_path="credentials.json"):
        self.credentials_path = credentials_path
        self.client = None
        self.spreadsheet = None
        self.spreadsheet_name = "Timetable_System_DB" # Default spreadsheet name
        self.is_local = False # Flag for local fallback

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
        """Opens the spreadsheet, creating it if it doesn't exist."""
        if self.is_local:
            return None

        if not self.client:
            if not self.connect():
                self.is_local = True
                return None
        
        if self.spreadsheet:
            return self.spreadsheet

        try:
            self.spreadsheet = self.client.open(self.spreadsheet_name)
        except gspread.SpreadsheetNotFound:
            try:
                self.spreadsheet = self.client.create(self.spreadsheet_name)
                st.warning(f"Created new spreadsheet: {self.spreadsheet_name}. Please check your Google Drive.")
            except Exception as e:
                # Check for Quota or Permission errors during creation
                if "quota" in str(e).lower() or "403" in str(e):
                    sa_email = self._get_service_account_email()
                    st.error(
                        f"""
                        ⚠️ **Google Drive 저장 용량 부족 (Quota Exceeded)**
                        
                        서비스 계정의 저장 공간이 부족하여 시트를 생성할 수 없습니다.
                        
                        **[해결 방법]**
                        1. 본인의 **개인 구글 드라이브**에 `{self.spreadsheet_name}` 라는 이름의 새 스프레드시트를 만드세요.
                        2. 해당 시트의 '공유' 버튼을 누르고 아래 이메일을 **편집자(Editor)**로 추가하세요:
                        
                        `{sa_email}`
                        
                        3. 공유 후 다시 시도하세요.
                        """
                    )
                    st.warning("⚠️ 임시로 **로컬 저장소 모드**로 전환합니다.")
                    self.is_local = True
                    return None
                st.error(f"Failed to open or create spreadsheet: {e}")
                return None
        except Exception as e:
             if "quota" in str(e).lower() or "403" in str(e):
                st.warning("⚠️ Google Drive 용량 초과(Quota Exceeded)로 인해 **로컬 저장소 모드**로 전환합니다.")
                self.is_local = True
                return None
             st.error(f"Connection Error: {e}")
             return None
        
        return self.spreadsheet

    def save_dataframe(self, sheet_name, df):
        """Saves a pandas DataFrame to a specific worksheet or local CSV."""
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
                if "quota" in str(e).lower() or "403" in str(e):
                    st.warning("⚠️ Google Drive 용량 부족으로 인해 **로컬 저장소 모드**로 전환합니다.")
                    self.is_local = True
                    return self._save_local(sheet_name, df)
                st.error(f"Failed to add worksheet: {e}")
                return False
        except Exception as e:
             st.error(f"Worksheet error: {e}")
             return False
        
        try:
            worksheet.update([df.columns.values.tolist()] + df.values.tolist())
            return True
        except Exception as e:
            if "quota" in str(e).lower() or "403" in str(e):
                st.warning("⚠️ Google Drive 용량 초과로 인해 **로컬 저장소 모드**로 전환하여 저장합니다.")
                self.is_local = True
                return self._save_local(sheet_name, df)
            st.error(f"Failed to save data to {sheet_name}: {e}")
            return False

    def load_dataframe(self, sheet_name):
        """Loads a worksheet into a pandas DataFrame."""
        if self.is_local:
            return self._load_local(sheet_name)

        sh = self.get_spreadsheet()
        if self.is_local:
             return self._load_local(sheet_name)
             
        if not sh:
            return pd.DataFrame() 

        try:
            worksheet = sh.worksheet(sheet_name)
            data = worksheet.get_all_records()
            return pd.DataFrame(data)
        except gspread.WorksheetNotFound:
            return pd.DataFrame() 
        except Exception as e:
             # Retry locally if connection fails?
             st.warning(f"Error loading from Sheets ({e}). Trying local...")
             return self._load_local(sheet_name)

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
