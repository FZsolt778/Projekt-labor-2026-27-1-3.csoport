import re

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QGridLayout, QLabel, QStackedWidget, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, LineEdit, MessageBoxBase, PasswordLineEdit, SegmentedWidget, SubtitleLabel

from api_client import ROLE_LABELS, ApiError, api, run_in_background

ERROR_STYLE = "color: #D13438; background: transparent;"
MUTED_STYLE = "color: #6B6B6B; background: transparent;"
ADDRESS_FIELDS = ("postal_code", "city", "street", "house_number")
PROFILE_FIELDS = {
    "last_name": "Vezetéknév",
    "first_name": "Keresztnév",
    "email": "Email cím",
    "phone": "Telefonszám (nem kötelező)",
    "postal_code": "Irányítószám",
    "city": "Település",
    "street": "Utca, közterület",
    "house_number": "Házszám",
}


def validate_profile(values: dict[str, str]) -> dict[str, str]:
    errors = {}
    for key, name in (("last_name", "A vezetéknév"), ("first_name", "A keresztnév")):
        if not values[key]:
            errors[key] = f"{name} megadása kötelező."
        elif len(values[key]) > 50:
            errors[key] = f"{name} legfeljebb 50 karakter lehet."
    email = values["email"]
    if not email:
        errors["email"] = "Az email cím megadása kötelező."
    elif len(email) > 100 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        errors["email"] = "Adj meg egy érvényes email címet."
    phone = values["phone"]
    if phone and (len(phone) > 20 or not re.fullmatch(r"\+?[0-9][0-9 /-]{5,18}", phone)):
        errors["phone"] = "Adj meg egy érvényes telefonszámot."
    if any(values[key] for key in ADDRESS_FIELDS):
        for key, name in zip(ADDRESS_FIELDS, ("Az irányítószám", "A település", "Az utca", "A házszám")):
            if not values[key]:
                errors[key] = f"{name} megadása szükséges a címhez."
        if values["postal_code"] and not re.fullmatch(r"[1-9][0-9]{3}", values["postal_code"]):
            errors["postal_code"] = "Az irányítószám 4 számjegyből álljon, és ne kezdődjön nullával."
        for key, name, maximum in (("city", "A település", 50), ("street", "Az utca", 100),
                                   ("house_number", "A házszám", 20)):
            if len(values[key]) > maximum:
                errors[key] = f"{name} legfeljebb {maximum} karakter lehet."
    return errors


def profile_changes(user: dict, values: dict[str, str]) -> dict:
    changes = {key: values[key] for key in ("last_name", "first_name", "email")
               if values[key] != (user.get(key) or "")}
    if values["phone"] != (user.get("phone") or ""):
        changes["phone"] = values["phone"] or None
    if any(values[key] != (user.get(key) or "") for key in ADDRESS_FIELDS):
        changes.update({key: values[key] or None for key in ADDRESS_FIELDS})
    return changes


def _field(parent: QWidget, edit: LineEdit) -> tuple[QWidget, QLabel]:
    container = QWidget(parent)
    container.setStyleSheet("background: transparent;")
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(2)
    error = QLabel(container)
    error.setStyleSheet(ERROR_STYLE)
    error.setWordWrap(True)
    error.hide()
    edit.textChanged.connect(error.hide)
    layout.addWidget(edit)
    layout.addWidget(error)
    return container, error


class ProfileDialog(MessageBoxBase):
    profileSaved = Signal(dict)
    passwordChanged = Signal()

    def __init__(self, account: dict | None, parent: QWidget):
        super().__init__(parent)
        self.user: dict = dict(account or {})
        self._busy = False

        self.titleLabel = SubtitleLabel("Saját fiók", self.widget)
        info = [f"Szerepkör: {ROLE_LABELS.get(api.role, {}).get('title', '')}"]
        if api.expires_at is not None:
            info.append(f"A munkamenet lejár: {api.expires_at.astimezone():%H:%M}")
        self.infoLabel = BodyLabel("\n".join(info), self.widget)
        self.infoLabel.setStyleSheet(MUTED_STYLE)

        self.messageLabel = QLabel(self.widget)
        self.messageLabel.setWordWrap(True)
        self.messageLabel.hide()

        self.tabs = SegmentedWidget(self.widget)
        self.pages = QStackedWidget(self.widget)
        self.pages.setStyleSheet("QStackedWidget, QStackedWidget > QWidget { background: transparent; }")
        self.pages.addWidget(self._build_profile_page())
        self.pages.addWidget(self._build_password_page())
        self.tabs.addItem("profile", "Személyes adatok", onClick=lambda: self._switch(0))
        self.tabs.addItem("password", "Jelszó", onClick=lambda: self._switch(1))
        self.tabs.setCurrentItem("profile")

        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.infoLabel)
        self.viewLayout.addWidget(self.tabs)
        self.viewLayout.addWidget(self.pages)
        self.viewLayout.addWidget(self.messageLabel)
        self.cancelButton.setText("Bezárás")
        self.widget.setMinimumWidth(560)
        self._switch(0)

        self._fill(self.user)
        self._set_profile_enabled(False)
        self._show_message("Adatok betöltése...")
        run_in_background(api.get, "/users/me", on_success=self._on_loaded, on_error=self._on_load_error)

    # --- layout ------------------------------------------------------------

    def _build_profile_page(self) -> QWidget:
        page = QWidget()
        grid = QGridLayout(page)
        grid.setContentsMargins(0, 8, 0, 0)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)
        self.fields: dict[str, LineEdit] = {}
        self.fieldErrors: dict[str, QLabel] = {}
        positions = {
            "last_name": (0, 0, 1), "first_name": (0, 1, 1),
            "email": (1, 0, 2), "phone": (2, 0, 2),
            "postal_code": (3, 0, 1), "city": (3, 1, 1),
            "street": (4, 0, 1), "house_number": (4, 1, 1),
        }
        for key, placeholder in PROFILE_FIELDS.items():
            edit = LineEdit(page)
            edit.setPlaceholderText(placeholder)
            edit.setClearButtonEnabled(True)
            container, error = _field(page, edit)
            row, column, span = positions[key]
            grid.addWidget(container, row, column, 1, span)
            self.fields[key] = edit
            self.fieldErrors[key] = error
        hint = QLabel("A cím nem kötelező, de ha megadod, mind a négy mezőjét ki kell tölteni.", page)
        hint.setStyleSheet(MUTED_STYLE)
        hint.setWordWrap(True)
        grid.addWidget(hint, 5, 0, 1, 2)
        return page

    def _build_password_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)
        self.passwordFields: dict[str, PasswordLineEdit] = {}
        self.passwordErrors: dict[str, QLabel] = {}
        for key, placeholder in (("current_password", "Jelenlegi jelszó"), ("new_password", "Új jelszó"),
                                 ("confirm_password", "Új jelszó még egyszer")):
            edit = PasswordLineEdit(page)
            edit.setPlaceholderText(placeholder)
            container, error = _field(page, edit)
            layout.addWidget(container)
            self.passwordFields[key] = edit
            self.passwordErrors[key] = error
        hint = QLabel("Az új jelszó legalább 8 karakter legyen.", page)
        hint.setStyleSheet(MUTED_STYLE)
        layout.addWidget(hint)
        layout.addStretch(1)
        return page

    def _switch(self, index: int) -> None:
        self.pages.setCurrentIndex(index)
        self.yesButton.setText("Mentés" if index == 0 else "Jelszó módosítása")
        ready = index == 1 or self.fields["last_name"].isEnabled()
        self.yesButton.setEnabled(ready and not self._busy)
        self.messageLabel.hide()

    def _show_message(self, text: str, error: bool = False) -> None:
        self.messageLabel.setStyleSheet(ERROR_STYLE if error else MUTED_STYLE)
        self.messageLabel.setText(text)
        self.messageLabel.show()

    def _set_profile_enabled(self, enabled: bool) -> None:
        for edit in self.fields.values():
            edit.setEnabled(enabled)
        if self.pages.currentIndex() == 0:
            self.yesButton.setEnabled(enabled)

    def _fill(self, user: dict) -> None:
        for key, edit in self.fields.items():
            edit.setText(user.get(key) or "")

    # --- loading -------------------------------------------------------------

    def _on_loaded(self, user: dict) -> None:
        self.user = user
        self._fill(user)
        self._set_profile_enabled(True)
        self.messageLabel.hide()

    def _on_load_error(self, error: ApiError) -> None:
        self._set_profile_enabled(bool(self.user))
        self._show_message(error.message, error=True)

    # --- saving (the dialog stays open until the server answers) ------------------

    def validate(self) -> bool:
        if not self._busy:
            if self.pages.currentIndex() == 0:
                self._save_profile()
            else:
                self._change_password()
        return False

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.yesButton.setEnabled(not busy)

    def _show_field_errors(self, errors: dict[str, str], labels: dict[str, QLabel]) -> int:
        for key, label in labels.items():
            if key in errors:
                label.setText(errors[key])
                label.show()
            else:
                label.hide()
        return sum(key in labels for key in errors)

    def _show_server_error(self, error: ApiError, errors: dict[str, str], labels: dict[str, QLabel]) -> None:
        shown = self._show_field_errors(errors, labels)
        self._show_message("Javítsd a pirossal jelölt mezőket." if shown else error.message, error=True)

    def _save_profile(self) -> None:
        values = {key: edit.text().strip() for key, edit in self.fields.items()}
        errors = validate_profile(values)
        self._show_field_errors(errors, self.fieldErrors)
        if errors:
            self._show_message("Javítsd a pirossal jelölt mezőket.", error=True)
            return
        changes = profile_changes(self.user, values)
        if not changes:
            self._show_message("Nem módosítottál semmit.")
            return
        self._set_busy(True)
        self._show_message("Mentés...")
        run_in_background(api.patch, "/users/me", changes,
                          on_success=self._on_profile_saved, on_error=self._on_profile_error)

    def _on_profile_saved(self, user: dict) -> None:
        self._set_busy(False)
        self.profileSaved.emit(user)
        self.accept()

    def _on_profile_error(self, error: ApiError) -> None:
        self._set_busy(False)
        errors = dict(error.field_errors)
        if error.status_code == 409 and not errors:
            errors["email"] = error.message
        self._show_server_error(error, errors, self.fieldErrors)

    def _change_password(self) -> None:
        values = {key: edit.text() for key, edit in self.passwordFields.items()}
        errors = {}
        if not values["current_password"]:
            errors["current_password"] = "A jelenlegi jelszó megadása kötelező."
        if len(values["new_password"]) < 8:
            errors["new_password"] = "Az új jelszó legalább 8 karakter legyen."
        elif len(values["new_password"]) > 128:
            errors["new_password"] = "Az új jelszó legfeljebb 128 karakter lehet."
        elif values["new_password"] == values["current_password"]:
            errors["new_password"] = "Az új jelszó nem egyezhet meg a jelenlegivel."
        if values["confirm_password"] != values["new_password"]:
            errors["confirm_password"] = "A két új jelszó nem egyezik."
        self._show_field_errors(errors, self.passwordErrors)
        if errors:
            self._show_message("Javítsd a pirossal jelölt mezőket.", error=True)
            return
        self._set_busy(True)
        self._show_message("Jelszó módosítása...")
        body = {"current_password": values["current_password"], "new_password": values["new_password"]}
        run_in_background(api.post, "/auth/change-password", body,
                          on_success=self._on_password_changed, on_error=self._on_password_error)

    def _on_password_changed(self, _result) -> None:
        self._set_busy(False)
        self.passwordChanged.emit()
        self.accept()

    def _on_password_error(self, error: ApiError) -> None:
        self._set_busy(False)
        errors = dict(error.field_errors)
        if error.status_code == 400 and not errors:
            errors["current_password"] = error.message
        self._show_server_error(error, errors, self.passwordErrors)
