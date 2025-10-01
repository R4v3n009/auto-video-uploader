from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QPushButton, QMessageBox, QLabel
)
from account_manager import AccountManager

class AccountsDialog(QDialog):
    def __init__(self, manager: AccountManager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.setWindowTitle("Quản lý tài khoản YouTube")
        self.setMinimumWidth(500)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Các tài khoản đã liên kết:"))
        
        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        button_layout = QHBoxLayout()
        add_btn = QPushButton("Thêm tài khoản mới...")
        remove_btn = QPushButton("Xóa tài khoản đã chọn")
        button_layout.addWidget(add_btn)
        button_layout.addWidget(remove_btn)
        layout.addLayout(button_layout)
        
        add_btn.clicked.connect(self.add_account)
        remove_btn.clicked.connect(self.remove_account)

        self.populate_list()

    def populate_list(self):
        self.list_widget.clear()
        for account in self.manager.get_accounts():
            self.list_widget.addItem(account['name'])
    
    def add_account(self):
        self.hide() # Hide dialog during browser auth
        success, message = self.manager.add_account()
        self.show() # Show it again

        if success:
            QMessageBox.information(self, "Thành công", message)
            self.populate_list()
        else:
            QMessageBox.critical(self, "Lỗi", message)

    def remove_account(self):
        selected_item = self.list_widget.currentItem()
        if not selected_item:
            QMessageBox.warning(self, "Chưa chọn", "Vui lòng chọn một tài khoản để xóa.")
            return

        selected_account_name = selected_item.text()
        selected_account = next((acc for acc in self.manager.get_accounts() if acc['name'] == selected_account_name), None)
        
        if selected_account:
            reply = QMessageBox.question(self, "Xác nhận xóa", 
                f"Bạn có chắc muốn xóa tài khoản '{selected_account_name}'?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            
            if reply == QMessageBox.Yes:
                self.manager.remove_account(selected_account['id'])
                self.populate_list()