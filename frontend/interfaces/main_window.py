from PySide6.QtGui import QIcon
from api_client import api, ROLE
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import NavigationItemPosition, FluentWindow
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

from .logistician.logistician_interface import LogisticianInterface

class Window(FluentWindow):
    """ Main Interface """

    def __init__(self):
        super().__init__()
        self.subInterfaces = []
        
        #self.shipmentsInterface = ShipmentsInterface("Shipments Interface", self)
        #self.historyInterface = HistoryInterface("History Interface", self)

        self.initNavigation()
        self.initWindow()

    def initNavigation(self):
        self.navigationInterface.removeWidget("logout")
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
            
    #Vendég
    def initQuest(self):
        print('init quest')
        
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
 
    #Ügyfél
    def initCustomer(self):
        print('init Customer')
        
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
        print('init courier')
        
        #Managment Interface
        managementInterface = ManagementInterface("Managment Interface", self)
        self.addSubInterface(managementInterface, QIcon(":/icons/boxes-linked.svg"), "Csomagkezelés", NavigationItemPosition.TOP)
        self.subInterfaces.append(managementInterface)
                
        #Delivery History Interface
        deliveryHistoryInterface = DeliveryHistoryInterface("Delivery History Interface", self)
        self.addSubInterface(deliveryHistoryInterface, QIcon(":/icons/rotate-ccw-clock.svg"), "Előzmények", NavigationItemPosition.TOP)
        self.subInterfaces.append(deliveryHistoryInterface)
        
    def initLogistician(self):
        #Logistician Interface
        logisticianInterface = LogisticianInterface("Logistician Interface", self)
        self.addSubInterface(logisticianInterface, QIcon(":/icons/boxes-linked.svg"), "Logisztika", NavigationItemPosition.TOP)
        self.subInterfaces.append(logisticianInterface)
        
    #Admin
    def initAdmin(self):
        print('init admin')
        
        #Users Interface
        usersInterface = UsersInterface("Admin Users", self)
        self.addSubInterface(usersInterface, FIF.PEOPLE, "Felhasználók", NavigationItemPosition.TOP)
        self.subInterfaces.append(usersInterface)
        
        #Parcels Interface
        parcelsInterface = ParcelsInterface("Admin Parcels", self)
        self.addSubInterface(parcelsInterface, FIF.DOCUMENT, "Csomagok", NavigationItemPosition.TOP)
        self.subInterfaces.append(parcelsInterface)
        
        #Statistics Interface
        statisticsInterface = StatisticsInterface("Admin Statistics", self)
        self.addSubInterface(statisticsInterface, FIF.PIE_SINGLE, "Statisztikák", NavigationItemPosition.TOP)
        self.subInterfaces.append(statisticsInterface)
        
        #Warehouse Interface
        warehouseInterface = WarehouseSettingsInterface("Admin Warehouse", self)
        self.addSubInterface(warehouseInterface, FIF.HOME, "Raktár", NavigationItemPosition.TOP)
        self.subInterfaces.append(warehouseInterface)
        
        #Trackin Interface
        trackingInterface = TrackingInterface('Tracking Interface', self)
        self.addSubInterface(trackingInterface, QIcon(":/icons/package-search.svg"), 'Nyomkövetés')
        self.subInterfaces.append(trackingInterface)
        
    def initWindow(self):
        #self.resize(900, 700)
        self.setWindowIcon(QIcon('C:/Users/User/Projekt-labor-2026-27-1/frontend/resources/truck-icon.png'))
        self.setWindowTitle('Csomagkezelő')
    
    def removeInterfaces(self):
        if self.subInterfaces:
            self.stackedWidget.currentChanged.disconnect(
                self._onCurrentInterfaceChanged
            )

        for interface in reversed(self.subInterfaces):
            self.removeInterface(interface)
            
        self.subInterfaces.clear()
        
    def logout(self):
        api.logout();
        self.initNavigation();