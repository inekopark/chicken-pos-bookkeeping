"""Transactional core for the chicken shop's first operational release."""
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path


def money(value):
    d = Decimal(str(value))
    if not d.is_finite() or d < 0:
        raise ValueError('Amount must be a nonnegative number')
    return int((d * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def qty(value):
    d = Decimal(str(value))
    if not d.is_finite() or d <= 0:
        raise ValueError('Quantity must be positive')
    return int((d * 1000).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY, sku TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
          unit TEXT NOT NULL, retail_cents INTEGER NOT NULL, wholesale_cents INTEGER NOT NULL, active INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS suppliers(id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);
        CREATE TABLE IF NOT EXISTS customers(id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);
        CREATE TABLE IF NOT EXISTS shifts(id INTEGER PRIMARY KEY, cashier TEXT NOT NULL, opened_at TEXT NOT NULL,
          opening_cents INTEGER NOT NULL, closed_at TEXT, counted_cents INTEGER, expected_cents INTEGER,
          variance_cents INTEGER, remitted_cents INTEGER, retained_cents INTEGER, receiver TEXT);
        CREATE TABLE IF NOT EXISTS purchases(id INTEGER PRIMARY KEY, supplier_id INTEGER NOT NULL REFERENCES suppliers(id),
          at TEXT NOT NULL, total_cents INTEGER NOT NULL, paid_cents INTEGER NOT NULL, ref TEXT UNIQUE);
        CREATE TABLE IF NOT EXISTS purchase_items(id INTEGER PRIMARY KEY, purchase_id INTEGER NOT NULL REFERENCES purchases(id),
          product_id INTEGER NOT NULL REFERENCES products(id), qty_milli INTEGER NOT NULL, unit_cost_cents INTEGER NOT NULL,
          total_cents INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS supplier_payments(id INTEGER PRIMARY KEY, supplier_id INTEGER NOT NULL REFERENCES suppliers(id),
          purchase_id INTEGER NOT NULL REFERENCES purchases(id), at TEXT NOT NULL, amount_cents INTEGER NOT NULL,
          method TEXT NOT NULL, shift_id INTEGER REFERENCES shifts(id));
        CREATE TABLE IF NOT EXISTS sales(id INTEGER PRIMARY KEY, at TEXT NOT NULL, shift_id INTEGER NOT NULL REFERENCES shifts(id),
          kind TEXT NOT NULL, method TEXT NOT NULL, customer_id INTEGER REFERENCES customers(id),
          total_cents INTEGER NOT NULL, cost_cents INTEGER NOT NULL, ref TEXT UNIQUE);
        CREATE TABLE IF NOT EXISTS sale_items(id INTEGER PRIMARY KEY, sale_id INTEGER NOT NULL REFERENCES sales(id),
          product_id INTEGER NOT NULL REFERENCES products(id), qty_milli INTEGER NOT NULL,
          unit_price_cents INTEGER NOT NULL, total_cents INTEGER NOT NULL, cost_cents INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS customer_payments(id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL REFERENCES customers(id),
          sale_id INTEGER NOT NULL REFERENCES sales(id), at TEXT NOT NULL, amount_cents INTEGER NOT NULL,
          method TEXT NOT NULL, shift_id INTEGER REFERENCES shifts(id));
        CREATE TABLE IF NOT EXISTS expenses(id INTEGER PRIMARY KEY, at TEXT NOT NULL, category TEXT NOT NULL,
          payee TEXT, amount_cents INTEGER NOT NULL, method TEXT NOT NULL, shift_id INTEGER REFERENCES shifts(id), note TEXT);
        CREATE TABLE IF NOT EXISTS movements(id INTEGER PRIMARY KEY, at TEXT NOT NULL, product_id INTEGER NOT NULL REFERENCES products(id),
          delta_milli INTEGER NOT NULL, value_cents INTEGER NOT NULL, kind TEXT NOT NULL, source_id INTEGER NOT NULL,
          actor TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS cash_events(id INTEGER PRIMARY KEY, shift_id INTEGER NOT NULL REFERENCES shifts(id),
          at TEXT NOT NULL, kind TEXT NOT NULL, delta_cents INTEGER NOT NULL, source_id INTEGER NOT NULL);
        CREATE INDEX IF NOT EXISTS movements_product ON movements(product_id,id);
        CREATE INDEX IF NOT EXISTS cash_shift ON cash_events(shift_id);
        ''')
        self.db.commit()

    @contextmanager
    def transaction(self):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            yield self.db
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def product(self, sku, name, unit, retail, wholesale):
        with self.transaction() as db:
            return db.execute('INSERT INTO products(sku,name,unit,retail_cents,wholesale_cents) VALUES(?,?,?,?,?)',
                              (sku.strip(),name.strip(),unit.strip(),money(retail),money(wholesale))).lastrowid

    def party(self, table, name):
        if table not in ('suppliers','customers'):
            raise ValueError('Invalid party')
        with self.transaction() as db:
            return db.execute(f'INSERT INTO {table}(name) VALUES(?)',(name.strip(),)).lastrowid

    def stock(self, product_id):
        r=self.db.execute('SELECT COALESCE(SUM(delta_milli),0) q,COALESCE(SUM(value_cents),0) v FROM movements WHERE product_id=?',(product_id,)).fetchone()
        return r['q'],r['v']

    def open_shift(self, cashier, opening):
        with self.transaction() as db:
            if db.execute('SELECT 1 FROM shifts WHERE cashier=? AND closed_at IS NULL',(cashier,)).fetchone():
                raise ValueError('Cashier already has an open shift')
            return db.execute('INSERT INTO shifts(cashier,opened_at,opening_cents) VALUES(?,?,?)',
                              (cashier.strip(),now(),money(opening))).lastrowid

    def _open(self, shift_id):
        r=self.db.execute('SELECT * FROM shifts WHERE id=? AND closed_at IS NULL',(shift_id,)).fetchone()
        if not r: raise ValueError('Open shift required')
        return r

    def _cash(self, db, shift, kind, cents, source):
        db.execute('INSERT INTO cash_events(shift_id,at,kind,delta_cents,source_id) VALUES(?,?,?,?,?)',
                   (shift,now(),kind,cents,source))

    def purchase(self, supplier, lines, paid=0, method='BANK', shift=None, ref=None):
        if not lines: raise ValueError('Purchase needs items')
        if method not in ('CASH','BANK','GCASH'): raise ValueError('Invalid method')
        with self.transaction() as db:
            if shift is not None: self._open(shift)
            prepared=[]
            for product, quantity, unit_cost in lines:
                q=qty(quantity); c=money(unit_cost)
                if not db.execute('SELECT 1 FROM products WHERE id=? AND active=1',(product,)).fetchone(): raise ValueError('Unknown product')
                prepared.append((product,q,c,(q*c+500)//1000))
            total=sum(x[3] for x in prepared); paid_c=money(paid)
            if paid_c>total: raise ValueError('Payment exceeds purchase')
            pid=db.execute('INSERT INTO purchases(supplier_id,at,total_cents,paid_cents,ref) VALUES(?,?,?,?,?)',
                           (supplier,now(),total,paid_c,ref or uuid.uuid4().hex)).lastrowid
            for product,q,c,value in prepared:
                db.execute('INSERT INTO purchase_items(purchase_id,product_id,qty_milli,unit_cost_cents,total_cents) VALUES(?,?,?,?,?)',(pid,product,q,c,value))
                db.execute('INSERT INTO movements(at,product_id,delta_milli,value_cents,kind,source_id,actor) VALUES(?,?,?,?,?,?,?)',(now(),product,q,value,'PURCHASE',pid,'supervisor'))
            if paid_c:
                db.execute('INSERT INTO supplier_payments(supplier_id,purchase_id,at,amount_cents,method,shift_id) VALUES(?,?,?,?,?,?)',(supplier,pid,now(),paid_c,method,shift))
                if method=='CASH' and shift: self._cash(db,shift,'SUPPLIER_PAYMENT',-paid_c,pid)
            return pid

    def pay_supplier(self, purchase_id, amount, method='BANK', shift=None):
        if method not in ('CASH','BANK','GCASH'): raise ValueError('Invalid method')
        with self.transaction() as db:
            if shift is not None: self._open(shift)
            p=db.execute('SELECT * FROM purchases WHERE id=?',(purchase_id,)).fetchone()
            if not p: raise ValueError('Unknown purchase')
            paid=db.execute('SELECT COALESCE(SUM(amount_cents),0) v FROM supplier_payments WHERE purchase_id=?',(purchase_id,)).fetchone()['v']
            a=money(amount)
            if a<=0 or a>p['total_cents']-paid: raise ValueError('Payment exceeds balance')
            id=db.execute('INSERT INTO supplier_payments(supplier_id,purchase_id,at,amount_cents,method,shift_id) VALUES(?,?,?,?,?,?)',(p['supplier_id'],purchase_id,now(),a,method,shift)).lastrowid
            if method=='CASH' and shift: self._cash(db,shift,'SUPPLIER_PAYMENT',-a,id)
            return id

    def sale(self, shift, lines, kind='RETAIL', method='CASH', customer=None, ref=None):
        if kind not in ('RETAIL','WHOLESALE') or method not in ('CASH','BANK','GCASH','CREDIT'): raise ValueError('Invalid sale')
        if method=='CREDIT' and not customer: raise ValueError('Credit needs customer')
        if not lines: raise ValueError('Sale needs items')
        with self.transaction() as db:
            user=self._open(shift)['cashier']; prepared=[]
            for product, quantity in lines:
                q=qty(quantity)
                p=db.execute('SELECT * FROM products WHERE id=? AND active=1',(product,)).fetchone()
                if not p: raise ValueError('Unknown product')
                available,value=self.stock(product)
                reserved=sum(x[1] for x in prepared if x[0]==product)
                if q+reserved>available: raise ValueError(f'Insufficient stock: {p["name"]}')
                cost=(value*q+available//2)//available if available else 0
                price=p['retail_cents'] if kind=='RETAIL' else p['wholesale_cents']
                prepared.append((product,q,price,(q*price+500)//1000,cost))
            total=sum(x[3] for x in prepared); cost=sum(x[4] for x in prepared)
            sid=db.execute('INSERT INTO sales(at,shift_id,kind,method,customer_id,total_cents,cost_cents,ref) VALUES(?,?,?,?,?,?,?,?)',
                           (now(),shift,kind,method,customer,total,cost,ref or uuid.uuid4().hex)).lastrowid
            for product,q,price,line,c in prepared:
                db.execute('INSERT INTO sale_items(sale_id,product_id,qty_milli,unit_price_cents,total_cents,cost_cents) VALUES(?,?,?,?,?,?)',(sid,product,q,price,line,c))
                db.execute('INSERT INTO movements(at,product_id,delta_milli,value_cents,kind,source_id,actor) VALUES(?,?,?,?,?,?,?)',(now(),product,-q,-c,'SALE',sid,user))
            if method=='CASH': self._cash(db,shift,'SALE',total,sid)
            return sid

    def collect(self, sale_id, amount, method='CASH', shift=None):
        if method not in ('CASH','BANK','GCASH'): raise ValueError('Invalid method')
        with self.transaction() as db:
            if shift is not None: self._open(shift)
            sale=db.execute('SELECT * FROM sales WHERE id=? AND method="CREDIT"',(sale_id,)).fetchone()
            if not sale: raise ValueError('Unknown credit sale')
            paid=db.execute('SELECT COALESCE(SUM(amount_cents),0) v FROM customer_payments WHERE sale_id=?',(sale_id,)).fetchone()['v']
            a=money(amount)
            if a<=0 or a>sale['total_cents']-paid: raise ValueError('Payment exceeds balance')
            id=db.execute('INSERT INTO customer_payments(customer_id,sale_id,at,amount_cents,method,shift_id) VALUES(?,?,?,?,?,?)',(sale['customer_id'],sale_id,now(),a,method,shift)).lastrowid
            if method=='CASH' and shift: self._cash(db,shift,'CUSTOMER_COLLECTION',a,id)
            return id

    def expense(self, category, amount, method='CASH', shift=None, payee='', note=''):
        if method not in ('CASH','BANK','GCASH'): raise ValueError('Invalid method')
        with self.transaction() as db:
            if shift is not None: self._open(shift)
            a=money(amount)
            if a<=0: raise ValueError('Amount must be positive')
            id=db.execute('INSERT INTO expenses(at,category,payee,amount_cents,method,shift_id,note) VALUES(?,?,?,?,?,?,?)',(now(),category, payee,a,method,shift,note)).lastrowid
            if method=='CASH' and shift: self._cash(db,shift,'EXPENSE',-a,id)
            return id

    def expected(self, shift):
        r=self._open(shift)
        return r['opening_cents']+self.db.execute('SELECT COALESCE(SUM(delta_cents),0) v FROM cash_events WHERE shift_id=?',(shift,)).fetchone()['v']

    def close_shift(self, shift, counted, remitted, receiver):
        with self.transaction() as db:
            expected=self.expected(shift); actual=money(counted); rem=money(remitted)
            if rem>actual: raise ValueError('Remittance exceeds cash counted')
            db.execute('UPDATE shifts SET closed_at=?,counted_cents=?,expected_cents=?,variance_cents=?,remitted_cents=?,retained_cents=?,receiver=? WHERE id=?',
                       (now(),actual,expected,actual-expected,rem,actual-rem,receiver,shift))
            return {'expected':expected,'counted':actual,'variance':actual-expected,'remitted':rem,'retained':actual-rem}

    def backup(self, destination):
        Path(destination).parent.mkdir(parents=True,exist_ok=True)
        with sqlite3.connect(str(destination)) as target: self.db.backup(target)
        return str(destination)
