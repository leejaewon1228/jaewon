# email_utils.py
import smtplib
import random
from email.mime.text import MIMEText

GMAIL_USER = 'iphjae12@gmail.com'
GMAIL_PASSWORD = 'peqpugliyscuwxsa'  # 붙여쓰기!

def generate_code():
    return str(random.randint(100000, 999999))  # 매번 다르게 생성됨

def send_verification_email(to_email, code):
    subject = '[회원가입 인증번호] 입력해 주세요'
    body = f'인증번호는 {code} 입니다. 5분 이내에 입력해주세요.'

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = GMAIL_USER
    msg['To'] = to_email

    try:
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(GMAIL_USER, GMAIL_PASSWORD)
        server.sendmail(GMAIL_USER, to_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f'이메일 전송 실패: {e}')
        return False
