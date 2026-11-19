
from datetime import date

from qfluentwidgets import (
    LineEdit,
    PrimaryPushButton,
    TableWidget,
    TransparentPushButton,
    PushButton,
    MessageBoxBase,
    SubtitleLabel,
    ComboBox
)

from PySide6.QtGui import QIcon

from PySide6.QtCore import QDate, QSize, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QDateEdit,
    QPushButton,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    
)

from api_client import STATUS_LABELS, TIME_SLOTS, ApiError, api, run_in_background

REFRESH_ICON_PATH = ":/icons/test-refresh.svg"
PICKUP_ICON_PATH = ":/icons/test-pickup.svg"
DELIVERY_ICON_PATH = ":/icons/test-delivery.svg"
WAREHOUSE_ICON_PATH = ":/icons/test-warehouse.svg"




class CourierAssignModal(MessageBoxBase):

    def __init__(self, parent=None, title: str = "Futár", parcel: dict | None = None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel(title)
        
        self.yesButton.setText("Hozzárendel")        
        self.cancelButton.setText("Mégsem")
        self.yesButton.setEnabled(False)
        
        self.courierBox = ComboBox()
        # Set placeholder text
        self.courierBox.setPlaceholderText("Válassz futárt...")

        # Add options
        run_in_background(
            api.get,
            "/warehouse/couriers",
            on_success=self._on_get_couriers_success,
            on_error=self._on_get_couriers_error,
        )

        # Signal of current option index change
        self.courierBox.currentIndexChanged.connect(
            lambda index: self.yesButton.setEnabled(index != -1)
        )


        # Add components to the layout
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.courierBox)

        self.deliveryDate: QDateEdit | None = None
        self.deliverySlot: ComboBox | None = None
        if parcel is not None:
            pickup_date = QDate.fromString(parcel["pickup_date"], "yyyy-MM-dd")
            minimum_date = max(QDate.currentDate(), pickup_date)

            self.deliveryDate = QDateEdit(self)
            self.deliveryDate.setCalendarPopup(True)
            self.deliveryDate.setDisplayFormat("yyyy-MM-dd")
            self.deliveryDate.setMinimumDate(minimum_date)

            delivery_date = QDate.fromString(
                parcel["delivery_date"] or "",
                "yyyy-MM-dd",
            )
            self.deliveryDate.setDate(
                delivery_date
                if delivery_date.isValid() and delivery_date >= minimum_date
                else minimum_date
            )
            self.viewLayout.addWidget(QLabel("Kiszállítás napja", self))
            self.viewLayout.addWidget(self.deliveryDate)

            self.deliverySlot = ComboBox(self)
            self.deliverySlot.addItems(TIME_SLOTS)
            start = parcel["delivery_window_start"]
            end = parcel["delivery_window_end"]
            if start is not None and end is not None:
                slot_index = self.deliverySlot.findText(f"{start[:5]}-{end[:5]}")
                if slot_index >= 0:
                    self.deliverySlot.setCurrentIndex(slot_index)
            self.viewLayout.addWidget(QLabel("Kiszállítási idősáv", self))
            self.viewLayout.addWidget(self.deliverySlot)

        # Set the minimum width of the dialog box
        self.widget.setMinimumWidth(350)
    
    def _on_get_couriers_success(self, result : object) -> None:
        for courier in result:
            self.courierBox.addItem(f"{courier["first_name"]} {courier["last_name"]}", userData=courier["id"])
        # Deselect
        self.courierBox.setCurrentIndex(-1)
        self.yesButton.setEnabled(False);
            
    def _on_get_couriers_error(error) -> None:
        error


def showCourierAssignModal(window) -> int:
    dialog = CourierAssignModal(window)
    if dialog.exec():
        return dialog.courierBox.currentData()
    else:
        return -1


def showDeliveryAssignModal(window, parcel: dict) -> dict | None:
    dialog = CourierAssignModal(window, parcel=parcel)
    if not dialog.exec():
        return None
    if dialog.deliveryDate is None or dialog.deliverySlot is None:
        raise RuntimeError("A kiszállítási időpont mezői nem jöttek létre.")
    return {
        "courier_id": dialog.courierBox.currentData(),
        "delivery_date": dialog.deliveryDate.date().toString("yyyy-MM-dd"),
        "delivery_slot": dialog.deliverySlot.currentText(),
    }





class LogisticianInterface(QFrame):
    

    def __init__(self, text: str, parent=None):
        super().__init__(parent=parent)

        self.setObjectName(text.replace(" ", "-"))
        
        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setContentsMargins(10, 10, 10, 10)
        self.vBoxLayout.setSpacing(0)
        
        self.table = TableWidget(self)

        # Enable border and set rounded corners
        self.table.setBorderVisible(True)
        self.table.setBorderRadius(8)

        self.table.setWordWrap(False)
        self.table.setColumnCount(17)

        # Set horizontal header and hide vertical header
        self.table.setHorizontalHeaderLabels(
            ['Id',
             'Nyomkövetési szám',
             'Méret',
             'Felvételi dátum',
             'Felvételi idő (k)',
             'Felvételi idő (v)',
             'Kézbesítési dátum',
             'Kézbesítési idő (k)',
             'Kézbesítési idő (v)',
             'Felvevő futár (id)',
             'Felvéve (dátum)',
             'Raktárba (dátum)',
             'Kiszállító futár (id)',
             'Kiszállítás k. (dátum)',
             'Kiszállítva (dátum)',
             'Státusz',
             'Műveletek'])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(16, QHeaderView.Fixed)
        self.table.setColumnWidth(16, 340)
        
        self.table.verticalHeader().hide()
        
        filterLayout = QHBoxLayout()
        self.searchEdit = LineEdit(self)
        self.searchEdit.setPlaceholderText("Csomagszám, feladó vagy címzett neve")
        self.searchEdit.setClearButtonEnabled(True)
        self.searchEdit.returnPressed.connect(self._apply_filters)
        filterLayout.addWidget(self.searchEdit, 2)

        filterLayout.addWidget(QLabel("Csomag állapota:"))
        self.statusFilter = QComboBox(self)
        self.statusFilter.addItem("Minden állapot", None)
        for status, label in STATUS_LABELS.items():
            self.statusFilter.addItem(label, status)
        filterLayout.addWidget(self.statusFilter)

        self.courierFilter = QComboBox(self)
        self.courierFilter.addItem("Minden futár", None)
        filterLayout.addWidget(self.courierFilter)

        self.filterButton = QPushButton("Szűrés", self)
        self.filterButton.setObjectName("applyFilters")
        self.filterButton.clicked.connect(self._apply_filters)
        filterLayout.addWidget(self.filterButton)

        self.refreshButton = QPushButton(QIcon(":/icons/refresh-cw.svg"), "Frissítés", self)
        self.refreshButton.setObjectName("refreshParcels")
        self.refreshButton.setIconSize(QSize(16, 16))
        self.refreshButton.setStyleSheet(
            "background-color: #2383E2; color: white; font-weight: bold;"
        )
        self.refreshButton.clicked.connect(
            lambda _checked=False: self.getParcels()
        )
        filterLayout.addWidget(self.refreshButton)
        filterLayout.addStretch()
        self.vBoxLayout.addLayout(filterLayout)

        self.vBoxLayout.addWidget(self.table)

        self.parcels_by_tracking_number: dict[str, dict] = {}
        self.getCouriers()
        self.getParcels()

    def _apply_filters(self, _checked: bool = False) -> None:
        self.getParcels()

    def getCouriers(self) -> None:
        run_in_background(
            api.get,
            "/warehouse/couriers",
            on_success=self._on_get_couriers_success,
            on_error=self._on_get_couriers_error,
        )

    def _on_get_couriers_success(self, couriers: list[dict]) -> None:
        selected_id = self.courierFilter.currentData()
        self.courierFilter.clear()
        self.courierFilter.addItem("Minden futár", None)
        for courier in couriers:
            self.courierFilter.addItem(
                f"{courier['first_name']} {courier['last_name']}",
                courier["id"],
            )
        self.courierFilter.setCurrentIndex(
            max(self.courierFilter.findData(selected_id), 0)
        )

    def _on_get_couriers_error(self, error: ApiError) -> None:
        print(error)

    def getParcels(self) -> None:
        run_in_background(
            api.get,
            "/parcels",
            params={
                "limit": 100,
                "offset": 0,
                "search": self.searchEdit.text().strip() or None,
                "status": self.statusFilter.currentData(),
                "courier_id": self.courierFilter.currentData(),
            },
            on_success=self._on_get_parcels_success,
            on_error=self._on_get_parcels_error,
        )

    def _on_get_parcels_success(self, result: object) -> None:
        items = result["items"]
        self.parcels_by_tracking_number = {
            item["tracking_number"]: item for item in items
        }
        
        self.table.setRowCount(0)
        self.table.setRowCount(len(items))

        for i, item in enumerate(items):
            self._set_table_item(i, 0, item["id"])
            self._set_table_item(i, 1, item["tracking_number"])
            self._set_table_item(i, 2, item["size"])
            
            self._set_table_item(i, 3, item["pickup_date"])
            self._set_table_item(i, 4, item["pickup_window_start"])
            self._set_table_item(i, 5, item["pickup_window_end"])
            
            self._set_table_item(i, 6, item["delivery_date"])
            self._set_table_item(i, 7, item["delivery_window_start"])
            self._set_table_item(i, 8, item["delivery_window_end"])
            
            self._set_table_item(
                i, 9, item["pickup_courier"]["id"] if item["pickup_courier"] is not None else None
            )
            self._set_table_item(i, 10, item["picked_up_at"])
            
            self._set_table_item(i, 11, item["warehouse_arrived_at"])
            
            self._set_table_item(
                i, 12, item["delivery_courier"]["id"] if item["delivery_courier"] is not None else None
            )
            self._set_table_item(i, 13, item["out_for_delivery_at"])
            self._set_table_item(i, 14, item["delivered_at"])


            self._set_table_item(i, 15, item["status"])
            
            
            
            #Műveletek
            widget = QWidget(self.table)
            layout = QHBoxLayout(widget)
            layout.setContentsMargins(2, 2, 2, 2)
            layout.setSpacing(6)

            pickupButton = QPushButton(QIcon(":/icons/package-plus.svg"), "Felvesz")
            pickupButton.setObjectName("pickup")
            pickupButton.setIconSize(QSize(16, 16))
            pickupButton.setStyleSheet(
                "background-color: #2E7D32; color: white; font-weight: bold;"
            )
            
            deliverButton = QPushButton(QIcon(":/icons/van.svg"), "Kiszállít")
            deliverButton.setObjectName("deliver")
            deliverButton.setIconSize(QSize(16, 16))
            deliverButton.setStyleSheet(
                "background-color: #1565C0; color: white; font-weight: bold;"
            )
            
            warehouseButton = QPushButton(QIcon(":/icons/warehouse.svg"), "Raktárba")
            warehouseButton.setObjectName("warehouse")
            warehouseButton.setIconSize(QSize(16, 16))
            warehouseButton.setStyleSheet(
                "background-color: #607D8B; color: white; font-weight: bold;"
            )


            #Raktárban
            warehouseButton.clicked.connect(
                lambda checked=False, tracking_number=item["tracking_number"], stat=item["status"], row=i:
                    self.warehouseParcel(tracking_number, stat, row)
            )
            warehouseButton.setEnabled(STATUS_LABELS[item["status"]] == STATUS_LABELS["picked_up"])

            #Kiszállítás
            deliverButton.clicked.connect(
                lambda checked=False, tracking_number=item["tracking_number"], row=i:
                    self.deliverParcel(tracking_number, row)
            )
            
            deliverButton.setEnabled(self._can_assign_delivery(item))

            
            #Felvétel
            pickupButton.clicked.connect(
                lambda checked=False, tracking_number=item["tracking_number"], row=i:
                    self.pickupParcel(tracking_number, row)
            )
            pickupButton.setEnabled(self._can_assign_pickup(item))

            
            
            layout.addWidget(pickupButton, 1)
            layout.addWidget(deliverButton, 1)
            layout.addWidget(warehouseButton, 1)

            self.table.setCellWidget(i, 16, widget)
            self.table.setRowHeight(i, max(self.table.rowHeight(i), widget.sizeHint().height() + 4))

    @staticmethod
    def _can_assign_pickup(parcel: dict) -> bool:
        return parcel["status"] == "booked" or (
            parcel["status"] == "pickup_assigned"
            and date.today() < date.fromisoformat(parcel["pickup_date"])
        )

    @staticmethod
    def _can_assign_delivery(parcel: dict) -> bool:
        return parcel["status"] == "in_warehouse" or (
            parcel["status"] == "delivery_assigned"
            and parcel["delivery_date"] is not None
            and date.today() < date.fromisoformat(parcel["delivery_date"])
        )

    def _set_table_item(self, row: int, column: int, value: object) -> None:
        text = "" if value is None else str(value)
        self.table.setItem(row, column, QTableWidgetItem(text))

        
    def _on_get_parcels_error(self, error: ApiError) -> None:
        print(error)
            
            
    def warehouseParcel(self, tracking_number: str, parcel_status: str, row: int):
        if STATUS_LABELS[parcel_status] is not STATUS_LABELS["picked_up"]:
            return;
        run_in_background(
            api.post,
            "/warehouse/check-in",
            json={
                "tracking_numbers": [tracking_number]
            },
            on_success=lambda result: self._on_check_in_success(result, row),
            on_error=self._on_check_in_success_error,
        )
        
    def _on_check_in_success(self, result: object, row: int) -> None:
        self._update_parcel_row(result[0], row)
        
    def _on_check_in_success_error(self, error: ApiError) -> None:
        print(error)
    
    



    def deliverParcel(self, tracking_number: str, row: int) -> None:
        parcel = self.parcels_by_tracking_number[tracking_number]
        if not self._can_assign_delivery(parcel):
            return

        assignment = showDeliveryAssignModal(self.window(), parcel)
        if assignment is None:
            return

        run_in_background(
            api.post,
            "/warehouse/assign-delivery",
            json={
                **assignment,
                "tracking_numbers": [tracking_number],
            },
            on_success=lambda result: self._on_assign_delivery_success(result, row),
            on_error=self._on_assign_delivery_error,
        )

    def _on_assign_delivery_success(self, result: object, row: int) -> None:
        self._update_parcel_row(result[0], row)

    def _on_assign_delivery_error(self, error: ApiError) -> None:
        print(error)

    def pickupParcel(self, tracking_number: str, row: int) -> None:
        parcel = self.parcels_by_tracking_number[tracking_number]
        if not self._can_assign_pickup(parcel):
            return
        
        courier_id = showCourierAssignModal(self.window())
        if courier_id == -1:
            return
        
        run_in_background(
            api.post,
            "/warehouse/assign-pickup",
            json={
                "courier_id" : courier_id,
                "tracking_numbers": [tracking_number]
                },
            on_success=lambda result: self._on_assign_pickup_success(result, row),
            on_error=self._on_assign_pickup_error
                                
            )
    def _on_assign_pickup_success(self, result: object, row: int) -> None:
        self._update_parcel_row(result[0], row)
                
    def _on_assign_pickup_error(self, error: ApiError) -> None:
        print(error)
        
        
        
    def _update_parcel_row(self, item, row) -> None:
        self.parcels_by_tracking_number[item["tracking_number"]] = item
        self._set_table_item(row, 3, item["pickup_date"])
        self._set_table_item(row, 4, item["pickup_window_start"])
        self._set_table_item(row, 5, item["pickup_window_end"])
        self._set_table_item(row, 6, item["delivery_date"])
        self._set_table_item(row, 7, item["delivery_window_start"])
        self._set_table_item(row, 8, item["delivery_window_end"])

        self._set_table_item(
            row, 9,
            item["pickup_courier"]["id"] if item["pickup_courier"] is not None else None
        )

        self._set_table_item(row, 10, item["picked_up_at"])
        self._set_table_item(row, 11, item["warehouse_arrived_at"])

        self._set_table_item(
            row, 12,
            item["delivery_courier"]["id"] if item["delivery_courier"] is not None else None
        )

        self._set_table_item(row, 13, item["out_for_delivery_at"])
        self._set_table_item(row, 14, item["delivered_at"])
        self._set_table_item(row, 15, item["status"])

        actions = self.table.cellWidget(row, 16)
        actions.findChild(PushButton, "pickup").setEnabled(
            self._can_assign_pickup(item)
        )
        actions.findChild(PushButton, "deliver").setEnabled(
            self._can_assign_delivery(item)
        )
        actions.findChild(PushButton, "warehouse").setEnabled(
            item["status"] == "picked_up"
        )
