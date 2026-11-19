# Admin: user list, new user, edit, deactivate / reactivate
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFormLayout, QFrame, QHBoxLayout, QLabel, QVBoxLayout
from qfluentwidgets import (
    ComboBox,
    LineEdit,
    PasswordLineEdit,
    PrimaryPushButton,
    PushButton,
    SubtitleLabel,
    setFont,
)

from api_client import ApiError, ROLE_LABELS, api, run_in_background
from .admin_helpers import (
    FORM_MAX_WIDTH,
    MUTED_STYLE,
    AdminPage,
    Pager,
    confirm,
    create_table,
    fill_table,
    full_name,
    select_by_id,
    selected_row,
    set_message,
    text_or_none,
)

ADDRESS_FIELDS = ("postal_code", "city", "street", "house_number")
REQUIRED_FIELDS = {"last_name": "Vezetéknév", "first_name": "Keresztnév", "email": "Email cím"}
MIN_PASSWORD_LENGTH = 8


def _role_title(role: str) -> str:
    # ROLE_LABELS: role -> {"title": ..., "value": ...}
    return ROLE_LABELS.get(role, {}).get("title", role)


class UsersInterface(AdminPage):
    def __init__(self, text: str = "Admin Users", parent=None):
        super().__init__(
            text.replace(" ", "-"),
            "Felhasználók",
            "Felhasználók keresése, új futár, raktáros vagy adminisztrátor felvétele, az adatok és a "
            "szerepkör módosítása. Az inaktivált felhasználó nem tud bejelentkezni, de az adatai megmaradnak.",
            parent,
        )
        self.users: list[dict] = []
        # None while creating a new user
        self.current: dict | None = None
        self._notice: str | None = None

        self.newButton = PushButton("Új felhasználó", self.content)
        self.newButton.clicked.connect(lambda: self._open_editor(None))
        self.headerLayout.insertWidget(2, self.newButton)

        filters = QHBoxLayout()
        self.searchEdit = LineEdit(self.content)
        self.searchEdit.setPlaceholderText("Név vagy email cím")
        self.searchEdit.setClearButtonEnabled(True)
        self.searchEdit.returnPressed.connect(self._apply_filters)
        self.roleFilter = ComboBox(self.content)
        self.roleFilter.addItem("Minden szerepkör", userData=None)
        for role in ROLE_LABELS:
            self.roleFilter.addItem(_role_title(role), userData=role)
        self.stateFilter = ComboBox(self.content)
        for label, value in (("Minden állapot", None), ("Aktív", True), ("Inaktív", False)):
            self.stateFilter.addItem(label, userData=value)
        self.filterButton = PushButton("Szűrés", self.content)
        self.filterButton.clicked.connect(self._apply_filters)
        filters.addWidget(self.searchEdit, 2)
        filters.addWidget(self.roleFilter, 1)
        filters.addWidget(self.stateFilter, 1)
        filters.addWidget(self.filterButton)
        self.contentLayout.insertLayout(2, filters)

        self.table = create_table(["Név", "Email cím", "Szerepkör", "Telefonszám", "Állapot"], self.content)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.contentLayout.addWidget(self.table)
        self.pager = Pager(self.content)
        self.pager.pageChanged.connect(self.refresh)
        self.contentLayout.addWidget(self.pager)

        self.editorFrame = QFrame(self.content)
        self.editorFrame.setMaximumWidth(FORM_MAX_WIDTH)
        editorLayout = QVBoxLayout(self.editorFrame)
        editorLayout.setContentsMargins(0, 8, 0, 0)
        editorLayout.setSpacing(10)
        self.editorTitle = SubtitleLabel(self.editorFrame)
        setFont(self.editorTitle, 20, QFont.Weight.DemiBold)
        editorLayout.addWidget(self.editorTitle)
        self.editorMessage = QLabel(self.editorFrame)
        self.editorMessage.setWordWrap(True)
        editorLayout.addWidget(self.editorMessage)

        form = QFormLayout()
        self.textFields: dict[str, LineEdit] = {}
        labels = {
            "last_name": "Vezetéknév",
            "first_name": "Keresztnév",
            "email": "Email cím",
            "phone": "Telefonszám",
        }
        for field, label in labels.items():
            self.textFields[field] = self._add_line(form, label)
        self.roleCombo = ComboBox(self.editorFrame)
        for role in ROLE_LABELS:
            self.roleCombo.addItem(_role_title(role), userData=role)
        form.addRow("Szerepkör", self.roleCombo)
        self.passwordEdit = PasswordLineEdit(self.editorFrame)
        self.passwordEdit.setMinimumHeight(42)
        form.addRow("Jelszó", self.passwordEdit)
        address_labels = {
            "postal_code": "Irányítószám",
            "city": "Település",
            "street": "Utca, házszám nélkül",
            "house_number": "Házszám",
        }
        for field, label in address_labels.items():
            self.textFields[field] = self._add_line(form, label)
        editorLayout.addLayout(form)
        hint = QLabel("A cím nem kötelező, de ha megadod, mind a négy mezőjét ki kell tölteni.", self.editorFrame)
        hint.setWordWrap(True)
        hint.setStyleSheet(MUTED_STYLE)
        editorLayout.addWidget(hint)

        buttons = QHBoxLayout()
        self.saveButton = PrimaryPushButton("Mentés", self.editorFrame)
        self.saveButton.clicked.connect(self.save)
        self.activeButton = PushButton(self.editorFrame)
        self.activeButton.clicked.connect(self.toggle_active)
        self.closeButton = PushButton("Bezárás", self.editorFrame)
        self.closeButton.clicked.connect(self._close_editor)
        buttons.addWidget(self.saveButton)
        buttons.addWidget(self.activeButton)
        buttons.addStretch(1)
        buttons.addWidget(self.closeButton)
        editorLayout.addLayout(buttons)
        self.editorFrame.hide()
        self.contentLayout.addWidget(self.editorFrame)
        self.contentLayout.addStretch(1)

    def _add_line(self, form: QFormLayout, label: str) -> LineEdit:
        edit = LineEdit(self.editorFrame)
        edit.setClearButtonEnabled(True)
        edit.setMinimumHeight(42)
        form.addRow(label, edit)
        return edit

    # --- List ---

    def _apply_filters(self) -> None:
        self.pager.reset()
        self.refresh()

    def refresh(self) -> None:
        if not self.can_load():
            return
        params = {
            **self.pager.params(),
            "search": text_or_none(self.searchEdit),
            "role": self.roleFilter.currentData(),
            "is_active": self.stateFilter.currentData(),
        }
        self.refreshButton.setEnabled(False)
        self.show_message("Felhasználók betöltése...")
        run_in_background(api.get, "/users", params, on_success=self._on_loaded, on_error=self._on_load_error)

    def _on_loaded(self, page: dict) -> None:
        self.refreshButton.setEnabled(True)
        selected_id = self.current["id"] if self.current else None
        self.current = None
        self.users = page["items"]
        self.pager.set_page(page)
        self.editorFrame.hide()
        fill_table(self.table, [
            [
                full_name(user),
                user["email"],
                _role_title(user["role"]),
                user["phone"] or "–",
                "Aktív" if user["is_active"] else "Inaktív",
            ]
            for user in self.users
        ])
        self.show_message(self._notice or f"{page['total']} felhasználó felel meg a szűrésnek.")
        self._notice = None
        select_by_id(self.table, self.users, selected_id)

    def _on_load_error(self, error: ApiError) -> None:
        self.refreshButton.setEnabled(True)
        self.show_message(error.message, error=True)

    def _on_selection_changed(self) -> None:
        row = selected_row(self.table)
        if 0 <= row < len(self.users):
            self._open_editor(self.users[row])

    # --- Editor ---

    def _open_editor(self, user: dict | None) -> None:
        if user is None and not self.can_load():
            return
        self.current = user
        creating = user is None
        if creating:
            self.table.clearSelection()
        values = user or {}
        self.editorTitle.setText("Új felhasználó" if creating else full_name(user))
        for field, edit in self.textFields.items():
            edit.setText(values.get(field) or "")
        self.roleCombo.setCurrentIndex(self.roleCombo.findData(values.get("role", "courier")))
        self.passwordEdit.clear()
        self.passwordEdit.setPlaceholderText(
            f"Legalább {MIN_PASSWORD_LENGTH} karakter" if creating else "Üresen hagyva nem változik"
        )
        # The server rejects these for the admin's own account
        is_self = not creating and user["id"] == api.user_id
        self.roleCombo.setEnabled(not is_self)
        self.activeButton.setVisible(not creating)
        if not creating:
            self.activeButton.setText("Inaktiválás" if user["is_active"] else "Újraaktiválás")
            self.activeButton.setEnabled(not is_self)
        set_message(
            self.editorMessage,
            "A saját szerepköröd és állapotod nem módosíthatod." if is_self else "",
        )
        self.editorFrame.setEnabled(True)
        self.editorFrame.show()
        self.textFields["last_name"].setFocus()

    def _close_editor(self) -> None:
        self.current = None
        self.table.clearSelection()
        self.editorFrame.hide()

    def _form_values(self) -> dict:
        values = {field: text_or_none(edit) for field, edit in self.textFields.items()}
        values["role"] = self.roleCombo.currentData()
        return values

    def _check_form(self, values: dict, password: str) -> str | None:
        missing = [label for field, label in REQUIRED_FIELDS.items() if not values[field]]
        if missing:
            return "Kötelező mező: " + ", ".join(missing)
        address = [values[field] for field in ADDRESS_FIELDS]
        if any(address) and not all(address):
            return "A cím mezőit együtt kell kitölteni, vagy mindet üresen hagyni."
        if (self.current is None or password) and len(password) < MIN_PASSWORD_LENGTH:
            return f"A jelszó legalább {MIN_PASSWORD_LENGTH} karakter legyen."
        return None

    def save(self) -> None:
        values = self._form_values()
        password = self.passwordEdit.text()
        problem = self._check_form(values, password)
        if problem is not None:
            set_message(self.editorMessage, problem, error=True)
            return

        if self.current is None:
            body = {field: value for field, value in values.items() if value is not None}
            body["password"] = password
            self._send(api.post, "/users", body, "létrehozva")
            return

        # Only the changed fields, the address always as a whole
        body = {field: value for field, value in values.items() if value != self.current.get(field)}
        if any(field in body for field in ADDRESS_FIELDS):
            body.update({field: values[field] for field in ADDRESS_FIELDS})
        if password:
            body["password"] = password
        if not body:
            set_message(self.editorMessage, "Nincs módosítás.")
            return
        self._send(api.patch, f"/users/{self.current['id']}", body, "elmentve")

    def _send(self, method, path: str, body: dict, done: str) -> None:
        self.editorFrame.setEnabled(False)
        set_message(self.editorMessage, "Mentés...")
        run_in_background(
            method, path, body,
            on_success=lambda user: self._on_saved(user, done),
            on_error=self._on_editor_error,
        )

    def _on_saved(self, user: dict, done: str) -> None:
        self.current = user
        self._notice = f"{full_name(user)} adatai {done}."
        self.refresh()

    def toggle_active(self) -> None:
        user = self.current
        if user is None:
            return
        name = full_name(user)
        if user["is_active"]:
            if not confirm(
                self, "Felhasználó inaktiválása",
                f"{name} ezután nem tud bejelentkezni. Az adatai megmaradnak, és később újraaktiválható.",
                "Inaktiválás",
            ):
                return
            call, done = (api.delete, f"/users/{user['id']}"), "inaktiválva"
        else:
            call, done = (api.patch, f"/users/{user['id']}", {"is_active": True}), "újraaktiválva"
        self.editorFrame.setEnabled(False)
        run_in_background(*call, on_success=lambda _: self._on_state_changed(name, done),
                          on_error=self._on_editor_error)

    def _on_state_changed(self, name: str, done: str) -> None:
        self._notice = f"{name} {done}."
        self.refresh()

    def _on_editor_error(self, error: ApiError) -> None:
        self.editorFrame.setEnabled(True)
        set_message(self.editorMessage, error.message, error=True)
