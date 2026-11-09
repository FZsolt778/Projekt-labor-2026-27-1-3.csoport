from PySide6.QtGui import QIcon
from qfluentwidgets import NavigationItemPosition, FluentWindow
from .auth.auth_interface import AuthInterface
from .customer.booking_interface import BookingInterface
from .customer.history_interface import HistoryInterface
from .customer.shipments_interface import ShipmentsInterface
from .customer.tracking_interface import TrackingInterface


class Window(FluentWindow):
    """ Main Interface """

    def __init__(self):
        super().__init__()

        # Create sub-interfaces, when actually using, replace Widget with your own sub-interface
        # self.homeInterface = Widget('Főoldal', self)
        self.trackInterface = TrackingInterface('Tracking Interface', self)
        # self.packageInterface = Widget('Csomagfeladás', self)
        # self.settingInterface = Widget('Beállítások', self)
        self.bookingInterface = BookingInterface("Booking Interface",self)
        self.shipmentsInterface = ShipmentsInterface("Shipments Interface", self)
        self.historyInterface = HistoryInterface("History Interface", self)
        self.authInterface = AuthInterface()

        self.initNavigation()
        self.initWindow()

    def initNavigation(self):
        # self.addSubInterface(self.homeInterface, FIF.HOME, 'Főoldal')
        self.addSubInterface(self.trackInterface, QIcon(":/icons/package-search.svg"), 'Nyomkövetés')
        # self.addSubInterface(self.packageInterface, FIF.APPLICATION, 'Csomagfeladás')
        self.addSubInterface(self.bookingInterface,  QIcon(":/icons/package.svg"), "Csomagfeladás", NavigationItemPosition.TOP)
        self.addSubInterface(self.shipmentsInterface, QIcon(":/icons/package-open.svg"), "Aktuális csomagok", NavigationItemPosition.TOP)
        self.addSubInterface(self.historyInterface, QIcon(":/icons/rotate-ccw-clock.svg"), "Előzmények", NavigationItemPosition.TOP)
        self.navigationInterface.addSeparator()
        self.addSubInterface(self.authInterface,  QIcon(":/icons/auth.svg"), 'Bejelentkezés', NavigationItemPosition.BOTTOM)
        # self.addSubInterface(self.testInterface1, FIF.ALBUM, 'Test 1', parent=self.loginInterface)

    def initWindow(self):
        #self.resize(900, 700)
        self.setWindowIcon(QIcon('C:/Users/User/Projekt-labor-2026-27-1/frontend/resources/truck-icon.png'))
        self.setWindowTitle('Csomagkezelő')