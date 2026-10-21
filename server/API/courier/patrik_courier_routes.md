**Courier modul – Futár műveletek (/API/courier/routes.py)**

## **Áttekintés**

A courier modul biztosítja a futárok napi feladataihoz tartozó API végpontokat, a felvételi és kézbesítési folyamatok lépéseit, valamint a teljesítmény-előzmények lekérését.

---

## **Végpontok és szolgáltatások**

### **1\. Feladatok listázása**

> * **Végpont**: GET /courier/tasks  
> * **Jogosultság**: CourierUser  
> * **Paraméterek**: CourierTaskParams (task: pickup | delivery, day: dátum)  
> * **Működés (list\_tasks)**:  
  * Lekéri a futárhoz rendelt aktív csomagfelvételi (PICKUP\_ASSIGNED, PICKED\_UP) és kézbesítési (DELIVERY\_ASSIGNED, OUT\_FOR\_DELIVERY, FAILED) feladatokat.  
  * A feladatokat a tervezett dátum és idősáv alapján időrendbe rendezi.

### **2\. Csomag felvétele**

> * **Végpont**: POST /courier/parcels/{parcel\_id}/pickup  
> * **Működés (pickup)**:  
  * Ellenőrzi, hogy a csomag a futárhoz van-e rendelve és PICKUP\_ASSIGNED állapotban van-e.  
  * A csomag státuszát PICKED\_UP állapotra frissíti és eseményt jegyez fel.

### **3\. Kézbesítés indítása**

> * **Végpont**: POST /courier/parcels/{parcel\_id}/start  
> * **Működés (start\_delivery)**:  
  * A kijelölt futár átváltja a csomag állapotát DELIVERY\_ASSIGNED állapotból OUT\_FOR\_DELIVERY állapotra.

### **4\. Csomag kézbesítése**

> * **Végpont**: POST /courier/parcels/{parcel\_id}/deliver  
> * **Működés (deliver)**:  
  * Sikeres átadás rögzítése OUT\_FOR\_DELIVERY állapotból DELIVERED állapotba.

### **5\. Sikertelen próbálkozás**

> * **Végpont**: POST /courier/parcels/{parcel\_id}/fail  
> * **Működés (fail)**:  
  * **Sikertelen felvétel**: A csomag állapota FAILED lesz, majd azonnal CANCELLED (törölt) állapotba kerül, így az ügyfél újra foglalhat.  
  * **Sikertelen kézbesítés**: A csomag állapota FAILED lesz. Ha a futár által rögzített sikertelen próbálkozások száma eléri a beállított korlátot (settings.MAX\_FAILED\_DELIVERIES), a csomag automatikusan CANCELLED állapotba vált.

### **6\. Előzmények lekérése**

> * **Végpont**: GET /courier/history  
> * **Paraméterek**: CourierHistoryParams (period: day | week | month, day: dátum)  
> * **Működés (get\_history)**:  
  * Összegzi a futár által az adott időszakban elvégzett felvételeket (PICKED\_UP), kézbesítéseket (DELIVERED) és sikertelen próbálkozásokat (FAILED).

# ---