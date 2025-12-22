# 배포 가이드 (Deployment Guide)

본 프로젝트는 **Streamlit** 기반 웹 애플리케이션으로, Netlify가 아닌 **Streamlit Community Cloud**에 배포하는 것이 가장 적합합니다. (Netlify는 정적 사이트 전용이므로 Streamlit 구동이 어렵습니다.)

Streamlit Cloud는 GitHub와 연동되어 무료로 웹 링크를 제공합니다.

## 1. GitHub 업로드 (GitHub Push)
1. GitHub에 새 Repository를 생성합니다 (Private 권장).
2. 현재 폴더의 파일들을 업로드합니다.
   > **주의**: `credentials.json` 파일은 절대 올리지 마세요! (`.gitignore`에 의해 자동 제외됨)

## 2. Streamlit Cloud 배포
1. [Streamlit Community Cloud](https://streamlit.io/cloud)에 로그인합니다.
2. 'New app'을 클릭하고 GitHub Repository를 선택합니다.
3. `Main file path`에 `app.py`를 입력하고 'Deploy!'를 클릭합니다.

## 3. Secrets 설정 (중요)
배포 직후에는 `credentials.json`이 없어서 오류가 날 것입니다. Streamlit Cloud 설정에서 키 값을 입력해야 합니다.

1. 배포된 앱 우측 하단의 'Manage app' > 'Settings' (또는 점 3개 메뉴 > Settings)로 이동합니다.
2. **Secrets** 탭을 클릭합니다.
3. 아래 형식으로 내용을 입력하고 저장합니다. (본인의 `credentials.json` 내용을 복사해서 포맷팅해야 함)

```toml
[gcp_service_account]
type = "service_account"
project_id = "your-project-id"
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----..."
client_email = "..."
client_id = "..."
auth_uri = "..."
token_uri = "..."
auth_provider_x509_cert_url = "..."
client_x509_cert_url = "..."
```
*Tip: `credentials.json` 내용을 복사 붙여넣기 하면 자동으로 TOML 포맷으로 변환해주는 경우가 많습니다.*

## 4. 완료
Secrets 저장 후 앱을 재부팅(Reboot)하면 정상적으로 Google Sheets와 연동되어 작동합니다.
