from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from api_client import api, ROLE, ROLE_LABELS, run_in_background
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import (
    InfoBar, InfoBarPosition, NavigationAvatarWidget, NavigationItemPosition,
    FluentWindow,
)
from .admin.parcels_interface import ParcelsInterface
from .admin.statistics_interface import StatisticsInterface
from .admin.users_interface import UsersInterface
from .admin.warehouse_settings_interface import WarehouseSettingsInterface
from .auth.auth_interface import AuthInterface
from .customer.booking_interface import BookingInterface
from .customer.history_interface import ShipHistoryInterface
from .customer.shipments_interface import ShipmentsInterface
from .customer.tracking_interface import TrackingInterface

from .courier.management_interface import ManagementInterface
from .courier.history_interface import DeliveryHistoryInterface
from .courier.tasks_interface import TasksInterface
from .common.profile_dialog import ProfileDialog
from .logistician.assignments_interface import LogisticianInterface

APP_TITLE = "Csomagkezelő"
APP_ICON = Path(__file__).resolve().parents[1] / "resources" / "truck-icon.png"


class Window(FluentWindow):
    """ Main Interface """

    def __init__(self):
        super().__init__()
        self.subInterfaces = []
        self.authInterface = None
        self.account: dict | None = None
        self.sessionRole: str | None = None
        self.sessionTimer = QTimer(self)
        self.sessionTimer.setInterval(5000)
        self.sessionTimer.timeout.connect(self._check_session)
        self.expiredNotice = None
        self.profileDialog = None
        api.events.session_expired.connect(self._on_session_expired)

        #self.shipmentsInterface = ShipmentsInterface("Shipments Interface", self)
        #self.historyInterface = HistoryInterface("History Interface", self)

        self.initWindow()
        self.initNavigation()

    def initNavigation(self):
        self.navigationInterface.removeWidget("logout")
        self.navigationInterface.removeWidget("account")
        self.authInterface = None
        #clear sub-interfaces before
        self.removeInterfaces()
        if api.role == ROLE.QUEST.value:
            self.initQuest()
        elif api.role == ROLE.CUSTOMER.value:
            self.initCustomer()
        elif api.role == ROLE.COURIER.value:
            self.initCourier()
        elif api.role == ROLE.LOGISTICIAN.value:
            self.initLogistician()
        elif api.role == ROLE.ADMIN.value:
            self.initAdmin()
            
        if api.is_logged_in:
            self.navigationInterface.addWidget(
                routeKey="account",
                widget=NavigationAvatarWidget(self._account_text()),
                onClick=self._show_account,
                position=NavigationItemPosition.BOTTOM,
                tooltip="Saját fiók: személyes adatok, jelszó",
            )
            logout_item = self.navigationInterface.addItem(
                routeKey="logout",
                icon=QIcon(":/icons/log-out.svg"),
                text="Kijelentkezés",
                onClick=self.logout,
                selectable=True,
                position=NavigationItemPosition.BOTTOM,
                tooltip="Kijelentkezés",
            )
            logout_item.setTextColor("#ff0000", "#ff0000")

        fresh_login = api.is_logged_in and self.sessionRole is None
        self.sessionRole = api.role if api.is_logged_in else None
        if api.is_logged_in:
            self.sessionTimer.start()
            if fresh_login:
                self._close_expired_notice()
                self._load_account()
        else:
            self.sessionTimer.stop()
            self.account = None
            self.setWindowTitle(APP_TITLE)

    #Vendég
    def initQuest(self):
        
        #Trackin Interface
        trackingInterface = TrackingInterface('Tracking Interface', self)
        self.addSubInterface(trackingInterface, QIcon(":/icons/package-search.svg"), 'Nyomkövetés')
        self.subInterfaces.append(trackingInterface)
        
        #Booking Interface
        bookingInterface = BookingInterface("Booking Interface",self)
        self.addSubInterface(bookingInterface,  QIcon(":/icons/package.svg"), "Csomagfeladás", NavigationItemPosition.TOP)
        self.subInterfaces.append(bookingInterface)
        
        #Auth Interface
        authInterface = AuthInterface(self)
        self.addSubInterface(authInterface,  QIcon(":/icons/auth.svg"), 'Bejelentkezés', NavigationItemPosition.BOTTOM)
        self.subInterfaces.append(authInterface)
        self.authInterface = authInterface
 
    #Ügyfél
    def initCustomer(self):
        
         #Trackin Interface
        trackingInterface = TrackingInterface('Tracking Interface', self)
        self.addSubInterface(trackingInterface, QIcon(":/icons/package-search.svg"), 'Nyomkövetés')
        self.subInterfaces.append(trackingInterface)
                
        #Booking Interface
        bookingInterface = BookingInterface("Booking Interface",self)
        self.addSubInterface(bookingInterface,  QIcon(":/icons/package.svg"), "Csomagfeladás", NavigationItemPosition.TOP)
        self.subInterfaces.append(bookingInterface)
        
        #Ship Interface
        shipmentsInterface = ShipmentsInterface("Shipments Interface", self)
        self.addSubInterface(shipmentsInterface, QIcon(":/icons/package-open.svg"), "Aktuális csomagok", NavigationItemPosition.TOP)
        self.subInterfaces.append(shipmentsInterface)
        
        #History Interface
        shipHistoryInterface = ShipHistoryInterface("Ship History Interface", self)
        self.addSubInterface(shipHistoryInterface, QIcon(":/icons/rotate-ccw-clock.svg"), "Előzmények", NavigationItemPosition.TOP)
        self.subInterfaces.append(shipHistoryInterface)


        
        
    #Futár
    def initCourier(self):

        #Tasks Interface: assigned and picked up parcels
        tasksInterface = TasksInterface("Courier Tasks", self)
        self.addSubInterface(tasksInterface, QIcon(":/icons/package-open.svg"), "Feladataim", NavigationItemPosition.TOP)
        self.subInterfaces.append(tasksInterface)

        #Managment Interface
        managementInterface = ManagementInterface("Managment Interface", self)
        self.addSubInterface(managementInterface, QIcon(":/icons/boxes-linked.svg"), "Csomagkezelés", NavigationItemPosition.TOP)
        self.subInterfaces.append(managementInterface)
                
        #Delivery History Interface
        deliveryHistoryInterface = DeliveryHistoryInterface("Delivery History Interface", self)
        self.addSubInterface(deliveryHistoryInterface, QIcon(":/icons/rotate-ccw-clock.svg"), "Előzmények", NavigationItemPosition.TOP)
        self.subInterfaces.append(deliveryHistoryInterface)

        #Trackin Interface: any parcel by its tracking number, like a guest
        trackingInterface = TrackingInterface('Tracking Interface', self)
        self.addSubInterface(trackingInterface, QIcon(":/icons/package-search.svg"), 'Nyomkövetés')
        self.subInterfaces.append(trackingInterface)
        
    def initLogistician(self):
        logisticianInterface = LogisticianInterface("Logistician Interface", self)
        self.addSubInterface(logisticianInterface, QIcon(":/icons/boxes-linked.svg"), "Logisztika", NavigationItemPosition.TOP)
        self.subInterfaces.append(logisticianInterface)
        
                
    #Admin
    def initAdmin(self):
        
        #Users Interface
        usersInterface = UsersInterface("Admin Users", self)
        self.addSubInterface(usersInterface,  QIcon(":/icons/users-round.svg"), "Felhasználók", NavigationItemPosition.TOP)
        self.subInterfaces.append(usersInterface)
        
        #Parcels Interface
        parcelsInterface = ParcelsInterface("Admin Parcels", self)
        self.addSubInterface(parcelsInterface, QIcon(":/icons/package.svg"), "Csomagok", NavigationItemPosition.TOP)
        self.subInterfaces.append(parcelsInterface)

        #Logistics: the admin reaches every logistician function too (F-21)
        logisticianInterface = LogisticianInterface("Logistician Interface", self)
        self.addSubInterface(logisticianInterface, QIcon(":/icons/boxes-linked.svg"), "Logisztika", NavigationItemPosition.TOP)
        self.subInterfaces.append(logisticianInterface)

        #Statistics Interface
        statisticsInterface = StatisticsInterface("Admin Statistics", self)
        self.addSubInterface(statisticsInterface, QIcon(":/icons/stat.svg"), "Statisztikák", NavigationItemPosition.TOP)
        self.subInterfaces.append(statisticsInterface)
        
        #Warehouse Interface
        warehouseInterface = WarehouseSettingsInterface("Admin Warehouse", self)
        self.addSubInterface(warehouseInterface, QIcon(":/icons/warehouse.svg"), "Raktár", NavigationItemPosition.TOP)
        self.subInterfaces.append(warehouseInterface)
        
        #Trackin Interface
        trackingInterface = TrackingInterface('Tracking Interface', self)
        self.addSubInterface(trackingInterface, QIcon(":/icons/package-search.svg"), 'Nyomkövetés')
        self.subInterfaces.append(trackingInterface)
        
    def initWindow(self):
        #self.resize(900, 700)
        self.setWindowIcon(QIcon(str(APP_ICON)))
        self.setWindowTitle(APP_TITLE)
    
    def removeInterfaces(self):
        if self.subInterfaces:
            self.stackedWidget.currentChanged.disconnect(
                self._onCurrentInterfaceChanged
            )

        for interface in reversed(self.subInterfaces):
            self.removeInterface(interface, isDelete=True)
            interface.setObjectName(f"{interface.objectName()}-removed")
            
        self.subInterfaces.clear()
        
    def logout(self):
        api.logout();
        self.initNavigation();
        self._notify(InfoBar.info, "Kijelentkeztél", "Sikeresen kijelentkeztél.", 3000)

    # --- Session ---

    def _role_title(self) -> str:
        return ROLE_LABELS.get(api.role, {}).get("title", "")

    def _account_text(self) -> str:
        if self.account is None:
            return self._role_title()
        return f"{self.account['last_name']} {self.account['first_name']} ({self._role_title()})"

    def _account_item(self) -> NavigationAvatarWidget | None:
        item = self.navigationInterface.panel.items.get("account")
        return item.widget if item is not None else None

    def _load_account(self):
        user_id = api.user_id
        run_in_background(
            api.get, "/users/me",
            on_success=lambda user: self._on_account_loaded(user_id, user),
            on_error=lambda error: self._welcome(user_id),
        )

    def _on_account_loaded(self, user_id: int, user: dict):
        if api.user_id != user_id:
            return
        self.account = user
        account_item = self._account_item()
        if account_item is not None:
            account_item.setName(self._account_text())
        self.setWindowTitle(f"{APP_TITLE} – {self._account_text()}")
        self._welcome(user_id)

    def _welcome(self, user_id: int):
        if api.user_id != user_id:
            return
        name = f"{self.account['last_name']} {self.account['first_name']}" if self.account else None
        greeting = f"Üdv, {name}! " if name else ""
        self._notify(InfoBar.success, "Sikeres bejelentkezés", f"{greeting}Szerepkör: {self._role_title()}", 4000)

    def _show_account(self):
        dialog = ProfileDialog(self.account, self)
        dialog.profileSaved.connect(self._on_profile_saved)
        dialog.passwordChanged.connect(self._on_password_changed)
        # Kept so that an expiring session can close it (_on_session_expired)
        self.profileDialog = dialog
        try:
            dialog.exec()
        finally:
            self.profileDialog = None
            dialog.deleteLater()

    def _on_profile_saved(self, user: dict):
        old_email = self.account["email"] if self.account else None
        self.account = user
        account_item = self._account_item()
        if account_item is not None:
            account_item.setName(self._account_text())
        self.setWindowTitle(f"{APP_TITLE} – {self._account_text()}")
        text = "Az adataidat elmentettük."
        if old_email is not None and user["email"].lower() != old_email.lower():
            text += f" Legközelebb az új email címmel jelentkezz be: {user['email']}"
        self._notify(InfoBar.success, "Sikeres mentés", text, 5000)

    def _on_password_changed(self):
        self._notify(InfoBar.success, "Jelszó módosítva",
                     "Legközelebb már az új jelszóval jelentkezz be.", 5000)

    def _check_session(self):
        seconds_left = api.session_seconds_left
        if seconds_left is not None and seconds_left <= 0:
            self._on_session_expired()

    def _on_session_expired(self):
        if self.sessionRole is None:
            return
        if self.profileDialog is not None:
            self.profileDialog.reject()
        api.logout()
        self.initNavigation()
        if self.authInterface is not None:
            self.switchTo(self.authInterface)
        self.expiredNotice = self._notify(InfoBar.warning, "Lejárt a munkamenet",
                                          "Biztonsági okból kijelentkeztettünk. Jelentkezz be újra a folytatáshoz.", -1)

    def _close_expired_notice(self):
        notice, self.expiredNotice = self.expiredNotice, None
        if notice is not None:
            try:
                notice.close()
            except RuntimeError:
                pass  # already closed by the user

    def _notify(self, show, title: str, content: str, duration: int):
        return show(title=title, content=content, isClosable=True, position=InfoBarPosition.TOP_RIGHT,
                    duration=duration, parent=self)