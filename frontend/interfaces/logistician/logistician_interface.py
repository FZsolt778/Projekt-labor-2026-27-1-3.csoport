
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

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    
)

from api_client import STATUS_LABELS, ApiError, api, run_in_background




class CourierAssignModal(MessageBoxBase):

    def __init__(self, parent=None, title : str = "Futár"):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel(title)
        
        self.yesButton.setText("Hozzárendel")        
        self.cancelButton.setText("Mégsem")
        
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
        self.courierBox.currentIndexChanged.connect(lambda index: self.yesButton.setEnabled(True) if index is not -1 else self.yesButton.setEnabled(False))


        # Add components to the layout
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.courierBox)

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
        return dialog.courierBox.currentData();
    else:
        return -1





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
        filterLayout.addWidget(QLabel("Csomag állapota:"))
        self.statusFilter = QComboBox(self)
        self.statusFilter.addItem("Összes", None)
        for status, label in STATUS_LABELS.items():
            self.statusFilter.addItem(label, status)
        self.statusFilter.currentIndexChanged.connect(self._on_status_filter_changed)
        filterLayout.addWidget(self.statusFilter)
        filterLayout.addStretch()
        self.vBoxLayout.addLayout(filterLayout)

        self.vBoxLayout.addWidget(self.table)

        self.getParcels()
        
    def getParcels(self, status: str | None = None):
        run_in_background(
            api.get,
            "/parcels",
            params={"limit": 100, "offset": 0, "status": status},
            on_success=self._on_get_parcels_success,
            on_error=self._on_get_parcels_error,
        )

    def _on_status_filter_changed(self, _index: int) -> None:
        self.getParcels(self.statusFilter.currentData())

    def _on_get_parcels_success(self, result: object) -> None:
        items = result["items"]
        
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

            pickupButton = PushButton(QIcon(":/icons/package-plus.svg"), "Felvesz")
            pickupButton.setObjectName("pickup")
            
            deliverButton = PushButton("Kiszállít")
            deliverButton.setObjectName("deliver")
            
            warehouseButton = PushButton("Raktárba")
            warehouseButton.setObjectName("warehouse")


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
            
            deliverButton.setEnabled(STATUS_LABELS[item["status"]] == STATUS_LABELS["in_warehouse"])

            
            #Felvétel
            pickupButton.clicked.connect(
                lambda checked=False, tracking_number=item["tracking_number"], stat=item["status"], row=i:
                    self.pickupParcel(tracking_number, stat, row)
            )
            pickupButton.setEnabled(STATUS_LABELS[item["status"]] == STATUS_LABELS["booked"])

            
            
            layout.addWidget(pickupButton)
            layout.addWidget(deliverButton)
            layout.addWidget(warehouseButton)

            self.table.setCellWidget(i, 16, widget)
            self.table.setRowHeight(i, max(self.table.rowHeight(i), widget.sizeHint().height() + 4))

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
        self.table.cellWidget(row, 16).findChild(PushButton, "warehouse").setEnabled(False)
        self.table.cellWidget(row, 16).findChild(PushButton, "deliver").setEnabled(True)
        
    def _on_check_in_success_error(self, error: ApiError) -> None:
        print(error)
    
    



    def deliverParcel(self, tracking_number: str, row: int):
        courier_id : int = showCourierAssignModal(self.window());
        if courier_id == -1:
            return
        
        run_in_background(
            api.post,
            "/warehouse/assign-delivery",
            json={
                "courier_id" : courier_id,
                "tracking_numbers": [tracking_number]
            },
            on_success=lambda result: self._on_assign_delivery_success(result, row),
            on_error=self._on_assign_delivery_error
                        
        )
    def _on_assign_delivery_success(self, result : object, row : int) -> None:
        self._update_parcel_row(result[0], row)
        self.table.cellWidget(row, 16).findChild(PushButton, "deliver").setEnabled(False)
        
    def _on_assign_delivery_error(self, error: ApiError) -> None:
        print(error)

    
            
            
            
            
    def pickupParcel(self, tracking_number: str, status: str, row: int):
        if STATUS_LABELS[status] is not STATUS_LABELS["booked"]:
            return
        
        courier_id : int = showCourierAssignModal(self.window());
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
    def _on_assign_pickup_success(self, result : object, row : int) -> None:
            self._update_parcel_row(result[0], row)
            self.table.cellWidget(row, 16).findChild(PushButton, "pickup").setEnabled(False)
                
    def _on_assign_pickup_error(self, error: ApiError) -> None:
        print(error)
        
        
        
    def _update_parcel_row(self, item, row) -> None:

        
        #self._set_table_item(row, 0, item["id"])
        #self._set_table_item(row, 1, item["tracking_number"])
        #self._set_table_item(row, 2, item["size"])

        #self._set_table_item(row, 3, item["pickup_date"])
        #self._set_table_item(row, 4, item["pickup_window_start"])
        #self._set_table_item(row, 5, item["pickup_window_end"])

        #self._set_table_item(row, 6, item["delivery_date"])
        #self._set_table_item(row, 7, item["delivery_window_start"])
        #self._set_table_item(row, 8, item["delivery_window_end"])

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
