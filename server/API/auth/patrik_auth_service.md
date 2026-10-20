# **Auth modul – Hitelesítési szolgáltatások (/API/auth/services.py)**

## **Áttekintés**

Az auth modul felelős a felhasználók regisztrációjáért, a bejelentkezési JWT tokenek generálásáért és a jelszómódosításért.

---

## **Szolgáltatások (services.py)**

### **register(db: Session, data: RegisterRequest) \-\> User**

> * **Működés**: Regisztrál egy új ügyfelet (CUSTOMER szerepkörrel).  
> * **Ellenőrzések**:  
  * Vizsgálja, hogy az megadott email cím szerepel-e már aktív felhasználónál.  
  * Ha létezik aktív fiók az adott email címmel, 409 CONFLICT hibát dob ("Email cím már foglalt egy aktív felhasználónál\!").  
> * **Adatkezelés**: A jelszót hash\_pass segítségével hash-eli, a fiókot is\_active=True státusszal menti az adatbázisba.

### **login(db: Session, email: str, password: str) \-\> TokenResponse**

> * **Működés**: Hitelesíti a felhasználót email és jelszó alapján, majd kiállítja a JWT hozzáférési tokent.  
> * **Ellenőrzések**:  
  * Keresi az aktív felhasználót az email cím alapján.  
  * Ellenőrzi a jelszó helyességét a verify\_pass függvénnyel.  
  * Érvénytelen email vagy jelszó esetén 401 UNAUTHORIZED hibát ad vissza ("Hibás email vagy jelszó").  
> * **Kimenet**: Visszaadja a TokenResponse objektumot (access\_token, expires\_in másodpercben, role, user\_id).

### **change\_password(db: Session, user: User, data: PasswordChangeRequest) \-\> None**

> * **Működés**: A bejelentkezett felhasználó jelszavának frissítése.  
> * **Ellenőrzések**:  
  * Ellenőrzi a jelenlegi jelszót (current\_password). Helytelen jelszó esetén 400 BAD\_REQUEST hibát dob.  
  * A lehetséges séma ellenőrzés biztosítja, hogy az új jelszó eltérjen a régitől.  
> * **Adatkezelés**: Hash-eli az új jelszót és elmenti a password\_hash mezőbe.

## ---

**Kapcsolódó sémák (schemas.py)**

> * RegisterRequest: UserCreateBase alapján tartalmazza a regisztrációhoz szükséges személyes és lakcím adatokat.  
> * TokenResponse: access\_token, token\_type ("bearer"), expires\_in, role, user\_id.  
> * PasswordChangeRequest: current\_password, new\_password (min. 8 karakter).

## ---

**Végpontok (routes.py)**

> * POST /auth/register (Siker esetén: 201 CREATED)  
> * POST /auth/login (OAuth2 form-data: username \= email, password)  
> * POST /auth/change-password (Hitelesített, siker esetén: 204 NO CONTENT)

# ---