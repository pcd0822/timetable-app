import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import streamlit as st
import os

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
        if not self.client:
            if not self.connect():
                return None
        
        if self.spreadsheet:
            return self.spreadsheet

        try:
            self.spreadsheet = self.client.open(self.spreadsheet_name)
        except gspread.SpreadsheetNotFound:
            try:
                self.spreadsheet = self.client.create(self.spreadsheet_name)
                # Share with the user if possible (requires user email, skipping for now or printing info)
                st.warning(f"Created new spreadsheet: {self.spreadsheet_name}. Please check your Google Drive.")
            except Exception as e:
                st.error(f"Failed to open or create spreadsheet: {e}")
                return None
        
        return self.spreadsheet

    def save_dataframe(self, sheet_name, df):
        """Saves a pandas DataFrame to a specific worksheet."""
        sh = self.get_spreadsheet()
        if not sh:
            return False

        try:
            worksheet = sh.worksheet(sheet_name)
            worksheet.clear()
        except gspread.WorksheetNotFound:
            worksheet = sh.add_worksheet(title=sheet_name, rows=100, cols=20)
        
        try:
            worksheet.update([df.columns.values.tolist()] + df.values.tolist())
            return True
        except Exception as e:
            st.error(f"Failed to save data to {sheet_name}: {e}")
            return False

    def load_dataframe(self, sheet_name):
        """Loads a worksheet into a pandas DataFrame."""
        sh = self.get_spreadsheet()
        if not sh:
            return pd.DataFrame() # Return empty if failed

        try:
            worksheet = sh.worksheet(sheet_name)
            data = worksheet.get_all_records()
            return pd.DataFrame(data)
        except gspread.WorksheetNotFound:
            return pd.DataFrame() # Return empty if not found
        except Exception as e:
            st.error(f"Error loading {sheet_name}: {e}")
            return pd.DataFrame()
