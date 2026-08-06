import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.core.mail import body
from app.core.config import SMTP_HOST, SMTP_PORT, SMTP_SENDER, SMTP_PASSWORD, SMTP_RECEIVER
# 发件人信息
sender_email = SMTP_SENDER
sender_password = SMTP_PASSWORD

# 收件人
receiver_email = SMTP_RECEIVER

# 创建邮件
msg = MIMEMultipart()
msg["From"] = sender_email
msg["To"] = receiver_email
msg["Subject"] = "[KubDoctor][Critical] Pod 异常告警"

body = body

msg.attach(MIMEText(body, "plain", "utf-8"))

# 发送
try:
    server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT)
    server.login(sender_email, sender_password)

    server.sendmail(
        sender_email,
        receiver_email,
        msg.as_string()
    )

    print("邮件发送成功！")

except Exception as e:
    print("发送失败：", e)

finally:
    server.quit()