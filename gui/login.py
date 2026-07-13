from PyQt6.QtWidgets import (
    QWidget,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QMessageBox,
    QCheckBox,
    QFrame,
    QDialog,
)

from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QGraphicsDropShadowEffect

from api import login, register
from chat import ChatWindow


class RegisterDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("注册")
        self.resize(360, 320)
        self.setStyleSheet("background: #0f172a; color: #e2e8f0;")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        title = QLabel("创建新账号")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 22px; font-weight: 700; color: #f8fafc;")

        self.reg_username = QLineEdit()
        self.reg_username.setPlaceholderText("用户名")
        self.reg_username.setStyleSheet(
            "background: #1f2937; border: 1px solid #374151; border-radius: 10px; padding: 10px 12px; color: #f9fafb;"
        )

        self.reg_password = QLineEdit()
        self.reg_password.setPlaceholderText("密码")
        self.reg_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.reg_password.setStyleSheet(
            "background: #1f2937; border: 1px solid #374151; border-radius: 10px; padding: 10px 12px; color: #f9fafb;"
        )

        confirm_btn = QPushButton("注册")
        confirm_btn.setStyleSheet(
            """
            QPushButton {
                background: #10b981;
                color: white;
                border: none;
                border-radius: 10px;
                padding: 10px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #059669;
            }
            """
        )
        confirm_btn.clicked.connect(self.handle_register)

        layout.addWidget(title)
        layout.addWidget(self.reg_username)
        layout.addWidget(self.reg_password)
        layout.addWidget(confirm_btn)

    def handle_register(self):
        username = self.reg_username.text().strip()
        password = self.reg_password.text()

        if not username or not password:
            QMessageBox.warning(self, "提示", "请输入用户名和密码")
            return

        result = register(username, password)
        if result.get("success"):
            QMessageBox.information(self, "成功", "注册成功，请返回登录")
            self.accept()
        else:
            QMessageBox.warning(self, "失败", result.get("message", "注册失败"))


class LoginWindow(QWidget):

    def __init__(self):
        super().__init__()
        self.settings = QSettings("Kubedoctor", "Client")
        self.setWindowTitle("Kubedoctor Login")
        self.resize(430, 560)
        self.setStyleSheet(
            """
            QWidget { background: #0f172a; color: #e2e8f0; }
            """
        )
        self.init_ui()
        self.load_saved_credentials()

    def init_ui(self):
        outer = QVBoxLayout()
        outer.setContentsMargins(24, 24, 24, 24)

        card = QFrame(self)
        card.setObjectName("card")
        card.setStyleSheet(
            """
            #card {
                background: #111827;
                border: 1px solid #2d3748;
                border-radius: 22px;
            }
            """
        )

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setOffset(0, 10)
        shadow.setColor(QColor(0, 0, 0, 120))
        card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(32, 32, 32, 32)
        card_layout.setSpacing(14)

        title = QLabel("Kubedoctor")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 30px; font-weight: 700; color: #f8fafc;")

        subtitle = QLabel("智能运维助手")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("font-size: 13px; color: #94a3b8; margin-bottom: 8px;")

        self.username = QLineEdit()
        self.username.setPlaceholderText("用户名")
        self.username.setStyleSheet(
            "background: #1f2937; border: 1px solid #374151; border-radius: 10px; padding: 10px 12px; color: #f9fafb;"
        )

        self.password = QLineEdit()
        self.password.setPlaceholderText("密码")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setStyleSheet(
            "background: #1f2937; border: 1px solid #374151; border-radius: 10px; padding: 10px 12px; color: #f9fafb;"
        )

        self.remember = QCheckBox("记住账号和密码")
        self.remember.setStyleSheet("color: #cbd5e1; padding: 4px 0px;")

        btn = QPushButton("登录")
        btn.setStyleSheet(
            """
            QPushButton {
                background: #10b981;
                color: white;
                border: none;
                border-radius: 10px;
                padding: 10px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #059669;
            }
            """
        )

        register_btn = QPushButton("注册")
        register_btn.setStyleSheet(
            """
            QPushButton {
                background: #1f2937;
                color: #f8fafc;
                border: 1px solid #374151;
                border-radius: 10px;
                padding: 10px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #374151;
            }
            """
        )

        btn.clicked.connect(self.handle_login)
        register_btn.clicked.connect(self.handle_register)
        self.password.returnPressed.connect(self.handle_login)

        card_layout.addWidget(title)
        card_layout.addWidget(subtitle)
        card_layout.addWidget(self.username)
        card_layout.addWidget(self.password)
        card_layout.addWidget(self.remember)
        card_layout.addWidget(btn)
        card_layout.addWidget(register_btn)

        outer.addWidget(card, alignment=Qt.AlignmentFlag.AlignCenter)
        self.setLayout(outer)

    def load_saved_credentials(self):
        username = self.settings.value("username", "")
        password = self.settings.value("password", "")
        remember = self.settings.value("remember", False, type=bool)
        if username:
            self.username.setText(username)
        if password:
            self.password.setText(password)
        self.remember.setChecked(remember)

    def save_credentials(self, username, password):
        if self.remember.isChecked():
            self.settings.setValue("username", username)
            self.settings.setValue("password", password)
            self.settings.setValue("remember", True)
        else:
            self.settings.remove("username")
            self.settings.remove("password")
            self.settings.setValue("remember", False)

    def handle_login(self):
        username = self.username.text().strip()
        password = self.password.text()

        if not username or not password:
            QMessageBox.warning(self, "提示", "请输入用户名和密码")
            return

        try:
            result = login(username, password)
            if result.get("success"):
                self.save_credentials(username, password)
                self.chat = ChatWindow(username)
                self.chat.show()
                self.close()
            else:
                QMessageBox.warning(self, "错误", "用户名或密码错误")
        except Exception as e:
            QMessageBox.critical(self, "错误", str(e))

    def handle_register(self):
        dialog = RegisterDialog(self)
        dialog.exec()